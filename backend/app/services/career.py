"""A bounded graph with no tool permissions or application-approval capability."""

from contextlib import contextmanager
from typing import TypedDict
from sqlalchemy import select, text
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.postgres import PostgresSaver
from app.config import settings
from app.config.database import Session
from app.models.runtime import CareerGoal
from app.models.runtime import CareerMilestone
from app.models.profile import Profile
from app.services.matching import match
from app.services.trust_checker import analyze
from app.repositories import documents


class State(TypedDict, total=False):
    owner: str
    goal_id: str
    goal: str
    profile: dict
    candidates: list
    suggestions: list
    token_usage: dict
    monetary_cost: float | None
    stopped: bool
    draft_preparation: list
    monitoring: dict
    messages: list


def stopped(state):
    with Session() as db:
        row = db.scalar(
            select(CareerGoal).where(
                CareerGoal.id == state["goal_id"], CareerGoal.owner_id == state["owner"]
            )
        )
        return not row or row.payload.get("status") in {"PAUSED", "CANCELLED"}


def profile_node(state):
    if stopped(state):
        return {"stopped": True}
    with Session() as db:
        row = db.scalar(select(Profile).where(Profile.owner_id == state["owner"]))
        return {"profile": row.payload if row else {}, "stopped": False}


def catalog_node(state):
    if stopped(state):
        return {"stopped": True}
    candidates = []
    for item in documents.scan("opportunities", limit=50):
        candidates.append(
            dict(id=item["id"], matching=match(state["profile"], item), risk=analyze(item))
        )
    candidates.sort(key=lambda c: -c["matching"]["score"])
    return {"candidates": candidates[:10]}


def plan_node(state):
    if stopped(state):
        return {"stopped": True}
    missing = sorted(
        {
            s
            for c in state.get("candidates", [])
            for s in c["matching"]["skill_analysis"]["missing_required"]
        }
    )
    suggestions = [
        {
            "title": f"Practice {s}",
            "description": f"Create a small project using {s}; confirm skills explicitly when ready.",
        }
        for s in missing[:10]
    ]
    if not suggestions:
        suggestions = [
            {
                "title": "Review target requirements",
                "description": "Confirm academic facts and select opportunities before preparing application drafts.",
            }
        ]
    if settings.ai_provider != "deterministic":
        from app.services.suggestions import suggest

        return suggest(state["goal"], missing)
    return {
        "suggestions": suggestions,
        "token_usage": {"input": 0, "output": 0},
        "monetary_cost": None,
    }


def route_plan(state):
    return END if state.get("stopped") else "plan"


def draft_node(state):
    if stopped(state):
        return {"stopped": True}
    drafts = []
    for candidate in state.get("candidates", []):
        if candidate["matching"]["recommendable"]:
            drafts.append(
                dict(
                    opportunity_id=candidate["id"],
                    status="SUGGESTED_DRAFT",
                    material={
                        "student_name": state.get("profile", {}).get("name"),
                        "profile_skill_claims": state.get("profile", {}).get("skills"),
                    },
                    requires_human_review=True,
                )
            )
    return {"draft_preparation": drafts[:3]}


def monitor_node(state):
    return {"monitoring": {"mode": "SNAPSHOT", "cooperative_stop_requested": stopped(state)}}


def graph(saver):
    builder = StateGraph(State)
    builder.add_node("profile", profile_node)
    builder.add_node("catalog_eligibility_risk_skills", catalog_node)
    builder.add_node("plan", plan_node)
    builder.add_node("draft_preparation", draft_node)
    builder.add_node("monitor", monitor_node)
    builder.add_edge(START, "profile")
    builder.add_conditional_edges(
        "profile", lambda state: END if state.get("stopped") else "catalog_eligibility_risk_skills"
    )
    builder.add_conditional_edges("catalog_eligibility_risk_skills", route_plan)
    builder.add_conditional_edges(
        "plan", lambda state: END if state.get("stopped") else "draft_preparation"
    )
    builder.add_edge("draft_preparation", "monitor")
    builder.add_edge("monitor", END)
    return builder.compile(checkpointer=saver)


@contextmanager
def saver():
    if settings.hosted:
        with PostgresSaver.from_conn_string(
            settings.database_url.replace("postgresql+psycopg://", "postgresql://")
        ) as checkpoint:
            yield checkpoint
    else:
        with SqliteSaver.from_conn_string(settings.career_checkpoint_db) as checkpoint:
            yield checkpoint


def setup_checkpoints():
    with saver() as checkpoint:
        checkpoint.setup()


def run(goal_id, owner):
    with Session() as lock_db:
        if settings.hosted:
            lock_db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": owner + ":" + goal_id},
            )
        row = lock_db.scalar(
            select(CareerGoal).where(CareerGoal.id == goal_id, CareerGoal.owner_id == owner)
        )
        if not row or row.payload.get("status") in {"CANCELLED", "PAUSED"}:
            return {"status": "STOPPED"}
        revision = row.revision
        config = {"configurable": {"thread_id": owner + ":" + goal_id + ":" + str(revision)}}
        with saver() as checkpoint:
            workflow = graph(checkpoint)
            previous = workflow.get_state(config)
            if previous.values and not previous.next:
                result = previous.values
            else:
                result = workflow.invoke(
                    None
                    if previous.values
                    else dict(
                        owner=owner,
                        goal_id=goal_id,
                        goal=row.payload["goal"],
                        messages=row.payload.get("messages", []),
                    ),
                    config,
                )
        lock_db.expire_all()
        row = lock_db.scalar(
            select(CareerGoal)
            .where(CareerGoal.id == goal_id, CareerGoal.owner_id == owner)
            .with_for_update()
        )
        if row.revision != revision:
            return {"status": "SUPERSEDED"}
        if row.payload["status"] in {"PAUSED", "CANCELLED"}:
            return {"status": row.payload["status"]}
        row.payload = dict(
            row.payload,
            status="ACTIVE",
            plan=result.get("suggestions", []),
            candidates=result.get("candidates", []),
            token_usage=result.get("token_usage"),
            monetary_cost=None,
            draft_preparation=result.get("draft_preparation", []),
            monitoring=result.get("monitoring", {}),
        )
        existing = list(
            lock_db.scalars(
                select(CareerMilestone).where(
                    CareerMilestone.goal_id == goal_id, CareerMilestone.owner_id == owner
                )
            )
        )
        if not existing:
            for suggestion in result.get("suggestions", []):
                lock_db.add(
                    CareerMilestone(
                        owner_id=owner, goal_id=goal_id, payload=dict(suggestion, completed=False)
                    )
                )
        lock_db.commit()
        documents.put(
            "agent_runs",
            goal_id,
            dict(
                owner_id=owner,
                execution_revision=revision,
                status="ACTIVE",
                token_usage=result.get("token_usage"),
                monetary_cost=None,
            ),
        )
        return {"goal_id": goal_id, "status": "ACTIVE"}

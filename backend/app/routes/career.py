from fastapi import APIRouter, HTTPException
from sqlalchemy import select, update
from app.routes.common import DB, Owner, ok
from app.models.runtime import CareerGoal
from app.models.runtime import CareerMilestone
from app.repositories.relational import owned, serialize
from app.schemas.runtime import GoalInput
from app.schemas.runtime import Message
from app.schemas.runtime import MilestonePatch
from app.services.jobs import enqueue

router = APIRouter()


@router.post("/career-agent/start", status_code=202)
def start(body: GoalInput, owner: Owner, db: DB):
    row = CareerGoal(
        owner_id=owner, payload=dict(goal=body.goal, status="PROCESSING", messages=[], plan=[])
    )
    db.add(row)
    db.flush()
    job = enqueue(db, owner, "career", {"goal_id": row.id}, dedupe="career:" + row.id + ":1")
    return ok(dict(id=row.id, job_id=job.id, status="PROCESSING"))


@router.get("/career-agent/{record_id}")
def get_goal(record_id: str, owner: Owner, db: DB):
    row = owned(db, CareerGoal, owner, record_id)
    milestones = list(
        db.scalars(
            select(CareerMilestone).where(
                CareerMilestone.goal_id == record_id, CareerMilestone.owner_id == owner
            )
        )
    )
    return ok(
        dict(
            serialize(row),
            milestones=[serialize(m) for m in milestones],
            progress=sum(bool(m.payload.get("completed")) for m in milestones) / len(milestones)
            if milestones
            else 0,
        )
    )


@router.get("/career-agent/{record_id}/plan")
def plan(record_id: str, owner: Owner, db: DB):
    return ok(owned(db, CareerGoal, owner, record_id).payload.get("plan", []))


@router.post("/career-agent/{record_id}/message")
def message(record_id: str, body: Message, owner: Owner, db: DB):
    row = owned(db, CareerGoal, owner, record_id, lock=True)
    if row.payload["status"] == "CANCELLED":
        raise HTTPException(409, "Session cancelled")
    messages = row.payload.get("messages", [])
    if len(messages) >= 100:
        raise HTTPException(409, "Session message limit reached")
    row.payload = dict(
        row.payload,
        messages=messages + [dict(role="user", text=body.text)],
        permission_notice="Messages cannot approve applications or grant permissions",
    )
    db.commit()
    return ok(serialize(row))


def control(record_id, action, owner, db):
    row = owned(db, CareerGoal, owner, record_id, lock=True)
    if row.payload["status"] == "CANCELLED":
        if action == "CANCELLED":
            return ok(serialize(row))
        raise HTTPException(409, "Cancelled sessions cannot resume")
    if action == "ACTIVE" and row.payload["status"] != "PAUSED":
        raise HTTPException(409, "Only paused sessions can resume")
    revision = row.revision
    result = db.execute(
        update(CareerGoal)
        .where(
            CareerGoal.id == record_id,
            CareerGoal.owner_id == owner,
            CareerGoal.revision == revision,
        )
        .values(revision=revision + 1, payload=dict(row.payload, status=action)),
        execution_options={"synchronize_session": False},
    )
    if result.rowcount != 1:
        raise HTTPException(409, "Concurrent session update")
    db.commit()
    db.refresh(row)
    if action == "ACTIVE":
        job = enqueue(
            db, owner, "career", {"goal_id": row.id}, dedupe=f"career:{row.id}:{row.revision}"
        )
        return ok(dict(id=row.id, job_id=job.id, status=action))
    return ok(serialize(row))


@router.post("/career-agent/{record_id}/pause")
def pause(record_id: str, owner: Owner, db: DB):
    return control(record_id, "PAUSED", owner, db)


@router.post("/career-agent/{record_id}/resume", status_code=202)
def resume(record_id: str, owner: Owner, db: DB):
    return control(record_id, "ACTIVE", owner, db)


@router.post("/career-agent/{record_id}/cancel")
def cancel(record_id: str, owner: Owner, db: DB):
    return control(record_id, "CANCELLED", owner, db)


@router.patch("/career-agent/{record_id}/milestones/{milestone_id}")
def milestone(record_id: str, milestone_id: str, body: MilestonePatch, owner: Owner, db: DB):
    owned(db, CareerGoal, owner, record_id)
    row = owned(db, CareerMilestone, owner, milestone_id)
    if row.goal_id != record_id:
        raise HTTPException(404, "Milestone not found")
    row.payload = dict(row.payload, completed=body.completed)
    db.commit()
    return ok(serialize(row))

"""Only a separately operated, isolated Judge0 service may execute submitted code."""

import time
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.config.database import Session
from app.models.runtime import Assessment
from app.models.runtime import Attempt
from app.services.readiness import QUESTIONS


def execute(arguments, owner):
    if not settings.judge0_isolation_confirmed or not settings.judge0_url:
        raise RuntimeError("Judge0 isolation unconfirmed")
    language = settings.judge0_language_ids.get(arguments["language"])
    if not language or arguments["language"] not in {"python", "javascript"}:
        raise ValueError("Language disabled")
    with Session() as db:
        assessment = db.scalar(
            select(Assessment).where(
                Assessment.id == arguments["assessment_id"], Assessment.owner_id == owner
            )
        )
        if not assessment or arguments["question_id"] not in assessment.payload["question_ids"]:
            raise HTTPException(404, "Assessment not found")
        old = db.scalar(
            select(Attempt).where(
                Attempt.assessment_id == assessment.id,
                Attempt.owner_id == owner,
                Attempt.question_id == arguments["question_id"],
            )
        )
        if old:
            return {"attempt_id": old.id, "correctness": old.payload.get("correctness")}
    question = QUESTIONS[arguments["question_id"]]
    if question["kind"] != "coding":
        raise ValueError("Not a coding question")
    headers = {"X-Auth-Token": settings.judge0_api_key} if settings.judge0_api_key else {}
    outcomes = []
    # The operator-controlled service address is trusted infrastructure, never a user URL.
    with httpx.Client(
        base_url=settings.judge0_url.rstrip("/"),
        headers=headers,
        timeout=5,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        for test in question["tests"]:
            response = client.post(
                "/submissions",
                params={"base64_encoded": "false", "wait": "false"},
                json=dict(
                    source_code=arguments["code"],
                    language_id=language,
                    stdin=test["stdin"],
                    expected_output=test["expected_output"],
                    cpu_time_limit=2,
                    wall_time_limit=4,
                    memory_limit=65536,
                    enable_network=False,
                ),
            )
            response.raise_for_status()
            token = response.json()["token"]
            if (
                not isinstance(token, str)
                or not token.replace("-", "").isalnum()
                or len(token) > 100
            ):
                raise ValueError("Invalid execution token")
            completed = False
            for _ in range(10):
                response = client.get(
                    "/submissions/" + token, params={"fields": "status", "base64_encoded": "false"}
                )
                response.raise_for_status()
                status = response.json()["status"]["id"]
                if status not in {1, 2}:
                    outcomes.append(status == 3)
                    completed = True
                    break
                time.sleep(0.2)
            if not completed:
                raise RuntimeError("Judge0 polling bound exceeded")
    with Session() as db:
        attempt = Attempt(
            owner_id=owner,
            assessment_id=arguments["assessment_id"],
            question_id=arguments["question_id"],
            payload=dict(
                correctness=all(outcomes),
                review_status="ISOLATED_JUDGE0",
                passed_count=sum(outcomes),
                test_count=len(outcomes),
            ),
        )
        db.add(attempt)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            attempt = db.scalar(
                select(Attempt).where(
                    Attempt.assessment_id == arguments["assessment_id"],
                    Attempt.owner_id == owner,
                    Attempt.question_id == arguments["question_id"],
                )
            )
        return dict(attempt_id=attempt.id, correctness=attempt.payload["correctness"])

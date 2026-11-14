from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app.routes.common import DB, Owner, ok
from app.config import settings
from app.models.runtime import Assessment
from app.models.runtime import Attempt
from app.models.profile import Profile
from app.repositories.relational import owned, serialize
from app.schemas.runtime import AssessmentInput
from app.schemas.runtime import Answer
from app.schemas.runtime import Code
from app.services.readiness import QUESTIONS
from app.services.jobs import enqueue

router = APIRouter()


@router.post("/readiness/assessment", status_code=201)
def create(body: AssessmentInput, owner: Owner, db: DB):
    questions = [key for key, value in QUESTIONS.items() if value["kind"] == body.kind]
    row = Assessment(owner_id=owner, payload=dict(kind=body.kind, question_ids=questions))
    db.add(row)
    db.commit()
    return ok(serialize(row))


@router.get("/readiness/questions")
def questions(assessment_id: str, owner: Owner, db: DB):
    row = owned(db, Assessment, owner, assessment_id)
    return ok(
        [
            dict(id=key, prompt=QUESTIONS[key]["prompt"], kind=QUESTIONS[key]["kind"])
            for key in row.payload["question_ids"]
        ]
    )


@router.post("/readiness/submit-answer")
def answer(body: Answer, owner: Owner, db: DB):
    row = owned(db, Assessment, owner, body.assessment_id)
    if body.question_id not in row.payload["question_ids"]:
        raise HTTPException(404, "Question not in assessment")
    old = db.scalar(
        select(Attempt).where(
            Attempt.owner_id == owner,
            Attempt.assessment_id == row.id,
            Attempt.question_id == body.question_id,
        )
    )
    if old:
        return ok(serialize(old))
    question = QUESTIONS[body.question_id]
    if question["kind"] == "coding":
        raise HTTPException(422, "Use isolated code execution for this question")
    result = dict(
        answer=body.answer,
        correctness=body.answer.strip().casefold() == question["accepted"]
        if question["kind"] == "aptitude"
        else None,
        review_status="DETERMINISTIC"
        if question["kind"] == "aptitude"
        else "HUMAN_REVIEW_REQUIRED",
        rubric=question.get("rubric"),
    )
    attempt = Attempt(
        owner_id=owner, assessment_id=row.id, question_id=body.question_id, payload=result
    )
    db.add(attempt)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        attempt = db.scalar(
            select(Attempt).where(
                Attempt.owner_id == owner,
                Attempt.assessment_id == row.id,
                Attempt.question_id == body.question_id,
            )
        )
    return ok(serialize(attempt))


@router.post("/readiness/execute-code", status_code=202)
def execute(body: Code, owner: Owner, db: DB):
    if (
        not settings.judge0_isolation_confirmed
        or not settings.judge0_url
        or body.language not in settings.judge0_language_ids
    ):
        raise HTTPException(
            503, "Independent Judge0 isolation and language allowlist must be configured"
        )
    assessment = owned(db, Assessment, owner, body.assessment_id)
    if (
        body.question_id not in assessment.payload["question_ids"]
        or QUESTIONS.get(body.question_id, {}).get("kind") != "coding"
    ):
        raise HTTPException(404, "Coding question not found")
    from app.models.persistent import Job
    from app.services.catalog import digest

    # Serialize quota decisions for a hosted owner and reuse an existing request before checking quota.
    owned(db, Profile, owner, owner, lock=True)
    prior = db.scalar(
        select(Job).where(
            Job.owner_id == owner, Job.dedupe_key == digest(["judge0", body.model_dump()])
        )
    )
    if prior:
        return ok(dict(job_id=prior.id, status=prior.status))
    count = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.owner_id == owner, Job.payload["kind"].as_string() == "judge0")
    )
    if count >= 5:
        raise HTTPException(429, "Code execution quota reached")
    job = enqueue(db, owner, "judge0", body.model_dump())
    return ok(dict(job_id=job.id, status=job.status))


@router.get("/readiness/results/{record_id}")
def results(record_id: str, owner: Owner, db: DB):
    owned(db, Assessment, owner, record_id)
    attempts = list(
        db.scalars(
            select(Attempt).where(Attempt.owner_id == owner, Attempt.assessment_id == record_id)
        )
    )
    return ok([serialize(a) for a in attempts])


@router.get("/readiness/progress")
def progress(owner: Owner, db: DB):
    rows = list(db.scalars(select(Attempt).where(Attempt.owner_id == owner).limit(100)))
    return ok(
        dict(attempted=len(rows), correct=sum(r.payload.get("correctness") is True for r in rows))
    )

"""SQL job state/outbox, leased execution, bounded retries and stale recovery."""

from datetime import timedelta
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from app.config import settings
from app.config.database import Session
from app.models.runtime import Job
from app.models.runtime import Outbox
from app.models.base import now
from app.models.base import uid
from app.services.catalog import digest


def enqueue(db, owner, kind, arguments, dedupe=None):
    key = dedupe or digest([kind, arguments])
    old = db.scalar(select(Job).where(Job.owner_id == owner, Job.dedupe_key == key))
    if old:
        return old
    row = Job(
        id=uid(), owner_id=owner, dedupe_key=key, payload=dict(kind=kind, arguments=arguments)
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
            db.add(Outbox(owner_id=owner, event_key="job:" + row.id, payload={"job_id": row.id}))
            db.flush()
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.scalar(select(Job).where(Job.owner_id == owner, Job.dedupe_key == key))
    return row


def dispatch():
    from app.worker import execute_job

    with Session() as db:
        # Dispatch may happen more than once. execute() claims by atomic status/lease predicate.
        events = list(db.scalars(select(Outbox).where(Outbox.status == "PENDING").limit(100)))
        for event in events:
            if settings.jobs_eager:
                execute(event.payload["job_id"])
            else:
                execute_job.delay(event.payload["job_id"])
            event.status = "SENT"
            db.commit()


def execute(job_id):
    with Session() as db:
        claim = db.execute(
            update(Job)
            .where(Job.id == job_id, Job.status.in_(["QUEUED", "RETRY"]), Job.attempts < 3)
            .values(
                status="RUNNING",
                attempts=Job.attempts + 1,
                lease_until=now() + timedelta(minutes=10),
            )
        )
        db.commit()
        if claim.rowcount != 1:
            return
        row = db.get(Job, job_id)
        attempt = row.attempts
        kind, args, owner = row.payload["kind"], row.payload["arguments"], row.owner_id
    try:
        result = perform(kind, args, owner)
        with Session.begin() as db:
            row = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if row.status != "RUNNING" or row.attempts != attempt:
                return
            db.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == "RUNNING", Job.attempts == attempt)
                .values(
                    payload=dict(row.payload, result=result), status="COMPLETED", lease_until=None
                ),
                execution_options={"synchronize_session": False},
            )
    except Exception:
        # Exception contents can contain credentials/provider payloads. Never persist them.
        with Session.begin() as db:
            row = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if row.status != "RUNNING" or row.attempts != attempt:
                return
            row.status = "DEAD_LETTER" if row.attempts >= 3 else "RETRY"
            row.lease_until = None
            row.payload = dict(
                row.payload, error="Operation failed; inspect sanitized operational diagnostics"
            )
            if row.status == "RETRY":
                db.add(
                    Outbox(
                        owner_id=owner,
                        event_key=f"retry:{job_id}:{row.attempts}",
                        payload={"job_id": job_id},
                    )
                )


def recover():
    with Session.begin() as db:
        rows = db.scalars(
            select(Job)
            .where(
                or_(
                    (Job.status == "RUNNING") & (Job.lease_until < now()),
                    Job.status.in_(["QUEUED", "RETRY"])
                    & (Job.updated_at < now() - timedelta(minutes=10)),
                )
            )
            .with_for_update(skip_locked=True)
            .limit(100)
        )
        for row in rows:
            row.status = "DEAD_LETTER" if row.attempts >= 3 else "RETRY"
            if row.status == "RETRY":
                db.add(
                    Outbox(
                        owner_id=row.owner_id,
                        event_key="recovery:" + uid(),
                        payload={"job_id": row.id},
                    )
                )


def perform(kind, args, owner):
    if kind in {"notice", "resume"}:
        import base64
        from app.repositories import documents
        from app.utils.file_handler import notice_draft, extract
        from app.services.resume_analyzer import analyze_resume
        from app.models.persistent import Document

        with Session() as db:
            row = db.scalar(
                select(Document).where(
                    Document.id == args["document_id"], Document.owner_id == owner
                )
            )
            if not row:
                raise ValueError("Unknown document")
            prior = documents.get(
                "extracted_notices" if kind == "notice" else "skill_analysis", row.id, owner
            )
            if prior and (kind == "resume" or prior.get("status") in {"NEEDS_REVIEW", "CONFIRMED"}):
                return prior
            parsed = extract(
                base64.b64decode(row.payload["content_base64"]),
                row.payload["filename"],
                resume=kind == "resume",
            )
            row.payload = dict(row.payload, **parsed)
            db.commit()
            if kind == "resume":
                result = analyze_resume(parsed["text"], owner, row.id)
                return documents.put("skill_analysis", row.id, result)
            result = dict(
                owner_id=owner,
                status="NEEDS_REVIEW",
                draft=notice_draft(parsed["text"]),
                warnings=parsed["warnings"],
            )
            return documents.put("extracted_notices", row.id, result)
    if kind == "discovery":
        from app.services.scraper import discover_feed

        return discover_feed(args["feed_url"], owner)
    if kind == "judge0":
        from app.services.judge0 import execute as judge

        return judge(args, owner)
    if kind == "career":
        from app.services.career import run

        return run(args["goal_id"], owner)
    raise ValueError("Unsupported job type")

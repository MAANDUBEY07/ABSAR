from fastapi import APIRouter
from sqlalchemy import select
from app.routes.common import DB, Owner, Limit, Offset, ok
from app.models.runtime import Job
from app.models.runtime import Notification
from app.models.runtime import NotificationPreference
from app.repositories.relational import owned, serialize
from app.schemas.runtime import NotificationPrefs

router = APIRouter()


@router.get("/jobs/{record_id}")
def job(record_id: str, owner: Owner, db: DB):
    row = owned(db, Job, owner, record_id)
    # Raw code and input documents are private but need not be repeated in polling responses.
    data = serialize(row)
    data.pop("arguments", None)
    return ok(data)


@router.get("/jobs/{record_id}/result")
def job_result(record_id: str, owner: Owner, db: DB):
    row = owned(db, Job, owner, record_id)
    return ok(
        dict(
            id=row.id,
            status=row.status,
            attempts=row.attempts,
            result=row.payload.get("result"),
            error=row.payload.get("error"),
        )
    )


@router.post("/jobs/{record_id}/cancel")
def cancel(record_id: str, owner: Owner, db: DB):
    row = owned(db, Job, owner, record_id, lock=True)
    if row.status not in {"COMPLETED", "DEAD_LETTER"}:
        row.status = "CANCELLED"
        db.commit()
    return ok(dict(id=row.id, status=row.status))


@router.get("/notifications")
def notifications(owner: Owner, db: DB, limit: Limit = 20, offset: Offset = 0):
    return ok(
        [
            serialize(row)
            for row in db.scalars(
                select(Notification)
                .where(Notification.owner_id == owner)
                .order_by(Notification.created_at.desc(), Notification.id)
                .limit(limit)
                .offset(offset)
            )
        ]
    )


@router.patch("/notifications/preferences")
def preferences(body: NotificationPrefs, owner: Owner, db: DB):
    row = db.scalar(
        select(NotificationPreference).where(
            NotificationPreference.owner_id == owner,
            NotificationPreference.kind_key == "preferences",
        )
    )
    if row is None:
        row = NotificationPreference(owner_id=owner, kind_key="preferences", payload={})
        db.add(row)
    row.payload = body.model_dump()
    db.commit()
    return ok(row.payload)

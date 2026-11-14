from datetime import timezone
from fastapi import HTTPException
from sqlalchemy import select


def owned(db, model, identity, record_id, lock=False):
    query = select(model).where(model.id == record_id, model.owner_id == identity)
    if lock:
        query = query.with_for_update()
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Resource not found")
    return row


def serialize(row):
    result = dict(
        row.payload,
        id=row.id,
        created_at=row.created_at.replace(tzinfo=row.created_at.tzinfo or timezone.utc).isoformat(),
    )
    for key in ("status", "revision", "opportunity_id", "attempts"):
        if hasattr(row, key):
            result[key] = getattr(row, key)
    return result

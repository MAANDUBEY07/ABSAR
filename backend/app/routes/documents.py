from fastapi import APIRouter
from sqlalchemy import select
from app.routes.common import DB, Owner, Limit, Offset, ok
from app.models.resume import Document

router = APIRouter()


@router.get("/documents")
def list_documents(owner: Owner, db: DB, limit: Limit = 20, offset: Offset = 0):
    rows = db.scalars(
        select(Document)
        .where(Document.owner_id == owner)
        .order_by(Document.created_at, Document.id)
        .limit(limit)
        .offset(offset)
    )
    return ok([dict(id=r.id, filename=r.payload["filename"], size=r.payload["size"]) for r in rows])

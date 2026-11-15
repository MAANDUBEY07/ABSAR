from fastapi import APIRouter, HTTPException, UploadFile
from app.routes.common import DB, Owner, ok
from app.models.resume import Document
from app.repositories.relational import owned
from app.repositories import documents
from app.schemas.opportunity import OpportunityInput
from app.services.catalog import opportunity, create_opportunity
from app.utils.file_handler import upload
from app.services.jobs import enqueue

router = APIRouter()


@router.post("/notices/upload", status_code=201)
async def notice_upload(file: UploadFile, owner: Owner, db: DB):
    row = await upload(file, db, owner, "notice")
    if not documents.get("extracted_notices", row.id, owner):
        documents.put(
            "extracted_notices", row.id, dict(owner_id=owner, status="UPLOADED", draft=None)
        )
    return ok(dict(id=row.id, status=documents.get("extracted_notices", row.id, owner)["status"]))


@router.post("/notices/{record_id}/extract", status_code=202)
def notice_extract(record_id: str, owner: Owner, db: DB):
    owned(db, Document, owner, record_id)
    record = documents.get("extracted_notices", record_id, owner)
    if not record:
        raise HTTPException(404, "Notice not found")
    job = enqueue(db, owner, "notice", {"document_id": record_id})
    documents.transition(
        "extracted_notices",
        record_id,
        owner,
        {"UPLOADED"},
        dict(status="PROCESSING", job_id=job.id),
    )
    return ok(dict(job_id=job.id, status=job.status))


def notice_record(record_id, owner):
    row = documents.get("extracted_notices", record_id, owner)
    if not row:
        raise HTTPException(404, "Notice not found")
    return row


@router.get("/notices/{record_id}/status")
def notice_status(record_id: str, owner: Owner):
    return ok(notice_record(record_id, owner))


@router.get("/notices/{record_id}/opportunity")
def notice_opportunity(record_id: str, owner: Owner):
    row = notice_record(record_id, owner)
    return ok(opportunity(row["opportunity_id"]) if row.get("opportunity_id") else row.get("draft"))


@router.post("/notices/{record_id}/confirm")
def confirm_notice(record_id: str, body: OpportunityInput, owner: Owner, db: DB):
    owned(db, Document, owner, record_id, lock=True)
    row = notice_record(record_id, owner)
    if row["status"] == "CONFIRMED":
        return ok(opportunity(row["opportunity_id"]))
    if row["status"] != "NEEDS_REVIEW":
        raise HTTPException(409, "Extraction must finish before confirmation")
    result = create_opportunity(body.model_dump(mode="json"))
    documents.put(
        "extracted_notices",
        record_id,
        dict(row, status="CONFIRMED", opportunity_id=result["id"], confirmed_by=owner),
    )
    db.commit()
    return ok(result)

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from app.routes.common import DB, Owner, Limit, Offset, ok
from app.models.application import Application
from app.models.application import Approval
from app.models.runtime import Outbox
from app.repositories.relational import owned, serialize
from app.schemas.application import ApplicationCreate
from app.schemas.application import ApplicationPatch
from app.schemas.application import Revision
from app.schemas.application import Submit
from app.services import applications as service
from app.services.catalog import opportunity, digest

router = APIRouter()


@router.post("/applications", status_code=201)
def create(body: ApplicationCreate, owner: Owner, db: DB):
    opportunity(body.opportunity_id)
    row = Application(
        owner_id=owner, opportunity_id=body.opportunity_id, payload={"material": body.material}
    )
    db.add(row)
    try:
        db.flush()
        service.version(db, row)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Application already exists for opportunity") from None
    return ok(serialize(row))


@router.get("/applications")
def listing(owner: Owner, db: DB, limit: Limit = 20, offset: Offset = 0):
    return ok(
        [
            serialize(r)
            for r in db.scalars(
                select(Application)
                .where(Application.owner_id == owner)
                .order_by(Application.created_at, Application.id)
                .limit(limit)
                .offset(offset)
            )
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/applications/analytics")
def analytics(owner: Owner, db: DB):
    return ok(
        dict(
            db.execute(
                select(Application.status, func.count())
                .where(Application.owner_id == owner)
                .group_by(Application.status)
            ).all()
        )
    )


@router.get("/applications/{record_id}")
def detail(record_id: str, owner: Owner, db: DB):
    return ok(serialize(owned(db, Application, owner, record_id)))


@router.patch("/applications/{record_id}")
def patch(record_id: str, body: ApplicationPatch, owner: Owner, db: DB):
    row = owned(db, Application, owner, record_id, lock=True)
    status, payload = row.status, dict(row.payload)
    if body.material is not None:
        if status not in service.EDITABLE:
            raise HTTPException(409, "Submitted material is immutable")
        if body.material != payload.get("material"):
            payload["material"] = body.material
            payload.pop("approved_version_id", None)
            status = "DRAFT"
    if body.status:
        if body.status not in service.TRANSITIONS.get(status, set()):
            raise HTTPException(409, "Invalid lifecycle transition")
        status = body.status
    service.change(db, row, body.revision, status, payload)
    db.commit()
    return ok(serialize(row))


@router.post("/applications/{record_id}/approve")
def approve(record_id: str, body: Revision, owner: Owner, db: DB):
    row = owned(db, Application, owner, record_id, lock=True)
    if row.revision != body.revision:
        raise HTTPException(409, "Stale application revision")
    if row.status != "READY_FOR_REVIEW":
        raise HTTPException(409, "Application must be ready for human review")
    snapshot = service.current_version(db, row)
    db.add(
        Approval(
            owner_id=owner,
            version_id=snapshot.id,
            payload=dict(approved_by=owner, digest=snapshot.digest),
        )
    )
    service.change(
        db, row, body.revision, "APPROVED", dict(row.payload, approved_version_id=snapshot.id)
    )
    db.commit()
    return ok(serialize(row))


@router.post("/applications/{record_id}/submit")
def submit(
    record_id: str,
    body: Submit,
    owner: Owner,
    db: DB,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
):
    row = owned(db, Application, owner, record_id, lock=True)
    request_hash = digest([record_id, body.model_dump()])
    key = "submission:" + digest([owner, idempotency_key])
    prior = db.scalar(select(Outbox).where(Outbox.owner_id == owner, Outbox.event_key == key))
    if prior:
        if prior.payload.get("request_hash") != request_hash:
            raise HTTPException(409, "Idempotency key already used for another request")
        return ok(prior.payload["receipt"])
    receipt = row.payload.get("receipt")
    if receipt:
        if (
            row.payload.get("submission_key") == idempotency_key
            and row.payload.get("submission_hash") == request_hash
        ):
            return ok(receipt)
        raise HTTPException(409, "Submission key conflict or already submitted")
    if row.status != "APPROVED" or not service.approval_matches(db, row):
        raise HTTPException(409, "Current material requires explicit human approval")
    receipt = dict(
        application_id=row.id,
        status="SUBMITTED",
        status_source="USER_REPORTED",
        external_submission_verified=False,
    )
    service.change(
        db,
        row,
        body.revision,
        "SUBMITTED",
        dict(
            row.payload,
            receipt=receipt,
            submission_key=idempotency_key,
            submission_hash=request_hash,
        ),
    )
    db.add(
        Outbox(
            owner_id=owner,
            event_key=key,
            status="RECORDED",
            payload=dict(request_hash=request_hash, receipt=receipt),
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Concurrent submission or conflicting idempotency key") from None
    return ok(receipt)

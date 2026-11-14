from fastapi import HTTPException
from sqlalchemy import select, update
from app.models.application import Application
from app.models.application import ApplicationVersion
from app.models.application import Approval
from app.models.application import Audit
from app.models.base import uid
from app.services.catalog import digest

TRANSITIONS = {
    "SAVED": {"DRAFT", "WITHDRAWN"},
    "DRAFT": {"READY_FOR_REVIEW", "WITHDRAWN"},
    "READY_FOR_REVIEW": {"DRAFT", "WITHDRAWN"},
    "APPROVED": {"DRAFT", "WITHDRAWN"},
    "SUBMITTED": {"ASSESSMENT", "INTERVIEW", "OFFER", "REJECTED", "WITHDRAWN"},
    "ASSESSMENT": {"INTERVIEW", "OFFER", "REJECTED", "WITHDRAWN"},
    "INTERVIEW": {"OFFER", "REJECTED", "WITHDRAWN"},
    "OFFER": {"WITHDRAWN"},
}
EDITABLE = {"SAVED", "DRAFT", "READY_FOR_REVIEW", "APPROVED"}


def version(db, app):
    snapshot = dict(material=app.payload.get("material", {}), opportunity_id=app.opportunity_id)
    record = ApplicationVersion(
        id=uid(),
        owner_id=app.owner_id,
        application_id=app.id,
        revision=app.revision,
        digest=digest(snapshot),
        payload=snapshot,
    )
    db.add(record)
    db.add(
        Audit(
            owner_id=app.owner_id,
            payload=dict(
                action="APPLICATION_VERSION",
                application_id=app.id,
                revision=app.revision,
                status=app.status,
                digest=record.digest,
            ),
        )
    )
    db.flush()
    return record


def change(db, app, revision, status, payload):
    if app.revision != revision:
        raise HTTPException(409, "Stale application revision")
    result = db.execute(
        update(Application)
        .where(
            Application.id == app.id,
            Application.owner_id == app.owner_id,
            Application.revision == revision,
        )
        .values(revision=revision + 1, status=status, payload=payload),
        execution_options={"synchronize_session": False},
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Concurrent application update")
    db.refresh(app)
    return version(db, app)


def current_version(db, app):
    return db.scalar(
        select(ApplicationVersion).where(
            ApplicationVersion.application_id == app.id,
            ApplicationVersion.owner_id == app.owner_id,
            ApplicationVersion.revision == app.revision,
        )
    )


def approval_matches(db, app):
    approved = app.payload.get("approved_version_id")
    if not approved:
        return False
    record = db.scalar(
        select(ApplicationVersion).where(
            ApplicationVersion.id == approved, ApplicationVersion.owner_id == app.owner_id
        )
    )
    approval = db.scalar(
        select(Approval).where(Approval.version_id == approved, Approval.owner_id == app.owner_id)
    )
    return bool(
        record
        and approval
        and record.digest
        == digest(dict(material=app.payload.get("material", {}), opportunity_id=app.opportunity_id))
    )

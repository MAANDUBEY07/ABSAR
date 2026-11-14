"""Development compatibility adapters. Unsupported historical auth actions fail closed."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import jwt
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.routes.common import DB, Owner
from app.config import settings
from app.schemas.profile import ProfileInput
from app.models.runtime import LocalDocument
from app.models.profile import Profile
from app.models.resume import Document
from app.models.application import Approval
from app.repositories.relational import owned, serialize
from app.services.catalog import digest, opportunity
from app.repositories import documents


def local_only():
    if settings.hosted:
        raise HTTPException(503, "Legacy routes are development-only; use /api/v1")


router = APIRouter(dependencies=[Depends(local_only)])


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=12, max_length=128)


def local_auth():
    if settings.auth_provider != "local" or settings.hosted:
        raise HTTPException(503, "Use the configured external authentication provider")


def hash_password(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def token(subject):
    instant = datetime.now(timezone.utc)
    return jwt.encode(
        dict(
            sub=subject,
            iss="opportunityos-local",
            aud="opportunityos",
            iat=instant,
            exp=instant + timedelta(minutes=30),
        ),
        settings.jwt_secret,
        algorithm="HS256",
    )


@router.post("/auth/signup", status_code=201)
def signup(body: Credentials, db: DB):
    local_auth()
    key, salt, subject = digest(body.email.casefold()), secrets.token_hex(16), str(uuid4())
    db.add(
        LocalDocument(
            collection="local_accounts",
            id=key,
            payload=dict(
                subject=subject, salt=salt, password_hash=hash_password(body.password, salt)
            ),
        )
    )
    db.add(
        Profile(
            id=subject,
            owner_id=subject,
            payload=dict(ProfileInput().model_dump(mode="json"), notification_email=None),
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Account unavailable") from None
    return {"access_token": token(subject), "token_type": "bearer"}  # nosec B105


@router.post("/auth/login")
def login(body: Credentials, db: DB):
    local_auth()
    row = db.get(LocalDocument, ("local_accounts", digest(body.email.casefold())))
    salt = row.payload["salt"] if row else "00" * 16
    computed = hash_password(body.password, salt)
    if not row or not hmac.compare_digest(computed, row.payload["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": token(row.payload["subject"]), "token_type": "bearer"}  # nosec B105


@router.post("/auth/forgot-password")
@router.post("/auth/reset-password")
@router.post("/auth/mfa/verify")
@router.post("/auth/mfa/setup")
def unsupported_auth():
    raise HTTPException(503, "Recovery and MFA require the configured external auth provider")


@router.get("/opportunities")
def catalog(owner: Owner):
    return documents.scan("opportunities", limit=100)


@router.post("/opportunities/{record_id}/analyze")
def analyze(record_id: str, owner: Owner, db: DB):
    from app.routes.eligibility import matching
    from app.schemas.persistent import MatchInput

    return matching(MatchInput(opportunity_id=record_id), owner, db)["data"]


@router.post("/opportunities/{record_id}/save")
def save(record_id: str, owner: Owner, db: DB):
    from app.routes.eligibility import feedback
    from app.schemas.persistent import Feedback

    opportunity(record_id)
    return feedback(Feedback(opportunity_id=record_id, feedback="saved"), owner, db)["data"]


@router.post("/documents/upload")
async def upload(file: UploadFile, owner: Owner, db: DB):
    from app.utils.file_handler import upload as store

    row = await store(file, db, owner, "resume")
    return dict(id=row.id, filename=row.payload["filename"])


@router.delete("/documents/{record_id}")
def delete_document(record_id: str, owner: Owner, db: DB):
    row = owned(db, Document, owner, record_id)
    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.get("/approvals")
def approvals(owner: Owner, db: DB):
    return [
        serialize(row)
        for row in db.scalars(select(Approval).where(Approval.owner_id == owner).limit(100))
    ]


@router.get("/agent/activity")
@router.get("/agent/events")
def activity(owner: Owner):
    return documents.scan("agent_runs", owner=owner)


@router.get("/agent/events/stream")
def events(owner: Owner):
    import json
    from fastapi.responses import StreamingResponse

    def stream():
        yield (
            "event: snapshot\ndata: "
            + json.dumps(documents.scan("agent_runs", owner=owner))
            + "\n\n"
        )

    return StreamingResponse(stream(), media_type="text/event-stream")


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    material: dict = Field(default_factory=dict)


@router.post("/applications/{record_id}/prepare")
@router.post("/applications/{record_id}/answer")
def prepare(record_id: str, body: DraftInput, owner: Owner, db: DB):
    from app.routes.applications import patch
    from app.schemas.persistent import ApplicationPatch

    return patch(
        record_id, ApplicationPatch(revision=body.revision, material=body.material), owner, db
    )["data"]

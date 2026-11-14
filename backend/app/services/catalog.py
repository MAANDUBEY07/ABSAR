from app.utils.validators import canonical_url
from datetime import date
import hashlib
import json
from fastapi import HTTPException
from app.repositories import documents
from app.models.opportunity import OpportunityDocument


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def create_opportunity(data):
    from app.schemas.opportunity import OpportunityInput

    data = OpportunityInput.model_validate(data).model_dump(mode="json")
    for key in ("application_url", "source_url", "company_url"):
        data[key] = canonical_url(data.get(key))
    fingerprint = digest(
        [
            data.get("title", "").strip().casefold(),
            (data.get("organization") or "").strip().casefold(),
            data.get("application_url"),
            data.get("deadline"),
        ]
    )
    record_id = fingerprint[:32]
    document = OpportunityDocument.model_validate(
        dict(
            data,
            id=record_id,
            fingerprint=fingerprint,
            verification_status="EXPIRED"
            if data.get("deadline") and date.fromisoformat(data["deadline"]) < date.today()
            else "UNKNOWN",
        )
    )
    return documents.put(
        "opportunities", record_id, document.model_dump(mode="json"), insert_only=True
    )


def opportunity(record_id):
    record = documents.get("opportunities", record_id)
    if not record:
        raise HTTPException(404, "Opportunity not found")
    return record

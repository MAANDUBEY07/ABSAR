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
    # Append every distinct source observation; conflicts never overwrite earlier facts.
    observation_id = digest([record_id, data])[:32]
    from app.models.base import now

    prior = documents.get("opportunities", record_id)
    conflicts = {
        key: {"existing": prior.get(key), "observed": value}
        for key, value in data.items()
        if prior and prior.get(key) != value
    }
    documents.put(
        "opportunity_observations",
        observation_id,
        dict(
            opportunity_id=record_id, observed_at=now().isoformat(), data=data, conflicts=conflicts
        ),
        insert_only=True,
    )
    from app.integrations.member1 import compare_opportunities

    candidates = documents.scan("opportunities", limit=501)
    for existing in candidates[:500]:
        decision = compare_opportunities(data, existing).to_dict()
        if decision["is_duplicate"] or decision["requires_review"]:
            documents.put(
                "duplicate_reviews",
                digest([record_id, existing["id"]])[:32],
                dict(
                    candidate_id=record_id,
                    existing_id=existing["id"],
                    decision=decision,
                    action="HUMAN_REVIEW_REQUIRED",
                    candidate_scan_truncated=len(candidates) > 500,
                ),
                insert_only=True,
            )
    return documents.put(
        "opportunities", record_id, document.model_dump(mode="json"), insert_only=True
    )


def opportunity(record_id):
    record = documents.get("opportunities", record_id)
    if not record and record_id.startswith("arbeitnow_"):
        from app.services import arbeitnow

        try:
            live = arbeitnow.get_listing(record_id)
        except (OSError, ValueError):
            live = None
        if live:
            # Materialize one listing when a workflow needs it, never every
            # listing on a search page before the HTTP response can be sent.
            record = documents.put("opportunities", record_id, live, insert_only=True)
    if not record:
        raise HTTPException(404, "Opportunity not found")
    return record

"""Daily deterministic refresh of a bounded batch of existing private analyses."""

from datetime import date
from app.models.base import now
from app.repositories import documents
from app.services.catalog import digest
from app.services.trust_checker import analyze


def refresh():
    seen = set()
    for previous in documents.scan("verification_results", limit=100):
        if (
            not previous.get("opportunity_id")
            or not previous.get("owner_id")
            or previous.get("type") == "USER_ALLEGATION"
        ):
            continue
        owner, opportunity_id = previous["owner_id"], previous["opportunity_id"]
        key = (owner, opportunity_id)
        if key in seen:
            continue
        seen.add(key)
        current = documents.get("opportunities", opportunity_id)
        if not current:
            continue
        record_id = digest([owner, opportunity_id, date.today().isoformat(), "refresh"])[:32]
        documents.put(
            "verification_results",
            record_id,
            dict(
                analyze(current),
                owner_id=owner,
                opportunity_id=opportunity_id,
                analyzed_at=now().isoformat(),
                source_snapshot=current,
                provenance="SCHEDULED_DETERMINISTIC_REFRESH",
            ),
            insert_only=True,
        )

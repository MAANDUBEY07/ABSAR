from fastapi import APIRouter
from app.routes.common import Owner, Limit, Offset, ok
from app.repositories import documents
from fastapi import Query
from app.schemas.opportunity import OpportunityInput
from app.services.catalog import opportunity, create_opportunity
from app.services import arbeitnow, category_sources, india_sources
from app.services.location_filter import matches_location
from pymongo.errors import PyMongoError
from sqlalchemy.exc import SQLAlchemyError
from typing import Literal

router = APIRouter()


@router.post("/opportunities", status_code=201)
def insert_opportunity(body: OpportunityInput, owner: Owner):
    return ok(create_opportunity(body.model_dump(mode="json")))


@router.get("/opportunities/{record_id}")
def get_opportunity(record_id: str, owner: Owner):
    from app.services.source_intelligence import enrich_opportunity

    existing = documents.get("opportunities", record_id)
    if existing and existing.get("source_summary") and existing.get("requirements", {}).get("confirmed"):
        return ok(existing)

    opp = existing
    if not opp and record_id.startswith("live_"):
        opp = category_sources.get_listing(record_id)
    elif not opp and record_id.startswith("arbeitnow_"):
        try:
            opp = arbeitnow.get_listing(record_id)
        except (OSError, ValueError):
            opp = None

    if not opp:
        opp = opportunity(record_id)

    # A minimal catalog record has nothing to inspect. Preserve its saved API
    # representation instead of persisting a synthetic failure on every read.
    # Explicit refresh still reports source failures for these records.
    if opp and (
        opp.get("source_url")
        or opp.get("application_url")
        or len((opp.get("description") or "").strip()) > 30
    ):
        opp = enrich_opportunity(opp)
    return ok(opp)


@router.post("/opportunities/{record_id}/refresh-source")
def refresh_opportunity_source(
    record_id: str,
    owner: Owner,
    body: dict | None = None,
):
    from app.services.source_intelligence import enrich_opportunity

    opp = documents.get("opportunities", record_id)
    if not opp and record_id.startswith("live_"):
        opp = category_sources.get_listing(record_id)
    elif not opp and record_id.startswith("arbeitnow_"):
        try:
            opp = arbeitnow.get_listing(record_id)
        except (OSError, ValueError):
            opp = None
    if not opp:
        opp = opportunity(record_id)

    user_desc = (body or {}).get("user_description")
    enriched = enrich_opportunity(opp, user_description=user_desc, force_refresh=True)
    return ok(enriched)


@router.get("/opportunities")
def list_opportunities(
    owner: Owner,
    limit: Limit = 20,
    offset: Offset = 0,
    category: str | None = None,
    state: str | None = Query(None, max_length=200),
    location: str | None = Query(None, max_length=200),
    country: Literal["India"] | None = None,
    search: str | None = Query(None, max_length=300),
    opportunity_mode: Literal["online", "offline", "hybrid"] | None = None,
):
    if category == "coding_challenge":
        category = "coding_competition"
    database_available = True
    try:
        candidates = documents.scan("opportunities", limit=501)
    except (PyMongoError, SQLAlchemyError):
        # Keep public listings useful during a database outage; private workflows
        # still use the database and continue to fail closed.
        candidates = []
        database_available = False

    live_source_available = True
    live_candidates = india_sources.listings(category)
    try:
        international_candidates = [] if country == "India" else (
            category_sources.listings(category)
            if category in category_sources.CATEGORIES
            else arbeitnow.listings()
        )
        live_candidates += international_candidates
    except (OSError, ValueError):
        live_source_available = False

    # Keep live listings at the front so page one includes fresh source data;
    # persisted records still win if an id exists in both collections.
    by_id = {record["id"]: record for record in live_candidates}
    by_id.update({record["id"]: record for record in candidates[:500]})
    candidates = list(by_id.values())
    result = []
    for record in candidates:
        if category and record.get("category") != category:
            continue
        if country == "India" and not (
            (record.get("category_metadata") or {}).get("country") == "India"
            or matches_location(record, "India")
        ):
            continue
        if not matches_location(record, state) or not matches_location(record, location):
            continue
        record_mode = record.get("opportunity_mode")
        if record_mode is None and record.get("remote") is True:
            record_mode = "online"
        if opportunity_mode and record_mode != opportunity_mode:
            continue
        if (
            search
            and search.casefold()
            not in " ".join(
                str(record.get(k) or "") for k in ("title", "description", "organization")
            ).casefold()
        ):
            continue
        result.append(record)
    page_items = result[offset : offset + limit]
    return ok(
        page_items,
        limit=limit,
        offset=offset,
        scanned=len(candidates),
        truncated=len(candidates) > 500,
        live_source=(live_candidates[0].get("source_attribution") if live_candidates else None),
        database_available=database_available,
        live_source_available=live_source_available,
        source_status=india_sources.source_status(category),
    )


@router.get("/opportunities/{record_id}/observations")
def observations(record_id: str, owner: Owner, limit: Limit = 20, offset: Offset = 0):
    opportunity(record_id)
    return ok(
        documents.related("opportunity_observations", "opportunity_id", record_id, limit, offset),
        limit=limit,
        offset=offset,
    )


@router.get("/opportunities/{record_id}/duplicates")
def duplicate_reviews(record_id: str, owner: Owner, limit: Limit = 20, offset: Offset = 0):
    opportunity(record_id)
    return ok(
        documents.related("duplicate_reviews", "candidate_id", record_id, limit, offset),
        limit=limit,
        offset=offset,
    )

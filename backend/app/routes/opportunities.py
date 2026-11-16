from fastapi import APIRouter
from app.routes.common import Owner, Limit, Offset, ok
from app.repositories import documents
from fastapi import Query
from app.schemas.opportunity import OpportunityInput
from app.services.catalog import opportunity, create_opportunity
from app.services import arbeitnow
from pymongo.errors import PyMongoError
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()


@router.post("/opportunities", status_code=201)
def insert_opportunity(body: OpportunityInput, owner: Owner):
    return ok(create_opportunity(body.model_dump(mode="json")))


@router.get("/opportunities/{record_id}")
def get_opportunity(record_id: str, owner: Owner):
    if record_id.startswith("arbeitnow_"):
        try:
            live = arbeitnow.get_listing(record_id)
        except (OSError, ValueError):
            live = None
        if live:
            return ok(live)
    return ok(opportunity(record_id))


@router.get("/opportunities")
def list_opportunities(
    owner: Owner,
    limit: Limit = 20,
    offset: Offset = 0,
    category: str | None = None,
    state: str | None = None,
    search: str | None = Query(None, max_length=300),
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
    try:
        live_candidates = arbeitnow.listings()
    except (OSError, ValueError):
        live_candidates = []
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
        if state and str(record.get("location") or "").casefold() != state.casefold():
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
    if database_available:
        # Persist only the page the student actually requested. This is an
        # idempotent cache fill, allowing existing detail/save flows to find
        # live source records without writing the entire provider feed per GET.
        for record in page_items:
            if record.get("source_attribution") == "Arbeitnow":
                try:
                    documents.put("opportunities", record["id"], record, insert_only=True)
                except (PyMongoError, SQLAlchemyError):
                    database_available = False
                    break
    return ok(
        page_items,
        limit=limit,
        offset=offset,
        scanned=len(candidates),
        truncated=len(candidates) > 500,
        live_source="Arbeitnow" if live_source_available else None,
        database_available=database_available,
        live_source_available=live_source_available,
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

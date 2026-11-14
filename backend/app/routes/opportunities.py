from fastapi import APIRouter
from app.routes.common import Owner, Limit, Offset, ok
from app.repositories import documents
from fastapi import Query
from app.schemas.opportunity import OpportunityInput
from app.services.catalog import opportunity, create_opportunity

router = APIRouter()


@router.post("/opportunities", status_code=201)
def insert_opportunity(body: OpportunityInput, owner: Owner):
    return ok(create_opportunity(body.model_dump(mode="json")))


@router.get("/opportunities/{record_id}")
def get_opportunity(record_id: str, owner: Owner):
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
    candidates = documents.scan("opportunities", limit=501)
    result = []
    for record in candidates[:500]:
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
    return ok(
        result[offset : offset + limit],
        limit=limit,
        offset=offset,
        scanned=min(500, len(candidates)),
        truncated=len(candidates) > 500,
    )

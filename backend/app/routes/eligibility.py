from fastapi import APIRouter
from sqlalchemy import select
from app.routes.common import DB, Owner, Limit, Offset, ok
from app.models.profile import Profile
from app.models.opportunity import Saved
from app.repositories.relational import owned
from app.repositories import documents
from app.schemas.eligibility import MatchInput, EligibilityBatch, CheckEligibilityInput
from app.schemas.opportunity import Feedback
from app.services.catalog import opportunity
from app.services.matching import match, is_open

router = APIRouter()


@router.get("/recommendations")
def recommendations(
    owner: Owner,
    db: DB,
    limit: Limit = 20,
    offset: Offset = 0,
    remote: bool | None = None,
    max_duration_months: int | None = None,
    min_stipend: float | None = None,
    domain: str | None = None,
    graduation_year: int | None = None,
    deadline: str | None = None,
    verification_status: str | None = None,
):
    profile = owned(db, Profile, owner, owner).payload
    catalog = documents.scan("opportunities", limit=501)
    results = []
    for record in catalog[:500]:
        if not is_open(record):
            continue
        if remote is not None and record.get("remote") != remote:
            continue
        if domain and record.get("domain") != domain:
            continue
        if verification_status and record.get("verification_status") != verification_status:
            continue
        if deadline and (not record.get("deadline") or record["deadline"] < deadline):
            continue
        if max_duration_months is not None and (
            record.get("duration_months") is None or record["duration_months"] > max_duration_months
        ):
            continue
        if min_stipend is not None and (
            record.get("stipend") is None or record["stipend"] < min_stipend
        ):
            continue
        years = record.get("requirements", {}).get("graduation_years", [])
        if graduation_year and years and graduation_year not in years:
            continue
        results.append(dict(match(profile, record), opportunity=record))
    results.sort(key=lambda r: (-r["score"], r["opportunity_id"]))
    return ok(
        results[offset : offset + limit],
        limit=limit,
        offset=offset,
        scanned=min(500, len(catalog)),
        truncated=len(catalog) > 500,
    )


@router.post("/recommendations/match")
def matching(body: MatchInput, owner: Owner, db: DB):
    return ok(match(owned(db, Profile, owner, owner).payload, opportunity(body.opportunity_id)))


@router.get("/recommendations/{record_id}/explanation")
def explanation(record_id: str, owner: Owner, db: DB):
    return matching(MatchInput(opportunity_id=record_id), owner, db)


@router.post("/recommendations/feedback")
def feedback(body: Feedback, owner: Owner, db: DB):
    opportunity(body.opportunity_id)
    key = "feedback:" + body.opportunity_id
    row = db.scalar(select(Saved).where(Saved.owner_id == owner, Saved.kind_key == key))
    if not row:
        row = Saved(owner_id=owner, kind_key=key, payload={})
        db.add(row)
    row.payload = body.model_dump()
    db.commit()
    return ok(row.payload)


@router.post("/eligibility/check/{opportunity_id}")
def check_eligibility(
    opportunity_id: str,
    owner: Owner,
    db: DB,
    body: CheckEligibilityInput | None = None,
):
    from app.services.eligibility_adapter import evaluate_opportunity
    from app.services.source_intelligence import enrich_opportunity

    user_profile = owned(db, Profile, owner, owner).payload
    opp = documents.get("opportunities", opportunity_id)
    if not opp:
        opp = opportunity(opportunity_id)

    force_refresh = bool(body and body.force_refresh)
    user_desc = body.user_description if body else None

    # Priority 2: Complete workflow - if criteria unconfirmed, or stale, or force_refresh,
    # or user supplied manual description, invoke source extraction workflow before evaluating.
    if not opp.get("requirements", {}).get("confirmed") or force_refresh or user_desc:
        opp = enrich_opportunity(opp, user_description=user_desc, force_refresh=force_refresh)

    eval_result = evaluate_opportunity(user_profile, opp)
    return ok(eval_result)


@router.post("/eligibility/batch")
def batch_eligibility(body: EligibilityBatch, owner: Owner, db: DB):
    from app.services.eligibility_adapter import evaluate_opportunity

    profile = owned(db, Profile, owner, owner).payload
    return ok(
        [
            evaluate_opportunity(profile, opportunity(record_id))
            for record_id in body.opportunity_ids
        ]
    )

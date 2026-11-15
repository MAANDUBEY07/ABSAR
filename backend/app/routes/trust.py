from fastapi import APIRouter, HTTPException
from app.routes.common import Owner, ok
from app.models.base import now
from app.models.base import uid
from app.repositories import documents
from app.schemas.eligibility import MatchInput
from app.schemas.trust import Report
from app.services.catalog import opportunity
from app.integrations import member1

router = APIRouter()


@router.post("/verification/analyze")
def risk(body: MatchInput, owner: Owner):
    data = opportunity(body.opportunity_id)
    result = dict(
        member1.analyze_trust(data),
        owner_id=owner,
        opportunity_id=data["id"],
        analyzed_at=now().isoformat(),
        source_snapshot=data,
    )
    snapshot_id = uid()
    documents.put(
        "opportunity_source_snapshots",
        snapshot_id,
        dict(owner_id=owner, opportunity_id=data["id"], source=data),
    )
    result["snapshot_id"] = snapshot_id
    return ok(documents.put("verification_results", uid(), result))


@router.get("/verification/{record_id}/history")
def history(record_id: str, owner: Owner):
    rows = documents.verification_history(owner, record_id)
    return ok(rows)


@router.get("/verification/{record_id}")
def verification(record_id: str, owner: Owner):
    rows = history(record_id, owner)["data"]
    if not rows:
        raise HTTPException(404, "No private verification history")
    return ok(rows[0])


@router.post("/verification/report", status_code=201)
def report(body: Report, owner: Owner):
    opportunity(body.opportunity_id)
    return ok(
        documents.put(
            "verification_results",
            uid(),
            dict(
                body.model_dump(),
                owner_id=owner,
                type="USER_ALLEGATION",
                proven=False,
                reported_at=now().isoformat(),
            ),
        )
    )


@router.get("/trust/verify/{opportunity_id}")
def trust_report(opportunity_id: str, owner: Owner):
    rows = history(opportunity_id, owner)["data"]
    analyses = [r for r in rows if "risk_score" in r]
    if not analyses:
        raise HTTPException(404, "Trust analysis unavailable; POST /verification/analyze first")
    return ok(analyses[0])

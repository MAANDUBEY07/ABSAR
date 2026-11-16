from fastapi import APIRouter, UploadFile, HTTPException
from app.routes.common import DB, Owner, ok
from app.models.profile import Profile
from app.repositories.relational import owned
from app.repositories import documents
from app.schemas.resume import Compare, ResumeMatchInput
from app.services.catalog import opportunity
from app.utils.file_handler import upload
from app.services.matching import compare_skills
from app.services.jobs import enqueue

router = APIRouter()


@router.post("/skills/analyze-resume", status_code=202)
@router.post("/resume/upload", status_code=202)
async def resume(file: UploadFile, owner: Owner, db: DB):
    row = await upload(file, db, owner, "resume")
    job = enqueue(db, owner, "resume", {"document_id": row.id})
    return ok(dict(document_id=row.id, job_id=job.id, status=job.status))


@router.post("/skills/compare")
def compare(body: Compare, owner: Owner, db: DB):
    profile = owned(db, Profile, owner, owner)
    opp = opportunity(body.opportunity_id)
    return ok(
        compare_skills(
            body.skills if body.skills is not None else profile.payload.get("skills"),
            opp.get("requirements", {}),
            opportunity=opp,
        )
    )


@router.get("/skills/gaps")
def gaps(opportunity_id: str, owner: Owner, db: DB):
    return compare(Compare(opportunity_id=opportunity_id), owner, db)


@router.post("/skills/roadmap")
def roadmap(body: Compare, owner: Owner, db: DB):
    analysis = compare(body, owner, db)["data"]
    missing = analysis["missing_required"] + analysis["missing_preferred"]
    return ok(
        dict(
            analysis=analysis,
            learning_order=missing,
            projects=[
                dict(
                    skill=s,
                    project=f"Build and document a small project using {s}",
                    estimated_hours=10,
                    estimate_type="ILLUSTRATIVE_EFFORT_ESTIMATE",
                )
                for s in missing
            ],
        )
    )


@router.get("/skills/progress")
def progress(owner: Owner):
    records = documents.scan("skill_analysis", owner=owner)
    return ok([dict(id=r["id"], skills=r["skills"]) for r in records])


@router.get("/resume/latest")
def latest_resume(owner: Owner):
    records = documents.scan("skill_analysis", limit=50, owner=owner)
    if not records:
        return ok(None)
    latest = max(records, key=lambda r: (str(r.get("_updated_at") or ""), str(r.get("id") or "")))
    return ok(latest)


@router.post("/resume/match/{opportunity_id}")
def match_resume(opportunity_id: str, body: ResumeMatchInput, owner: Owner):
    analysis = documents.get("skill_analysis", body.document_id, owner)
    if not analysis:
        raise HTTPException(404, "Resume analysis not found")
    opp = opportunity(opportunity_id)
    return ok(
        compare_skills(analysis["skills"], opp.get("requirements", {}), opportunity=opp)
    )

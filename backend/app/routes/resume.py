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
    candidate_skills = analysis.get("skills") or analysis.get("parsed_skills") or []
    return ok(
        compare_skills(candidate_skills, opp.get("requirements", {}), opportunity=opp)
    )


@router.post("/resume/matches")
def match_top_opportunities(owner: Owner, body: dict | None = None):
    doc_id = (body or {}).get("document_id")
    if doc_id:
        analysis = documents.get("skill_analysis", doc_id, owner)
    else:
        records = documents.scan("skill_analysis", limit=50, owner=owner)
        analysis = (
            max(records, key=lambda r: (str(r.get("_updated_at") or ""), str(r.get("id") or "")))
            if records
            else None
        )

    if not analysis:
        raise HTTPException(404, "No resume analysis available. Please upload a resume first.")

    candidate_skills = analysis.get("skills") or analysis.get("parsed_skills") or []
    tech_skills = analysis.get("technical_skills") or []
    has_tech_skills = len(tech_skills) > 0

    # Safe early-exit if candidate has no extracted skills at all
    if not candidate_skills:
        raw_opps = []
        try:
            raw_opps.extend(documents.scan("opportunities", limit=3))
        except Exception:
            pass
        return ok([
            {
                "opportunity_id": opp["id"],
                "title": opp.get("title") or "Opportunity",
                "organization": opp.get("organization") or opp.get("company_name") or "Employer / Sponsor",
                "category": opp.get("category") or "opportunity",
                "location": opp.get("location") or "Remote / Unspecified",
                "match_percentage": None,
                "criteria_available": False,
                "matched_skills": [],
                "missing_skills": [],
                "reasons": [
                    "Resume contains no extracted skills; technical-skill matching cannot be meaningfully calculated."
                ],
                "detail_url": f"/opportunities/{opp['id']}",
            }
            for opp in raw_opps
        ])

    from app.services import arbeitnow
    raw_opps = []
    try:
        raw_opps.extend(documents.scan("opportunities", limit=50))
    except Exception:
        pass
    try:
        raw_opps.extend(arbeitnow.listings()[:50])
    except Exception:
        pass

    seen_ids = set()
    opps = []
    for opp in raw_opps:
        if opp.get("id") and opp["id"] not in seen_ids:
            seen_ids.add(opp["id"])
            opps.append(opp)

    scored = []
    for opp in opps:
        comp = compare_skills(candidate_skills, opp.get("requirements", {}), opportunity=opp)
        has_criteria = comp.get("criteria_available", False)
        score = comp.get("score")
        matched = comp.get("matched_required", []) + comp.get("matched_preferred", [])
        missing = comp.get("missing_required", [])

        reasons = []
        if matched:
            reasons.append(f"Matched {len(matched)} relevant skill(s): {', '.join(matched[:4])}")
        if missing:
            reasons.append(f"Missing {len(missing)} requirement(s): {', '.join(missing[:3])}")

        # Truthful result when candidate has no comparable technical skills
        if not has_tech_skills:
            if not matched:
                has_criteria = False
                score = None
                reasons.append(
                    "Candidate profile contains no comparable technical skills; technical-skill matching cannot be meaningfully calculated."
                )
            else:
                reasons.append(
                    "Matched on non-technical competencies; technical skills are unlisted in resume."
                )
        elif not has_criteria:
            reasons.append(
                "Opportunity does not publish structured skill requirements; criteria cannot be evaluated."
            )

        scored.append(
            {
                "opportunity_id": opp["id"],
                "title": opp.get("title") or "Opportunity",
                "organization": opp.get("organization") or opp.get("company_name") or "Employer / Sponsor",
                "category": opp.get("category") or "opportunity",
                "location": opp.get("location") or "Remote / Unspecified",
                "match_percentage": round(score) if (has_criteria and score is not None) else None,
                "criteria_available": has_criteria,
                "matched_skills": matched,
                "missing_skills": missing,
                "reasons": reasons,
                "detail_url": f"/opportunities/{opp['id']}",
            }
        )

    scored.sort(
        key=lambda x: (
            1 if x["criteria_available"] and x["match_percentage"] is not None else 0,
            x["match_percentage"] or 0,
            len(x["matched_skills"]),
        ),
        reverse=True,
    )

    top_3 = scored[:3]
    return ok(top_3)

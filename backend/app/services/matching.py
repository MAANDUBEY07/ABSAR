"""Deterministic ranking; unknown factors remain null and contribute zero."""

from datetime import date
from app.utils.validators import normalized

from app.config import settings
from app.integrations.profile import eligibility_profile


def is_open(opportunity):
    deadline = opportunity.get("deadline")
    return opportunity.get("verification_status") != "EXPIRED" and (
        not deadline or date.fromisoformat(str(deadline)) >= date.today()
    )


def compare_skills(skills, requirements=None, *, opportunity=None):
    if requirements is None and isinstance(opportunity, dict):
        requirements = opportunity.get("requirements", {})
    elif isinstance(requirements, dict) and (
        "category_metadata" in requirements or "title" in requirements
    ):
        opportunity = requirements
        requirements = opportunity.get("requirements", {})

    requirements = requirements or {}
    actual = normalized(skills)
    required = normalized(requirements.get("required_skills"))
    preferred = normalized(requirements.get("preferred_skills"))

    # Fallback to opportunity metadata if required_skills is empty/unconfirmed
    if not required and opportunity:
        cached_req = opportunity.get("_extracted_skills")
        if cached_req is not None:
            required = cached_req
        else:
            tags = opportunity.get("category_metadata", {}).get("tags", [])
            extracted_from_tags = set()
            if isinstance(tags, list):
                norm_tags = normalized([t for t in tags if isinstance(t, str)])
                if norm_tags:
                    extracted_from_tags = norm_tags

            # If tags exist, use them directly to avoid expensive regex scanning over descriptions
            if extracted_from_tags:
                required = extracted_from_tags
            else:
                from app.services.resume_analyzer import extract_skills

                # Truncate text context to prevent running full taxonomy regexes over huge descriptions
                text_context = f"{opportunity.get('title', '')} {(opportunity.get('description') or '')[:1200]}"
                extracted_opp_skills = normalized(extract_skills(text_context))
                if extracted_opp_skills:
                    required = extracted_opp_skills

            opportunity["_extracted_skills"] = required

    criteria_available = bool(required or preferred)
    has_missing_opportunity_criteria = not criteria_available

    score = None
    if required and skills is not None:
        score = 100.0 * len(actual & required) / len(required)

    return {
        "matched_required": sorted(actual & required),
        "missing_required": sorted(required - actual),
        "missing_preferred": sorted(preferred - actual),
        "score": round(score, 1) if score is not None else None,
        "criteria_available": criteria_available,
        "has_missing_opportunity_criteria": has_missing_opportunity_criteria,
    }


def match(profile, opportunity):
    profile = eligibility_profile(profile)
    requirements = opportunity.get("requirements", {})
    checks = []

    def check(field, needed, predicate):
        if needed is None or needed == []:
            return
        value = profile.get(field)
        passed = (
            None
            if value is None or not requirements.get("confirmed")
            else bool(predicate(value, needed))
        )
        checks.append({"field": field, "required": needed, "actual": value, "passed": passed})

    for field, key in (
        ("graduation_year", "graduation_years"),
        ("degree", "degrees"),
        ("branch", "branches"),
        ("location", "locations"),
    ):
        check(
            field,
            requirements.get(key),
            lambda v, n: str(v).casefold() in {str(x).casefold() for x in n},
        )
    check("cgpa", requirements.get("min_cgpa"), lambda v, n: v >= n)
    check("experience_months", requirements.get("min_experience_months"), lambda v, n: v >= n)
    check(
        "skills", requirements.get("required_skills"), lambda v, n: normalized(n) <= normalized(v)
    )
    from app.services.eligibility_adapter import evaluate_opportunity

    decision = evaluate_opportunity(
        profile, dict(opportunity, title=opportunity.get("title") or "Opportunity")
    )
    status = {"ELIGIBLE": "ELIGIBLE", "NOT_ELIGIBLE": "INELIGIBLE"}.get(
        decision["api_status"], "UNKNOWN"
    )
    analysis = compare_skills(profile.get("skills"), requirements)
    pref_checks = []
    prefs = profile.get("preferences") or {}
    for key in ("remote", "domain"):
        if prefs.get(key) is not None and opportunity.get(key) is not None:
            pref_checks.append(prefs[key] == opportunity[key])
    if prefs.get("min_stipend") is not None and opportunity.get("stipend") is not None:
        pref_checks.append(opportunity["stipend"] >= prefs["min_stipend"])
    if (
        prefs.get("max_duration_months") is not None
        and opportunity.get("duration_months") is not None
    ):
        pref_checks.append(opportunity["duration_months"] <= prefs["max_duration_months"])
    minimum = requirements.get("min_experience_months")
    experience = (
        None
        if minimum is None or profile.get("experience_months") is None
        else 100
        if minimum == 0
        else min(100, 100 * profile["experience_months"] / minimum)
    )
    preferred = normalized(requirements.get("preferred_skills"))
    learning = (
        100 * len(preferred - normalized(profile.get("skills"))) / len(preferred)
        if preferred and profile.get("skills") is not None
        else None
    )
    factors = dict(
        skills=analysis["score"],
        preferences=100 * sum(pref_checks) / len(pref_checks) if pref_checks else None,
        experience=experience,
        learning=learning,
    )
    return dict(
        opportunity_id=opportunity["id"],
        eligibility=status,
        eligibility_detail=decision,
        checks=checks,
        factors=factors,
        weights=settings.match_weights,
        score=round(sum((factors[k] or 0) * w for k, w in settings.match_weights.items()), 4),
        data_coverage=sum(w for k, w in settings.match_weights.items() if factors[k] is not None),
        skill_analysis=analysis,
        recommendable=status == "ELIGIBLE" and is_open(opportunity),
        explanation="Eligibility is independent of ranking. Learning measures missing preferred skills, not proficiency.",
    )

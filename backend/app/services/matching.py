"""Deterministic ranking; unknown factors remain null and contribute zero."""

from app.utils.validators import normalized

from app.config import settings


def compare_skills(skills, requirements):
    actual = normalized(skills)
    required, preferred = (
        normalized(requirements.get("required_skills")),
        normalized(requirements.get("preferred_skills")),
    )
    return {
        "matched_required": sorted(actual & required),
        "missing_required": sorted(required - actual),
        "missing_preferred": sorted(preferred - actual),
        "score": 100 * len(actual & required) / len(required)
        if required and skills is not None
        else None,
    }


def match(profile, opportunity):
    requirements = opportunity.get("requirements", {})
    checks = []

    def check(field, needed, predicate):
        if needed is None or needed == []:
            return
        value = profile.get(field)
        passed = None if value is None else bool(predicate(value, needed))
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
    status = (
        "INELIGIBLE"
        if any(c["passed"] is False for c in checks)
        else "UNKNOWN"
        if not requirements.get("confirmed") or any(c["passed"] is None for c in checks)
        else "ELIGIBLE"
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
        checks=checks,
        factors=factors,
        weights=settings.match_weights,
        score=round(sum((factors[k] or 0) * w for k, w in settings.match_weights.items()), 4),
        data_coverage=sum(w for k, w in settings.match_weights.items() if factors[k] is not None),
        skill_analysis=analysis,
        recommendable=status == "ELIGIBLE",
        explanation="Eligibility is independent of ranking. Learning measures missing preferred skills, not proficiency.",
    )

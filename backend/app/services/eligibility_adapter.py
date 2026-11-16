"""Adapt confirmed catalog requirements to the original AVSAR rule engine.

The external engine's four statuses remain separate from persistent ranking statuses.
Only typed, stored requirements become rules; clients cannot submit executable custom rules.
"""

from app.services.eligibility_engine import Criterion, EligibilityEngine, Operator, Scheme
from app.schemas.eligibility import EligibilityEvaluationResponse
from app.utils.validators import normalized
from app.integrations.profile import eligibility_profile


def evaluate_opportunity(profile, opportunity):
    requirements = opportunity.get("requirements", {})
    criteria = []
    if requirements.get("confirmed"):
        for field, source in (
            ("graduation_year", "graduation_years"),
            ("degree", "degrees"),
            ("branch", "branches"),
            ("location", "locations"),
            ("gender", "genders"),
            ("category", "social_categories"),
            ("domicile_state", "domicile_states"),
        ):
            expected = requirements.get(source)
            if expected:
                criteria.append(
                    Criterion(field=field, operator=Operator.IN, value=list(normalized(expected)))
                )
        for field, source in (("cgpa", "min_cgpa"), ("experience_months", "min_experience_months")):
            expected = requirements.get(source)
            if expected is not None:
                criteria.append(
                    Criterion(field=field, operator=Operator.GREATER_THAN_OR_EQUAL, value=expected)
                )
        for field, source, operator in (
            ("age", "min_age", Operator.GREATER_THAN_OR_EQUAL),
            ("age", "max_age", Operator.LESS_THAN_OR_EQUAL),
            ("annual_income", "max_annual_income", Operator.LESS_THAN_OR_EQUAL),
            ("differently_abled", "required_disability_status", Operator.EQUALS),
        ):
            if requirements.get(source) is not None:
                criteria.append(
                    Criterion(field=field, operator=operator, value=requirements[source])
                )
        if requirements.get("required_skills"):
            criteria.append(
                Criterion(
                    field="skills",
                    operator=Operator.ALL_OF,
                    value=list(normalized(requirements["required_skills"])),
                )
            )
        if requirements.get("languages"):
            criteria.append(
                Criterion(
                    field="languages",
                    operator=Operator.ANY_OF,
                    value=list(normalized(requirements["languages"])),
                )
            )
    candidate = eligibility_profile(profile)
    for field in (
        "graduation_year",
        "degree",
        "branch",
        "location",
        "gender",
        "category",
        "domicile_state",
    ):
        if candidate.get(field) is not None:
            candidate[field] = str(candidate[field]).casefold()
    if candidate.get("skills") is not None:
        candidate["skills"] = list(normalized(candidate["skills"]))
    if candidate.get("languages") is not None:
        raw_langs = candidate["languages"]
        if isinstance(raw_langs, list):
            norm_langs = []
            for item in raw_langs:
                if isinstance(item, dict) and "language" in item:
                    norm_langs.append(str(item["language"]).casefold())
                elif isinstance(item, str):
                    norm_langs.append(item.casefold())
            candidate["languages"] = norm_langs
    result = EligibilityEngine().evaluate(
        candidate, Scheme(id=opportunity["id"], title=opportunity["title"], criteria=criteria)
    )
    payload = result.to_dict()
    if requirements.get("confirmed") and not criteria:
        payload.update(
            status="ELIGIBLE",
            api_status="ELIGIBLE",
            is_eligible=True,
            score=100.0,
            summary="Reviewer confirmed no eligibility restrictions",
            reasons=[],
            has_missing_opportunity_criteria=False,
        )
    elif not requirements.get("confirmed"):
        payload.update(
            status="CANNOT_DETERMINE",
            api_status="CANNOT_DETERMINE",
            is_eligible=False,
            score=0.0,
            summary="Eligibility criteria could not be confirmed by the source. Please review the original listing or provide requirement text for evaluation.",
            reasons=["Eligibility criteria have not been confirmed by the source."],
            has_missing_opportunity_criteria=True,
        )
    payload["source_summary"] = opportunity.get("source_summary")
    payload["requirements"] = requirements
    payload["evidence"] = requirements.get("evidence")
    return EligibilityEvaluationResponse.model_validate(payload).model_dump(mode="json")

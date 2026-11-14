"""Adapt confirmed catalog requirements to the original AVSAR rule engine.

The external engine's four statuses remain separate from persistent ranking statuses.
Only typed, stored requirements become rules; clients cannot submit executable custom rules.
"""

from app.services.eligibility_engine import Criterion, EligibilityEngine, Operator, Scheme
from app.schemas.eligibility import EligibilityEvaluationResponse
from app.utils.validators import normalized


def evaluate_opportunity(profile, opportunity):
    requirements = opportunity.get("requirements", {})
    criteria = []
    if requirements.get("confirmed"):
        for field, source in (
            ("graduation_year", "graduation_years"),
            ("degree", "degrees"),
            ("branch", "branches"),
            ("location", "locations"),
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
        if requirements.get("required_skills"):
            criteria.append(
                Criterion(
                    field="skills",
                    operator=Operator.ALL_OF,
                    value=list(normalized(requirements["required_skills"])),
                )
            )
    candidate = dict(profile)
    for field in ("graduation_year", "degree", "branch", "location"):
        if candidate.get(field) is not None:
            candidate[field] = str(candidate[field]).casefold()
    if candidate.get("skills") is not None:
        candidate["skills"] = list(normalized(candidate["skills"]))
    result = EligibilityEngine().evaluate(
        candidate, Scheme(id=opportunity["id"], title=opportunity["title"], criteria=criteria)
    )
    return EligibilityEvaluationResponse.model_validate(result.to_dict()).model_dump(mode="json")

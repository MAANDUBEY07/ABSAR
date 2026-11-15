"""Project explicit legacy education facts for backend matching without changing stored data."""

from pydantic import ValidationError
from app.schemas.profile import ProfileInput


def eligibility_profile(profile):
    candidate = dict(profile)
    education = profile.get("education")
    if isinstance(education, dict):
        aliases = {
            "degree": ("degree", "highest_degree"),
            "branch": ("branch", "stream"),
            "graduation_year": ("graduation_year", "passing_year"),
            "cgpa": ("cgpa",),
        }
        for field, sources in aliases.items():
            if candidate.get(field) is not None:
                continue
            for source in sources:
                value = education.get(source)
                if value is None:
                    continue
                try:
                    candidate[field] = getattr(ProfileInput.model_validate({field: value}), field)
                except ValidationError:
                    # A malformed nested value remains unknown; never turn it into a fact.
                    continue
                break
    # Preserve original engine age derivation when an older payload contains age=null.
    if candidate.get("age") is None:
        candidate.pop("age", None)
    return candidate

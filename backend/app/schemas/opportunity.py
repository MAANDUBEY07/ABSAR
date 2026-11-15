from datetime import date, datetime
from typing import Literal, get_args
from pydantic import Field, HttpUrl, JsonValue, field_validator, model_validator

from .base import Input


# Categories supplied by the project owner; existing API identifiers stay stable.
CanonicalOpportunityCategory = Literal[
    "scholarship",
    "internship",
    "job",
    "government_scheme",
    "fellowship",
    "apprenticeship",
    "hackathon",
    "coding_competition",
    "innovation_challenge",
    "startup_challenge",
    "grant",
]
CANONICAL_CATEGORIES = get_args(CanonicalOpportunityCategory)
LegacyOpportunityCategory = Literal[
    "scheme", "competition", "other", "coding_challenge", "research"
]
CATEGORY_LABELS = {
    "Scholarships": "scholarship",
    "Internships": "internship",
    "Jobs & more": "job",
    "Government schemes": "government_scheme",
    "Fellowships": "fellowship",
    "Apprenticeships": "apprenticeship",
    "Hackathons": "hackathon",
    "Coding challenges": "coding_competition",
    "Coding competitions": "coding_competition",
    "Innovation challenges": "innovation_challenge",
    "Research": "research",
    "Startup challenges": "startup_challenge",
    "Grants": "grant",
}


class Requirements(Input):
    confirmed: bool = False
    graduation_years: list[int] = Field(default_factory=list)
    degrees: list[str] = Field(default_factory=list)
    branches: list[str] = Field(default_factory=list)
    min_age: int | None = Field(None, ge=0, le=120)
    max_age: int | None = Field(None, ge=0, le=120)
    max_annual_income: float | None = Field(None, ge=0)
    genders: list[str] = Field(default_factory=list, max_length=20)
    social_categories: list[str] = Field(default_factory=list, max_length=50)
    domicile_states: list[str] = Field(default_factory=list, max_length=100)
    required_disability_status: bool | None = None
    min_cgpa: float | None = Field(None, ge=0, le=10)
    locations: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    min_experience_months: int | None = Field(None, ge=0)


class OpportunityInput(Input):
    title: str = Field(min_length=1, max_length=300)
    category: CanonicalOpportunityCategory | LegacyOpportunityCategory = "other"
    opportunity_mode: Literal["online", "offline", "hybrid"] | None = None
    category_metadata: dict[str, JsonValue] = Field(default_factory=dict, max_length=100)
    description: str = Field(default="", max_length=30000)
    organization: str | None = Field(None, max_length=300)
    application_url: HttpUrl | None = None
    company_url: HttpUrl | None = None
    source_url: HttpUrl | None = None
    source_attribution: str | None = Field(None, max_length=500)
    retrieved_at: datetime | None = None
    provenance: dict[str, JsonValue] = Field(default_factory=dict, max_length=100)
    deadline: date | None = None
    stipend: float | None = Field(None, ge=0)
    benefit: str | None = None
    duration_months: int | None = Field(None, ge=0, le=120)
    location: str | None = None
    remote: bool | None = None
    domain: str | None = None
    requirements: Requirements = Field(default_factory=Requirements)

    @field_validator("category", mode="before")
    @classmethod
    def accept_owner_supplied_labels(cls, value):
        if isinstance(value, str):
            labels = {label.casefold(): category for label, category in CATEGORY_LABELS.items()}
            value = labels.get(value.strip().casefold(), value)
            return {"coding_challenge": "coding_competition"}.get(value, value)
        return value

    @field_validator("deadline", mode="before")
    @classmethod
    def normalize_deadline(cls, value):
        from app.integrations.normalization import deadline

        return deadline(value)

    @model_validator(mode="after")
    def legacy_remote_mode(self):
        # False only means not fully remote; it does not distinguish hybrid from offline.
        if self.opportunity_mode is None and self.remote is True:
            self.opportunity_mode = "online"
        return self


class Feedback(Input):
    opportunity_id: str
    feedback: Literal["relevant", "not_relevant", "saved"]


class Discovery(Input):
    feed_url: HttpUrl

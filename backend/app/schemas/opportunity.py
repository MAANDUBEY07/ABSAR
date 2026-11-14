from datetime import date
from typing import Literal
from pydantic import Field, HttpUrl

from .base import Input


class Requirements(Input):
    confirmed: bool = False
    graduation_years: list[int] = Field(default_factory=list)
    degrees: list[str] = Field(default_factory=list)
    branches: list[str] = Field(default_factory=list)
    min_cgpa: float | None = Field(None, ge=0, le=10)
    locations: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    min_experience_months: int | None = Field(None, ge=0)


class OpportunityInput(Input):
    title: str = Field(min_length=1, max_length=300)
    category: Literal[
        "internship",
        "job",
        "scholarship",
        "government_scheme",
        "grant",
        "fellowship",
        "scheme",
        "competition",
        "hackathon",
        "other",
    ] = "other"
    description: str = Field(default="", max_length=30000)
    organization: str | None = Field(None, max_length=300)
    application_url: HttpUrl | None = None
    company_url: HttpUrl | None = None
    source_url: HttpUrl | None = None
    deadline: date | None = None
    stipend: float | None = Field(None, ge=0)
    benefit: str | None = None
    duration_months: int | None = Field(None, ge=0, le=120)
    location: str | None = None
    remote: bool | None = None
    domain: str | None = None
    requirements: Requirements = Field(default_factory=Requirements)


class Feedback(Input):
    opportunity_id: str
    feedback: Literal["relevant", "not_relevant", "saved"]


class Discovery(Input):
    feed_url: HttpUrl

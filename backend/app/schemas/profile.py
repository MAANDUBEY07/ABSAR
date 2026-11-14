from datetime import date
from pydantic import Field

from .base import Input


class StudentPreferences(Input):
    remote: bool | None = None
    domain: str | None = Field(None, max_length=200)
    min_stipend: float | None = Field(None, ge=0)
    max_duration_months: int | None = Field(None, ge=0, le=120)


class ProfileInput(Input):
    name: str | None = Field(None, max_length=200)
    date_of_birth: date | None = None
    degree: str | None = None
    branch: str | None = None
    cgpa: float | None = Field(None, ge=0, le=10)
    graduation_year: int | None = Field(None, ge=1950, le=2150)
    location: str | None = None
    experience_months: int | None = Field(None, ge=0, le=1200)
    experience: list[dict] = Field(default_factory=list, max_length=100)
    education: list[dict] = Field(default_factory=list, max_length=30)
    skills: list[str] | None = Field(None, max_length=200)
    preferences: StudentPreferences = Field(default_factory=StudentPreferences)


class ProfileResponse(ProfileInput):
    notification_email: str | None = None

from datetime import date
from pydantic import Field, model_validator

from .base import Input


class StudentPreferences(Input):
    remote: bool | None = None
    domain: str | None = Field(None, max_length=200)
    min_stipend: float | None = Field(None, ge=0)
    max_duration_months: int | None = Field(None, ge=0, le=120)


class ProfileInput(Input):
    name: str | None = Field(None, max_length=200)
    date_of_birth: date | None = None
    dob: date | None = None
    phone: str | None = Field(None, max_length=40)
    gender: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=100)
    domicile_state: str | None = Field(None, max_length=200)
    domicile_district: str | None = Field(None, max_length=200)
    annual_income: float | None = Field(None, ge=0)
    differently_abled: bool | None = None
    disability_percentage: float | None = Field(None, ge=0, le=100)
    degree: str | None = None
    branch: str | None = None
    cgpa: float | None = Field(None, ge=0, le=10)
    graduation_year: int | None = Field(None, ge=1950, le=2150)
    location: str | None = None
    experience_months: int | None = Field(None, ge=0, le=1200)
    experience: list[dict] = Field(default_factory=list, max_length=100)
    # The shared legacy contract uses one object; the persistent API also accepts a list.
    education: list[dict] | dict | None = Field(default_factory=list, max_length=30)
    skills: list[str] | None = Field(None, max_length=200)
    preferences: StudentPreferences = Field(default_factory=StudentPreferences)

    @model_validator(mode="after")
    def consistent_birth_date(self):
        if self.date_of_birth and self.dob and self.date_of_birth != self.dob:
            raise ValueError("dob and date_of_birth must identify the same date")
        birthday = self.date_of_birth or self.dob
        if birthday and birthday > date.today():
            raise ValueError("Date of birth cannot be in the future")
        self.date_of_birth = self.dob = birthday
        return self


class ProfileResponse(ProfileInput):
    id: str | None = None
    email: str | None = None
    notification_email: str | None = None

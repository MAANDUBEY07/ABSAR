from sqlalchemy import (
    String,
    UniqueConstraint,
)

from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Owned

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Document(Owned, Base):
    __tablename__ = "user_documents"
    content_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("owner_id", "content_hash"),)


class SkillClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill: str
    quote: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    source: Literal["RESUME_CLAIM"]


class ResumeAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: str
    document_id: str
    skills: list[str]
    evidence: list[SkillClaim]
    parsed_skills: list[str] | None = None
    experience_years: float | None = Field(None, ge=0)
    education: list[dict] | None = None
    readiness_score: float | None = Field(None, ge=0, le=100)
    recommendations: list[str] | None = None
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str

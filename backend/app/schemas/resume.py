from app.models.resume import ResumeAnalysis as ResumeAnalysisResponse
from .base import Input
from pydantic import Field


class Compare(Input):
    opportunity_id: str
    skills: list[str] | None = None


class ResumeMatchInput(Input):
    document_id: str = Field(min_length=1, max_length=64)


__all__ = ["Compare", "ResumeMatchInput", "ResumeAnalysisResponse"]

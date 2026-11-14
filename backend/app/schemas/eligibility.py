"""Persistent matching requests and the separate AVSAR eligibility contract."""

from typing import Literal
from pydantic import Field
from .base import Input


class MatchInput(Input):
    opportunity_id: str


class EligibilityBatch(Input):
    opportunity_ids: list[str] = Field(min_length=1, max_length=50)


class EligibilityEvaluationResponse(Input):
    scheme_id: str | None
    scheme_title: str | None
    status: str
    api_status: Literal["ELIGIBLE", "POTENTIALLY_ELIGIBLE", "NOT_ELIGIBLE", "CANNOT_DETERMINE"]
    is_eligible: bool
    score: float
    summary: str
    reasons: list[str]
    missing_fields: list[str]
    has_missing_student_info: bool
    has_missing_opportunity_criteria: bool
    passed_count: int
    failed_count: int
    missing_count: int
    passed_criteria: list[dict]
    failed_criteria: list[dict]
    missing_criteria: list[dict]

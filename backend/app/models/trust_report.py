"""Validated evidence reports; no verified-fraud or verified-employer claim."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class RiskEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signal: str
    points: int = Field(ge=0, le=100)
    quote: str


class TrustReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    risk_score: int = Field(ge=0, le=100)
    risk_level: Literal["HIGH", "REVIEW", "NO_SIGNALS_DETECTED"]
    verification_status: Literal["UNKNOWN", "EXPIRED"]
    evidence: list[RiskEvidence]
    source_assessment: dict | None = None
    disclaimer: str

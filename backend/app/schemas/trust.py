from app.models.trust_report import TrustReport as TrustReportResponse
from pydantic import Field

from .base import Input


class Report(Input):
    opportunity_id: str
    reason: str = Field(min_length=1, max_length=2000)


__all__ = ["Report", "TrustReportResponse"]

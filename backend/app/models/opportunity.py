from .base import record_type

from typing import Literal

from app.schemas.opportunity import OpportunityInput

Saved = record_type("Saved", "saved_opportunities")


class OpportunityDocument(OpportunityInput):
    id: str
    fingerprint: str
    verification_status: Literal["UNKNOWN", "EXPIRED"] = "UNKNOWN"

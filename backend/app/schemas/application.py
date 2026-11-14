from typing import Literal
from pydantic import Field

from .base import Input


class ApplicationCreate(Input):
    opportunity_id: str = Field(max_length=64)
    material: dict = Field(default_factory=dict)


class ApplicationPatch(Input):
    revision: int = Field(ge=1)
    status: (
        Literal[
            "DRAFT", "READY_FOR_REVIEW", "ASSESSMENT", "INTERVIEW", "OFFER", "REJECTED", "WITHDRAWN"
        ]
        | None
    ) = None
    material: dict | None = None


class Revision(Input):
    revision: int = Field(ge=1)


class Submit(Revision):
    confirmation: Literal[True]

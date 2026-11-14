from typing import Literal
from pydantic import Field, field_validator

from .base import Input


class GoalInput(Input):
    goal: str = Field(min_length=1, max_length=2000)


class Message(Input):
    text: str = Field(min_length=1, max_length=4000)


class MilestonePatch(Input):
    completed: bool


class AssessmentInput(Input):
    kind: Literal["aptitude", "interview", "coding"] = "aptitude"


class Answer(Input):
    assessment_id: str
    question_id: str
    answer: str = Field(max_length=10000)


class Code(Input):
    assessment_id: str
    question_id: str
    language: Literal["python", "javascript"]
    code: str = Field(min_length=1, max_length=20000)


class NotificationPrefs(Input):
    timezone: str = "UTC"
    quiet_start: int = Field(22, ge=0, le=23)
    quiet_end: int = Field(8, ge=0, le=23)
    channels: list[Literal["in_app", "email"]] = Field(default_factory=lambda: ["in_app"])

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("Unknown IANA timezone") from None
        return value

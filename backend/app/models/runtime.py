from datetime import datetime
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Owned, record_type


class Job(Owned, Base):
    __tablename__ = "jobs"
    dedupe_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("owner_id", "dedupe_key"),)


class Outbox(Owned, Base):
    __tablename__ = "integration_outbox"
    event_key: Mapped[str] = mapped_column(String(128), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)


class CareerGoal(Owned, Base):
    __tablename__ = "career_goals"
    revision: Mapped[int] = mapped_column(Integer, default=1)


class CareerMilestone(Owned, Base):
    __tablename__ = "career_milestones"
    goal_id: Mapped[str] = mapped_column(ForeignKey("career_goals.id"), index=True)


class Attempt(Owned, Base):
    __tablename__ = "assessment_attempts"
    assessment_id: Mapped[str] = mapped_column(String(64), ForeignKey("assessments.id"))
    question_id: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("assessment_id", "question_id"),)


class LocalDocument(Base):
    __tablename__ = "local_documents"
    collection: Mapped[str] = mapped_column(String(64), primary_key=True)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


Notification = record_type("Notification", "notifications")
NotificationPreference = record_type("NotificationPreference", "notification_preferences")
Assessment = record_type("Assessment", "assessments")

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Owned, record_type


class Application(Owned, Base):
    __tablename__ = "applications"
    opportunity_id: Mapped[str] = mapped_column(String(64), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="SAVED")
    __table_args__ = (
        CheckConstraint("revision >= 1"),
        UniqueConstraint("owner_id", "opportunity_id"),
    )


class ApplicationVersion(Owned, Base):
    __tablename__ = "application_versions"
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"))
    revision: Mapped[int] = mapped_column(Integer)
    digest: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        UniqueConstraint("application_id", "revision"),
        CheckConstraint("revision >= 1"),
    )


class Approval(Owned, Base):
    __tablename__ = "application_approvals"
    version_id: Mapped[str] = mapped_column(ForeignKey("application_versions.id"))
    __table_args__ = (UniqueConstraint("version_id"),)


Audit = record_type("Audit", "audit_events")

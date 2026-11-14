from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    JSON,
    DateTime,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Owned:
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


def record_type(name, table):
    return type(
        name,
        (Owned, Base),
        {
            "__tablename__": table,
            "__annotations__": {"kind_key": Mapped[str]},
            "kind_key": mapped_column(String(128), default=uid),
            "__table_args__": (UniqueConstraint("owner_id", "kind_key"),),
        },
    )

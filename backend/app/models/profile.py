from sqlalchemy import (
    UniqueConstraint,
)

from .base import Base, Owned, record_type


class Profile(Owned, Base):
    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("owner_id"),)


Skill = record_type("Skill", "student_skills")
Education = record_type("Education", "education")
Preference = record_type("Preference", "student_preferences")

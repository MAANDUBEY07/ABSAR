"""Compatibility exports; definitions live in the domain model modules."""

from .base import now as now
from .base import uid as uid
from .base import Base as Base
from .base import Owned as Owned
from .base import record_type as record_type
from .profile import Profile as Profile
from .profile import Skill as Skill
from .profile import Education as Education
from .profile import Preference as Preference
from .opportunity import Saved as Saved
from .resume import Document as Document
from .application import Application as Application
from .application import ApplicationVersion as ApplicationVersion
from .application import Approval as Approval
from .application import Audit as Audit
from .runtime import Job as Job
from .runtime import Outbox as Outbox
from .runtime import CareerGoal as CareerGoal
from .runtime import CareerMilestone as CareerMilestone
from .runtime import Attempt as Attempt
from .runtime import LocalDocument as LocalDocument
from .runtime import Notification as Notification
from .runtime import NotificationPreference as NotificationPreference
from .runtime import Assessment as Assessment

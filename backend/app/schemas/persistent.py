"""Compatibility exports for the domain request schemas."""

from .base import Input as Input
from .profile import StudentPreferences as StudentPreferences
from .profile import ProfileInput as ProfileInput
from .opportunity import Requirements as Requirements
from .opportunity import OpportunityInput as OpportunityInput
from .opportunity import Feedback as Feedback
from .opportunity import Discovery as Discovery
from .eligibility import MatchInput as MatchInput
from .resume import Compare as Compare
from .trust import Report as Report
from .application import ApplicationCreate as ApplicationCreate
from .application import ApplicationPatch as ApplicationPatch
from .application import Revision as Revision
from .application import Submit as Submit
from .runtime import GoalInput as GoalInput
from .runtime import Message as Message
from .runtime import MilestonePatch as MilestonePatch
from .runtime import AssessmentInput as AssessmentInput
from .runtime import Answer as Answer
from .runtime import Code as Code
from .runtime import NotificationPrefs as NotificationPrefs

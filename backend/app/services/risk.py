"""Compatibility module for deterministic risk rules."""

import sys
from app.services import trust_checker

sys.modules[__name__] = trust_checker

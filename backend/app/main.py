"""Compatibility import for the canonical backend/main.py application."""

import sys
import main as implementation

sys.modules[__name__] = implementation

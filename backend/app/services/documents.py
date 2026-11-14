"""Compatibility module for the bounded file-handling implementation."""

import sys
from app.utils import file_handler

sys.modules[__name__] = file_handler

"""
Remediation module for Audit Pit-Crew.

This module provides fix suggestions for security issues detected by
Slither, Mythril, and other security analysis tools.

The suggestions are framed as "Educational Snippets" to avoid liability
while still providing actionable guidance to developers.
"""

from src.core.remediation.patterns import (
    SLITHER_PATTERNS,
    MYTHRIL_PATTERNS,
    get_pattern_for_detector,
    get_pattern_for_swc,
)
from src.core.remediation.suggester import RemediationSuggester

__all__ = [
    "SLITHER_PATTERNS",
    "MYTHRIL_PATTERNS",
    "get_pattern_for_detector",
    "get_pattern_for_swc",
    "RemediationSuggester",
]

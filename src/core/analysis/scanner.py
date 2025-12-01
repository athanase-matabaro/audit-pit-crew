"""
Multi-tool scanner module providing unified interface for security analysis tools.

This module re-exports the scanner components for backward compatibility:
- BaseScanner: Abstract base class for all scanners
- SlitherScanner: Slither static analysis implementation
- MythrilScanner: Mythril bytecode analysis implementation
- OyenteScanner: Oyente bytecode analysis implementation
- AderynScanner: Aderyn comprehensive analysis implementation
- UnifiedScanner: Multi-tool orchestrator
- Exception classes: ToolExecutionError, SlitherExecutionError, MythrilExecutionError, OyenteExecutionError, AderynExecutionError
"""

from src.core.analysis.base_scanner import (
    BaseScanner,
    ToolExecutionError,
    SlitherExecutionError,
    MythrilExecutionError,
    OyenteExecutionError,
    AderynExecutionError,
)
from src.core.analysis.slither_scanner import SlitherScanner
from src.core.analysis.mythril_scanner import MythrilScanner
from src.core.analysis.oyente_scanner import OyenteScanner
from src.core.analysis.aderyn_scanner import AderynScanner
from src.core.analysis.unified_scanner import UnifiedScanner

__all__ = [
    "BaseScanner",
    "SlitherScanner",
    "MythrilScanner",
    "OyenteScanner",
    "AderynScanner",
    "UnifiedScanner",
    "ToolExecutionError",
    "SlitherExecutionError",
    "MythrilExecutionError",
    "OyenteExecutionError",
    "AderynExecutionError",
]

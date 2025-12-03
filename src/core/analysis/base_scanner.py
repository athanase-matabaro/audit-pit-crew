import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING, Tuple
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from src.core.config import AuditConfig

# Configure a logger for this module
logger = logging.getLogger(__name__)

# Custom exceptions for tool failures
class ToolExecutionError(Exception):
    """Base exception for tool execution failures."""
    pass

class SlitherExecutionError(ToolExecutionError):
    """Custom exception for Slither execution failures."""
    pass

class MythrilExecutionError(ToolExecutionError):
    """Custom exception for Mythril execution failures."""
    pass

class OyenteExecutionError(ToolExecutionError):
    """Custom exception for Oyente execution failures."""
    pass

class AderynExecutionError(ToolExecutionError):
    """Custom exception for Aderyn execution failures."""
    pass


class BaseScanner(ABC):
    """
    Abstract base class for security analysis tools.
    Provides common functionality like severity mapping and issue fingerprinting.
    """

    # Severity level mapping (numeric for comparison)
    SEVERITY_MAP = {'informational': 1, 'low': 2, 'medium': 3, 'high': 4}

    @abstractmethod
    def run(self, target_path: str, files: Optional[List[str]] = None, config: Optional['AuditConfig'] = None) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
        """
        Run the scanner on the target path and return a list of issues.
        
        Args:
            target_path: Path to the repository root
            files: Optional list of specific files to scan
            config: Optional ScanConfig object containing filtering rules
            
        Returns:
            A tuple containing:
                - List of issue dictionaries with standard format
                - Dictionary of log file paths for each tool
        """
        pass


    @staticmethod
    def get_issue_fingerprint(issue: Dict[str, Any]) -> str:
        """
        Creates a unique, stable identifier for a given issue based on its
        type, file path, line number, and tool name.
        """
        issue_type = issue.get('type', 'unknown-type')
        file_path = issue.get('file', 'unknown-file')
        line = issue.get('line', 0)
        tool = issue.get('tool', 'unknown-tool')
        return f"{tool}|{issue_type}|{file_path}|{line}"

    @staticmethod
    def diff_issues(current_issues: List[Dict[str, Any]], baseline_issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Compares current issues against a baseline and returns only the new issues.
        """
        baseline_fingerprints = {BaseScanner.get_issue_fingerprint(issue) for issue in baseline_issues}
        new_issues = [
            issue for issue in current_issues 
            if BaseScanner.get_issue_fingerprint(issue) not in baseline_fingerprints
        ]
        return new_issues

    def _filter_by_severity(self, issues: List[Dict[str, Any]], min_severity: str) -> List[Dict[str, Any]]:
        """
        Filter issues to only include those meeting or exceeding the minimum severity threshold.
        
        Args:
            issues: List of issue dictionaries
            min_severity: Minimum severity level (Low, Medium, High, Critical)
            
        Returns:
            Filtered list of issues
        """
        min_severity_level = self.SEVERITY_MAP.get(min_severity.lower(), 2)
        filtered_issues = []

        for issue in issues:
            severity = issue.get('severity', 'Informational')
            severity_level = self.SEVERITY_MAP.get(severity.lower(), 1)

            # Skip issues below the minimum severity threshold
            if severity_level < min_severity_level:
                logger.debug(f"Filtering out {severity} issue: {issue.get('type', 'Unknown')}")
                continue

            filtered_issues.append(issue)

        return filtered_issues

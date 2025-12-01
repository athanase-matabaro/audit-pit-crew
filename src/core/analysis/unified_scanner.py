import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from src.core.analysis.base_scanner import BaseScanner, SlitherExecutionError, MythrilExecutionError
from src.core.analysis.slither_scanner import SlitherScanner
from src.core.analysis.mythril_scanner import MythrilScanner

if TYPE_CHECKING:
    from src.core.config import AuditConfig

# Configure a logger for this module
logger = logging.getLogger(__name__)


class UnifiedScanner:
    """
    Aggregates findings from multiple security analysis tools (Slither, Mythril)
    into a single, deduplicated list of issues.
    """

    def __init__(self):
        """Initialize the unified scanner with all available tool scanners."""
        self.scanners = [
            SlitherScanner(),
            MythrilScanner(),
        ]
        logger.info(f"📊 UnifiedScanner initialized with {len(self.scanners)} tool(s).")

    def run(self, target_path: str, files: Optional[List[str]] = None, config: Optional['AuditConfig'] = None) -> List[Dict[str, Any]]:
        """
        Runs all scanners and aggregates their results into a deduplicated list.

        Args:
            target_path: Path to the repository root
            files: Optional list of specific files to scan
            config: Optional ScanConfig object containing filtering rules

        Returns:
            Deduplicated list of issues from all tools
        """
        logger.info(f"🔄 UnifiedScanner: Starting multi-tool analysis on {target_path}")

        all_issues: List[Dict[str, Any]] = []
        seen_fingerprints: set = set()

        for scanner in self.scanners:
            try:
                logger.info(f"📌 Running {scanner.TOOL_NAME}...")
                issues = scanner.run(target_path, files=files, config=config)
                logger.info(f"✅ {scanner.TOOL_NAME} completed: {len(issues)} issue(s) found.")

                # Deduplicate based on fingerprint
                for issue in issues:
                    fingerprint = BaseScanner.get_issue_fingerprint(issue)
                    if fingerprint not in seen_fingerprints:
                        seen_fingerprints.add(fingerprint)
                        all_issues.append(issue)
                    else:
                        logger.debug(f"UnifiedScanner: Deduplicating issue with fingerprint: {fingerprint}")

            except (SlitherExecutionError, MythrilExecutionError) as e:
                logger.error(f"⚠️ {scanner.TOOL_NAME} scan failed: {e}")
                # Continue with other scanners
            except Exception as e:
                logger.error(f"❌ Unexpected error during {scanner.TOOL_NAME} scan: {e}", exc_info=True)
                # Continue with other scanners

        logger.info(f"🎯 UnifiedScanner: Completed. Found {len(all_issues)} total unique issues across all tools.")
        return all_issues

import logging
import time
from typing import List, Dict, Any, Optional, TYPE_CHECKING, Tuple

from src.core.analysis.base_scanner import (
    BaseScanner, SlitherExecutionError, MythrilExecutionError,
    OyenteExecutionError, AderynExecutionError
)
from src.core.analysis.slither_scanner import SlitherScanner
from src.core.analysis.mythril_scanner import MythrilScanner
from src.core.analysis.oyente_scanner import OyenteScanner
from src.core.analysis.aderyn_scanner import AderynScanner

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
            OyenteScanner(),
            AderynScanner(),
        ]
        logger.info(f"📊 UnifiedScanner initialized with {len(self.scanners)} tool(s).")

    def run(self, target_path: str, files: Optional[List[str]] = None, config: Optional['AuditConfig'] = None) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
        """
        Runs all scanners and aggregates their results into a deduplicated list.

        Args:
            target_path: Path to the repository root
            files: Optional list of specific files to scan
            config: Optional ScanConfig object containing filtering rules

        Returns:
            A tuple containing:
                - Deduplicated list of issues from all tools
                - Dictionary of log file paths for each tool
        """
        logger.info(f"🔄 UnifiedScanner: Starting multi-tool analysis on {target_path}")

        all_issues: List[Dict[str, Any]] = []
        all_log_paths: Dict[str, List[str]] = {}
        seen_fingerprints: set = set()
        tool_timings: Dict[str, float] = {}

        for scanner in self.scanners:
            try:
                logger.info(f"📌 Running {scanner.TOOL_NAME}...")
                start_time = time.time()
                result = scanner.run(target_path, files=files, config=config)
                elapsed_time = time.time() - start_time
                tool_timings[scanner.TOOL_NAME] = elapsed_time
                
                if isinstance(result, tuple):
                    issues = result[0]
                    log_paths = result[1]
                else:
                    issues = result
                    log_paths = {}
                logger.info(f"✅ {scanner.TOOL_NAME} completed in {elapsed_time:.2f}s: {len(issues)} issue(s) found.")

                all_log_paths.update(log_paths)

                # Deduplicate based on fingerprint
                for issue in issues:
                    fingerprint = BaseScanner.get_issue_fingerprint(issue)
                    if fingerprint not in seen_fingerprints:
                        seen_fingerprints.add(fingerprint)
                        all_issues.append(issue)
                    else:
                        logger.debug(f"UnifiedScanner: Deduplicating issue with fingerprint: {fingerprint}")

            except (SlitherExecutionError, MythrilExecutionError, OyenteExecutionError, AderynExecutionError) as e:
                logger.error(f"⚠️ {scanner.TOOL_NAME} scan failed: {e}")
                # Continue with other scanners
            except Exception as e:
                logger.error(f"❌ Unexpected error during {scanner.TOOL_NAME} scan: {e}", exc_info=True)
                # Continue with other scanners

        # Log timing summary
        total_time = sum(tool_timings.values())
        logger.info(f"⏱️ Tool execution times: {', '.join([f'{k}: {v:.2f}s' for k, v in tool_timings.items()])}")
        logger.info(f"🎯 UnifiedScanner: Completed in {total_time:.2f}s total. Found {len(all_issues)} total unique issues across all tools.")
        return all_issues, all_log_paths


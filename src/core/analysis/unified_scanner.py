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
    Aggregates findings from multiple security analysis tools (Slither, Mythril, Oyente, Aderyn)
    into a single, deduplicated list of issues.
    """

    # All available scanners - will be filtered by config.enabled_tools at runtime
    ALL_SCANNERS = {
        'slither': SlitherScanner,
        'mythril': MythrilScanner,
        'oyente': OyenteScanner,
        'aderyn': AderynScanner,
    }

    def __init__(self):
        """Initialize the unified scanner with all available tool scanners."""
        # Scanners are initialized lazily in run() based on enabled_tools config
        self.scanners = []

    def _get_enabled_scanners(self, config = None) -> List[BaseScanner]:
        """
        Returns list of scanner instances based on enabled_tools configuration.
        
        Args:
            config: Optional ScanConfig (or AuditConfig) with enabled_tools setting
            
        Returns:
            List of enabled scanner instances
        """
        # Default enabled tools if no config provided (excludes Oyente - unmaintained)
        default_enabled = ['slither', 'mythril', 'aderyn']
        
        # Handle both ScanConfig (direct) and AuditConfig (nested) objects
        # tasks.py passes audit_config.scan which is a ScanConfig object
        if config and hasattr(config, 'enabled_tools'):
            # config is ScanConfig - access enabled_tools directly
            enabled_tools = config.enabled_tools
        elif config and hasattr(config, 'scan') and hasattr(config.scan, 'enabled_tools'):
            # config is AuditConfig - access via .scan
            enabled_tools = config.scan.enabled_tools
        else:
            enabled_tools = default_enabled
        
        scanners = []
        for tool_name in enabled_tools:
            tool_lower = tool_name.lower()
            if tool_lower in self.ALL_SCANNERS:
                scanners.append(self.ALL_SCANNERS[tool_lower]())
            else:
                logger.warning(f"⚠️ Unknown tool '{tool_name}' in enabled_tools config. Skipping.")
        
        return scanners

    def run(self, target_path: str, files: Optional[List[str]] = None, config = None) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
        """
        Runs all enabled scanners and aggregates their results into a deduplicated list.

        Args:
            target_path: Path to the repository root
            files: Optional list of specific files to scan
            config: Optional ScanConfig or AuditConfig object containing filtering rules

        Returns:
            A tuple containing:
                - Deduplicated list of issues from all tools
                - Dictionary of log file paths for each tool
        """
        # Get enabled scanners based on config
        self.scanners = self._get_enabled_scanners(config)
        logger.info(f"📊 UnifiedScanner initialized with {len(self.scanners)} tool(s): {[s.TOOL_NAME for s in self.scanners]}")
        logger.info(f"🔄 UnifiedScanner: Starting multi-tool analysis on {target_path}")

        all_issues: List[Dict[str, Any]] = []
        all_log_paths: Dict[str, List[str]] = {}
        seen_fingerprints: set = set()
        tool_timings: Dict[str, float] = {}
        tool_status: Dict[str, str] = {}  # Track success/failure status

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
                tool_status[scanner.TOOL_NAME] = f"✅ {len(issues)} issues"

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
                tool_status[scanner.TOOL_NAME] = "❌ Failed"
                # Continue with other scanners
            except Exception as e:
                logger.error(f"❌ Unexpected error during {scanner.TOOL_NAME} scan: {e}", exc_info=True)
                tool_status[scanner.TOOL_NAME] = "❌ Error"
                # Continue with other scanners

        # Log timing summary
        total_time = sum(tool_timings.values())
        timing_str = ', '.join([f'{k}: {v:.2f}s' for k, v in tool_timings.items()]) if tool_timings else "No tools completed"
        logger.info(f"⏱️ Tool execution times: {timing_str}")
        
        # Log tool status summary
        status_str = ', '.join([f'{k}: {v}' for k, v in tool_status.items()])
        logger.info(f"📋 Tool status summary: {status_str}")
        
        logger.info(f"🎯 UnifiedScanner: Completed in {total_time:.2f}s total. Found {len(all_issues)} total unique issues across all tools.")
        return all_issues, all_log_paths


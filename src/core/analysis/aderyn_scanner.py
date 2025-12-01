import subprocess
import json
import os
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from src.core.analysis.base_scanner import BaseScanner, AderynExecutionError

if TYPE_CHECKING:
    from src.core.config import AuditConfig

# Configure a logger for this module
logger = logging.getLogger(__name__)


class AderynScanner(BaseScanner):
    """
    Wraps the Aderyn CLI tool to scan Solidity contracts for security vulnerabilities.
    Aderyn performs directory-level analysis and outputs a comprehensive JSON report.
    """

    TOOL_NAME = "Aderyn"

    # Severity mapping from Aderyn's native severity levels to standard system levels
    SEVERITY_MAP = {
        'critical': 'Critical',
        'high': 'High',
        'medium': 'Medium',
        'low': 'Low',
        'info': 'Low',
        'informational': 'Low',
    }

    def _execute_aderyn(self, target_path: str) -> Dict[str, Any]:
        """
        Executes the Aderyn CLI tool against the entire target directory.
        Returns the JSON output from Aderyn.

        Args:
            target_path: Path to the repository root to scan

        Returns:
            Dictionary containing Aderyn's JSON output

        Raises:
            AderynExecutionError: If the command fails or returns invalid output
        """
        # Create a temporary output file path
        output_filepath = os.path.join(target_path, "aderyn_report.json")

        # Construct the command
        cmd = ["aderyn", target_path, "-o", "json"]

        logger.info(f"Executing Aderyn command: {' '.join(cmd)}")
        logger.info(f"Working directory (cwd): {target_path}")

        try:
            result = subprocess.run(
                cmd,
                cwd=target_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=600  # Aderyn can take longer
            )

            # Try to parse JSON from stdout
            if result.stdout.strip():
                try:
                    json_output = json.loads(result.stdout)
                    logger.info("✅ Aderyn analysis finished. JSON output received.")
                    return json_output
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ Aderyn stdout is not valid JSON: {e}")
                    logger.debug(f"Aderyn stdout: {result.stdout[:500]}")

            # If no JSON output, check if file was created
            if os.path.exists(output_filepath):
                try:
                    with open(output_filepath, 'r') as f:
                        json_output = json.load(f)
                    logger.info("✅ Aderyn analysis finished. JSON output read from file.")
                    return json_output
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ Aderyn output file is not valid JSON: {e}")

            # If no JSON output, return empty results
            if result.returncode != 0:
                logger.warning(f"⚠️ Aderyn exited with code {result.returncode}")
                if result.stderr:
                    logger.debug(f"Aderyn stderr: {result.stderr}")

            logger.info("Aderyn analysis completed with no JSON output (likely no issues found).")
            return {"issues": []}

        except subprocess.TimeoutExpired:
            logger.error("❌ Aderyn execution timed out.")
            raise AderynExecutionError("Aderyn Scan Failed. Execution timed out after 600 seconds.")
        except FileNotFoundError:
            logger.error("❌ Aderyn CLI not found. Is it installed?")
            raise AderynExecutionError("Aderyn Scan Failed. Aderyn CLI not found.")
        except Exception as e:
            logger.error(f"❌ Aderyn execution failed: {e}")
            raise AderynExecutionError(f"Aderyn Scan Failed. Details: {str(e)}")

    def run(self, target_path: str, files: Optional[List[str]] = None, config: Optional['AuditConfig'] = None) -> List[Dict[str, Any]]:
        """
        Runs Aderyn on the target directory.

        Args:
            target_path: Path to the repository root
            files: Optional list of specific files (ignored - Aderyn scans the entire directory)
            config: Optional AuditConfig object containing filtering rules (min_severity)

        Returns:
            List of standardized issue dictionaries
        """
        logger.info("🔍 Starting Aderyn scan on: {}".format(target_path))

        if files:
            logger.info(f"📌 Note: Aderyn scans entire directory. Individual file filtering is not applied.")

        try:
            json_output = self._execute_aderyn(target_path)

            all_issues: List[Dict[str, Any]] = []

            # Parse Aderyn output and convert to standard format
            # Aderyn returns issues in a top-level "issues" array
            issues = json_output.get("issues", [])

            for raw_issue in issues:
                # Extract file path and make it relative to target_path
                file_path = raw_issue.get('file', '')

                # Ensure file path is relative to target_path
                if os.path.isabs(file_path):
                    file_path = os.path.relpath(file_path, target_path)

                # Convert Aderyn's format to standard issue dictionary
                issue = {
                    'type': raw_issue.get('title', raw_issue.get('name', 'Unknown')),
                    'severity': self.SEVERITY_MAP.get(
                        raw_issue.get('severity', 'low').lower(),
                        'Low'
                    ),
                    'confidence': raw_issue.get('confidence', 'Unknown'),
                    'description': raw_issue.get('description', ''),
                    'file': file_path,
                    'line': raw_issue.get('line', 0),
                    'tool': self.TOOL_NAME,
                    'raw_data': raw_issue,
                }
                all_issues.append(issue)

        except AderynExecutionError as e:
            logger.error(f"⚠️ Aderyn scan failed: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error during Aderyn scan: {e}", exc_info=True)
            return []

        # Apply severity filtering
        min_severity = 'Low'
        if config and hasattr(config, 'scan') and hasattr(config.scan, 'min_severity'):
            min_severity = config.scan.min_severity

        logger.info(f"🎯 Aderyn: Filtering issues with minimum severity: {min_severity}")
        filtered_issues = self._filter_by_severity(all_issues, min_severity)
        logger.info(f"Aderyn found {len(filtered_issues)} total issues meeting the severity threshold (Min: {min_severity}).")

        return filtered_issues

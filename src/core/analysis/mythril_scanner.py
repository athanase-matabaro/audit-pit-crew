import subprocess
import json
import os
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from src.core.analysis.base_scanner import BaseScanner, MythrilExecutionError

if TYPE_CHECKING:
    from src.core.config import AuditConfig

# Configure a logger for this module
logger = logging.getLogger(__name__)


class MythrilScanner(BaseScanner):
    """
    Wraps the Mythril CLI tool for EVM bytecode analysis.
    """

    TOOL_NAME = "Mythril"

    def _execute_mythril(self, target_path: str, relative_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Executes the mythril command and returns the JSON output.
        Raises MythrilExecutionError on failure.
        """
        output_filename = "mythril_report.json"
        output_filepath = os.path.join(target_path, output_filename)

        # --- Command Construction ---
        cmd = ["myth", "analyze"]

        # For files, analyze each file individually
        if relative_files:
            logger.info(f"⚡ Mythril: Running partial scan on: {relative_files}")
            # Mythril needs full file paths
            cmd.extend(relative_files)
        else:
            logger.info("⚙️ Mythril: Running full scan on repository root.")
            cmd.append(".")

        # Append common flags (--max-depth 0 for performance)
        cmd.extend(["--max-depth", "0", "--json"])

        logger.info(f"Executing Mythril command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=target_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=300
            )

            # Try to parse JSON output from stdout
            json_output = None
            try:
                json_output = json.loads(result.stdout)
            except json.JSONDecodeError:
                pass

            # If no valid JSON, try to read from output file
            if not json_output and os.path.exists(output_filepath):
                try:
                    with open(output_filepath, 'r') as f:
                        json_output = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    pass

            if not json_output:
                # Mythril might not find issues, which is okay
                logger.info("Mythril analysis completed with no JSON output (likely no issues found).")
                return {"issues": []}

            logger.info(f"Mythril analysis finished (Exit Code: {result.returncode}). Issues found.")
            return json_output

        except subprocess.TimeoutExpired:
            logger.error("❌ Mythril execution timed out.")
            raise MythrilExecutionError("Mythril Scan Failed. Execution timed out after 300 seconds.")
        except FileNotFoundError:
            logger.error("❌ Mythril CLI not found. Is it installed?")
            raise MythrilExecutionError("Mythril Scan Failed. Mythril CLI not found.")
        except Exception as e:
            logger.error(f"❌ Mythril execution failed: {e}")
            raise MythrilExecutionError(f"Mythril Scan Failed. Details: {str(e)}")

    def run(self, target_path: str, files: Optional[List[str]] = None, config: Optional['AuditConfig'] = None) -> List[Dict[str, Any]]:
        """
        Runs Mythril on the target_path.

        Args:
            target_path: Path to the repository root
            files: Optional list of specific files to scan
            config: Optional ScanConfig object containing filtering rules (min_severity)

        Returns:
            List of cleaned issue dictionaries, filtered by severity
        """
        logger.info(f"🔍 Starting Mythril scan on: {target_path}")

        relative_files = None
        if files:
            relative_files = [os.path.relpath(f, target_path) for f in files]

        try:
            raw_output = self._execute_mythril(target_path, relative_files=relative_files)
        except MythrilExecutionError:
            # Return empty list if Mythril fails (it's not critical)
            logger.warning("⚠️ Mythril scan failed, continuing without Mythril results.")
            return []

        # Extract min_severity from config, default to 'Low'
        min_severity = config.get_min_severity() if config else 'Low'
        logger.info(f"🎯 Mythril: Filtering issues with minimum severity: {min_severity}")

        clean_issues: List[Dict[str, Any]] = []

        # Handle different Mythril output formats
        issues_list = raw_output.get("issues", [])
        if not issues_list and isinstance(raw_output, dict):
            # Try alternative format
            issues_list = []

        for issue in issues_list:
            # Map Mythril severity to our standard format
            mythril_severity = issue.get('severity', 'Informational')
            if mythril_severity == 'High':
                severity = 'High'
            elif mythril_severity == 'Medium':
                severity = 'Medium'
            elif mythril_severity == 'Low':
                severity = 'Low'
            else:
                severity = 'Informational'

            severity_level = self.SEVERITY_MAP.get(severity.lower(), 1)

            # Skip issues below the minimum severity threshold
            if severity_level < self.SEVERITY_MAP.get(min_severity.lower(), 2):
                logger.debug(f"Mythril: Filtering out {severity} issue: {issue.get('title', 'Unknown')}")
                continue

            # Extract file and line information
            file_path = 'Unknown'
            line_number = 0
            if 'locations' in issue and issue['locations']:
                location = issue['locations'][0]
                if isinstance(location, dict):
                    file_path = location.get('sourceMap', 'Unknown')
                    line_number = location.get('line', 0)

            clean_issues.append({
                "tool": self.TOOL_NAME,
                "type": issue.get('title', 'Unknown'),
                "severity": severity,
                "confidence": issue.get('confidence', 'Low').capitalize(),
                "description": issue.get('description', 'No description'),
                "file": file_path,
                "line": int(line_number) if line_number else 0,
                "raw_data": issue
            })

        logger.info(f"Mythril found {len(clean_issues)} total issues meeting the severity threshold (Min: {min_severity}).")
        return clean_issues

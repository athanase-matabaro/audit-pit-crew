import subprocess
import json
import os
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from src.core.analysis.base_scanner import BaseScanner, OyenteExecutionError

if TYPE_CHECKING:
    from src.core.config import AuditConfig

# Configure a logger for this module
logger = logging.getLogger(__name__)


class OyenteScanner(BaseScanner):
    """
    Wraps the Oyente CLI tool to scan Solidity files for security vulnerabilities.
    Oyente performs bytecode-level analysis on compiled smart contracts.
    """

    TOOL_NAME = "Oyente"

    # Severity mapping from Oyente's native severity levels to standard system levels
    SEVERITY_MAP = {
        'critical': 'Critical',
        'high': 'High',
        'medium': 'Medium',
        'warning': 'Medium',
        'low': 'Low',
        'informational': 'Low',
        'info': 'Low',
        'note': 'Low',
    }

    def _execute_oyente(self, target_path: str, file_path: str) -> Dict[str, Any]:
        """
        Executes the Oyente CLI tool against a single Solidity file.
        Returns the JSON output from Oyente.

        Args:
            target_path: Path to the repository root (working directory)
            file_path: Relative path to the Solidity file to scan

        Returns:
            Dictionary containing Oyente's JSON output

        Raises:
            OyenteExecutionError: If the command fails or returns invalid output
        """
        # Construct the command
        cmd = ["oyente", "-s", file_path, "-j"]

        logger.info(f"Executing Oyente command: {' '.join(cmd)}")
        logger.info(f"Working directory (cwd): {target_path}")

        try:
            result = subprocess.run(
                cmd,
                cwd=target_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=300
            )

            # Try to parse JSON from stdout
            if result.stdout.strip():
                try:
                    json_output = json.loads(result.stdout)
                    return json_output
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ Oyente output is not valid JSON: {e}")
                    logger.debug(f"Oyente stdout: {result.stdout}")

            # If no JSON output, return empty results
            if result.returncode != 0:
                logger.warning(f"⚠️ Oyente exited with code {result.returncode}")
                if result.stderr:
                    logger.debug(f"Oyente stderr: {result.stderr}")

            return {"issues": []}

        except subprocess.TimeoutExpired:
            logger.error("❌ Oyente execution timed out.")
            raise OyenteExecutionError("Oyente Scan Failed. Execution timed out after 300 seconds.")
        except FileNotFoundError:
            logger.error("❌ Oyente CLI not found. Is it installed?")
            raise OyenteExecutionError("Oyente Scan Failed. Oyente CLI not found.")
        except Exception as e:
            logger.error(f"❌ Oyente execution failed: {e}")
            raise OyenteExecutionError(f"Oyente Scan Failed. Details: {str(e)}")

    def run(self, target_path: str, files: Optional[List[str]] = None, config: Optional['AuditConfig'] = None) -> List[Dict[str, Any]]:
        """
        Runs Oyente on the specified files.

        Args:
            target_path: Path to the repository root
            files: Optional list of specific Solidity files to scan (relative to target_path)
            config: Optional AuditConfig object containing filtering rules (min_severity)

        Returns:
            List of standardized issue dictionaries
        """
        logger.info("🔍 Starting Oyente scan on: {}".format(target_path))

        # Determine which files to scan
        if not files:
            logger.info("⚙️ Oyente: Running full scan on repository root.")
            # For full scan, find all .sol files
            sol_files = []
            for root, dirs, filenames in os.walk(target_path):
                # Skip node_modules and hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
                for filename in filenames:
                    if filename.endswith('.sol'):
                        rel_path = os.path.relpath(os.path.join(root, filename), target_path)
                        sol_files.append(rel_path)
            files = sol_files if sol_files else None

        if not files:
            logger.warning("⚠️ No Solidity files found for Oyente scan.")
            return []

        logger.info(f"⚡ Oyente: Running partial scan on: {files}")

        all_issues: List[Dict[str, Any]] = []

        # Scan each file
        for file_path in files:
            # Verify file exists
            full_path = os.path.join(target_path, file_path)
            if not os.path.isfile(full_path):
                logger.warning(f"⚠️ File not found (will skip): {full_path}")
                continue

            try:
                logger.info(f"📄 Scanning file with Oyente: {file_path}")
                json_output = self._execute_oyente(target_path, file_path)

                # Parse Oyente output and convert to standard format
                issues = json_output.get("issues", [])

                for raw_issue in issues:
                    # Convert Oyente's format to standard issue dictionary
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

            except OyenteExecutionError as e:
                logger.error(f"⚠️ Oyente failed on file {file_path}: {e}")
                # Continue with next file
                continue
            except Exception as e:
                logger.error(f"❌ Unexpected error processing Oyente output for {file_path}: {e}", exc_info=True)
                continue

        # Apply severity filtering
        min_severity = 'Low'
        if config and hasattr(config, 'scan') and hasattr(config.scan, 'min_severity'):
            min_severity = config.scan.min_severity

        logger.info(f"🎯 Oyente: Filtering issues with minimum severity: {min_severity}")
        filtered_issues = self._filter_by_severity(all_issues, min_severity)
        logger.info(f"Oyente found {len(filtered_issues)} total issues meeting the severity threshold (Min: {min_severity}).")

        return filtered_issues

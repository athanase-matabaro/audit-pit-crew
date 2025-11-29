import subprocess
import json
import os
import logging
import shutil
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.config import AuditConfig

# Configure a logger for this module
logger = logging.getLogger(__name__)

# Custom exception for Slither failures
class SlitherExecutionError(Exception):
    """Custom exception for Slither execution failures."""
    pass

class SlitherScanner:
    """
    Wraps the Slither CLI tool to scan local directories.
    """

    def _execute_slither(self, target_path: str, relative_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Executes the slither command and returns the JSON output.
        Raises SlitherExecutionError on failure.
        """
        # --- Set solc version ---
        try:
            solc_version_to_use = "0.8.20"
            logger.info(f"🐍 Attempting to set solc version using 'solc-select use {solc_version_to_use}'...")
            subprocess.run(
                ["solc-select", "use", solc_version_to_use],
                capture_output=True, text=True, check=True, timeout=60,
                cwd=target_path
            )
            logger.info(f"✅ Successfully set solc version to {solc_version_to_use}.")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"⚠️ Could not set solc version via solc-select: {e}")

        output_filename = "slither_report.json"
        output_filepath = os.path.join(target_path, output_filename)

        # --- Command Construction ---
        cmd = ["slither"]
        if relative_files:
            logger.info(f"⚡ Running partial scan on: {relative_files}")
            cmd.extend(relative_files)
        else:
            logger.info("⚙️ Running full scan on repository root.")
            cmd.append(".")

        # Append common flags
        cmd.extend(["--exclude", "**/*.pem", "--json", output_filepath])
        
        logger.info(f"Executing Slither command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            cwd=target_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=300
        )

        # --- Error Handling based on output file ---
        try:
            with open(output_filepath, 'r') as f:
                json_output = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            stdout = result.stdout.strip() if result.stdout else ""
            stderr = result.stderr.strip() if result.stderr else ""
            
            logger.error(f"❌ Slither execution failed to produce a valid report file (Exit Code {result.returncode}). Exception: {e}")
            if stdout:
                logger.error(f"Slither STDOUT: {stdout}")
            if stderr:
                logger.error(f"Slither STDERR: {stderr}")
            
            error_message = stderr or stdout or f"Slither failed with exit code {result.returncode} and did not produce a valid report file."
            raise SlitherExecutionError(f"Slither Scan Failed. Details: {error_message}")

        logger.info(f"Slither analysis finished (Exit Code: {result.returncode}). Report read from {output_filepath}")
        return json_output


    def run(self, target_path: str, files: Optional[List[str]] = None, config: Optional['AuditConfig'] = None) -> List[Dict[str, Any]]:
        """
        Runs Slither on the target_path. For differential scans, it scans only the changed files.
        """
        logger.info(f"🔍 Starting Slither scan on: {target_path}")
        
        relative_files = None
        if files:
            relative_files = [os.path.relpath(f, target_path) for f in files]
        
        raw_output = self._execute_slither(target_path, relative_files=relative_files)
        
        min_severity = config.get_min_severity() if config else 'Low'
        
        clean_issues: List[Dict[str, Any]] = []

        if not raw_output.get("success") or "results" not in raw_output or "detectors" not in raw_output["results"]:
            logger.warning(f"Slither output is empty or indicates failure. Raw: {str(raw_output)[:500]}")
            return []

        severity_map = {'high': 4, 'medium': 3, 'low': 2, 'informational': 1}
        min_severity_level = severity_map.get(min_severity.lower(), 1)

        for issue in raw_output["results"]["detectors"]:
            severity = issue.get('impact', 'Informational').capitalize()
            
            if severity_map.get(severity.lower(), 0) < min_severity_level:
                continue
            
            primary_element = issue.get('elements', [{}])[0]
            file_path = primary_element.get('source_mapping', {}).get('filename_relative', 'Unknown')
            line_number = primary_element.get('source_mapping', {}).get('lines', [0])[0]

            clean_issues.append({
                "type": issue.get('check', 'Unknown'),
                "severity": severity,
                "confidence": issue.get('confidence', 'Low').capitalize(),
                "description": issue.get('description', 'No description'),
                "file": file_path,
                "line": int(line_number) if line_number else 0,
                "raw_data": issue
            })

        logger.info(f"Slither found {len(clean_issues)} total issues meeting the severity threshold (Min: {min_severity}).")
        return clean_issues

    @staticmethod
    def get_issue_fingerprint(issue: Dict[str, Any]) -> str:
        """
        Creates a unique, stable identifier for a given issue based on its
        type, file path, and line number.
        """
        issue_type = issue.get('type', 'unknown-type')
        file_path = issue.get('file', 'unknown-file')
        line = issue.get('line', 0)
        return f"{issue_type}|{file_path}|{line}"
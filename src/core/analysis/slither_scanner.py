import json
import os
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING, Tuple

from src.core.tools.run_tool import run_tool
from src.core.analysis.base_scanner import BaseScanner, SlitherExecutionError

if TYPE_CHECKING:
    from src.core.config import AuditConfig

# Configure a logger for this module
logger = logging.getLogger(__name__)


class SlitherScanner(BaseScanner):
    """
    Wraps the Slither CLI tool to scan local directories.
    """

    TOOL_NAME = "Slither"

    def _execute_slither(self, target_path: str, relative_files: Optional[List[str]] = None) -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
        """
        Executes the slither command and returns the JSON output.
        Raises SlitherExecutionError on failure.
        
        Args:
            target_path: Path to the repository root (working directory for slither)
            relative_files: List of relative file paths to scan (relative to target_path)
        """
        # --- Verify files exist before passing to slither ---
        if relative_files:
            existing_files = []
            for file_path in relative_files:
                full_path = os.path.join(target_path, file_path)
                if os.path.isfile(full_path):
                    existing_files.append(file_path)
                    logger.debug(f"✓ File exists: {full_path}")
                else:
                    logger.warning(f"⚠️ File not found (will skip): {full_path} (Exists: {os.path.exists(full_path)})")
            
            if not existing_files:
                logger.warning(f"⚠️ No Solidity files found at specified paths. Falling back to full scan.")
                relative_files = None
            else:
                relative_files = existing_files
        
        # --- Set solc version ---
        try:
            solc_version_to_use = "0.8.20"
            logger.info(f"🐍 Attempting to set solc version using 'solc-select use {solc_version_to_use}'...")
            rc, _, stderr, _, _ = run_tool(
                ["solc-select", "use", solc_version_to_use],
                cwd=target_path,
                timeout=60
            )
            if rc == 0:
                logger.info(f"✅ Successfully set solc version to {solc_version_to_use}.")
            else:
                logger.warning(f"⚠️ Could not set solc version via solc-select: {stderr.decode('utf-8', errors='ignore')}")
        except Exception as e:
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
        logger.info(f"Working directory (cwd): {target_path}")

        rc, stdout, stderr, out_path, err_path = run_tool(cmd, cwd=target_path, timeout=300)
        
        log_paths = {self.TOOL_NAME: [out_path, err_path]}

        # --- Error Handling based on output file ---
        try:
            with open(output_filepath, 'r') as f:
                json_output = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            stderr_str = stderr.decode('utf-8', errors='ignore')
            stdout_str = stdout.decode('utf-8', errors='ignore')

            logger.error(f"❌ Slither execution failed to produce a valid report file (Exit Code {rc}). Exception: {e}")
            if stdout_str:
                logger.error(f"Slither STDOUT: {stdout_str}")
            if stderr_str:
                logger.error(f"Slither STDERR: {stderr_str}")

            # Check for file not found errors in stderr
            if "is not a file or directory" in stderr_str:
                logger.error(f"❌ Slither could not find specified files. Ensure file paths are correct relative to {target_path}")
                error_message = f"Slither could not find the specified files. This often indicates file path resolution issues or files that don't exist in the target repository."
            else:
                error_message = stderr_str or stdout_str or f"Slither failed with exit code {rc} and did not produce a valid report file."
            
            raise SlitherExecutionError(f"Slither Scan Failed. Details: {error_message}")

        logger.info(f"Slither analysis finished (Exit Code: {rc}). Report read from {output_filepath}")
        
        return json_output, log_paths

    def run(self, target_path: str, files: Optional[List[str]] = None, config: Optional['AuditConfig'] = None) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
        """
        Runs Slither on the target_path. For differential scans, it scans only the changed files.
        Filters issues by minimum severity from the config.

        Args:
            target_path: Path to the repository root
            files: Optional list of specific files to scan
            config: Optional ScanConfig object containing filtering rules (min_severity)

        Returns:
            A tuple containing:
                - List of cleaned issue dictionaries, filtered by severity
                - Dictionary of log file paths
        """
        logger.info(f"🔍 Starting Slither scan on: {target_path}")

        if files is not None and len(files) == 0:
            logger.info("⚠️ No files provided for Slither scan. Skipping.")
            return [], {}

        relative_files = None
        if files:
            relative_files = [os.path.relpath(f, target_path) for f in files]

        raw_output, log_paths = self._execute_slither(target_path, relative_files=relative_files)

        # Extract min_severity from config, default to 'Low'
        min_severity = config.get_min_severity() if config else 'Low'
        logger.debug(f"🎯 Slither: Filtering issues with minimum severity: {min_severity}")

        clean_issues: List[Dict[str, Any]] = []

        if not raw_output.get("success") or "results" not in raw_output or "detectors" not in raw_output["results"]:
            logger.warning(f"Slither output is empty or indicates failure. Raw: {str(raw_output)[:500]}")
            return [], log_paths

        for issue in raw_output["results"]["detectors"]:
            # Slither reports impact/importance in 'impact' field. Normalize and map to severity rank.
            severity = issue.get('impact', 'Informational').capitalize()
            severity_level = self.SEVERITY_MAP.get(severity.lower(), self.SEVERITY_MAP['informational'])

            # Determine required minimum severity rank (default to 'Low')
            min_rank = self.SEVERITY_MAP.get(min_severity.lower(), self.SEVERITY_MAP['low'])

            # Skip issues below the minimum severity threshold
            if severity_level < min_rank:
                logger.debug(f"Slither: Filtering out {severity} issue: {issue.get('check', 'Unknown')}")
                continue

            primary_element = issue.get('elements', [{}])[0]
            file_path = primary_element.get('source_mapping', {}).get('filename_relative', 'Unknown')
            line_number = primary_element.get('source_mapping', {}).get('lines', [0])[0]

            clean_issues.append({
                "tool": self.TOOL_NAME,
                "type": issue.get('check', 'Unknown'),
                "severity": severity,
                "confidence": issue.get('confidence', 'Low').capitalize(),
                "description": issue.get('description', 'No description'),
                "file": file_path,
                "line": int(line_number) if line_number else 0,
                "raw_data": issue
            })

        logger.info(f"Slither found {len(clean_issues)} total issues meeting the severity threshold (Min: {min_severity}).")
        return clean_issues, log_paths


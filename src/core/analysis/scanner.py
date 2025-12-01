import subprocess
import json
import os
import logging
import shutil
from typing import List, Dict, Any, Optional, TYPE_CHECKING
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


class BaseScanner(ABC):
    """
    Abstract base class for security analysis tools.
    Provides common functionality like severity mapping and issue fingerprinting.
    """

    # Severity level mapping (numeric for comparison)
    SEVERITY_MAP = {'informational': 1, 'low': 2, 'medium': 3, 'high': 4}

    @abstractmethod
    def run(self, target_path: str, files: Optional[List[str]] = None, config: Optional['AuditConfig'] = None) -> List[Dict[str, Any]]:
        """
        Run the scanner on the target path and return a list of issues.
        
        Args:
            target_path: Path to the repository root
            files: Optional list of specific files to scan
            config: Optional ScanConfig object containing filtering rules
            
        Returns:
            List of issue dictionaries with standard format
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


class SlitherScanner(BaseScanner):
    """
    Wraps the Slither CLI tool to scan local directories.
    """

    TOOL_NAME = "Slither"

    def _execute_slither(self, target_path: str, relative_files: Optional[List[str]] = None) -> Dict[str, Any]:
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
                    logger.warning(f"⚠️ File not found (will skip): {full_path}")
            
            if not existing_files:
                logger.warning(f"⚠️ No Solidity files found at specified paths. Falling back to full scan.")
                relative_files = None
            else:
                relative_files = existing_files
        
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
        logger.info(f"Working directory (cwd): {target_path}")

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

            # Check for file not found errors in stderr
            if "is not a file or directory" in stderr:
                logger.error(f"❌ Slither could not find specified files. Ensure file paths are correct relative to {target_path}")
                error_message = f"Slither could not find the specified files. This often indicates file path resolution issues or files that don't exist in the target repository."
            else:
                error_message = stderr or stdout or f"Slither failed with exit code {result.returncode} and did not produce a valid report file."
            
            raise SlitherExecutionError(f"Slither Scan Failed. Details: {error_message}")

        logger.info(f"Slither analysis finished (Exit Code: {result.returncode}). Report read from {output_filepath}")
        return json_output

    def run(self, target_path: str, files: Optional[List[str]] = None, config: Optional['AuditConfig'] = None) -> List[Dict[str, Any]]:
        """
        Runs Slither on the target_path. For differential scans, it scans only the changed files.
        Filters issues by minimum severity from the config.

        Args:
            target_path: Path to the repository root
            files: Optional list of specific files to scan
            config: Optional ScanConfig object containing filtering rules (min_severity)

        Returns:
            List of cleaned issue dictionaries, filtered by severity
        """
        logger.info(f"🔍 Starting Slither scan on: {target_path}")

        relative_files = None
        if files:
            relative_files = [os.path.relpath(f, target_path) for f in files]

        raw_output = self._execute_slither(target_path, relative_files=relative_files)

        # Extract min_severity from config, default to 'Low'
        min_severity = config.get_min_severity() if config else 'Low'
        logger.info(f"🎯 Slither: Filtering issues with minimum severity: {min_severity}")

        clean_issues: List[Dict[str, Any]] = []

        if not raw_output.get("success") or "results" not in raw_output or "detectors" not in raw_output["results"]:
            logger.warning(f"Slither output is empty or indicates failure. Raw: {str(raw_output)[:500]}")
            return []

        for issue in raw_output["results"]["detectors"]:
            severity = issue.get('impact', 'Informational').capitalize()
            severity_level = self.SEVERITY_MAP.get(severity.lower(), 1)

            # Skip issues below the minimum severity threshold
            if severity_level < self.SEVERITY_MAP.get(min_severity.lower(), 2):
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
        return clean_issues


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
        return f"{issue_type}|{file_path}|{line}"
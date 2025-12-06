import json
import os
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from src.core.tools.run_tool import run_tool
from src.core.analysis.base_scanner import BaseScanner, MythrilExecutionError

if TYPE_CHECKING:
    from src.core.config import AuditConfig

# Configure a logger for this module
logger = logging.getLogger(__name__)

# Set environment variable to prevent Mythril from making network calls during import
# This helps avoid "Connection reset by peer" errors when solcx tries to fetch version list
os.environ.setdefault('SOLCX_BINARY_PATH_PREFIX', '/root/.solcx')


class MythrilScanner(BaseScanner):
    """
    Wraps the Mythril CLI tool for EVM bytecode analysis.
    """

    TOOL_NAME = "Mythril"

    def _execute_mythril(self, target_path: str, relative_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Executes the mythril command and returns the JSON output.
        Raises MythrilExecutionError on failure.
        
        Returns a dict with 'issues' list and 'scanned_files' for file attribution.
        """
        output_filename = "mythril_report.json"
        output_filepath = os.path.join(target_path, output_filename)

        # --- Command Construction ---
        cmd = ["myth", "analyze"]

        # Track which files we're scanning for file attribution
        scanned_files = []

        # For files, analyze each file individually
        if relative_files:
            logger.info(f"⚡ Mythril: Running partial scan on: {relative_files}")
            # Mythril needs full file paths
            cmd.extend(relative_files)
            scanned_files = relative_files
        else:
            logger.info("⚙️ Mythril: Running full scan on repository root.")
            cmd.append(".")

        # Append common flags (--max-depth 3 for better vulnerability detection)
        # Higher depth = more thorough analysis but slower execution
        # --max-depth 3 = ~30 seconds per scan (good balance)
        cmd.extend(["--max-depth", "3", "-o", "json"])

        logger.info(f"Executing Mythril command: {' '.join(cmd)}")

        rc, stdout, stderr, out_path, err_path = run_tool(cmd, cwd=target_path, timeout=300)

        logger.info(f"Mythril stdout log: {out_path}")
        logger.info(f"Mythril stderr log: {err_path}")

        if not stdout.strip():
            stderr_str = stderr.decode('utf-8', errors='ignore')
            if stderr_str.strip():
                logger.error(f"tool_error: Mythril stdout was empty, but stderr contained: {stderr_str}")
                raise MythrilExecutionError(f"Mythril Scan Failed. Stderr: {stderr_str}")
            else:
                logger.info("tool_no_output: Mythril stdout and stderr were empty. No issues found.")
                return {"issues": [], "scanned_files": scanned_files}

        if rc != 0:
            stderr_str = stderr.decode('utf-8', errors='ignore')
            logger.error(f"❌ Mythril execution failed with exit code {rc}")
            if stderr_str:
                logger.error(f"Mythril STDERR: {stderr_str}")
            raise MythrilExecutionError(f"Mythril Scan Failed. Details: {stderr_str}")

        try:
            json_output = json.loads(stdout)
            json_output['scanned_files'] = scanned_files
            logger.info(f"Mythril analysis finished (Exit Code: {rc}). Issues found.")
            return json_output
        except json.JSONDecodeError:
            # If no valid JSON, try to read from output file
            if os.path.exists(output_filepath):
                try:
                    with open(output_filepath, 'r') as f:
                        json_output = json.load(f)
                        json_output['scanned_files'] = scanned_files
                        logger.info(f"Mythril analysis finished (Exit Code: {rc}). Issues found.")
                        return json_output
                except (FileNotFoundError, json.JSONDecodeError):
                    pass
            
            stderr_str = stderr.decode('utf-8', errors='ignore')
            logger.error(f"Mythril output was not valid JSON. Stderr: {stderr_str}")
            raise MythrilExecutionError(f"Mythril Scan Failed. Output was not valid JSON. Stderr: {stderr_str}")



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

        if files is not None and len(files) == 0:
            logger.info("⚠️ No files provided for Mythril scan. Skipping.")
            return []

        relative_files = None
        if files:
            relative_files = [os.path.relpath(f, target_path) for f in files]

        raw_output = self._execute_mythril(target_path, relative_files=relative_files)

        # Extract min_severity from config, default to 'Low'
        min_severity = config.get_min_severity() if config else 'Low'
        logger.debug(f"🎯 Mythril: Filtering issues with minimum severity: {min_severity}")

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
            # Mythril doesn't provide file paths directly in issues, but we know which files we scanned
            scanned_files = raw_output.get('scanned_files', [])
            
            # Get file from scanned files (Mythril typically scans one file at a time in our setup)
            if scanned_files and len(scanned_files) == 1:
                file_path = scanned_files[0]
            elif scanned_files:
                # Multiple files - try to match by contract name if available
                contract_name = issue.get('contract', '')
                file_path = scanned_files[0]  # Default to first file
                for f in scanned_files:
                    if contract_name.lower() in f.lower():
                        file_path = f
                        break
            else:
                file_path = 'Unknown'
            
            # Parse source map for line information
            # Mythril provides sourceMap in format "offset:length:sourceIndex:jump"
            source_map = issue.get('sourceMap', '')
            line_number = 0
            if source_map and source_map != 'Unknown':
                byte_offset = self._parse_source_map(source_map)
                # Approximate line number from byte offset (rough estimate: ~40 chars per line)
                # This is imprecise but better than 0
                if byte_offset > 0:
                    line_number = max(1, byte_offset // 40)

            clean_issues.append({
                "tool": self.TOOL_NAME,
                "type": issue.get('title', 'Unknown'),
                "severity": severity,
                "confidence": issue.get('confidence', 'Low').capitalize() if issue.get('confidence') else 'Medium',
                "description": issue.get('description', 'No description'),
                "file": file_path,
                "line": int(line_number) if line_number else 0,
                "function": issue.get('function', 'Unknown'),
                "swc_id": issue.get('swc-id', ''),
                "raw_data": issue
            })

        logger.info(f"Mythril found {len(clean_issues)} total issues meeting the severity threshold (Min: {min_severity}).")
        return clean_issues

    def _parse_source_map(self, source_map: str) -> int:
        """
        Parse Solidity source map format to extract line offset.
        Source map format: offset:length:sourceIndex:jump
        
        Returns the byte offset which can be used for approximate line location.
        """
        try:
            parts = source_map.split(':')
            if parts:
                return int(parts[0])  # Return byte offset
        except (ValueError, IndexError):
            pass
        return 0

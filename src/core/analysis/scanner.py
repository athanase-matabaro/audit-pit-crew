import subprocess
import json
import os
import logging
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.config import AuditConfig

# Configure a logger for this module
logger = logging.getLogger(__name__)

class SlitherScanner:
    """
    Wraps the Slither CLI tool to scan local directories.
    """

    def run(self, target_path: str, config: Optional['AuditConfig'] = None, files: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Runs Slither on the target_path.
        
        Args:
            target_path: The path to the cloned repository.
            config: Optional repository-specific audit configuration object.
            files: Optional list of relative file paths to scan (for diff scanning).

        Returns:
            A list of issues found, filtered by the configured severity.
        """
        logger.info(f"🔍 Starting Slither scan on: {target_path}")

        # Define where to save the raw JSON report
        output_file = os.path.join(target_path, "slither_report.json")

        # --- COMMAND CONSTRUCTION ---
        cmd = ["slither"]
        
        if files:
            logger.info(f"⚡ Running efficient scan on {len(files)} changed files.")
            # For differential scans, Slither must be run from the root directory (target_path) 
            # with relative paths to the changed files.
            # Note: get_changed_solidity_files now returns absolute paths, so we make them relative.
            relative_files = [os.path.relpath(f, target_path) for f in files]
            cmd.extend(relative_files)
        else:
            logger.info("Scanning entire project (No files specified).")
            cmd.append(".") 
        
        cmd.extend(["--json", output_file])
        # --- END COMMAND CONSTRUCTION ---

        try:
            # Run the command. Slither returns non-zero exit codes for found issues.
            subprocess.run(
                cmd,
                cwd=target_path,
                capture_output=True,
                text=True,
                check=False
            )

            if not os.path.exists(output_file):
                logger.error("❌ Slither failed to generate a report.")
                return [] 

            with open(output_file, 'r') as f:
                raw_data = json.load(f)

        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"❌ Slither execution failed: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ An unexpected error occurred during Slither execution: {e}")
            return []
        
        finally:
            # Clean up the report file
            if os.path.exists(output_file):
                os.remove(output_file)

        return self._process_raw_report(raw_data, config)

    def _process_raw_report(self, raw_data: Dict[str, Any], config: Optional['AuditConfig']) -> List[Dict[str, Any]]:
        """
        Parses the raw Slither JSON and filters issues based on configured severity.
        """
        clean_issues = []
        detectors = raw_data.get('results', {}).get('detectors', [])

        for issue in detectors:
            severity = issue.get('impact', 'Informational')
            
            # Determine if the issue should be reported based on severity
            should_report = False
            if config:
                should_report = config.is_severity_reported(severity)
            else:
                # Default behavior if no config is provided: report Medium and High
                should_report = severity in ['High', 'Medium']

            if should_report:
                elements = issue.get('elements', [])
                file_path = "Unknown"
                line_number = 0
                
                if elements and 'source_mapping' in elements[0]:
                    file_path = elements[0]['source_mapping'].get('filename_relative', 'Unknown')
                    line_number = elements[0]['source_mapping'].get('lines', [0])[0]

                clean_issues.append({
                    "type": issue.get('check', 'Unknown'),
                    "severity": severity,
                    "confidence": issue.get('confidence', 'Low'),
                    "description": issue.get('description', 'No description'),
                    "file": file_path,
                    "line": line_number
                })

        logger.info(f"✅ Scan complete. Found {len(clean_issues)} issues meeting the severity threshold.")
        return clean_issues

    @staticmethod
    def get_issue_fingerprint(issue: Dict[str, Any]) -> str:
        """
        Creates a unique, stable identifier for a given issue based on its
        type, file path, and line number.

        Args:
            issue: The issue dictionary processed from Slither's report.
        
        Returns:
            A pipe-delimited string acting as a unique fingerprint.
        """
        issue_type = issue.get('type', 'unknown-type')
        # Use relative file path for stable fingerprinting across environments
        file_path = issue.get('file', 'unknown-file')
        line = issue.get('line', 0)
        return f"{issue_type}|{file_path}|{line}"
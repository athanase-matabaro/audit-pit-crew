import subprocess
import json
import os
import logging
from typing import List, Dict, Any, Optional

# Configure a logger for this module
logger = logging.getLogger(__name__)

class SlitherScanner:
    """
    Wraps the Slither CLI tool to scan local directories.
    """

    def run(self, target_path: str, files: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Runs Slither on the target_path.
        
        Args:
            target_path: The path to the cloned repository.
            files: Optional list of relative file paths to scan (for diff scanning).

        Returns:
            A list of issues found, filtered for Medium/High severity.
        """
        logger.info(f"🔍 Starting Slither scan on: {target_path}")

        # Define where to save the raw JSON report
        output_file = os.path.join(target_path, "slither_report.json")

        # --- CORRECTED COMMAND CONSTRUCTION ---
        cmd = ["slither"]
        
        if files:
            logger.info(f"⚡ Running efficient scan on {len(files)} changed files: {files}")
            # Slither must be run from the root directory (target_path) 
            # and the files must be relative paths.
            cmd.extend(files)
        else:
            logger.info("Scanning entire project (No files specified).")
            # Slither can be pointed to the current directory when scanning all files
            cmd.append(".") 
        
        # Always append the output format arguments
        cmd.extend(["--json", output_file])
        # --- END COMMAND CONSTRUCTION ---

        try:
            # Run the command. We don't use check=True because Slither returns
            # non-zero exit codes when bugs are found (which is good!).
            result = subprocess.run(
                cmd,
                cwd=target_path,
                capture_output=True,
                text=True,
                check=False
            )

            # Check if the JSON file was actually created
            if not os.path.exists(output_file):
                logger.error("❌ Slither failed to generate a report.")
                # Log the captured output to see why
                logger.error(f"Slither stdout: {result.stdout.strip()}")
                logger.error(f"Slither stderr: {result.stderr.strip()}")
                # If the JSON file is missing, something critical failed (e.g., compilation)
                return [] 

            # Read the JSON report
            with open(output_file, 'r') as f:
                raw_data = json.load(f)

        except FileNotFoundError:
            logger.error(f"❌ Slither command not found. Ensure 'slither-analyzer' is installed in the worker container.")
            return []
        except json.JSONDecodeError:
            logger.error(f"❌ Slither generated invalid JSON report at {output_file}.")
            return []
        except Exception as e:
            logger.error(f"❌ An unexpected error occurred during Slither execution: {e}")
            return []
        
        finally:
            # Clean up the report file after reading it
            if os.path.exists(output_file):
                os.remove(output_file)

        return self._process_raw_report(raw_data)

    def _process_raw_report(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parses the raw Slither JSON and remove 'Low' severity noise.
        """
        clean_issues = []
        
        # Slither JSON structure is: {'results': {'detectors': [...]}}
        detectors = raw_data.get('results', {}).get('detectors', [])

        for issue in detectors:
            severity = issue.get('impact', 'Low')
            confidence = issue.get('confidence', 'Low')
            description = issue.get('description', 'No description')
            check_type = issue.get('check', 'Unknown')

            # FILTER: We only want Medium or High severity for the MVP
            if severity in ['High', 'Medium']:
                
                # Extract the first file location if available
                elements = issue.get('elements', [])
                file_path = "Unknown"
                line_number = 0
                
                if elements and 'source_mapping' in elements[0]:
                    file_path = elements[0]['source_mapping'].get('filename_relative', 'Unknown')
                    # Get the start line of the issue location
                    line_number = elements[0]['source_mapping'].get('lines', [0])[0]

                clean_issues.append({
                    "type": check_type,
                    "severity": severity,
                    "confidence": confidence,
                    "description": description,
                    "file": file_path,
                    "line": line_number
                })

        logger.info(f"✅ Scan complete. Found {len(clean_issues)} major issues.")
        return clean_issues
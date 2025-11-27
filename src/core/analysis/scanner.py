import subprocess
import json
import os
import logging
from typing import List, Dict, Any, Optional

# Configure a logger for this module
logger = logging.getLogger(__name__)
# The basicConfig line should be removed or commented out if configuration is handled centrally
# logging.basicConfig(level=logging.INFO) 

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
            # FIX: Use the list of files as the targets instead of '.'
            # Slither must be run from the root directory (target_path) 
            # and the files must be relative paths.
            cmd.extend(files)
        else:
            logger.info("Scanning entire project...")
            # Default to scanning the whole project if no files are provided
            cmd.append(".")
            
        # Add the output flags AFTER the target files/directory
        cmd.extend(["--json", output_file])
        # --- END CORRECTED CONSTRUCTION ---

        try:
            # Run the command. cwd=target_path is essential.
            result = subprocess.run(
                cmd,
                cwd=target_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=300 
            )

            # Check if the JSON file was actually created
            if not os.path.exists(output_file):
                logger.error("❌ Slither failed to generate a report.")
                # Log the captured output to see why it failed
                logger.error(f"Slither stdout: {result.stdout}")
                logger.error(f"Slither stderr: {result.stderr}")
                return []

            # Read and parse the JSON
            with open(output_file, 'r') as f:
                data = json.load(f)

            return self._filter_results(data)

        except FileNotFoundError:
            logger.error("❌ Slither command not found. Is it installed?")
            return []
        except subprocess.TimeoutExpired:
            logger.error("❌ Slither scan timed out after 300 seconds.")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error during scan: {e}")
            return []

    def _filter_results(self, raw_data: Dict) -> List[Dict[str, Any]]:
        """
        Private method to clean up the JSON and remove 'Low' severity noise.
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
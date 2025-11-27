import subprocess
import json
import os
import logging
from typing import List, Dict, Any

# Configure a logger for this module
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class SlitherScanner:
    """
    Wraps the Slither CLI tool to scan local directories.
    """

    def run(self, target_path: str) -> List[Dict[str, Any]]:
        """
        Runs Slither on the target_path and returns a list of Critical/Medium issues.
        """
        logger.info(f"🔍 Starting Slither scan on: {target_path}")

        # Define where to save the raw JSON report
        output_file = os.path.join(target_path, "slither_report.json")

        # Construct the command: slither . --json slither_report.json
        cmd = ["slither", ".", "--json", output_file]

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
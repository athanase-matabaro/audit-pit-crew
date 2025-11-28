import os
import yaml
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Define the order and value of severity levels for comparison.
SEVERITY_LEVELS = {"informational": 0, "low": 1, "medium": 2, "high": 3}

# Default configuration used if the config file is missing, invalid, or a key is absent.
DEFAULT_CONFIG = {
    'contracts_path': '.',
    'ignore_files': [],
    'min_severity': 'Medium',
}

class AuditConfig:
    """
    Handles reading and parsing the 'audit-pit-crew.yml' configuration file
    from a repository, with robust support for default values and severity logic.
    """
    def __init__(self, repository_path: str):
        """
        Initializes the config object by loading the YAML file from the given path.

        Args:
            repository_path: The absolute path to the root of the cloned repository.
        """
        self.repository_path = repository_path
        self.config_file_path = os.path.join(repository_path, 'audit-pit-crew.yml')
        self._config = self._load_config()
        self.min_severity_level = SEVERITY_LEVELS.get(self.min_severity.lower(), 2)

    def _load_config(self) -> Dict[str, Any]:
        """
        Loads configuration from the YAML file. If the file doesn't exist or
        is malformed, it returns the default configuration.
        """
        if not os.path.exists(self.config_file_path):
            logger.info("⚙️ 'audit-pit-crew.yml' not found. Using default settings.")
            return DEFAULT_CONFIG

        try:
            with open(self.config_file_path, 'r') as f:
                user_config = yaml.safe_load(f)
                logger.info("⚙️ Successfully loaded 'audit-pit-crew.yml'.")
                
                config = DEFAULT_CONFIG.copy()
                if user_config:
                    config.update(user_config)
                return config
        except (yaml.YAMLError, IOError) as e:
            logger.error(f"❌ Error reading or parsing 'audit-pit-crew.yml': {e}. Using default settings.")
            return DEFAULT_CONFIG

    @property
    def contracts_path(self) -> str:
        """The relative path within the repo to scan for contracts."""
        return self._config.get('contracts_path', DEFAULT_CONFIG['contracts_path'])

    @property
    def ignore_files(self) -> List[str]:
        """A list of file paths or glob patterns to ignore during the scan."""
        return self._config.get('ignore_files', DEFAULT_CONFIG['ignore_files'])
        
    @property
    def min_severity(self) -> str:
        """The minimum severity level to report (e.g., 'Low', 'Medium', 'High')."""
        return self._config.get('min_severity', DEFAULT_CONFIG['min_severity'])

    def is_severity_reported(self, severity: str) -> bool:
        """
        Determines if an issue's severity meets the configured minimum threshold.
        
        Args:
            severity: The severity of the issue found (e.g., 'High', 'Medium').
            
        Returns:
            True if the issue should be reported, False otherwise.
        """
        issue_severity_level = SEVERITY_LEVELS.get(severity.lower())
        
        # If the severity from the scanner isn't in our defined list, report it by default.
        if issue_severity_level is None:
            return True
            
        return issue_severity_level >= self.min_severity_level

    def get_full_contracts_path(self) -> str:
        """
        Returns the absolute path for the configured contracts directory.
        """
        return os.path.abspath(os.path.join(self.repository_path, self.contracts_path))
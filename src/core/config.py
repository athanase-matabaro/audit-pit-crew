import os
from typing import List, Dict, Any
import yaml

class AuditConfig:
    """
    Manages audit configuration, loading from a project file if it exists,
    and providing default values.
    """
    def __init__(self, project_path: str):
        """
        Initializes the configuration for a given project path.

        Args:
            project_path: The root path of the project being audited.
        """
        self.project_path = project_path
        self.config_file = os.path.join(project_path, 'audit-pit-crew.yml')
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Loads configuration from `audit-pit-crew.yml` if it exists.
        Returns an empty dict if the file is not found.
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return yaml.safe_load(f) or {}
            except (IOError, yaml.YAMLError):
                # In case of file read error or parsing error, default to empty config
                return {}
        return {}

    def get_target_extensions(self) -> List[str]:
        """
        Returns the list of file extensions to target for scanning.
        Defaults to ['.sol'] if not specified in the config file.
        """
        scanner_config = self.config.get('scanner', {})
        return scanner_config.get('target_extensions', ['.sol'])

    def get_exclude_patterns(self) -> List[str]:
        """
        Returns the list of file/directory patterns to exclude from scanning.
        Defaults to an empty list. It can include contract names, file paths,
        or directories. Standard unix glob patterns are supported.
        
        Example patterns: 
        - `contracts/mocks/*`
        - `*Test.sol`
        """
        scanner_config = self.config.get('scanner', {})
        return scanner_config.get('exclude', [])

    def get_min_severity(self) -> str:
        """
        Returns the minimum severity level to report from the config, defaulting to 'Low'.
        """
        scanner_config = self.config.get('scanner', {})
        return scanner_config.get('min_severity', 'Low')
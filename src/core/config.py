import os
import logging
from typing import List, Literal, Optional
import yaml
from pydantic import BaseModel, Field, ValidationError


logger = logging.getLogger(__name__)

# Define the severity levels
Severity = Literal["Low", "Medium", "High", "Critical"]


class ScanConfig(BaseModel):
    """Configuration for the scan behavior."""
    contracts_path: str = Field(default=".", description="Root path for Solidity source files")
    ignore_paths: List[str] = Field(
        default_factory=lambda: ["node_modules/**", "test/**"],
        description="Glob patterns to exclude from scanning"
    )
    min_severity: Severity = Field(default="Low", description="Minimum severity to report")

    def get_min_severity(self) -> str:
        """Returns the minimum severity level as a string."""
        return self.min_severity


class AuditConfig(BaseModel):
    """Root configuration object."""
    scan: ScanConfig = Field(default_factory=ScanConfig)


class AuditConfigManager:
    """Manages loading and parsing of audit-pit-crew.yml configuration files."""
    
    CONFIG_FILE_NAME = "audit-pit-crew.yml"

    @staticmethod
    def load_config(workspace: str) -> AuditConfig:
        """
        Loads the audit-pit-crew.yml configuration from the workspace.
        Falls back to default configuration if file is missing or invalid.
        
        Args:
            workspace: The repository workspace directory path
            
        Returns:
            AuditConfig object with user config or defaults
        """
        config_path = os.path.join(workspace, AuditConfigManager.CONFIG_FILE_NAME)
        
        if not os.path.exists(config_path):
            logger.info(f"ℹ️ Config file not found at {config_path}. Using default configuration.")
            return AuditConfig()
        
        try:
            logger.info(f"📖 Loading configuration from {config_path}")
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f)
            
            if not config_data:
                logger.warning(f"⚠️ Config file {config_path} is empty. Using default configuration.")
                return AuditConfig()
            
            # Parse and validate the configuration
            audit_config = AuditConfig.parse_obj(config_data)
            logger.info(
                f"✅ Configuration loaded successfully. "
                f"Contracts path: {audit_config.scan.contracts_path}, "
                f"Min severity: {audit_config.scan.min_severity}, "
                f"Ignore patterns: {len(audit_config.scan.ignore_paths)} pattern(s)"
            )
            return audit_config
            
        except yaml.YAMLError as e:
            logger.error(f"❌ Failed to parse YAML config file: {e}. Using default configuration.")
            return AuditConfig()
        except ValidationError as e:
            logger.error(f"❌ Configuration validation failed: {e}. Using default configuration.")
            return AuditConfig()
        except Exception as e:
            logger.error(f"❌ Unexpected error loading config: {e}. Using default configuration.")
            return AuditConfig()


"""
Unit tests for AuditConfigManager and config loading.
"""
import os
import tempfile
import pytest
import yaml

from src.core.config import AuditConfig, AuditConfigManager, ScanConfig


class TestScanConfigDefaults:
    """Test default ScanConfig values."""

    def test_default_contracts_path(self):
        config = ScanConfig()
        assert config.contracts_path == "."

    def test_default_ignore_paths(self):
        config = ScanConfig()
        assert config.ignore_paths == ["node_modules/**", "test/**"]

    def test_default_min_severity(self):
        config = ScanConfig()
        assert config.min_severity == "Low"

    def test_default_block_on_severity(self):
        config = ScanConfig()
        assert config.block_on_severity == "High"

    def test_default_enabled_tools(self):
        config = ScanConfig()
        assert config.enabled_tools == ["slither", "mythril"]


class TestAuditConfigManagerLoadConfig:
    """Test AuditConfigManager.load_config behavior."""

    def test_no_config_file_returns_defaults(self, tmp_path):
        """When no config file exists, defaults are used."""
        config = AuditConfigManager.load_config(str(tmp_path))

        assert config.scan.contracts_path == "."
        assert config.scan.ignore_paths == ["node_modules/**", "test/**"]
        assert config.scan.min_severity == "Low"

    def test_empty_config_file_returns_defaults(self, tmp_path):
        """When config file is empty, defaults are used."""
        config_file = tmp_path / "audit-pit-crew.yml"
        config_file.write_text("")

        config = AuditConfigManager.load_config(str(tmp_path))

        assert config.scan.contracts_path == "."
        assert config.scan.min_severity == "Low"

    def test_partial_config_merges_with_defaults(self, tmp_path):
        """When config has only some keys, others use defaults."""
        config_file = tmp_path / "audit-pit-crew.yml"
        config_file.write_text(yaml.dump({
            "scan": {
                "min_severity": "High"
            }
        }))

        config = AuditConfigManager.load_config(str(tmp_path))

        assert config.scan.min_severity == "High"
        # Defaults for missing keys
        assert config.scan.contracts_path == "."
        assert config.scan.ignore_paths == ["node_modules/**", "test/**"]

    def test_full_config_overrides_defaults(self, tmp_path):
        """When config has all keys, they override defaults."""
        config_file = tmp_path / "audit-pit-crew.yml"
        config_file.write_text(yaml.dump({
            "scan": {
                "contracts_path": "contracts/",
                "ignore_paths": ["mocks/**", "upgrades/**"],
                "min_severity": "Critical"
            }
        }))

        config = AuditConfigManager.load_config(str(tmp_path))

        assert config.scan.contracts_path == "contracts/"
        assert config.scan.ignore_paths == ["mocks/**", "upgrades/**"]
        assert config.scan.min_severity == "Critical"

    def test_invalid_yaml_returns_defaults(self, tmp_path):
        """When YAML is malformed, defaults are used."""
        config_file = tmp_path / "audit-pit-crew.yml"
        config_file.write_text("this is: not: valid yaml:::")

        config = AuditConfigManager.load_config(str(tmp_path))

        assert config.scan.contracts_path == "."
        assert config.scan.min_severity == "Low"

    def test_invalid_severity_raises_validation_error(self, tmp_path):
        """When min_severity is invalid, defaults are used."""
        config_file = tmp_path / "audit-pit-crew.yml"
        config_file.write_text(yaml.dump({
            "scan": {
                "min_severity": "Invalid"
            }
        }))

        # Pydantic should fall back to defaults when validation fails
        config = AuditConfigManager.load_config(str(tmp_path))
        # ValidationError should result in defaults
        assert config.scan.min_severity == "Low"


class TestScanConfigMethods:
    """Test ScanConfig helper methods."""

    def test_get_min_severity_returns_string(self):
        config = ScanConfig(min_severity="High")
        assert config.get_min_severity() == "High"

    def test_get_block_severity_returns_string(self):
        config = ScanConfig(block_on_severity="Critical")
        assert config.get_block_severity() == "Critical"

    def test_is_tool_enabled_case_insensitive(self):
        config = ScanConfig(enabled_tools=["Slither", "MYTHRIL"])
        assert config.is_tool_enabled("slither") is True
        assert config.is_tool_enabled("Mythril") is True
        assert config.is_tool_enabled("SLITHER") is True
        assert config.is_tool_enabled("aderyn") is False

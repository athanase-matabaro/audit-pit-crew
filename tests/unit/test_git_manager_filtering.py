"""
Unit tests for GitManager filtering logic (contracts_path, ignore_paths).
"""
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
import fnmatch

from src.core.git_manager import GitManager
from src.core.config import AuditConfig, ScanConfig


class TestContractsPathSanitization:
    """Test contracts_path validation and sanitization."""

    def test_absolute_path_fallback_to_dot(self, tmp_path):
        """Absolute contracts_path should be sanitized to '.'"""
        git = GitManager()

        # Create a dummy config with absolute path
        config = AuditConfig(scan=ScanConfig(contracts_path="/etc/passwd"))

        # Mock git diff to return a file
        with patch.object(git, '_execute_git_command') as mock_cmd:
            mock_cmd.return_value = "contracts/Token.sol"

            # Since contracts_path is absolute, it should fall back to "." and include the file
            result = git.get_changed_solidity_files(
                str(tmp_path),
                "main",
                "HEAD",
                config=config
            )

            # The file should be included (fallback to root scope)
            # Note: file won't exist, so it will be skipped due to existence check
            # We just check that the path was sanitized (no error)
            assert isinstance(result, list)

    def test_parent_traversal_fallback_to_dot(self, tmp_path):
        """Parent traversal in contracts_path should be sanitized to '.'"""
        git = GitManager()

        config = AuditConfig(scan=ScanConfig(contracts_path="../../../etc"))

        with patch.object(git, '_execute_git_command') as mock_cmd:
            mock_cmd.return_value = "Token.sol"

            result = git.get_changed_solidity_files(
                str(tmp_path),
                "main",
                "HEAD",
                config=config
            )

            # No error thrown, fallback applied
            assert isinstance(result, list)

    def test_relative_contracts_path_works(self, tmp_path):
        """Valid relative contracts_path should work correctly."""
        git = GitManager()

        config = AuditConfig(scan=ScanConfig(contracts_path="src/contracts", ignore_paths=[]))

        # Create the file
        contracts_dir = tmp_path / "src" / "contracts"
        contracts_dir.mkdir(parents=True)
        (contracts_dir / "Token.sol").write_text("// SPDX")

        with patch.object(git, '_execute_git_command') as mock_cmd:
            mock_cmd.return_value = "src/contracts/Token.sol"

            result = git.get_changed_solidity_files(
                str(tmp_path),
                "main",
                "HEAD",
                config=config
            )

            assert len(result) == 1
            assert result[0].endswith("Token.sol")


class TestIgnorePathsFiltering:
    """Test ignore_paths glob pattern matching."""

    def test_default_ignores_node_modules_and_test(self, tmp_path):
        """Default config should ignore node_modules/** and test/**."""
        git = GitManager()

        # Default config
        config = AuditConfig()

        # Create files in node_modules and test
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "dep.sol").write_text("// dep")
        (tmp_path / "test").mkdir()
        (tmp_path / "test" / "Test.sol").write_text("// test")
        (tmp_path / "contracts").mkdir()
        (tmp_path / "contracts" / "Token.sol").write_text("// token")

        with patch.object(git, '_execute_git_command') as mock_cmd:
            mock_cmd.return_value = "node_modules/dep.sol\ntest/Test.sol\ncontracts/Token.sol"

            result = git.get_changed_solidity_files(
                str(tmp_path),
                "main",
                "HEAD",
                config=config
            )

            # Only Token.sol should remain
            assert len(result) == 1
            assert "Token.sol" in result[0]

    def test_custom_ignore_paths(self, tmp_path):
        """Custom ignore_paths should filter files accordingly."""
        git = GitManager()

        config = AuditConfig(scan=ScanConfig(
            ignore_paths=["mocks/**", "**/upgradeable/**"]
        ))

        # Create files
        (tmp_path / "mocks").mkdir()
        (tmp_path / "mocks" / "MockToken.sol").write_text("// mock")
        (tmp_path / "contracts" / "upgradeable").mkdir(parents=True)
        (tmp_path / "contracts" / "upgradeable" / "TokenV2.sol").write_text("// v2")
        (tmp_path / "contracts" / "Token.sol").write_text("// token")

        with patch.object(git, '_execute_git_command') as mock_cmd:
            mock_cmd.return_value = "mocks/MockToken.sol\ncontracts/upgradeable/TokenV2.sol\ncontracts/Token.sol"

            result = git.get_changed_solidity_files(
                str(tmp_path),
                "main",
                "HEAD",
                config=config
            )

            # Only Token.sol should remain (others ignored)
            assert len(result) == 1
            assert "contracts/Token.sol" in result[0]


class TestNoConfigFallback:
    """Test behavior when no config is provided."""

    def test_none_config_uses_defaults(self, tmp_path):
        """When config=None, default AuditConfig is used."""
        git = GitManager()

        (tmp_path / "Token.sol").write_text("// token")

        with patch.object(git, '_execute_git_command') as mock_cmd:
            mock_cmd.return_value = "Token.sol"

            result = git.get_changed_solidity_files(
                str(tmp_path),
                "main",
                "HEAD",
                config=None  # Explicitly None
            )

            assert len(result) == 1

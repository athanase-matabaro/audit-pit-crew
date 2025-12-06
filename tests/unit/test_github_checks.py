"""
Unit tests for GitHubChecksManager and check run functionality.
"""
import pytest
from unittest.mock import patch, MagicMock

from src.core.github_checks import GitHubChecksManager


class TestGitHubChecksManager:
    """Test GitHubChecksManager initialization and setup."""

    def test_initialization(self):
        manager = GitHubChecksManager(
            token="test-token",
            repo_owner="test-owner",
            repo_name="test-repo"
        )
        
        assert manager.token == "test-token"
        assert manager.repo_owner == "test-owner"
        assert manager.repo_name == "test-repo"
        assert "test-owner/test-repo" in manager.base_url
        assert "Bearer test-token" in manager.headers["Authorization"]

    def test_check_name_constant(self):
        assert GitHubChecksManager.CHECK_NAME == "Audit Pit-Crew Security Scan"


class TestCreateCheckRun:
    """Test check run creation."""

    def test_create_check_run_success(self):
        manager = GitHubChecksManager("token", "owner", "repo")
        
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": 12345}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response
            
            check_run_id = manager.create_check_run(head_sha="abc123")
            
            assert check_run_id == 12345
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert "abc123" in str(call_kwargs)

    def test_create_check_run_failure(self):
        manager = GitHubChecksManager("token", "owner", "repo")
        
        with patch('requests.post') as mock_post:
            mock_post.side_effect = Exception("API Error")
            
            check_run_id = manager.create_check_run(head_sha="abc123")
            
            assert check_run_id is None


class TestReportScanResults:
    """Test scan result reporting and conclusion logic."""

    def setup_method(self):
        self.manager = GitHubChecksManager("token", "owner", "repo")

    def test_no_issues_returns_success(self):
        with patch.object(self.manager, 'complete_check_run', return_value=True) as mock_complete:
            conclusion = self.manager.report_scan_results(
                check_run_id=123,
                issues=[],
                block_on_severity="High"
            )
            
            assert conclusion == "success"
            mock_complete.assert_called_once()
            call_args = mock_complete.call_args
            assert call_args.kwargs['conclusion'] == "success"

    def test_high_issues_with_high_threshold_returns_failure(self):
        issues = [
            {"severity": "High", "type": "reentrancy", "file": "Token.sol", "line": 10, "tool": "Slither", "description": "Reentrancy vulnerability"}
        ]
        
        with patch.object(self.manager, 'complete_check_run', return_value=True) as mock_complete:
            conclusion = self.manager.report_scan_results(
                check_run_id=123,
                issues=issues,
                block_on_severity="High"
            )
            
            assert conclusion == "failure"

    def test_medium_issues_with_high_threshold_returns_neutral(self):
        issues = [
            {"severity": "Medium", "type": "unused-return", "file": "Token.sol", "line": 10, "tool": "Slither", "description": "Unused return value"}
        ]
        
        with patch.object(self.manager, 'complete_check_run', return_value=True) as mock_complete:
            conclusion = self.manager.report_scan_results(
                check_run_id=123,
                issues=issues,
                block_on_severity="High"
            )
            
            assert conclusion == "neutral"

    def test_critical_issues_always_block(self):
        issues = [
            {"severity": "Critical", "type": "arbitrary-send", "file": "Token.sol", "line": 10, "tool": "Slither", "description": "Arbitrary send"}
        ]
        
        with patch.object(self.manager, 'complete_check_run', return_value=True) as mock_complete:
            conclusion = self.manager.report_scan_results(
                check_run_id=123,
                issues=issues,
                block_on_severity="High"  # Critical > High, so should block
            )
            
            assert conclusion == "failure"

    def test_low_issues_with_medium_threshold_returns_neutral(self):
        issues = [
            {"severity": "Low", "type": "naming-convention", "file": "Token.sol", "line": 10, "tool": "Slither", "description": "Naming issue"}
        ]
        
        with patch.object(self.manager, 'complete_check_run', return_value=True) as mock_complete:
            conclusion = self.manager.report_scan_results(
                check_run_id=123,
                issues=issues,
                block_on_severity="Medium"
            )
            
            assert conclusion == "neutral"


class TestBuildAnnotations:
    """Test annotation building for inline PR feedback."""

    def setup_method(self):
        self.manager = GitHubChecksManager("token", "owner", "repo")

    def test_builds_annotations_from_issues(self):
        issues = [
            {"severity": "High", "type": "reentrancy", "file": "contracts/Token.sol", "line": 42, "tool": "Slither", "description": "Reentrancy"}
        ]
        
        annotations = self.manager._build_annotations(issues)
        
        assert len(annotations) == 1
        assert annotations[0]["path"] == "contracts/Token.sol"
        assert annotations[0]["start_line"] == 42
        assert annotations[0]["annotation_level"] == "failure"  # High severity

    def test_skips_issues_without_file_info(self):
        issues = [
            {"severity": "High", "type": "reentrancy", "file": "Unknown", "line": 0, "tool": "Slither", "description": "Reentrancy"}
        ]
        
        annotations = self.manager._build_annotations(issues)
        
        assert len(annotations) == 0

    def test_medium_severity_gets_warning_level(self):
        issues = [
            {"severity": "Medium", "type": "unused", "file": "Token.sol", "line": 10, "tool": "Slither", "description": "Unused"}
        ]
        
        annotations = self.manager._build_annotations(issues)
        
        assert annotations[0]["annotation_level"] == "warning"


class TestReportError:
    """Test error reporting."""

    def test_report_error_calls_complete_with_failure(self):
        manager = GitHubChecksManager("token", "owner", "repo")
        
        with patch.object(manager, 'complete_check_run', return_value=True) as mock_complete:
            result = manager.report_error(123, "Compilation failed")
            
            assert result is True
            mock_complete.assert_called_once()
            call_kwargs = mock_complete.call_args.kwargs
            assert call_kwargs['conclusion'] == "failure"
            assert "Compilation failed" in call_kwargs['summary']


class TestReportSkipped:
    """Test skipped status reporting."""

    def test_report_skipped_calls_complete_with_skipped(self):
        manager = GitHubChecksManager("token", "owner", "repo")
        
        with patch.object(manager, 'complete_check_run', return_value=True) as mock_complete:
            result = manager.report_skipped(123, "No Solidity files")
            
            assert result is True
            mock_complete.assert_called_once()
            call_kwargs = mock_complete.call_args.kwargs
            assert call_kwargs['conclusion'] == "skipped"

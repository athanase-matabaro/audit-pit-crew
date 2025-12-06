"""
Unit tests for BaseScanner severity filtering.
"""
import pytest

from src.core.analysis.base_scanner import BaseScanner


class DummyScanner(BaseScanner):
    """Concrete implementation for testing."""
    
    def run(self, target_path, files=None, config=None):
        return [], {}


class TestSeverityMapping:
    """Test SEVERITY_MAP values."""

    def test_severity_map_values(self):
        scanner = DummyScanner()

        assert scanner.SEVERITY_MAP['informational'] == 0
        assert scanner.SEVERITY_MAP['low'] == 1
        assert scanner.SEVERITY_MAP['medium'] == 2
        assert scanner.SEVERITY_MAP['high'] == 3
        assert scanner.SEVERITY_MAP['critical'] == 4


class TestFilterBySeverity:
    """Test _filter_by_severity method."""

    def setup_method(self):
        self.scanner = DummyScanner()
        self.issues = [
            {"type": "info-check", "severity": "Informational"},
            {"type": "low-check", "severity": "Low"},
            {"type": "medium-check", "severity": "Medium"},
            {"type": "high-check", "severity": "High"},
            {"type": "critical-check", "severity": "Critical"},
        ]

    def test_filter_min_low_includes_all_except_informational(self):
        result = self.scanner._filter_by_severity(self.issues, "Low")

        # Low filter should include Low, Medium, High, Critical (exclude Informational)
        assert len(result) == 4
        severities = [i["severity"] for i in result]
        assert "Informational" not in severities

    def test_filter_min_medium_includes_medium_high_critical(self):
        result = self.scanner._filter_by_severity(self.issues, "Medium")

        assert len(result) == 3
        severities = [i["severity"] for i in result]
        assert "Medium" in severities
        assert "High" in severities
        assert "Critical" in severities

    def test_filter_min_high_includes_high_critical(self):
        result = self.scanner._filter_by_severity(self.issues, "High")

        assert len(result) == 2
        severities = [i["severity"] for i in result]
        assert "High" in severities
        assert "Critical" in severities

    def test_filter_min_critical_only_critical(self):
        result = self.scanner._filter_by_severity(self.issues, "Critical")

        assert len(result) == 1
        assert result[0]["severity"] == "Critical"

    def test_filter_case_insensitive(self):
        result_upper = self.scanner._filter_by_severity(self.issues, "HIGH")
        result_lower = self.scanner._filter_by_severity(self.issues, "high")
        result_mixed = self.scanner._filter_by_severity(self.issues, "High")

        assert len(result_upper) == len(result_lower) == len(result_mixed) == 2

    def test_filter_unknown_severity_defaults_to_low(self):
        # Unknown severity in issue defaults to level 1 (informational)
        issues = [
            {"type": "unknown-sev", "severity": "SuperCritical"},  # Not in map -> defaults
        ]

        # min_severity "Low" (rank 1) should include unknown (defaults to rank 1)
        result = self.scanner._filter_by_severity(issues, "Low")
        # Unknown severity gets rank 1, Low is rank 1, so 1 >= 1 -> included
        assert len(result) == 1

    def test_filter_unknown_min_severity_defaults_to_low(self):
        # Unknown min_severity should default to Low (rank 1)
        result = self.scanner._filter_by_severity(self.issues, "NotASeverity")

        # Default to Low (rank 1) -> include all except Informational
        assert len(result) == 4

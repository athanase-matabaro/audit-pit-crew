"""
Unit tests for the remediation module.

Tests cover:
- Pattern lookups for Slither detectors
- Pattern lookups for Mythril SWC IDs
- RemediationSuggester enrichment
- Markdown formatting
"""

import pytest
from src.core.remediation import (
    RemediationSuggester,
    get_pattern_for_detector,
    get_pattern_for_swc,
    SLITHER_PATTERNS,
    MYTHRIL_PATTERNS,
)
from src.core.remediation.suggester import format_remediation_markdown, get_coverage_report


class TestSlitherPatternLookup:
    """Tests for Slither detector pattern lookups."""
    
    def test_reentrancy_eth_pattern_exists(self):
        """Test that reentrancy-eth has a pattern."""
        pattern = get_pattern_for_detector("reentrancy-eth")
        assert pattern is not None
        assert pattern.detector_id == "reentrancy-eth"
        assert "ReentrancyGuard" in pattern.fix_snippet
    
    def test_unchecked_transfer_pattern_exists(self):
        """Test that unchecked-transfer has a pattern."""
        pattern = get_pattern_for_detector("unchecked-transfer")
        assert pattern is not None
        assert "SafeERC20" in pattern.fix_snippet
    
    def test_tx_origin_pattern_exists(self):
        """Test that tx-origin has a pattern."""
        pattern = get_pattern_for_detector("tx-origin")
        assert pattern is not None
        assert "msg.sender" in pattern.fix_snippet
    
    def test_case_insensitive_lookup(self):
        """Test that lookups are case-insensitive."""
        pattern1 = get_pattern_for_detector("REENTRANCY-ETH")
        pattern2 = get_pattern_for_detector("reentrancy-eth")
        assert pattern1 is not None
        assert pattern1.detector_id == pattern2.detector_id
    
    def test_unknown_detector_returns_none(self):
        """Test that unknown detectors return None."""
        pattern = get_pattern_for_detector("unknown-detector-xyz")
        assert pattern is None
    
    def test_all_slither_patterns_have_required_fields(self):
        """Test that all Slither patterns have required fields."""
        for detector_id, pattern in SLITHER_PATTERNS.items():
            assert pattern.detector_id == detector_id
            assert pattern.title, f"{detector_id} missing title"
            assert pattern.summary, f"{detector_id} missing summary"
            assert pattern.fix_snippet, f"{detector_id} missing fix_snippet"
            assert pattern.references, f"{detector_id} missing references"


class TestMythrilPatternLookup:
    """Tests for Mythril SWC pattern lookups."""
    
    def test_swc_110_pattern_exists(self):
        """Test that SWC-110 (Exception State) has a pattern."""
        pattern = get_pattern_for_swc("110")
        assert pattern is not None
        assert "require" in pattern.fix_snippet.lower()
    
    def test_swc_107_pattern_exists(self):
        """Test that SWC-107 (Reentrancy) has a pattern."""
        pattern = get_pattern_for_swc("107")
        assert pattern is not None
        assert "ReentrancyGuard" in pattern.fix_snippet
    
    def test_swc_prefix_handling(self):
        """Test that SWC- prefix is handled correctly."""
        pattern1 = get_pattern_for_swc("SWC-110")
        pattern2 = get_pattern_for_swc("110")
        assert pattern1 is not None
        assert pattern1.detector_id == pattern2.detector_id
    
    def test_unknown_swc_returns_none(self):
        """Test that unknown SWC IDs return None."""
        pattern = get_pattern_for_swc("999")
        assert pattern is None
    
    def test_all_mythril_patterns_have_required_fields(self):
        """Test that all Mythril patterns have required fields."""
        for swc_id, pattern in MYTHRIL_PATTERNS.items():
            assert pattern.title, f"SWC-{swc_id} missing title"
            assert pattern.summary, f"SWC-{swc_id} missing summary"
            assert pattern.fix_snippet, f"SWC-{swc_id} missing fix_snippet"


class TestRemediationSuggester:
    """Tests for the RemediationSuggester class."""
    
    def test_enrich_slither_reentrancy_issue(self):
        """Test enriching a Slither reentrancy issue."""
        suggester = RemediationSuggester()
        issues = [{
            "tool": "Slither",
            "type": "reentrancy-eth",
            "severity": "High",
            "confidence": "High",
            "description": "Reentrancy in Contract.withdraw()",
            "file": "Contract.sol",
            "line": 42,
        }]
        
        enriched = suggester.enrich_issues(issues)
        
        assert len(enriched) == 1
        assert enriched[0]["remediation"] is not None
        assert "ReentrancyGuard" in enriched[0]["remediation"]["fix_snippet"]
    
    def test_enrich_mythril_issue_with_swc_id(self):
        """Test enriching a Mythril issue with SWC ID."""
        suggester = RemediationSuggester()
        issues = [{
            "tool": "Mythril",
            "type": "Exception State",
            "severity": "Low",
            "confidence": "Medium",
            "description": "Assert violation triggered",
            "file": "Contract.sol",
            "line": 10,
            "swc_id": "110",
        }]
        
        enriched = suggester.enrich_issues(issues)
        
        assert len(enriched) == 1
        assert enriched[0]["remediation"] is not None
        assert "require" in enriched[0]["remediation"]["fix_snippet"].lower()
    
    def test_enrich_mythril_issue_without_swc_id(self):
        """Test enriching a Mythril issue by guessing from type."""
        suggester = RemediationSuggester()
        issues = [{
            "tool": "Mythril",
            "type": "Reentrancy",
            "severity": "High",
            "confidence": "High",
            "description": "State change after external call",
            "file": "Contract.sol",
            "line": 20,
        }]
        
        enriched = suggester.enrich_issues(issues)
        
        assert len(enriched) == 1
        # Should guess SWC-107 from "Reentrancy" type
        assert enriched[0]["remediation"] is not None
    
    def test_unknown_issue_gets_no_remediation(self):
        """Test that unknown issues get no remediation."""
        suggester = RemediationSuggester()
        issues = [{
            "tool": "UnknownTool",
            "type": "unknown-issue-type",
            "severity": "High",
            "confidence": "High",
            "description": "Some issue",
            "file": "Contract.sol",
            "line": 1,
        }]
        
        enriched = suggester.enrich_issues(issues)
        
        assert len(enriched) == 1
        assert enriched[0]["remediation"] is None
    
    def test_stats_tracking(self):
        """Test that statistics are tracked correctly."""
        suggester = RemediationSuggester()
        issues = [
            {"tool": "Slither", "type": "reentrancy-eth", "severity": "High", "confidence": "High", "description": "Test", "file": "a.sol", "line": 1},
            {"tool": "Slither", "type": "unknown-type", "severity": "High", "confidence": "High", "description": "Test", "file": "b.sol", "line": 2},
            {"tool": "Mythril", "type": "Exception State", "swc_id": "110", "severity": "Low", "confidence": "Low", "description": "Test", "file": "c.sol", "line": 3},
        ]
        
        suggester.enrich_issues(issues)
        stats = suggester.get_stats()
        
        assert stats["total_processed"] == 3
        assert stats["suggestions_added"] == 2  # reentrancy-eth and SWC-110
        assert stats["no_pattern_found"] == 1  # unknown-type
    
    def test_reset_stats(self):
        """Test that stats can be reset."""
        suggester = RemediationSuggester()
        issues = [{"tool": "Slither", "type": "reentrancy-eth", "severity": "High", "confidence": "High", "description": "Test", "file": "a.sol", "line": 1}]
        
        suggester.enrich_issues(issues)
        assert suggester.get_stats()["total_processed"] == 1
        
        suggester.reset_stats()
        assert suggester.get_stats()["total_processed"] == 0


class TestMarkdownFormatting:
    """Tests for remediation Markdown formatting."""
    
    def test_format_remediation_with_all_fields(self):
        """Test formatting a complete remediation."""
        remediation = {
            "title": "Reentrancy Vulnerability",
            "summary": "Use ReentrancyGuard",
            "explanation": "Reentrancy allows recursive calls.",
            "fix_snippet": "// Use nonReentrant modifier",
            "references": ["https://example.com/1", "https://example.com/2"],
            "risk_context": "Can drain funds.",
        }
        
        markdown = format_remediation_markdown(remediation)
        
        assert "💡 Suggested Fix" in markdown
        assert "ReentrancyGuard" in markdown
        assert "```solidity" in markdown
        assert "https://example.com/1" in markdown
        assert "Can drain funds" in markdown
    
    def test_format_remediation_compact(self):
        """Test compact formatting."""
        remediation = {
            "title": "Test",
            "summary": "Short fix",
            "explanation": "Details",
            "fix_snippet": "// code",
            "references": ["https://example.com"],
            "risk_context": "Risk",
        }
        
        markdown = format_remediation_markdown(remediation, compact=True)
        
        assert "💡 **Fix:**" in markdown
        assert "```solidity" not in markdown  # No code block in compact mode
    
    def test_format_none_remediation(self):
        """Test formatting None remediation."""
        markdown = format_remediation_markdown(None)
        assert markdown == ""


class TestCoverageReport:
    """Tests for coverage reporting."""
    
    def test_coverage_report_structure(self):
        """Test that coverage report has expected structure."""
        report = get_coverage_report()
        
        assert "slither" in report
        assert "mythril" in report
        assert "total_patterns" in report
        
        assert "covered_detectors" in report["slither"]
        assert "count" in report["slither"]
        
        assert "covered_swc_ids" in report["mythril"]
        assert "count" in report["mythril"]
    
    def test_coverage_counts_are_positive(self):
        """Test that we have patterns defined."""
        report = get_coverage_report()
        
        assert report["slither"]["count"] > 0
        assert report["mythril"]["count"] > 0
        assert report["total_patterns"] > 10  # We have at least 10 patterns

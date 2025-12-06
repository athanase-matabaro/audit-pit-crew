"""
Remediation Suggester - Enriches security issues with fix suggestions.

This module takes raw security issues from scanners and adds remediation
information including fix snippets, explanations, and reference links.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import asdict

from src.core.remediation.patterns import (
    get_pattern_for_detector,
    get_pattern_for_swc,
    RemediationPattern,
)

logger = logging.getLogger(__name__)


class RemediationSuggester:
    """
    Enriches security issues with remediation suggestions.
    
    Takes issues from Slither, Mythril, etc. and adds fix suggestions,
    code snippets, and reference links based on the issue type.
    """
    
    def __init__(self):
        """Initialize the suggester with statistics tracking."""
        self.stats = {
            "total_processed": 0,
            "suggestions_added": 0,
            "no_pattern_found": 0,
        }
    
    def enrich_issues(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Add remediation suggestions to a list of issues.
        
        Args:
            issues: List of issue dictionaries from scanners
            
        Returns:
            List of issues enriched with 'remediation' field
        """
        enriched = []
        
        for issue in issues:
            enriched_issue = self._enrich_single_issue(issue)
            enriched.append(enriched_issue)
        
        logger.info(
            f"📚 Remediation: Processed {self.stats['total_processed']} issues, "
            f"added suggestions to {self.stats['suggestions_added']}, "
            f"no pattern for {self.stats['no_pattern_found']}"
        )
        
        return enriched
    
    def _enrich_single_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add remediation suggestion to a single issue.
        
        Args:
            issue: Single issue dictionary
            
        Returns:
            Issue dictionary with 'remediation' field added
        """
        self.stats["total_processed"] += 1
        
        # Create a copy to avoid mutating original
        enriched = issue.copy()
        
        # Get the tool and issue type
        tool = issue.get("tool", "").lower()
        issue_type = issue.get("type", "")
        
        # Try to find a matching pattern
        pattern = None
        
        if tool == "slither":
            pattern = get_pattern_for_detector(issue_type)
        elif tool == "mythril":
            # Mythril uses SWC IDs
            swc_id = issue.get("swc_id", "")
            if swc_id:
                pattern = get_pattern_for_swc(swc_id)
            else:
                # Try to match by issue type/title
                pattern = self._guess_mythril_pattern(issue_type)
        
        if pattern:
            enriched["remediation"] = self._pattern_to_dict(pattern)
            self.stats["suggestions_added"] += 1
            logger.debug(f"✅ Found remediation for {tool}:{issue_type}")
        else:
            enriched["remediation"] = None
            self.stats["no_pattern_found"] += 1
            logger.debug(f"⚠️ No remediation pattern for {tool}:{issue_type}")
        
        return enriched
    
    def _pattern_to_dict(self, pattern: RemediationPattern) -> Dict[str, Any]:
        """
        Convert a RemediationPattern to a dictionary for JSON serialization.
        
        Args:
            pattern: RemediationPattern object
            
        Returns:
            Dictionary representation
        """
        return {
            "title": pattern.title,
            "summary": pattern.summary,
            "explanation": pattern.explanation.strip(),
            "fix_snippet": pattern.fix_snippet.strip(),
            "references": pattern.references,
            "risk_context": pattern.risk_context,
        }
    
    def _guess_mythril_pattern(self, issue_type: str) -> Optional[RemediationPattern]:
        """
        Try to guess the SWC pattern from a Mythril issue type/title.
        
        Args:
            issue_type: The issue type string (e.g., "Exception State")
            
        Returns:
            RemediationPattern if matched, None otherwise
        """
        # Common Mythril issue type to SWC mappings
        type_to_swc = {
            "exception state": "110",
            "assert violation": "110",
            "integer overflow": "101",
            "integer underflow": "101",
            "reentrancy": "107",
            "external call": "107",
            "unchecked call": "104",
            "unprotected ether": "105",
            "selfdestruct": "106",
            "delegatecall": "112",
            "dos": "113",
            "denial of service": "113",
            "tx.origin": "115",
            "timestamp": "116",
            "block.timestamp": "116",
            "weak randomness": "116",
        }
        
        issue_lower = issue_type.lower()
        
        for keyword, swc_id in type_to_swc.items():
            if keyword in issue_lower:
                return get_pattern_for_swc(swc_id)
        
        return None
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about remediation suggestions.
        
        Returns:
            Dictionary with processing statistics
        """
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset the statistics counters."""
        self.stats = {
            "total_processed": 0,
            "suggestions_added": 0,
            "no_pattern_found": 0,
        }


def format_remediation_markdown(remediation: Dict[str, Any], compact: bool = False) -> str:
    """
    Format a remediation suggestion as Markdown for PR comments.
    
    Args:
        remediation: Remediation dictionary from enrich_issues
        compact: If True, use a more compact format
        
    Returns:
        Markdown string
    """
    if not remediation:
        return ""
    
    if compact:
        # Compact format: just summary and one reference
        lines = [
            f"💡 **Fix:** {remediation['summary']}",
        ]
        if remediation.get("references"):
            lines.append(f"📖 [Learn more]({remediation['references'][0]})")
        return "\n".join(lines)
    
    # Full format with code snippet
    lines = [
        "",
        "#### 💡 Suggested Fix",
        "",
        f"**{remediation['summary']}**",
        "",
        remediation['explanation'],
        "",
        "<details>",
        "<summary>📝 Code Pattern (click to expand)</summary>",
        "",
        "```solidity",
        remediation['fix_snippet'],
        "```",
        "",
        "</details>",
        "",
    ]
    
    # Add references
    if remediation.get("references"):
        lines.append("**📚 References:**")
        for ref in remediation["references"][:3]:  # Limit to 3 refs
            lines.append(f"- {ref}")
        lines.append("")
    
    # Add risk context
    if remediation.get("risk_context"):
        lines.append(f"⚠️ _{remediation['risk_context']}_")
        lines.append("")
    
    return "\n".join(lines)


def get_coverage_report() -> Dict[str, Any]:
    """
    Get a report of which detectors have remediation patterns.
    
    Returns:
        Dictionary with coverage statistics
    """
    from src.core.remediation.patterns import SLITHER_PATTERNS, MYTHRIL_PATTERNS
    
    return {
        "slither": {
            "covered_detectors": list(SLITHER_PATTERNS.keys()),
            "count": len(SLITHER_PATTERNS),
        },
        "mythril": {
            "covered_swc_ids": list(MYTHRIL_PATTERNS.keys()),
            "count": len(MYTHRIL_PATTERNS),
        },
        "total_patterns": len(SLITHER_PATTERNS) + len(MYTHRIL_PATTERNS),
    }

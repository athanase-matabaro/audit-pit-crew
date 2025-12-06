"""
GitHub Checks API integration for PR status reporting.

This module provides the "Blocker" functionality - the ability to make PRs
pass or fail based on security scan results. This transforms Audit Pit-Crew
from a notification bot into a quality gate.

GitHub API Reference:
- Create check run: POST /repos/{owner}/{repo}/check-runs
- Update check run: PATCH /repos/{owner}/{repo}/check-runs/{check_run_id}

Required GitHub App Permissions:
- checks: write
"""
import logging
import requests
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Type definitions for GitHub Check Run conclusions
CheckConclusion = Literal[
    "action_required",
    "cancelled",
    "failure",
    "neutral",
    "success",
    "skipped",
    "stale",
    "timed_out"
]

CheckStatus = Literal["queued", "in_progress", "completed"]


class GitHubChecksManager:
    """
    Manages GitHub Check Runs for PR status reporting.
    
    Check Runs appear in the PR's "Checks" tab and can block merging
    when configured with branch protection rules.
    """
    
    CHECK_NAME = "Audit Pit-Crew Security Scan"
    
    def __init__(self, token: str, repo_owner: str, repo_name: str):
        """
        Initialize the checks manager.
        
        Args:
            token: GitHub App installation token
            repo_owner: Repository owner (org or user)
            repo_name: Repository name
        """
        self.token = token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    
    def create_check_run(
        self,
        head_sha: str,
        status: CheckStatus = "in_progress",
        details_url: Optional[str] = None
    ) -> Optional[int]:
        """
        Create a new check run for a commit.
        
        This should be called at the start of the scan to show
        "in progress" status on the PR.
        
        Args:
            head_sha: The SHA of the commit to attach the check to
            status: Initial status (usually "in_progress")
            details_url: Optional URL to link to for more details
            
        Returns:
            The check run ID if successful, None otherwise
        """
        url = f"{self.base_url}/check-runs"
        
        payload: Dict[str, Any] = {
            "name": self.CHECK_NAME,
            "head_sha": head_sha,
            "status": status,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        
        if details_url:
            payload["details_url"] = details_url
        
        # Add output for in-progress status
        if status == "in_progress":
            payload["output"] = {
                "title": "Security scan in progress...",
                "summary": "Audit Pit-Crew is analyzing your code for security vulnerabilities."
            }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            check_run_id = response.json().get("id")
            logger.info(f"✅ Created check run {check_run_id} for commit {head_sha[:7]}")
            return check_run_id
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ Failed to create check run: {e.response.status_code}")
            logger.error(f"Response: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error creating check run: {e}")
            return None
    
    def complete_check_run(
        self,
        check_run_id: int,
        conclusion: CheckConclusion,
        title: str,
        summary: str,
        text: Optional[str] = None,
        annotations: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Complete a check run with a conclusion.
        
        Args:
            check_run_id: The ID of the check run to update
            conclusion: The final result ("success", "failure", "neutral", etc.)
            title: Short title for the check result
            summary: Markdown summary of the results
            text: Optional detailed markdown text
            annotations: Optional list of file annotations
            
        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/check-runs/{check_run_id}"
        
        output: Dict[str, Any] = {
            "title": title,
            "summary": summary,
        }
        
        if text:
            output["text"] = text
        
        if annotations:
            # GitHub limits to 50 annotations per request
            output["annotations"] = annotations[:50]
        
        payload = {
            "status": "completed",
            "conclusion": conclusion,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "output": output
        }
        
        try:
            response = requests.patch(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            logger.info(f"✅ Completed check run {check_run_id} with conclusion: {conclusion}")
            return True
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ Failed to complete check run: {e.response.status_code}")
            logger.error(f"Response: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error completing check run: {e}")
            return False
    
    def report_scan_results(
        self,
        check_run_id: int,
        issues: List[Dict[str, Any]],
        block_on_severity: str = "High",
        baseline_count: int = 0
    ) -> CheckConclusion:
        """
        Report scan results and determine pass/fail conclusion.
        
        This is the main method that determines whether the PR should
        be blocked based on the severity of issues found.
        
        Args:
            check_run_id: The check run ID to update
            issues: List of issues found in the scan
            block_on_severity: Minimum severity that causes failure
            baseline_count: Number of pre-existing issues (for context)
            
        Returns:
            The conclusion that was applied
        """
        # Severity ranking for comparison
        severity_rank = {
            "informational": 0,
            "low": 1,
            "medium": 2,
            "high": 3,
            "critical": 4
        }
        
        block_rank = severity_rank.get(block_on_severity.lower(), 3)  # Default to High
        
        # Count issues by severity
        severity_counts: Dict[str, int] = {
            "Critical": 0,
            "High": 0,
            "Medium": 0,
            "Low": 0,
            "Informational": 0
        }
        
        blocking_issues: List[Dict[str, Any]] = []
        
        for issue in issues:
            sev = issue.get("severity", "Low")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            
            issue_rank = severity_rank.get(sev.lower(), 1)
            if issue_rank >= block_rank:
                blocking_issues.append(issue)
        
        # Determine conclusion
        if blocking_issues:
            conclusion: CheckConclusion = "failure"
            title = f"❌ {len(blocking_issues)} blocking issue(s) found"
        elif issues:
            conclusion = "neutral"  # Issues exist but none blocking
            title = f"⚠️ {len(issues)} issue(s) found (none blocking)"
        else:
            conclusion = "success"
            title = "✅ No new security issues found"
        
        # Build summary
        summary_parts = []
        
        if issues:
            summary_parts.append("### Issue Summary\n")
            summary_parts.append("| Severity | Count |")
            summary_parts.append("|----------|-------|")
            for sev in ["Critical", "High", "Medium", "Low", "Informational"]:
                count = severity_counts.get(sev, 0)
                if count > 0:
                    emoji = "🔴" if sev in ["Critical", "High"] else "🟠" if sev == "Medium" else "🟡"
                    summary_parts.append(f"| {emoji} {sev} | {count} |")
            summary_parts.append("")
            
            if blocking_issues:
                summary_parts.append(f"\n**⛔ Blocking threshold:** `{block_on_severity}` or higher\n")
                summary_parts.append(f"Found **{len(blocking_issues)}** issue(s) that block this PR.\n")
            else:
                summary_parts.append(f"\n**ℹ️ Blocking threshold:** `{block_on_severity}` or higher\n")
                summary_parts.append("No issues meet the blocking threshold.\n")
        else:
            summary_parts.append("🎉 **Great job!** No new security vulnerabilities were introduced in this PR.\n")
            if baseline_count > 0:
                summary_parts.append(f"_Note: The baseline has {baseline_count} existing issue(s)._")
        
        summary = "\n".join(summary_parts)
        
        # Build detailed text with issue list
        text_parts = []
        if issues:
            text_parts.append("## Detailed Findings\n")
            for i, issue in enumerate(issues[:20], 1):  # Limit to 20 for readability
                sev = issue.get("severity", "Unknown")
                emoji = "🔴" if sev in ["Critical", "High"] else "🟠" if sev == "Medium" else "🟡"
                text_parts.append(f"### {i}. {emoji} [{sev}] {issue.get('type', 'Unknown')}")
                text_parts.append(f"**File:** `{issue.get('file', 'Unknown')}:{issue.get('line', 0)}`")
                text_parts.append(f"**Tool:** {issue.get('tool', 'Unknown')}")
                text_parts.append(f"\n> {issue.get('description', 'No description')[:500]}\n")
            
            if len(issues) > 20:
                text_parts.append(f"\n_...and {len(issues) - 20} more issue(s). See PR comment for full details._")
        
        text = "\n".join(text_parts) if text_parts else None
        
        # Build annotations for inline PR feedback
        annotations = self._build_annotations(issues[:50])  # GitHub limit
        
        # Complete the check run
        self.complete_check_run(
            check_run_id=check_run_id,
            conclusion=conclusion,
            title=title,
            summary=summary,
            text=text,
            annotations=annotations
        )
        
        return conclusion
    
    def _build_annotations(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Build GitHub annotations from issues for inline PR feedback.
        
        Annotations appear as inline comments on the changed files
        in the PR diff view.
        """
        annotations = []
        
        for issue in issues:
            file_path = issue.get("file", "")
            line = issue.get("line", 0)
            
            # Skip if we don't have file/line info
            if not file_path or file_path == "Unknown" or line == 0:
                continue
            
            severity = issue.get("severity", "Low")
            annotation_level = "failure" if severity in ["Critical", "High"] else "warning"
            
            annotations.append({
                "path": file_path,
                "start_line": line,
                "end_line": line,
                "annotation_level": annotation_level,
                "title": f"[{issue.get('tool', 'Scanner')}] {issue.get('type', 'Security Issue')}",
                "message": issue.get("description", "Security issue detected")[:65535]  # GitHub limit
            })
        
        return annotations
    
    def report_error(self, check_run_id: int, error_message: str) -> bool:
        """
        Report a scan error/failure.
        
        Args:
            check_run_id: The check run ID to update
            error_message: Description of what went wrong
            
        Returns:
            True if successful, False otherwise
        """
        return self.complete_check_run(
            check_run_id=check_run_id,
            conclusion="failure",
            title="❌ Security scan failed",
            summary=f"The security scan could not be completed.\n\n**Error:**\n```\n{error_message}\n```",
            text="Please check the CI/CD logs for more information. "
                 "This may be due to compilation errors in your Solidity code."
        )
    
    def report_skipped(self, check_run_id: int, reason: str) -> bool:
        """
        Report that the scan was skipped.
        
        Args:
            check_run_id: The check run ID to update
            reason: Why the scan was skipped
            
        Returns:
            True if successful, False otherwise
        """
        return self.complete_check_run(
            check_run_id=check_run_id,
            conclusion="skipped",
            title="⏭️ Security scan skipped",
            summary=f"The security scan was skipped.\n\n**Reason:** {reason}"
        )

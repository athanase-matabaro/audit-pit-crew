import requests
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class GitHubReporter:
    """
    Handles formatting and posting security scan results as a GitHub PR comment.
    """

    def __init__(self, token: str, repo_owner: str, repo_name: str, pr_number: int):
        self.token = token
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments"
        
        # FIX: Changed "token" to "Bearer"
        # GitHub App Installation Tokens require the "Bearer" prefix.
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.run_tag = "<!-- audit-pit-crew-report-v1 -->"

    def _format_report(self, issues: List[Dict[str, Any]], baseline_issue_count: int) -> str:
        """
        Formats the list of new issues into a comprehensive Markdown report.
        """
        if not issues:
            return (
                f"{self.run_tag}\n\n## 🛡️ Audit Pit-Crew Report\n\n"
                f"✅ **Scan Complete:** No new security issues were introduced in this PR.\n\n"
                f"ℹ️ _The baseline for the `main` branch contains **{baseline_issue_count}** existing issue(s)._"
            )

        report_header = (
            f"{self.run_tag}\n\n"
            f"## 🚨 Audit Pit-Crew Security Report\n\n"
            f"Found **{len(issues)}** new issue(s) in this PR. "
            f"The `main` branch baseline has **{baseline_issue_count}** existing issue(s)."
        )

        report = report_header
        
        severity_order = {'High': 3, 'Medium': 2, 'Low': 1}
        issues.sort(key=lambda x: severity_order.get(x['severity'], 0), reverse=True)

        for issue in issues:
            emoji = "🔴" if issue['severity'] == "High" else "🟠"
            
            report += f"""
---
### {emoji} {issue['severity']}: {issue['type']}
**File:** `{issue['file']}:{issue['line']}`
**Confidence:** {issue['confidence']}

> {issue['description'].strip().splitlines()[0]}
<details>
<summary>Click for Full Description</summary>

```text
{issue['description'].strip()}
```
</details>
"""
        return report

    def post_report(self, issues: List[Dict[str, Any]], baseline_issue_count: int = 0):
        """
        Formats the report and posts it as a comment to the GitHub Pull Request.
        Issues provided should ONLY be the NEW issues that passed filtering.
        """
        markdown_body = self._format_report(issues, baseline_issue_count)
        
        data = {"body": markdown_body}

        try:
            response = requests.post(self.base_url, headers=self.headers, json=data)
            response.raise_for_status() 
            logger.info(f"✅ Report posted successfully to {self.base_url}")
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ Failed to post report. HTTP Error: {e.response.status_code}")
            logger.error(f"GitHub API response: {e.response.text}")
            raise Exception("GitHub Reporter failed to post comment")
        except Exception as e:
            logger.error(f"❌ An unexpected error occurred: {e}")
            raise e
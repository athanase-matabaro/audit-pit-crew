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

    def _format_report(self, issues: List[Dict[str, Any]]) -> str:
        """
        Formats the list of issues into a comprehensive Markdown report.
        """
        # If the list is empty (Clean Scan), return a success message
        if not issues:
            return f"{self.run_tag}\n\n## 🛡️ Audit Pit-Crew Report\n\n✅ **Scan Complete:** No Critical or High severity issues found. Great job!"

        report = f"{self.run_tag}\n\n## 🚨 Audit Pit-Crew Security Report ({len(issues)} Findings)"
        
        # Sort issues by severity (High first)
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
\n
```text
{issue['description'].strip()}
```
</details>
"""
        return report

    def post_report(self, issues: List[Dict[str, Any]]):
        """
        Formats the issues and posts the comment to GitHub.
        """
        markdown_body = self._format_report(issues)
        
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
        
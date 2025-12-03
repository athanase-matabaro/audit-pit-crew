import requests
import logging
import os
from typing import List, Dict, Any, Optional

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

    def _format_report(self, issues: List[Dict[str, Any]], baseline_issue_count: int, log_paths: Optional[Dict[str, List[str]]] = None) -> str:
        """
        Formats the list of new issues into a comprehensive Markdown report,
        including links to raw tool output logs.
        """
        report_parts = []
        report_parts.append(f"{self.run_tag}\n\n## 🛡️ Audit Pit-Crew Report\n\n")

        if not issues:
            report_parts.append(
                f"✅ **Scan Complete:** No new security issues were introduced in this PR.\n\n"
                f"ℹ️ _The baseline for the `main` branch contains **{baseline_issue_count}** existing issue(s)._"
            )
        else:
            report_parts.append(
                f"## 🚨 Audit Pit-Crew Security Report\n\n"
                f"Found **{len(issues)}** new issue(s) in this PR. "
                f"The `main` branch baseline has **{baseline_issue_count}** existing issue(s)."
            )

            severity_order = {'High': 3, 'Medium': 2, 'Low': 1}
            issues.sort(key=lambda x: severity_order.get(x['severity'], 0), reverse=True)

            for issue in issues:
                emoji = "🔴" if issue['severity'] == "High" else "🟠"
                report_parts.append(f"""
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
""")
        
        # Add tool output logs if available
        if log_paths:
            report_parts.append("\n## 📝 Raw Tool Outputs\n\n<details><summary>Click to expand</summary>\n\n")
            for tool_name, paths in log_paths.items():
                report_parts.append(f"### {tool_name}\n")
                for path in paths:
                    report_parts.append(f"- `{os.path.basename(path)}`\n")
            report_parts.append("\n</details>")

        return "".join(report_parts)

    def post_report(self, issues: List[Dict[str, Any]], baseline_issue_count: int = 0, log_paths: Optional[Dict[str, List[str]]] = None):
        """
        Formats the report and posts it as a comment to the GitHub Pull Request.
        Issues provided should ONLY be the NEW issues that passed filtering.
        """
        markdown_body = self._format_report(issues, baseline_issue_count, log_paths)
        
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

    def post_error_report(self, error_message: str):
        """
        Posts a formatted error report to the GitHub Pull Request.
        """
        body = (
            f"{self.run_tag}\n\n"
            f"## ❌ Audit Pit-Crew Scan Failed\n\n"
            f"The security scan could not be completed due to a critical error.\n\n"
            f"<details>\n<summary>Error Details</summary>\n\n"
            f"```\n{error_message}\n```\n\n"
            f"</details>\n\n"
            f"Please check the CI/CD logs for more information."
        )
        self.post_comment(body)

    def post_comment(self, body: str):
        """
        Posts a raw string as a comment to the GitHub Pull Request.
        This is a generic method for posting any content.
        """
        data = {"body": body}
        try:
            response = requests.post(self.base_url, headers=self.headers, json=data)
            response.raise_for_status()
            logger.info(f"✅ Comment posted successfully to {self.base_url}")
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ Failed to post comment. HTTP Error: {e.response.status_code}")
            logger.error(f"GitHub API response: {e.response.text}")
        except Exception as e:
            logger.error(f"❌ An unexpected error occurred while posting comment: {e}")
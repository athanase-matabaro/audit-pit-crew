import logging
import json
from typing import Dict, Any
from celery import shared_task
from src.worker.celery_app import celery_app
from src.core.git_manager import GitManager
from src.core.analysis.scanner import SlitherScanner
from src.core.github_reporter import GitHubReporter

logger = logging.getLogger(__name__)

@celery_app.task(name="scan_repo_task", bind=True)
def scan_repo_task(self, repo_url: str, token: str = None, pr_context: Dict[str, Any] = None):
    """
    Background task that clones, scans, and posts results based on PR context.
    """

    logger.info(f"🚀 [Task {self.request.id}] Starting scan for: {repo_url}")

    # Initialize Tools
    git = GitManager()
    scanner = SlitherScanner()
    workspace = None

    try:
        # 1. Create Workspace & Clone
        workspace = git.create_workspace()
        # Assumes token is used for cloning, even if it's a dummy for public repos
        git.clone_repo(workspace, repo_url, token)

        # 2. Scan
        issues = scanner.run(workspace)
        logger.info(f"✅ [Task {self.request.id}] Scan complete. Found {len(issues)} issues.")

        # 3. Report Results (Streamlined Logic)
        # Report if we have PR context and a token, regardless of issue count, 
        # as the GitHubReporter handles the "No Issues" message internally.
        if pr_context and token:
            # All necessary conditions met: context and token.
            try:
                reporter = GitHubReporter(
                    token=token,
                    repo_owner=pr_context['owner'],
                    repo_name=pr_context['repo'],
                    pr_number=pr_context['pr_number']
                )
                
                # The reporter handles an empty 'issues' list by posting a "clean scan" message.
                reporter.post_report(issues) 
                logger.info(f"📤 [Task {self.request.id}] Successfully posted report to PR #{pr_context.get('pr_number')}.")
            except KeyError as e:
                # Catches cases where pr_context exists but is malformed (missing owner/repo/pr_number)
                logger.error(f"❌ [Task {self.request.id}] Reporting skipped: Malformed PR context (Missing key: {e}).")
            except Exception as e:
                # Catches GitHub API errors (e.g., invalid token, permissions)
                logger.error(f"❌ [Task {self.request.id}] GitHub Reporting failed: {str(e)}")

        else:
            # Log why reporting was skipped for clarity
            reason = []
            if not pr_context:
                reason.append("Missing PR context (Manual test or non-PR event).")
            if not token:
                reason.append("Missing GitHub token (Cannot authenticate reporting).")

            # This log is now only for infrastructure problems, not scan results.
            logger.info(f"ℹ️ [Task {self.request.id}] Skipping GitHub posting. Reason(s): {', '.join(reason)}")

        # 4. Return summary
        return {"status": "success", "issues_count": len(issues)}

    except Exception as e:
        logger.error(f"❌ [Task {self.request.id}] Failed: {str(e)}")
        # Adding retry logic as a best practice for transient network issues
        raise self.retry(exc=e, countdown=5, max_retries=3)

    finally:
        # 5. Cleanup
        if workspace:
            git.remove_workspace(workspace)
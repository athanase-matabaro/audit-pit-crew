import logging
import json
from typing import Dict, Any
from celery import shared_task
from src.worker.celery_app import celery_app
from src.core.git_manager import GitManager
from src.core.analysis.scanner import SlitherScanner
from src.core.github_reporter import GitHubReporter

logger = logging.getLogger(__name__)

from src.core.github_auth import GitHubAuth


logger = logging.getLogger(__name__)

@celery_app.task(name="scan_repo_task", bind=True)
def scan_repo_task(self, repo_url: str, pr_context: Dict[str, Any] = None):
    """
    Background task that clones, scans, and posts results based on PR context.
    """

    logger.info(f"🚀 [Task {self.request.id}] Starting scan for: {repo_url}")

    # Initialize Tools
    auth = GitHubAuth()
    git = GitManager()
    scanner = SlitherScanner()
    workspace = None
    
    try:
        # 1. Get Installation Token
        installation_id = pr_context.get("installation_id")
        if not installation_id:
            logger.error("❌ Missing installation_id in pr_context. Skipping.")
            return {"status": "error", "message": "Missing installation_id"}

        token = auth.get_installation_token(installation_id)
        if not token:
            logger.error("❌ Failed to get installation token. Skipping.")
            return {"status": "error", "message": "Failed to get installation token"}

        # 2. Create Workspace & Clone
        workspace = git.create_workspace()
        git.clone_repo(workspace, repo_url, token)

        # 3. Scan
        issues = scanner.run(workspace)
        logger.info(f"✅ [Task {self.request.id}] Scan complete. Found {len(issues)} issues.")

        # 4. Report Results
        if pr_context:
            try:
                reporter = GitHubReporter(
                    token=token,
                    repo_owner=pr_context['owner'],
                    repo_name=pr_context['repo'],
                    pr_number=pr_context['pr_number']
                )
                reporter.post_report(issues)
                logger.info(f"📤 [Task {self.request.id}] Successfully posted report to PR #{pr_context.get('pr_number')}.")
            except KeyError as e:
                logger.error(f"❌ [Task {self.request.id}] Reporting skipped: Malformed PR context (Missing key: {e}).")
            except Exception as e:
                logger.error(f"❌ [Task {self.request.id}] GitHub Reporting failed: {str(e)}")
        else:
            logger.info(f"ℹ️ [Task {self.request.id}] Skipping GitHub posting: Missing PR context.")

        # 5. Return summary
        return {"status": "success", "issues_count": len(issues)}

    except Exception as e:
        logger.error(f"❌ [Task {self.request.id}] Failed: {str(e)}")
        raise self.retry(exc=e, countdown=5, max_retries=3)

    finally:
        # 6. Cleanup
        if workspace:
            git.remove_workspace(workspace)
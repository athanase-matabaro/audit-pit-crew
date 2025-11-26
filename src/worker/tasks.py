import logging
import os
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
    Background task that clones, scans, and posts results.
    
    :param repo_url: The URL of the repository to clone.
    :param token: The GitHub token for cloning (if private) and reporting.
    :param pr_context: Dict containing reporting context (owner, repo, pr_number) for webhooks.
    """
    
    # We rely on the local path hack for testing.
    # Note: If you want to distinguish between the /test/scan endpoint and real webhooks,
    # it's cleaner to check for the presence of pr_context instead of a magic string in repo_url.
    is_local_test = pr_context is None
    
    logger.info(f"🚀 [Task {self.request.id}] Starting scan for: {repo_url}")
    
    # Initialize Tools
    git = GitManager()
    scanner = SlitherScanner()
    workspace = None
    
    try:
        # 1. Create Workspace & Clone
        workspace = git.create_workspace()
        
        # We assume the cloning token is required for all repos for simplicity here
        git.clone_repo(workspace, repo_url, token)
        
        # 2. Scan
        issues = scanner.run(workspace)
        
        logger.info(f"✅ [Task {self.request.id}] Scan complete. Found {len(issues)} issues.")
        
        # 3. Report Results
        
        # 🌟 FIX: Use the pr_context to determine reporting mode
        if pr_context and token and issues: # Only report if we have context, a token, AND issues
            
            # Safely extract context data using .get() or simple dict access
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
                # Handle cases where pr_context is missing expected keys
                logger.error(f"❌ [Task {self.request.id}] Reporting failed. Missing key in pr_context: {e}")
                # We will still proceed to clean up and return success status for the task
                
        elif is_local_test:
            # Local test mode (pr_context is None)
            logger.warning(f"⚠️ [Task {self.request.id}] Skipping GitHub posting (Local Test). Issues found: {len(issues)}")
            # Log full results for local testing verification
            logger.debug(f"Local Test Results: {json.dumps(issues, indent=2)}")
            
        else:
            # Real webhook but missing token or no issues found
            log_message = "Skipping GitHub posting (No issues found or missing token/pr_context)."
            logger.info(f"ℹ️ [Task {self.request.id}] {log_message}")


        # 4. Return summary
        return {"status": "success", "issues_count": len(issues)}

    except Exception as e:
        logger.error(f"❌ [Task {self.request.id}] Failed: {str(e)}")
        # Raise the exception so Celery marks the task as FAILED and stores the traceback
        raise self.retry(exc=e, countdown=5, max_retries=3) # Optional: Add retry logic

    finally:
        # 5. Cleanup
        if workspace:
            git.remove_workspace(workspace)
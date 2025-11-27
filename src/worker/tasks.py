import logging
import json
from typing import Dict, Any, List 
from celery import shared_task
from src.worker.celery_app import celery_app
from src.core.git_manager import GitManager
from src.core.analysis.scanner import SlitherScanner
from src.core.github_reporter import GitHubReporter
from src.core.github_auth import GitHubAuth
from src.core.github_client import GitHubClient 

logger = logging.getLogger(__name__)

# FIX: Add **kwargs to absorb the unexpected 'token' argument coming from the API
@celery_app.task(name="scan_repo_task", bind=True)
def scan_repo_task(self, repo_url: str, pr_context: Dict[str, Any] = None, **kwargs):
    """
    Background task that clones, scans, and posts results based on PR context.
    Now implements PR diff scanning for efficiency and relevance on Pull Requests.
    """

    logger.info(f"🚀 [Task {self.request.id}] Starting scan for: {repo_url}")

    # Initialize Tools
    auth = GitHubAuth()
    git = GitManager()
    scanner = SlitherScanner()
    workspace = None
    
    # Safely extract PR context variables
    pr_owner = pr_context.get('owner') if pr_context else None
    pr_repo = pr_context.get('repo') if pr_context else None
    pr_number = pr_context.get('pr_number') if pr_context else None
    base_ref = pr_context.get('base_ref') if pr_context else None
    head_ref = pr_context.get('head_ref') if pr_context else None
    installation_id = pr_context.get("installation_id") if pr_context else None

    try:
        # --- 1. Get Authentication & Context ---
        
        if not installation_id:
            logger.error("❌ Missing installation_id in pr_context. Skipping.")
            return {"status": "error", "message": "Missing installation_id"}

        token = auth.get_installation_token(installation_id)
        if not token:
            logger.error("❌ Failed to get installation token. Skipping.")
            return {"status": "error", "message": "Failed to get installation token"}

        # --- 2. Setup Git Environment ---
        workspace = git.create_workspace()
        
        # Determine if we run differential scanning (requires both base and head refs)
        is_pr_scan = bool(base_ref and head_ref)

        if is_pr_scan:
            logger.info("⚙️ Running differential PR scan. Cloning full history.")
            # For diff scanning, we need the full history to compare commits
            git.clone_repo(workspace, repo_url, token, shallow_clone=False)
            
            # Fetch and checkout the necessary references
            git.fetch_base_ref(workspace, base_ref)
            git.checkout_ref(workspace, head_ref)
            
            # Get list of files to scan
            files_to_scan = git.get_changed_solidity_files(workspace, base_ref, head_ref)

            if not files_to_scan:
                logger.info(f"ℹ️ [Task {self.request.id}] No Solidity files changed between {base_ref} and {head_ref}. Clean scan.")
                issues: List[Dict[str, Any]] = []
            else:
                # --- 3. Scan only changed files ---
                # Pass the list of files to the scanner
                issues = scanner.run(workspace, files=files_to_scan)

        else:
            logger.info("⚙️ Running standard full repository scan (not a PR).")
            # For full scan, a shallow clone is fine
            git.clone_repo(workspace, repo_url, token, shallow_clone=True)
            # --- 3. Run full scan ---
            issues = scanner.run(workspace)

        logger.info(f"✅ [Task {self.request.id}] Scan complete. Found {len(issues)} issues.")


        # --- 4. Report Results ---
        if pr_owner and pr_repo and pr_number:
            try:
                reporter = GitHubReporter(
                    token=token,
                    repo_owner=pr_owner,
                    repo_name=pr_repo,
                    pr_number=pr_number
                )
                # The reporter posts a 'Clean Scan' if issues is empty.
                reporter.post_report(issues)
                logger.info(f"📤 [Task {self.request.id}] Successfully posted report to PR #{pr_number}.")
            except Exception as e:
                logger.error(f"❌ [Task {self.request.id}] GitHub Reporting failed: {str(e)}")
        else:
            # This path is usually hit for non-PR scans where pr_context is None
            logger.info(f"ℹ️ [Task {self.request.id}] Skipping GitHub posting: Missing PR context (owner/repo/number).")

        # --- 6. Return summary ---
        return {"status": "success", "issues_count": len(issues)}

    # Robust error handling for both KeyError (missing context) and general exceptions
    except KeyError as e:
        logger.error(f"❌ [Task {self.request.id}] Failed: Malformed PR context or missing essential data (Key: {e}).")
        return {"status": "error", "message": f"Malformed PR context: {e}"}
    except Exception as e:
        logger.error(f"❌ [Task {self.request.id}] Failed: {str(e)}")
        # Use retry logic for transient network or API errors
        raise self.retry(exc=e, countdown=5, max_retries=3)

    finally:
        # --- 7. Cleanup ---
        if workspace:
            git.remove_workspace(workspace)
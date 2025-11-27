import logging
import json
from typing import Dict, Any, List # Added List import
from celery import shared_task
from src.worker.celery_app import celery_app
from src.core.git_manager import GitManager
from src.core.analysis.scanner import SlitherScanner
from src.core.github_reporter import GitHubReporter
from src.core.github_auth import GitHubAuth
# --- NEW IMPORT ---
from src.core.github_client import GitHubClient 

logger = logging.getLogger(__name__)

@celery_app.task(name="scan_repo_task", bind=True)
def scan_repo_task(self, repo_url: str, pr_context: Dict[str, Any] = None):
    """
    Background task that clones, scans, and posts results based on PR context.
    Now implements PR diff scanning for efficiency.
    """

    logger.info(f"🚀 [Task {self.request.id}] Starting scan for: {repo_url}")

    # Initialize Tools
    auth = GitHubAuth()
    git = GitManager()
    scanner = SlitherScanner()
    workspace = None
    
    try:
        # --- 1. Get Authentication & Context ---
        pr_owner = pr_context['owner']
        pr_repo = pr_context['repo']
        pr_number = pr_context['pr_number']
        installation_id = pr_context.get("installation_id")

        if not installation_id:
            logger.error("❌ Missing installation_id in pr_context. Skipping.")
            return {"status": "error", "message": "Missing installation_id"}

        token = auth.get_installation_token(installation_id)
        if not token:
            logger.error("❌ Failed to get installation token. Skipping.")
            return {"status": "error", "message": "Failed to get installation token"}

        # --- 2. Fetch Changed Files (Diff Logic) ---
        # Initialize the client with the necessary context and token
        client = GitHubClient(token, pr_owner, pr_repo, pr_number)
        
        # This list will contain file paths like ['contracts/token.sol', 'src/vulnerable.sol']
        changed_files: List[str] = client.get_changed_solidity_files()
        
        if not changed_files:
            logger.info("ℹ️ No Solidity files found in PR diff. Skipping scan but proceeding to report a clean status.")
            # Skip the heavy cloning/scanning but still post a 'clean' report
            issues = []
        else:
            # --- 3. Create Workspace & Clone (Only if files need scanning) ---
            workspace = git.create_workspace()
            # The token is needed for cloning private repositories
            git.clone_repo(workspace, repo_url, token)

            # --- 4. Scan Only Changed Files ---
            # IMPORTANT: We pass the list of files to the scanner here.
            issues = scanner.run(workspace, files=changed_files)
        
        logger.info(f"✅ [Task {self.request.id}] Scan complete. Found {len(issues)} issues.")

        # --- 5. Report Results ---
        # We report even if issues is empty to confirm the scan ran successfully
        if pr_context:
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
            except KeyError as e:
                logger.error(f"❌ [Task {self.request.id}] Reporting skipped: Malformed PR context (Missing key: {e}).")
            except Exception as e:
                logger.error(f"❌ [Task {self.request.id}] GitHub Reporting failed: {str(e)}")
        else:
            logger.info(f"ℹ️ [Task {self.request.id}] Skipping GitHub posting: Missing PR context.")

        # --- 6. Return summary ---
        return {"status": "success", "issues_count": len(issues)}

    except KeyError as e:
        logger.error(f"❌ [Task {self.request.id}] Failed: Malformed PR context (Missing key: {e}).")
        return {"status": "error", "message": f"Malformed PR context: {e}"}
    except Exception as e:
        logger.error(f"❌ [Task {self.request.id}] Failed: {str(e)}")
        # Use retry logic for transient network or API errors
        raise self.retry(exc=e, countdown=5, max_retries=3)

    finally:
        # --- 7. Cleanup ---
        if workspace:
            git.remove_workspace(workspace)
import logging
import json
import os
import fnmatch
from typing import Dict, Any, List 
from celery import shared_task
from src.worker.celery_app import celery_app
from src.core.git_manager import GitManager
from src.core.analysis.scanner import SlitherScanner, SlitherExecutionError
from src.core.github_reporter import GitHubReporter
from src.core.github_auth import GitHubAuth
from src.core.config import AuditConfig
from src.core.redis_client import RedisClient

logger = logging.getLogger(__name__)

@celery_app.task(name="scan_repo_task", bind=True)
def scan_repo_task(self, repo_url: str, pr_context: Dict[str, Any] = None, **kwargs):
    """
    Background task that clones, scans, and posts results. It operates in two modes:
    1. Differential Scan: For PRs, it scans changed files and reports only new issues
       by comparing against a stored baseline.
    2. Baseline Scan: For pushes to the main branch, it performs a full scan and updates
       the security baseline in Redis.
    """
    logger.info(f"🚀 [Task {self.request.id}] Starting scan for: {repo_url}")

    # Initialize tools
    auth = GitHubAuth()
    git = GitManager()
    scanner = SlitherScanner()
    redis_client = RedisClient()
    workspace = None
    
    pr_context = pr_context or {}
    pr_owner = pr_context.get('owner')
    pr_repo = pr_context.get('repo')
    installation_id = pr_context.get("installation_id")
    
    token = None
    
    try:
        # --- 1. Get Authentication & Setup Workspace ---
        if not installation_id:
            logger.error("❌ Missing installation_id in context. Skipping.")
            return {"status": "error", "message": "Missing installation_id"}

        token = auth.get_installation_token(installation_id)
        logger.info(f"🔑 Successfully fetched installation token for ID {installation_id}.")
        
        workspace = git.create_workspace()

        if pr_context:
            # --- DIFFERENTIAL SCAN (PR) ---
            logger.info("⚙️ Running differential PR scan...")

            pr_number = pr_context.get("pr_number")
            base_ref = pr_context.get("base_ref")
            head_sha = pr_context.get("head_sha") 

            if not all([pr_number, base_ref, head_sha]):
                logger.error("❌ Missing essential PR context (number, base_ref, or head_sha). Skipping.")
                return {"status": "error", "message": "Missing essential PR context"}

            git.clone_repo(workspace, repo_url, token, shallow_clone=False)
            git.fetch_base_ref(workspace, base_ref)
            git.checkout_ref(workspace, head_sha)
            
            audit_config = AuditConfig(workspace)
            
            changed_solidity_files = git.get_changed_files(
                workspace, 
                base_ref, 
                head_sha, 
                target_extensions=audit_config.get_target_extensions(),
                exclude_patterns=audit_config.get_exclude_patterns()
            )
            
            if not changed_solidity_files:
                logger.info("ℹ️ No target files changed in PR based on config. Skipping scan.")
                return {"status": "skipped", "message": "No target files changed"}

            logger.info(f"🔍 Starting Slither scan on: {workspace}")
            pr_issues = scanner.run(workspace, files=changed_solidity_files, config=audit_config)

            baseline_key = f"{pr_owner}:{pr_repo}"
            baseline_issues = redis_client.get_baseline_issues(baseline_key)
            
            # NOTE: Placeholder diffing logic
            new_issues = pr_issues
            
            logger.info(f"✅ Scan complete. Found {len(new_issues)} new issues ({len(pr_issues)} total issues in PR).")
            
            reporter = GitHubReporter(
                token=token, 
                repo_owner=pr_owner, 
                repo_name=pr_repo, 
                pr_number=pr_context['pr_number']
            )
            reporter.post_report(new_issues) 
            logger.info(f"📤 Successfully posted report for PR #{pr_context['pr_number']}.")

            return {"status": "success", "new_issues_found": len(new_issues)}

        else:
            # --- BASELINE SCAN (MAIN BRANCH) ---
            logger.info("⚙️ Running baseline scan for main branch...")
            git.clone_repo(workspace, repo_url, token, shallow_clone=True) 
            
            audit_config = AuditConfig(workspace)
            
            baseline_issues = scanner.run(workspace, config=audit_config)
            
            if pr_owner and pr_repo:
                baseline_key = f"{pr_owner}:{pr_repo}"
                redis_client.save_baseline_issues(baseline_key, baseline_issues)
                logger.info(f"✅ Baseline saved to Redis: {len(baseline_issues)} issues.")
            else:
                logger.warning("⚠️ Missing repository owner/name, cannot save baseline.")

            return {"status": "success", "baseline_issues_saved": len(baseline_issues)}

    except SlitherExecutionError as e:
        logger.error(f"⚔️ Slither scan failed during task {self.request.id}: {e}", exc_info=True)
        if pr_context and pr_owner and pr_repo and token:
            try:
                reporter = GitHubReporter(
                    token=token, 
                    repo_owner=pr_owner, 
                    repo_name=pr_repo, 
                    pr_number=pr_context['pr_number']
                )
                reporter.post_error_report(str(e))
                logger.info("✅ Posted Slither failure report to GitHub.")
            except Exception as post_e:
                logger.error(f"❌ Failed to post error report to GitHub during Slither failure handling: {post_e}")
        # Re-raise to mark the task as FAILED. Do not retry, as Slither errors are likely deterministic.
        raise e

    except Exception as e:
        logger.error(f"❌ [Task {self.request.id}] An unexpected error occurred: {str(e)}", exc_info=True)
        # Use retry logic for other transient network or API errors
        raise self.retry(exc=e, countdown=10, max_retries=2)

    finally:
        # --- 7. Cleanup ---
        if workspace:
            git.remove_workspace(workspace)
import logging
import json
import os
import fnmatch
from typing import Dict, Any, List 
from celery import shared_task
from src.worker.celery_app import celery_app
from src.core.git_manager import GitManager
from src.core.analysis.scanner import SlitherScanner
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

    try:
        if not installation_id:
            return {"status": "error", "message": "Missing installation_id"}

        token = auth.get_installation_token(installation_id)
        if not token:
            return {"status": "error", "message": "Failed to get installation token"}

        workspace = git.create_workspace()
        
        is_pr_scan = bool(pr_context.get('base_ref') and pr_context.get('head_ref'))

        if is_pr_scan:
            # --- DIFFERENTIAL SCAN (PULL REQUEST) ---
            logger.info("⚙️ Running differential PR scan...")
            git.clone_repo(workspace, repo_url, token, shallow_clone=False)
            audit_config = AuditConfig(workspace)
            
            base_ref = pr_context['base_ref']
            head_ref = pr_context['head_ref']
            git.fetch_base_ref(workspace, base_ref)
            git.checkout_ref(workspace, head_ref)
            
            all_changed_files = git.get_changed_solidity_files(workspace, base_ref, head_ref)
            files_to_scan = [f for f in all_changed_files if not any(fnmatch.fnmatch(os.path.relpath(f, workspace), p) for p in audit_config.ignore_files)]

            if not files_to_scan:
                logger.info("ℹ️ No Solidity files to scan after filtering. Clean scan.")
                pr_issues = []
            else:
                pr_issues = scanner.run(workspace, config=audit_config, files=files_to_scan)

            # Filter out pre-existing issues
            baseline_key = f"{pr_owner}:{pr_repo}"
            baseline_issues = redis_client.get_baseline_issues(baseline_key)
            baseline_fingerprints = {scanner.get_issue_fingerprint(iss) for iss in baseline_issues}
            
            new_issues = [iss for iss in pr_issues if scanner.get_issue_fingerprint(iss) not in baseline_fingerprints]
            
            logger.info(f"✅ Scan complete. Found {len(new_issues)} new issues ({len(pr_issues)} total issues in PR).")
            
            reporter = GitHubReporter(token=token, repo_owner=pr_owner, repo_name=pr_repo, pr_number=pr_context['pr_number'])
            reporter.post_report(new_issues, baseline_issue_count=len(baseline_issues))
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
            else:
                logger.warning("⚠️ Missing repository owner/name, cannot save baseline.")

            return {"status": "success", "baseline_issues_saved": len(baseline_issues)}

    except Exception as e:
        logger.error(f"❌ [Task {self.request.id}] An unexpected error occurred: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=10, max_retries=2)

    finally:
        if workspace:
            git.remove_workspace(workspace)
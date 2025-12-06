import logging
import json
import os
import fnmatch
from typing import Dict, Any, List, Optional
from celery import shared_task
from src.worker.celery_app import celery_app
from src.core.git_manager import GitManager
from src.core.analysis.scanner import UnifiedScanner, ToolExecutionError
from src.core.analysis.base_scanner import BaseScanner
from src.core.github_reporter import GitHubReporter
from src.core.github_checks import GitHubChecksManager
from src.core.github_auth import GitHubAuth
from src.core.config import AuditConfigManager
from src.core.redis_client import RedisClient
from src.core.remediation import RemediationSuggester

logger = logging.getLogger(__name__)

@celery_app.task(name="scan_repo_task", bind=True)
def scan_repo_task(self, repo_url: str, pr_context: Dict[str, Any] = None, **kwargs):
    """
    Background task that clones, scans, and posts results. It operates in two modes:
    1. Differential Scan: For PRs, it scans changed files and reports only new issues
       by comparing against a stored baseline. Creates GitHub Check Runs for PR status.
    2. Baseline Scan: For pushes to the main branch, it performs a full scan and updates
       the security baseline in Redis.
    """
    logger.info(f"🚀 [Task {self.request.id}] Starting scan for: {repo_url}")

    # Initialize tools
    auth = GitHubAuth()
    git = GitManager()
    scanner = UnifiedScanner()
    redis_client = RedisClient()
    workspace = None
    check_run_id = None  # Track check run for cleanup
    checks_manager = None
    
    pr_context = pr_context or {}
    pr_owner = pr_context.get('owner')
    pr_repo = pr_context.get('repo')
    installation_id = pr_context.get("installation_id")
    
    token = None
    all_log_paths = {}
    
    try:
        # --- 1. Get Authentication & Setup Workspace ---
        if not installation_id:
            logger.error("❌ Missing installation_id in context. Skipping.")
            return {"status": "error", "message": "Missing installation_id"}

        token = auth.get_installation_token(installation_id)
        
        workspace = git.create_workspace()
        repo_dir = None

        if pr_context:
            # --- DIFFERENTIAL SCAN (PR) ---
            logger.info("⚙️ Running differential PR scan...")

            pr_number = pr_context.get("pr_number")
            base_ref = pr_context.get("base_ref")
            head_sha = pr_context.get("head_sha") 

            if not all([pr_number, base_ref, head_sha]):
                logger.error("❌ Missing essential PR context (number, base_ref, or head_sha). Skipping.")
                return {"status": "error", "message": "Missing essential PR context"}

            # --- Create GitHub Check Run (The "Blocker") ---
            checks_manager = GitHubChecksManager(
                token=token,
                repo_owner=pr_owner,
                repo_name=pr_repo
            )
            check_run_id = checks_manager.create_check_run(head_sha=head_sha)
            if check_run_id:
                logger.info(f"📋 Created GitHub Check Run: {check_run_id}")
            else:
                logger.warning("⚠️ Failed to create check run. PR status will not be updated.")

            git.clone_repo(workspace, repo_url, token, shallow_clone=False)
            
            # Detect the actual repository root directory
            repo_dir = git.get_repo_dir(workspace)
            
            git.fetch_base_ref(repo_dir, base_ref)
            git.checkout_ref(repo_dir, head_sha)
            
            audit_config = AuditConfigManager.load_config(repo_dir)
            logger.info(
                f"Loaded config: min_severity={audit_config.scan.min_severity}, "
                f"block_on_severity={audit_config.scan.block_on_severity}, "
                f"contracts_path={audit_config.scan.contracts_path}, "
                f"ignore_paths={audit_config.scan.ignore_paths}"
            )
            
            changed_solidity_files = git.get_changed_solidity_files(
                repo_dir, 
                base_ref, 
                head_sha,
                config=audit_config
            )
            
            if not changed_solidity_files:
                logger.info("ℹ️ No target files changed in PR based on config. Skipping scan.")
                # Report skipped status to check run
                if check_run_id and checks_manager:
                    checks_manager.report_skipped(check_run_id, "No Solidity files changed in this PR")
                
                # Post informational PR comment
                try:
                    reporter = GitHubReporter(
                        token=token,
                        repo_owner=pr_owner,
                        repo_name=pr_repo,
                        pr_number=pr_context['pr_number']
                    )
                    config_summary = (
                        f"contracts_path: {audit_config.scan.contracts_path}\n"
                        f"ignore_paths: {audit_config.scan.ignore_paths}"
                    )
                    reporter.post_skipped_report(
                        reason="No Solidity (`.sol`) files were changed in this PR.",
                        config_summary=config_summary
                    )
                    logger.info("📤 Posted skipped scan notification to PR.")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to post skipped notification: {e}")
                
                return {"status": "skipped", "message": "No target files changed"}

            logger.info(f"🔍 Starting security scan on: {repo_dir}")
            pr_issues, all_log_paths = scanner.run(repo_dir, files=changed_solidity_files, config=audit_config.scan if audit_config else None)

            baseline_key = f"{pr_owner}:{pr_repo}"
            baseline_issues = redis_client.get_baseline_issues(baseline_key)
            
            new_issues = BaseScanner.diff_issues(pr_issues, baseline_issues)
            
            logger.info(f"✅ Scan complete. Found {len(new_issues)} new issues ({len(pr_issues)} total issues in PR).")
            
            # --- Enrich issues with remediation suggestions ---
            suggester = RemediationSuggester()
            enriched_issues = suggester.enrich_issues(new_issues)
            stats = suggester.get_stats()
            logger.info(
                f"💡 Remediation: {stats['suggestions_added']} of {stats['total_processed']} "
                f"issues have fix suggestions"
            )
            
            # --- Update GitHub Check Run with results ---
            check_conclusion = None
            if check_run_id and checks_manager:
                check_conclusion = checks_manager.report_scan_results(
                    check_run_id=check_run_id,
                    issues=enriched_issues,
                    block_on_severity=audit_config.scan.block_on_severity,
                    baseline_count=len(baseline_issues)
                )
                logger.info(f"📋 Check run conclusion: {check_conclusion}")
            
            # --- Post PR comment report with enriched issues ---
            reporter = GitHubReporter(
                token=token, 
                repo_owner=pr_owner, 
                repo_name=pr_repo, 
                pr_number=pr_context['pr_number']
            )
            reporter.post_report(enriched_issues, baseline_issue_count=len(baseline_issues), log_paths=all_log_paths) 
            logger.info(f"📤 Successfully posted report for PR #{pr_context['pr_number']}.")

            return {
                "status": "success", 
                "new_issues_found": len(new_issues),
                "check_conclusion": check_conclusion
            }

        else:
            # --- BASELINE SCAN (MAIN BRANCH) ---
            logger.info("⚙️ Running baseline scan for main branch...")
            git.clone_repo(workspace, repo_url, token, shallow_clone=True)
            
            # Detect the actual repository root directory
            repo_dir = git.get_repo_dir(workspace)
            
            audit_config = AuditConfigManager.load_config(repo_dir)
            logger.info(
                f"Loaded config: min_severity={audit_config.scan.min_severity}, "
                f"block_on_severity={audit_config.scan.block_on_severity}, "
                f"contracts_path={audit_config.scan.contracts_path}, "
                f"ignore_paths={audit_config.scan.ignore_paths}"
            )
            
            baseline_issues, all_log_paths = scanner.run(repo_dir, config=audit_config.scan if audit_config else None)
            
            if pr_owner and pr_repo:
                baseline_key = f"{pr_owner}:{pr_repo}"
                redis_client.save_baseline_issues(baseline_key, baseline_issues)
                logger.info(f"✅ Baseline saved to Redis: {len(baseline_issues)} issues.")
            else:
                logger.warning("⚠️ Missing repository owner/name, cannot save baseline.")

            return {"status": "success", "baseline_issues_saved": len(baseline_issues)}

    except ToolExecutionError as e:
        logger.error(f"⚔️ Security scan failed during task {self.request.id}: {e}", exc_info=True)
        
        # Report error to check run
        if check_run_id and checks_manager:
            checks_manager.report_error(check_run_id, str(e))
        
        if pr_context and pr_owner and pr_repo and token:
            try:
                reporter = GitHubReporter(
                    token=token, 
                    repo_owner=pr_owner, 
                    repo_name=pr_repo, 
                    pr_number=pr_context['pr_number']
                )
                reporter.post_error_report(str(e), log_paths=all_log_paths)
                logger.info("✅ Posted security scan failure report to GitHub.")
            except Exception as post_e:
                logger.error(f"❌ Failed to post error report to GitHub during security scan failure handling: {post_e}")
        # Re-raise to mark the task as FAILED. Do not retry, as tool errors are likely deterministic.
        raise e

    except Exception as e:
        logger.error(f"❌ [Task {self.request.id}] An unexpected error occurred: {str(e)}", exc_info=True)
        
        # Report error to check run
        if check_run_id and checks_manager:
            checks_manager.report_error(check_run_id, f"Unexpected error: {str(e)}")
        
        # Use retry logic for other transient network or API errors
        raise self.retry(exc=e, countdown=10, max_retries=2)

    finally:
        # --- 7. Cleanup ---
        if workspace:
            git.remove_workspace(workspace)
import os
import shutil
import tempfile
import subprocess
import logging
import fnmatch
from typing import Optional, List

logger = logging.getLogger(__name__)

class GitManager:
    """
    Handles secure cloning and cleanup of repositories, as well as specific 
    Git operations needed for differential scanning (fetch, checkout, diff).
    """

    def create_workspace(self) -> str:
        """
        Creates a temporary directory with a random name.
        Returns the absolute path.
        """
        # Prefix 'audit_pit_' makes it easy to find/debug if needed
        workspace = tempfile.mkdtemp(prefix="audit_pit_")
        logger.info(f"📂 Created workspace: {workspace}")
        return workspace

    def _execute_git_command(self, cmd: list, workspace: str, timeout: int = 60) -> str:
        """Helper to execute a git command, handle errors, and return stdout."""
        try:
            result = subprocess.run(
                cmd,
                cwd=workspace,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_output = e.stderr.strip()
            # Suppress token from error logs
            safe_cmd = [c.split('@')[-1] if 'token' in c else c for c in cmd]
            logger.error(f"❌ Git command failed: {' '.join(safe_cmd)} (Exit Code {e.returncode}): {error_output}")
            raise Exception(f"Git command failed: {error_output}")
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Git command timed out: {' '.join(cmd)}")
            raise Exception(f"Git command timed out: {' '.join(cmd)}")
        except Exception as e:
            logger.error(f"❌ An unexpected error occurred during git execution: {e}")
            raise Exception(f"An unexpected error occurred: {e}")

    def clone_repo(self, workspace: str, repo_url: str, token: Optional[str] = None, shallow_clone: bool = True):
        """
        Clones a repo into the workspace. It intelligently handles local paths
        (by cloning directly) vs. remote URLs (by injecting the token).
        
        The 'shallow_clone' flag allows switching between cloning the full history 
        (False) or only the latest commit (True, which is the default for performance).
        """
        final_url = repo_url
        
        # --- START FIX: URL SANITIZATION (From previous step) ---
        if final_url.startswith('['):
            logger.warning(f"⚠️ Detected corrupted Markdown link in repo_url: {final_url}. Sanitizing.")
            final_url = final_url.strip('[]() ')
            
            if '](' in final_url:
                final_url = final_url.split('](')[0]
            
            logger.info(f"✅ Sanitized repo_url to: {final_url}")
        # --- END FIX: URL SANITIZATION ---

        # Check if this is a local file path (not starting with http or git protocol)
        is_local_path = not (final_url.startswith("http") or final_url.startswith("git"))

        if is_local_path:
            # For local paths, clone directly without authentication.
            logger.info("⬇️ Cloning local repository (full history)...")
            clone_args = []
            
        else:
            # For remote URLs, inject the token for authentication if available.
            auth_url = final_url
            if token and "github.com" in final_url:
                # Inject the token for authenticated cloning over HTTPS
                protocol_end_index = final_url.find("://")
                if protocol_end_index != -1:
                    host_path = final_url[protocol_end_index + 3:]
                    # Format: https://x-access-token:{token}@{host}/{owner}/{repo}.git
                    auth_url = f"https://x-access-token:{token}@{host_path}"
                    logger.info(f"⬇️ Cloning remote repository (full history) with token: {host_path}")
                else:
                    logger.warning("⚠️ Could not detect protocol, attempting clone without token injection.")
            else:
                logger.info(f"⬇️ Cloning remote repository (full history): {final_url}")
            
            final_url = auth_url
            
            # Determine clone depth
            clone_args = ["--depth", "1"] if shallow_clone else []
            
        # The final git command
        cmd = ["git", "clone"] + clone_args + [final_url, "."]
        self._execute_git_command(cmd, workspace, timeout=120)
        logger.info("✅ Clone successful.")

    def checkout_ref(self, workspace: str, ref: str):
        """
        Checks out a specific branch, tag, or commit SHA.
        """
        logger.info(f"🚚 Checking out reference: {ref}")
        self._execute_git_command(["git", "checkout", ref], workspace, timeout=30)
        logger.info(f"✅ Checkout of reference '{ref}' successful.")


    def fetch_base_ref(self, workspace: str, base_ref: str):
        """
        Fetches the specific base branch/commit (e.g., 'main' or a base commit SHA)
        into the local repository for differential analysis.
        """
        logger.info(f"⬇️ Fetching base reference: {base_ref}")
        # Use the helper to execute and handle errors
        self._execute_git_command(["git", "fetch", "origin", base_ref], workspace, timeout=30)
        logger.info(f"✅ Fetch of base reference '{base_ref}' successful.")

    
    def get_changed_files(self, workspace: str, base_ref: str, head_ref: str, target_extensions: List[str], exclude_patterns: Optional[List[str]] = None) -> List[str]:
        """
        Compares the currently checked-out HEAD (head_ref) against a base_ref
        and returns a list of absolute paths to changed files matching the target extensions,
        while filtering out any files matching the exclusion patterns.
        """
        logger.info(f"🆚 Determining changed files between base '{base_ref}' and HEAD ('{head_ref}')...")
        
        # Use git diff --name-only to find files changed between the base and HEAD.
        cmd = ["git", "diff", "--name-only", base_ref, "HEAD"]
        
        output = self._execute_git_command(cmd, workspace, timeout=30)
        
        all_changed_files = output.splitlines() if output else []

        # Proactively filter out known artifacts that are not part of the source code
        if "dummy.sol" in all_changed_files:
            logger.warning("Found and removing 'dummy.sol' from changed files list.")
            all_changed_files = [f for f in all_changed_files if f != "dummy.sol"]

        logger.info(f"Found {len(all_changed_files)} total changed files before filtering.")

        exclude_patterns = exclude_patterns or []

        # Filter files based on two criteria:
        # 1. Must match one of the target_extensions.
        # 2. Must NOT match any of the exclude_patterns.
        filtered_files = []
        for f_path in all_changed_files:
            # Check for inclusion based on extension
            is_target = any(f_path.endswith(ext) for ext in target_extensions)
            
            # Check for exclusion based on pattern matching
            is_excluded = any(fnmatch.fnmatch(f_path, pattern) for pattern in exclude_patterns)
            
            if is_target and not is_excluded:
                filtered_files.append(os.path.join(workspace, f_path))

        logger.info(f"✅ Found {len(filtered_files)} changed files after applying extensions ({target_extensions}) and exclusions.")
        return filtered_files

    def remove_workspace(self, workspace: str):
        """
        Nuclear option: Deletes the folder and everything in it.
        """
        if os.path.exists(workspace):
            shutil.rmtree(workspace)
            logger.info(f"🧹 Wiped workspace: {workspace}")
        else:
            logger.warning(f"⚠️ Workspace not found during cleanup: {workspace}")
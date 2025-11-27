import os
import shutil
import tempfile
import subprocess
import logging
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
            raise Exception("Git command timed out")

    def clone_repo(self, workspace: str, repo_url: str, token: Optional[str] = None, shallow_clone: bool = True):
        """
        Clones a repo into the workspace. It intelligently handles local paths
        (by cloning directly) vs. remote URLs (by injecting the token).
        
        The 'shallow_clone' flag allows switching between cloning the full history 
        (False) or only the latest commit (True, which is the default for performance).
        """
        final_url = repo_url
        is_local_path = not (repo_url.startswith("http") or repo_url.startswith("git"))

        if is_local_path:
            logger.info("⬇️ Cloning local repository (full history)...")
            cmd = ["git", "clone", final_url, "."]
        
        else:
            if token and "DUMMY_INSTALLATION_TOKEN" not in token:
                # Format: https://x-access-token:TOKEN@github.com/user/repo
                clean_url = repo_url.replace("https://", "")
                final_url = f"https://x-access-token:{token}@{clean_url}"
            
            cmd = ["git", "clone", final_url, "."]

            if shallow_clone:
                cmd.insert(2, "--depth")
                cmd.insert(3, "1")
                logger.info(f"⬇️ Cloning remote repository (shallow depth 1): {final_url.split('@')[-1]}")
            else:
                logger.info(f"⬇️ Cloning remote repository (full history): {final_url.split('@')[-1]}")
        
        self._execute_git_command(cmd, workspace, timeout=120) 
        logger.info("✅ Clone successful.")

    def fetch_base_ref(self, workspace: str, base_ref: str):
        """
        Fetches the specific base branch/commit (e.g., 'main' or a base commit SHA)
        into the local repository for differential analysis.
        """
        logger.info(f"⬇️ Fetching base reference: {base_ref}")
        cmd = ["git", "fetch", "origin", base_ref]
        self._execute_git_command(cmd, workspace, timeout=30)
        logger.info(f"✅ Fetch of base reference '{base_ref}' successful.")

    def checkout_ref(self, workspace: str, ref: str):
        """
        Checks out a specific commit SHA or branch name.
        """
        logger.info(f"🔄 Checking out reference: {ref}")
        cmd = ["git", "checkout", ref]
        self._execute_git_command(cmd, workspace, timeout=30)
        logger.info(f"✅ Checkout of reference '{ref}' successful.")

    def get_last_commit_hash(self, workspace: str) -> str:
        """Returns the full commit hash of the current HEAD."""
        logger.info("🔍 Retrieving last commit hash (HEAD)...")
        cmd = ["git", "rev-parse", "HEAD"]
        commit_hash = self._execute_git_command(cmd, workspace)
        logger.info(f"✅ Found HEAD commit hash: {commit_hash}")
        return commit_hash
        
    def get_changed_solidity_files(self, workspace: str, base_ref: str, head_ref: str) -> List[str]:
        """
        Compares the currently checked-out HEAD (head_ref) against a base_ref
        and returns a list of absolute paths to changed files ending with a .sol extension.
        """
        # head_ref is provided for logging clarity, but the diff is against HEAD.
        logger.info(f"🆚 Determining changed files between base '{base_ref}' and HEAD ('{head_ref}')...")
        
        # Use git diff --name-only to find files changed between the base and HEAD.
        # HEAD is used because head_ref has already been checked out.
        cmd = ["git", "diff", "--name-only", base_ref, "HEAD"]
        
        output = self._execute_git_command(cmd, workspace, timeout=30)
        
        all_changed_files = output.splitlines() if output else []
        logger.info(f"Found {len(all_changed_files)} total changed files before filtering.")

        solidity_files = [
            os.path.join(workspace, f) for f in all_changed_files 
            if f.endswith('.sol') 
        ]

        logger.info(f"✅ Found {len(solidity_files)} changed Solidity files.")
        return solidity_files

    def remove_workspace(self, workspace: str):
        """
        Nuclear option: Deletes the folder and everything in it.
        """
        if os.path.exists(workspace):
            shutil.rmtree(workspace)
            logger.info(f"🧹 Wiped workspace: {workspace}")
        else:
            logger.warning(f"⚠️ Workspace not found during cleanup: {workspace}")
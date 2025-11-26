import os
import shutil
import tempfile
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class GitManager:
    """
    Handles secure cloning and cleanup of repositories.
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

    # In src/core/git_manager.py, replace the clone_repo method:

    def clone_repo(self, workspace: str, repo_url: str, token: Optional[str] = None):
        """
        Clones a repo into the workspace. It intelligently handles local paths
        (by cloning directly) vs. remote URLs (by injecting the token).
        """
        try:
            final_url = repo_url
            
            # Check if this is a local file path (not starting with http or git protocol)
            is_local_path = not (repo_url.startswith("http") or repo_url.startswith("git"))

            if is_local_path:
                # For local paths, clone directly without authentication.
                logger.info("⬇️ Cloning local repository...")
                cmd = ["git", "clone", final_url, "."]
            
            else:
                # For remote URLs, construct the Auth URL if a token exists
                if token and "DUMMY_INSTALLATION_TOKEN" not in token:
                    # Format: https://x-access-token:TOKEN@github.com/user/repo
                    clean_url = repo_url.replace("https://", "")
                    final_url = f"https://x-access-token:{token}@{clean_url}"
                
                logger.info(f"⬇️ Cloning remote repository: {final_url}")
                cmd = ["git", "clone", final_url, "."]

            # Run git clone
            subprocess.run(
                cmd,
                cwd=workspace,
                capture_output=True,
                text=True,
                check=True,  # Check is True now to catch git errors
                timeout=60
            )
            logger.info("✅ Clone successful.")

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Git Clone Failed: {e.stderr.decode().strip()}")
            raise Exception("Failed to clone repository")
        except subprocess.TimeoutExpired:
            logger.error("❌ Git Clone Timed Out")
            raise Exception("Clone timed out")

    def remove_workspace(self, workspace: str):
        """
        Nuclear option: Deletes the folder and everything in it.
        """
        if os.path.exists(workspace):
            shutil.rmtree(workspace)
            logger.info(f"🧹 Wiped workspace: {workspace}")
        else:
            logger.warning(f"⚠️ Workspace not found during cleanup: {workspace}")
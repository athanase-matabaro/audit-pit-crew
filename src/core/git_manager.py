import os
import shutil
import tempfile
import subprocess
import logging
import fnmatch
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.config import AuditConfig

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

    def get_repo_dir(self, workspace: str) -> str:
        """
        Detects the actual repository root directory within the workspace.
        
        After cloning, the repo might be in:
        - workspace/.  (if cloned with "." as target)
        - workspace/repo-name/  (if cloned with repo name)
        
        This method finds the directory containing .git
        
        Args:
            workspace: The workspace directory where the repo was cloned
            
        Returns:
            Absolute path to the repository root (containing .git)
            
        Raises:
            Exception if no .git directory is found
        """
        # First, check if workspace itself is the repo root
        if os.path.isdir(os.path.join(workspace, ".git")):
            logger.info(f"✅ Repository root detected at workspace: {workspace}")
            return workspace
        
        # Otherwise, check immediate subdirectories
        try:
            entries = os.listdir(workspace)
            for entry in entries:
                potential_repo = os.path.join(workspace, entry)
                if os.path.isdir(potential_repo) and os.path.isdir(os.path.join(potential_repo, ".git")):
                    logger.info(f"✅ Repository root detected at subdirectory: {potential_repo}")
                    return potential_repo
        except OSError as e:
            logger.error(f"❌ Error scanning workspace for repo root: {e}")
        
        # If no .git found, raise an error
        error_msg = f"Repository root (.git directory) not found in workspace: {workspace}"
        logger.error(f"❌ {error_msg}")
        raise Exception(error_msg)

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
        
        This method is resilient to cases where base_ref might be:
        - A branch name (e.g., 'main', 'rf-multitool-scanning-revision')
        - A commit SHA
        - A tag
        
        If the base_ref is not found in origin, it assumes it's a commit SHA
        and proceeds without fetching.
        """
        logger.info(f"⬇️ Fetching base reference: {base_ref}")
        try:
            # Try to fetch the base_ref from origin (handles branches, tags, etc.)
            self._execute_git_command(["git", "fetch", "origin", base_ref], workspace, timeout=30)
            logger.info(f"✅ Fetch of base reference '{base_ref}' successful.")
        except Exception as e:
            # If fetch fails, assume it's a commit SHA and it's already available locally
            # or it will fail later during diff, which is fine
            logger.warning(f"⚠️ Could not fetch base reference '{base_ref}' from origin: {str(e)[:100]}")
            logger.info(f"ℹ️ Assuming '{base_ref}' is a commit SHA or already available locally.")

    
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
                full_path = os.path.join(workspace, f_path)
                if os.path.exists(full_path):
                    filtered_files.append(full_path)
                else:
                    logger.debug(f"Skipping deleted or missing file: {f_path}")

        logger.info(f"✅ Found {len(filtered_files)} changed files after applying extensions ({target_extensions}) and exclusions.")
        return filtered_files

    def get_changed_solidity_files(
        self, 
        repo_dir: str,
        base_ref: str, 
        head_ref: str,
        config: Optional['AuditConfig'] = None
    ) -> List[str]:
        """
        Gets changed Solidity files (.sol) between base_ref and head_ref,
        applying contracts_path and ignore_paths filters from the config.
        
        Args:
            repo_dir: Actual repository root directory (containing .git)
            base_ref: Base reference (branch/commit) to compare against
            head_ref: Head reference (branch/commit) to compare to
            config: AuditConfig object containing filtering rules
            
        Returns:
            List of absolute paths to changed .sol files matching the config filters
        """
        if config is None:
            # Use default config if none provided
            from src.core.config import AuditConfig
            config = AuditConfig()
        
        logger.info(f"🆚 Determining changed Solidity files between base '{base_ref}' and HEAD ('{head_ref}')...")
        logger.info(f"📋 Using contracts_path: {config.scan.contracts_path}")
        logger.info(f"📂 Repository root: {repo_dir}")
        
        # First, try to resolve base_ref to a valid reference
        # This handles cases where base_ref is a branch that needs to be fetched as origin/base_ref
        resolved_base_ref = base_ref
        try:
            # Check if base_ref exists locally
            self._execute_git_command(["git", "rev-parse", resolved_base_ref], repo_dir, timeout=10)
        except Exception:
            # If not found, try origin/base_ref (for remote branches)
            try:
                logger.info(f"ℹ️ Base reference '{base_ref}' not found locally, trying 'origin/{base_ref}'...")
                self._execute_git_command(["git", "rev-parse", f"origin/{base_ref}"], repo_dir, timeout=10)
                resolved_base_ref = f"origin/{base_ref}"
                logger.info(f"✅ Resolved base reference to: {resolved_base_ref}")
            except Exception as e:
                logger.warning(f"⚠️ Could not resolve base reference: {e}")
                # Continue anyway - git diff will fail with a clearer error if truly invalid
        
        # Use git diff --name-only to find files changed between the base and HEAD
        # Run git commands from the actual repo_dir, not the workspace
        cmd = ["git", "diff", "--name-only", resolved_base_ref, "HEAD"]
        output = self._execute_git_command(cmd, repo_dir, timeout=30)
        
        all_changed_files = output.splitlines() if output else []
        logger.info(f"Found {len(all_changed_files)} total changed files before filtering.")
        
        # Filter files based on:
        # 1. Must be a .sol file
        # 2. Must be within contracts_path (or root if contracts_path is ".")
        # 3. Must NOT match any ignore_paths patterns
        filtered_files = []
        
        for f_path in all_changed_files:
            # Check if it's a Solidity file
            if not f_path.endswith('.sol'):
                continue
            
            # Check if it's within the contracts_path
            contracts_path = config.scan.contracts_path.rstrip('/')
            
            if contracts_path != ".":
                # If contracts_path is specified, ensure file is under that path
                if not f_path.startswith(contracts_path + "/") and f_path != contracts_path:
                    continue
                # Remove the contracts_path prefix for relative matching
                relative_to_contracts = f_path[len(contracts_path) + 1:] if f_path.startswith(contracts_path + "/") else f_path
            else:
                relative_to_contracts = f_path
            
            # Check if it matches any ignore patterns
            is_ignored = any(
                fnmatch.fnmatch(f_path, pattern) or fnmatch.fnmatch(relative_to_contracts, pattern)
                for pattern in config.scan.ignore_paths
            )
            
            if not is_ignored:
                # Build full path using repo_dir (the actual repository root)
                full_path = os.path.join(repo_dir, f_path)
                filtered_files.append(full_path)
        
        logger.info(
            f"✅ Found {len(filtered_files)} changed Solidity files after applying config filters "
            f"(contracts_path: {config.scan.contracts_path}, ignore_paths: {len(config.scan.ignore_paths)} patterns)."
        )
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
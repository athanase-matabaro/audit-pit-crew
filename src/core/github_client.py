import requests
import logging
from typing import List

logger = logging.getLogger(__name__)

class GitHubClient:
    """
    Client for non-authentication related GitHub API interactions, 
    such as fetching PR details or diffs.
    """

    def __init__(self, token: str, owner: str, repo: str, pr_number: int):
        self.token = token
        self.base_url = f"https://api.github.com/repos/{owner}/{repo}"
        self.pr_files_url = f"{self.base_url}/pulls/{pr_number}/files"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def get_changed_solidity_files(self) -> List[str]:
        """
        Fetches the list of files modified in the current Pull Request and filters 
        them to return only Solidity files (.sol).
        
        Returns:
            A list of file paths relative to the repository root.
        """
        logger.info(f"🔎 Fetching list of changed files for PR.")
        
        all_files = []
        page = 1
        
        # GitHub uses pagination, so we loop until we get an empty response
        while True:
            response = requests.get(
                self.pr_files_url, 
                headers=self.headers, 
                params={"page": page, "per_page": 100} # Max page size is 100
            )
            response.raise_for_status() # Raises HTTPError for bad status codes (4xx or 5xx)
            
            files_page = response.json()
            if not files_page:
                break # Exit loop if no more files
            
            all_files.extend(files_page)
            page += 1

        solidity_files = []
        for file in all_files:
            filename = file.get("filename", "")
            # We only care about files that are added (status 'added') or modified (status 'modified')
            if filename.endswith(".sol") and file.get("status") in ["added", "modified"]:
                solidity_files.append(filename)

        logger.info(f"✅ Found {len(solidity_files)} Solidity files in the PR diff.")
        
        return solidity_files
import time
import jwt
import requests
import logging
from typing import Optional
from src.config import settings # Assuming settings.GITHUB_APP_ID and GITHUB_PRIVATE_KEY_PATH exist

logger = logging.getLogger(__name__)

class GitHubAuth:
    """
    Handles generation of JWTs and fetching temporary Installation Access Tokens
    for the GitHub App to interact with the API.
    """

    def __init__(self):
        # Configuration setup (ensure these settings exist in your .env/config)
        self.app_id = settings.GITHUB_APP_ID
        self.private_key = self._load_private_key(settings.GITHUB_PRIVATE_KEY_PATH)

    def _load_private_key(self, path: str) -> str:
        """Loads the private key content from the specified file path."""
        try:
            with open(path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.critical(f"Private key file not found at: {path}")
            raise

    def _generate_jwt(self) -> str:
        """Generates a signed JWT valid for 10 minutes."""
        now = int(time.time())
        
        payload = {
            # issued at time
            'iat': now,
            # JWT expiration time (10 minutes maximum)
            'exp': now + (10 * 60),
            # GitHub App's identifier
            'iss': self.app_id
        }
        
        # Use RS256 algorithm with the private key
        encoded_jwt = jwt.encode(
            payload,
            self.private_key,
            algorithm='RS256'
        )
        return encoded_jwt

    def get_installation_token(self, installation_id: int) -> Optional[str]:
        """
        Exchanges a JWT for a short-lived Installation Access Token.
        This token is used by the worker to post comments.
        """
        jwt_token = self._generate_jwt()
        
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        
        # GitHub endpoint to request an installation token
        token_url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        
        try:
            response = requests.post(token_url, headers=headers)
            response.raise_for_status()
            token_data = response.json()
            
            # The token is valid for one hour
            logger.info(f"🔑 Successfully fetched installation token for ID {installation_id}.")
            return token_data.get("token")

        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ Failed to fetch installation token (HTTP {e.response.status_code}): {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error during token fetching: {e}")
            return None
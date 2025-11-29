import httpx
from typing import Optional, Dict, Any


class GitHubClient:
    """
    An asynchronous client for interacting with the GitHub API.

    This client is a wrapper around `httpx.AsyncClient` and is designed to
    handle authentication and make requests to the GitHub API endpoints.

    Attributes:
        base_url (str): The base URL for the GitHub API.
        _client (httpx.AsyncClient): The underlying async HTTP client.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = "https://api.github.com",
    ):
        """
        Initializes the GitHubClient.

        Args:
            token: An optional GitHub API token for authentication.
            base_url: The base URL of the GitHub API.
        """
        self.base_url = base_url
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self._client = httpx.AsyncClient(base_url=self.base_url, headers=headers)

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """
        Sends a GET request to the specified URL.

        Args:
            url: The API endpoint to request.
            **kwargs: Additional arguments to pass to the httpx client.

        Returns:
            The `httpx.Response` object.

        Raises:
            httpx.HTTPStatusError: If the request returns a 4xx or 5xx status code.
        """
        response = await self._client.get(url, **kwargs)
        response.raise_for_status()
        return response

    async def post(
        self, url: str, json: Optional[Dict[str, Any]] = None, **kwargs
    ) -> httpx.Response:
        """
        Sends a POST request to the specified URL.

        Args:
            url: The API endpoint to request.
            json: The JSON payload to send with the request.
            **kwargs: Additional arguments to pass to the httpx client.

        Returns:
            The `httpx.Response` object.

        Raises:
            httpx.HTTPStatusError: If the request returns a 4xx or 5xx status code.
        """
        response = await self._client.post(url, json=json, **kwargs)
        response.raise_for_status()
        return response

    async def __aenter__(self):
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager and close the client."""
        await self._client.aclose()

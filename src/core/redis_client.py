import redis
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from src.config import settings

logger = logging.getLogger(__name__)

class RedisClient:
    """
    A client for interacting with Redis to store and retrieve security baselines
    and scan results.
    """
    def __init__(self):
        """
        Initializes the Redis client using the connection URL from settings.
        """
        self.client: Optional[redis.Redis] = None
        try:
            # decode_responses=True ensures that Redis returns strings, not bytes.
            self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            self.client.ping()
            logger.info("✅ Successfully connected to Redis.")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"❌ Could not connect to Redis. Baseline functionality will be disabled. Error: {e}")
            self.client = None

    def save_baseline_issues(self, key: str, issues: List[Dict[str, Any]]):
        """
        Serializes a list of issues to JSON and saves them to Redis under a given key.

        Args:
            key: The key to store the baseline under (e.g., 'owner:repo').
            issues: A list of issue dictionaries to save.
        """
        if not self.client:
            logger.warning("⚠️ Redis client not available. Cannot save baseline.")
            return

        try:
            serialized_issues = json.dumps(issues)
            self.client.set(key, serialized_issues)
            logger.info(f"💾 Saved baseline for '{key}' with {len(issues)} issues.")
        except Exception as e:
            logger.error(f"❌ Failed to save baseline for key '{key}': {e}")

    def get_baseline_issues(self, key: str) -> List[Dict[str, Any]]:
        """
        Retrieves and deserializes a list of issues from Redis.

        Args:
            key: The key where the baseline is stored.

        Returns:
            A list of issue dictionaries, or an empty list if not found or on error.
        """
        if not self.client:
            logger.warning("⚠️ Redis client not available. Cannot retrieve baseline.")
            return []

        try:
            serialized_issues = self.client.get(key)
            if serialized_issues:
                issues = json.loads(serialized_issues)
                logger.info(f"✅ Loaded baseline for '{key}' with {len(issues)} issues.")
                return issues
            else:
                logger.info(f"ℹ️ No baseline found for key '{key}'. An empty baseline will be used.")
                return []
        except Exception as e:
            logger.error(f"❌ Failed to retrieve or parse baseline for key '{key}': {e}")
            return []

    def save_scan_result(self, repo_owner: str, repo_name: str, scan_result: Dict[str, Any], 
                         ttl_seconds: int = 604800):
        """
        Saves scan results for PDF report generation.
        
        Args:
            repo_owner: Repository owner/organization
            repo_name: Repository name
            scan_result: Full scan result data including issues, metadata, etc.
            ttl_seconds: Time to live in seconds (default: 7 days)
        """
        if not self.client:
            logger.warning("⚠️ Redis client not available. Cannot save scan result.")
            return False

        try:
            key = f"scan_result:{repo_owner}:{repo_name}"
            scan_result["saved_at"] = datetime.utcnow().isoformat()
            serialized = json.dumps(scan_result)
            self.client.setex(key, ttl_seconds, serialized)
            logger.info(f"💾 Saved scan result for '{repo_owner}/{repo_name}'")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to save scan result for '{repo_owner}/{repo_name}': {e}")
            return False

    def get_scan_result(self, repo_owner: str, repo_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the latest scan result for a repository.
        
        Args:
            repo_owner: Repository owner/organization
            repo_name: Repository name
            
        Returns:
            Scan result dictionary or None if not found
        """
        if not self.client:
            logger.warning("⚠️ Redis client not available. Cannot retrieve scan result.")
            return None

        try:
            key = f"scan_result:{repo_owner}:{repo_name}"
            serialized = self.client.get(key)
            if serialized:
                result = json.loads(serialized)
                logger.info(f"✅ Loaded scan result for '{repo_owner}/{repo_name}'")
                return result
            else:
                logger.info(f"ℹ️ No scan result found for '{repo_owner}/{repo_name}'")
                return None
        except Exception as e:
            logger.error(f"❌ Failed to retrieve scan result for '{repo_owner}/{repo_name}': {e}")
            return None

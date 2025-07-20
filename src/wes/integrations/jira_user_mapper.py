"""Jira user mapping functionality for email to username resolution."""

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..utils.exceptions import JiraIntegrationError
from ..utils.logging_config import get_logger


@dataclass
class JiraUser:
    """Represents a Jira user."""

    account_id: str
    email: str
    display_name: str
    username: Optional[str] = None
    active: bool = True


class UserMappingCache:
    """Cache for email to Jira user mappings."""

    def __init__(self, cache_dir: Optional[Path] = None, ttl_seconds: int = 86400):
        """Initialize cache.

        Args:
            cache_dir: Directory for persistent cache
            ttl_seconds: Time to live in seconds (default 24 hours)
        """
        self.logger = get_logger(__name__)
        self.ttl = ttl_seconds

        # Memory cache: email -> (username, timestamp)
        self.memory_cache: Dict[str, Tuple[str, float]] = {}

        # Persistent cache setup
        if cache_dir:
            self.cache_file = cache_dir / "user_mappings.json"
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self._load_persistent_cache()
        else:
            self.cache_file = None

    def _load_persistent_cache(self) -> None:
        """Load cache from disk."""
        if not self.cache_file or not self.cache_file.exists():
            return

        try:
            with open(self.cache_file, "r") as f:
                data = json.load(f)

            now = time.time()
            # Load only non-expired entries
            for email, (username, timestamp) in data.items():
                if now - timestamp < self.ttl:
                    self.memory_cache[email] = (username, timestamp)

            self.logger.debug(f"Loaded {len(self.memory_cache)} cached mappings")
        except Exception as e:
            self.logger.warning(f"Failed to load cache: {e}")

    def _save_persistent_cache(self) -> None:
        """Save cache to disk."""
        if not self.cache_file:
            return

        try:
            # Convert to JSON-serializable format
            data = {
                email: [username, timestamp]
                for email, (username, timestamp) in self.memory_cache.items()
            }

            with open(self.cache_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            self.logger.warning(f"Failed to save cache: {e}")

    def get(self, email: str) -> Optional[str]:
        """Get cached username for email."""
        if email not in self.memory_cache:
            return None

        username, timestamp = self.memory_cache[email]

        # Check if expired
        if time.time() - timestamp > self.ttl:
            del self.memory_cache[email]
            self._save_persistent_cache()
            return None

        return username

    def set(self, email: str, username: str) -> None:
        """Cache email to username mapping."""
        self.memory_cache[email] = (username, time.time())
        self._save_persistent_cache()

    def clear_expired(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired = [
            email
            for email, (_, timestamp) in self.memory_cache.items()
            if now - timestamp > self.ttl
        ]

        for email in expired:
            del self.memory_cache[email]

        if expired:
            self._save_persistent_cache()
            self.logger.debug(f"Cleared {len(expired)} expired cache entries")


class JiraUserMapper:
    """Maps email addresses to Jira usernames."""

    def __init__(self, jira_client, cache_dir: Optional[Path] = None):
        """Initialize mapper.

        Args:
            jira_client: JiraClient instance
            cache_dir: Directory for cache storage
        """
        self.logger = get_logger(__name__)
        self.jira_client = jira_client
        self.cache = UserMappingCache(cache_dir)

    async def map_emails_to_usernames(
        self, emails: List[str], fallback_to_prefix: bool = True
    ) -> Dict[str, str]:
        """Map email addresses to Jira usernames.

        Args:
            emails: List of email addresses
            fallback_to_prefix: Use email prefix if user not found

        Returns:
            Dictionary mapping email to username
        """
        mapping = {}
        uncached_emails = []

        # Check cache first
        for email in emails:
            cached_username = self.cache.get(email)
            if cached_username:
                mapping[email] = cached_username
                self.logger.debug(f"Cache hit for {email}")
            else:
                uncached_emails.append(email)

        if not uncached_emails:
            return mapping

        # Batch search for uncached emails
        self.logger.info(f"Searching Jira for {len(uncached_emails)} users")

        # Process in batches to avoid rate limits
        batch_size = 50
        for i in range(0, len(uncached_emails), batch_size):
            batch = uncached_emails[i : i + batch_size]

            try:
                batch_results = await self._search_users_batch(batch)

                for email, username in batch_results.items():
                    mapping[email] = username
                    self.cache.set(email, username)

            except Exception as e:
                self.logger.error(f"Failed to search users: {e}")

                # Fallback to email prefix if enabled
                if fallback_to_prefix:
                    for email in batch:
                        if email not in mapping and "@" in email:
                            username = email.split("@")[0]
                            mapping[email] = username
                            self.logger.warning(
                                f"Using email prefix fallback for {email}"
                            )

        return mapping

    async def _search_users_batch(self, emails: List[str]) -> Dict[str, str]:
        """Search for users by email in a single batch.

        Args:
            emails: List of email addresses

        Returns:
            Dictionary mapping email to username
        """
        mapping = {}

        # For standard Jira, we need to search each email individually
        # Some Jira instances don't support bulk email search
        search_tasks = []

        for email in emails:
            task = self._search_single_user(email)
            search_tasks.append(task)

        # Execute searches concurrently
        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        for email, result in zip(emails, results):
            if isinstance(result, Exception):
                self.logger.warning(f"Failed to find user for {email}: {result}")
                continue

            if result:
                mapping[email] = result

        return mapping

    async def _search_single_user(self, email: str) -> Optional[str]:
        """Search for a single user by email.

        Args:
            email: Email address to search

        Returns:
            Username if found, None otherwise
        """
        try:
            # Use Jira's user search API
            # Note: This requires appropriate permissions
            search_params = {"query": email, "maxResults": 5}

            # For Red Hat Jira, we might use a different approach
            if hasattr(self.jira_client, "is_redhat") and self.jira_client.is_redhat:
                # Red Hat Jira often uses the email prefix as username
                if "@redhat.com" in email:
                    username = email.split("@")[0]
                    # Verify the user exists
                    try:
                        user_data = await self.jira_client._make_request(
                            "GET", f"/rest/api/2/user?username={username}"
                        )
                        # Verify it's the correct user by email if possible
                        if user_data:
                            user_email = user_data.get("emailAddress", "")
                            if not user_email or user_email.lower() == email.lower():
                                return username
                    except Exception as e:
                        self.logger.debug(
                            f"Failed to verify Red Hat user {username}: {e}"
                        )

            # Try different API versions for user search
            # First try API v2 which is more widely supported
            try:
                # API v2 user picker endpoint
                response = await self.jira_client._make_request(
                    "GET", "/rest/api/2/user/picker", params={"query": email}
                )

                # Check if we got users
                if response and "users" in response:
                    for user in response["users"]:
                        # Check for exact email match
                        if user.get("emailAddress", "").lower() == email.lower():
                            return user.get("name") or user.get("key")

                    # If only one user returned, assume it's the right one
                    if len(response["users"]) == 1:
                        user = response["users"][0]
                        return user.get("name") or user.get("key")

            except Exception as e:
                self.logger.debug(f"API v2 user picker failed: {e}")

                # Fallback to API v3 if available
                try:
                    response = await self.jira_client._make_request(
                        "GET", "/rest/api/3/user/search", params=search_params
                    )

                    # Process API v3 response
                    if response and isinstance(response, list):
                        for user in response:
                            if user.get("emailAddress", "").lower() == email.lower():
                                return user.get("name") or user.get("accountId")

                        if len(response) == 1:
                            user = response[0]
                            return user.get("name") or user.get("accountId")

                except Exception as e:
                    self.logger.debug(f"API v3 user search failed: {e}")

        except Exception as e:
            self.logger.debug(f"User search failed for {email}: {e}")

        return None

    async def get_user_details(self, username: str) -> Optional[JiraUser]:
        """Get detailed information about a Jira user.

        Args:
            username: Jira username or account ID

        Returns:
            JiraUser object if found
        """
        try:
            response = await self.jira_client._make_request(
                "GET", f"/rest/api/2/user?username={username}"
            )

            return JiraUser(
                account_id=response.get("accountId", username),
                email=response.get("emailAddress", ""),
                display_name=response.get("displayName", username),
                username=response.get("name"),
                active=response.get("active", True),
            )

        except Exception as e:
            self.logger.error(f"Failed to get user details for {username}: {e}")
            return None

"""
Xquik Toolkit for X/Twitter data extraction.

Uses https://xquik.com - an API for X data and automation. Provides endpoints
for user profiles, user tweets, and following lists.

Docs: https://docs.xquik.com/api-reference/overview

Supports multiple API keys for load balancing.
"""

import json
import os
from typing import Any, Dict, List, Optional

import requests
from agno.tools import Toolkit
from agno.utils.log import logger


class XquikToolkit(Toolkit):
    """
    Toolkit for fetching X/Twitter data using Xquik.

    Set XQUIK_API_KEY for a single key, or XQUIK_API_KEYS for multiple
    comma-separated keys.
    """

    BASE_URL = "https://xquik.com/api/v1"

    def __init__(
        self, api_key: Optional[str] = None, api_keys: Optional[List[str]] = None
    ):
        super().__init__(name="xquik")

        self.base_url = os.getenv("XQUIK_BASE_URL", self.BASE_URL).rstrip("/")
        self.api_keys = []

        if api_keys:
            self.api_keys = api_keys
        elif api_key:
            self.api_keys = [api_key]
        else:
            keys_str = os.getenv("XQUIK_API_KEYS", "")
            if keys_str:
                self.api_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
            else:
                single_key = os.getenv("XQUIK_API_KEY")
                if single_key:
                    self.api_keys = [single_key]

        if self.api_keys:
            logger.info(f"✅ Xquik initialized with {len(self.api_keys)} API key(s)")
        else:
            logger.info("No XQUIK_API_KEY(S), Xquik disabled")

        self._key_index = 0

        self.register(self.get_user_info)
        self.register(self.get_user_tweets)
        self.register(self.get_user_followings)

    def _get_next_key(self) -> Optional[str]:
        """Get next API key using round-robin."""
        if not self.api_keys:
            return None
        key = self.api_keys[self._key_index % len(self.api_keys)]
        self._key_index += 1
        return key

    def is_available(self) -> bool:
        """Check if API key is configured."""
        return len(self.api_keys) > 0

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to Xquik."""
        if api_key is None:
            api_key = self._get_next_key()

        if not api_key:
            return {"status": "error", "message": "API key not configured"}

        headers = {"X-API-Key": api_key}
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = requests.get(
                url, headers=headers, params=params or {}, timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"Xquik request failed: {e}")
            return {"status": "error", "message": str(e)}

    def get_user_info(self, username: str) -> str:
        """
        Get user profile information.

        Args:
            username: X handle (without @)

        Returns:
            JSON string of profile info or error message
        """
        username = username.replace("@", "").strip()

        logger.info(f"Fetching profile for @{username} via Xquik...")

        result = self._make_request(f"x/users/{username}")

        if result.get("status") == "error" or result.get("error"):
            return (
                f"Error: {result.get('message', result.get('error', 'Unknown error'))}"
            )

        profile = {
            "username": result.get("username", username),
            "name": result.get("name", ""),
            "description": result.get("description", ""),
            "followers_count": result.get("followers", 0),
            "following_count": result.get("following", 0),
            "verified": result.get("verified", False),
            "location": result.get("location", ""),
            "created_at": result.get("createdAt", ""),
        }
        logger.info(f"✅ Retrieved profile for @{username}")
        return json.dumps(profile, indent=2)

    def get_user_tweets(
        self, username: str, max_tweets: int = 20, include_replies: bool = False
    ) -> str:
        """
        Get recent tweets from a user.

        Args:
            username: X handle (without @)
            max_tweets: Maximum number of tweets to retrieve
            include_replies: Whether to include replies

        Returns:
            JSON string of tweets or error message
        """
        username = username.replace("@", "").strip()

        logger.info(f"Fetching tweets for @{username} via Xquik...")

        all_tweets = []
        cursor = ""

        while len(all_tweets) < max_tweets:
            params = {
                "includeReplies": str(include_replies).lower(),
                "pageSize": min(100, max_tweets - len(all_tweets)),
            }
            if cursor:
                params["cursor"] = cursor

            result = self._make_request(f"x/users/{username}/tweets", params)

            if result.get("status") == "error" or result.get("error"):
                error_msg = result.get("message", result.get("error", "Unknown error"))
                if all_tweets:
                    break
                return f"Error: {error_msg}"

            for tweet in result.get("tweets", []):
                if len(all_tweets) >= max_tweets:
                    break
                all_tweets.append(
                    {
                        "id": tweet.get("id", ""),
                        "text": tweet.get("text", ""),
                        "created_at": tweet.get("createdAt", tweet.get("created", "")),
                        "retweet_count": tweet.get(
                            "retweetCount", tweet.get("retweet_count", 0)
                        ),
                        "like_count": tweet.get(
                            "likeCount", tweet.get("like_count", 0)
                        ),
                        "reply_count": tweet.get(
                            "replyCount", tweet.get("reply_count", 0)
                        ),
                        "view_count": tweet.get(
                            "viewCount", tweet.get("view_count", 0)
                        ),
                        "is_reply": tweet.get("isReply", tweet.get("is_reply", False)),
                    }
                )

            next_cursor = result.get("next_cursor", "")
            if (
                not result.get("has_next_page")
                or not next_cursor
                or next_cursor == cursor
            ):
                break
            cursor = next_cursor

        logger.info(f"✅ Retrieved {len(all_tweets)} tweets for @{username}")
        return json.dumps(all_tweets, indent=2)

    def get_user_followings(
        self,
        username: str,
        max_users: int = 100,
        verified_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get list of users that a user follows.

        Args:
            username: X handle (without @)
            max_users: Maximum number of followings to retrieve
            verified_only: Only return verified users

        Returns:
            List of user profile dicts
        """
        username = username.replace("@", "").strip()

        logger.info(f"Fetching followings for @{username} via Xquik...")

        all_users = []
        cursor = ""

        while len(all_users) < max_users:
            params = {"pageSize": max(20, min(200, max_users - len(all_users)))}
            if cursor:
                params["cursor"] = cursor

            result = self._make_request(f"x/users/{username}/following", params)

            if result.get("status") == "error" or result.get("error"):
                error_msg = result.get("message", result.get("error", "Unknown error"))
                logger.warning(f"Failed to get Xquik followings: {error_msg}")
                break

            for user in result.get("users", []):
                if len(all_users) >= max_users:
                    break

                if verified_only and not user.get("verified", False):
                    continue

                all_users.append(
                    {
                        "username": user.get("username", ""),
                        "name": user.get("name", ""),
                        "description": user.get("description", ""),
                        "verified": user.get("verified", False),
                        "followers_count": user.get("followers", 0),
                    }
                )

            next_cursor = result.get("next_cursor", "")
            if (
                not result.get("has_next_page")
                or not next_cursor
                or next_cursor == cursor
            ):
                break
            cursor = next_cursor

        logger.info(f"✅ Retrieved {len(all_users)} followings for @{username}")
        return all_users


def get_xquik_toolkit() -> Optional[XquikToolkit]:
    """Get an initialized XquikToolkit if available."""
    toolkit = XquikToolkit()
    return toolkit if toolkit.is_available() else None

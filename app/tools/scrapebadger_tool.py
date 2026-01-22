"""
ScrapeBadger Toolkit for X/Twitter data extraction.

Uses https://scrapebadger.com - "The API that never misses"
Provides endpoints for:
- User profiles
- User tweets
- User followings
- Search

Pricing: Per credit
Docs: https://scrapebadger.com/sdks

Supports multiple API keys for load balancing.
"""
import os
import asyncio
import json
import random
from typing import List, Dict, Any, Optional
from agno.tools import Toolkit
from agno.utils.log import logger
from scrapebadger import ScrapeBadger

class ScrapeBadgerToolkit(Toolkit):
    """
    Toolkit for scraping X/Twitter using ScrapeBadger service.
    
    Supports multiple API keys for load balancing.
    Set SCRAPEBADGER_API_KEY for single key, or
    SCRAPEBADGER_API_KEYS (comma-separated) for multiple keys.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_keys: Optional[List[str]] = None):
        super().__init__(name="scrapebadger")
        
        # Support multiple API keys for load balancing
        self.api_keys = []
        
        if api_keys:
            self.api_keys = api_keys
        elif api_key:
            self.api_keys = [api_key]
        else:
            # Check for comma-separated keys first
            keys_str = os.getenv("SCRAPEBADGER_API_KEYS", "")
            if keys_str:
                self.api_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
            else:
                # Fall back to single key
                single_key = os.getenv("SCRAPEBADGER_API_KEY")
                if single_key:
                    self.api_keys = [single_key]
        
        if self.api_keys:
            logger.info(f"✅ ScrapeBadger initialized with {len(self.api_keys)} API key(s)")
        else:
            logger.info("No SCRAPEBADGER_API_KEY(S), ScrapeBadger disabled")
        
        self._key_index = 0  # For round-robin
        
        # Register tools
        self.register(self.get_user_profile)
        self.register(self.get_user_tweets)
        self.register(self.get_user_followings)
    
    def _get_next_key(self) -> str:
        """Get next API key using round-robin."""
        if not self.api_keys:
            return None
        key = self.api_keys[self._key_index % len(self.api_keys)]
        self._key_index += 1
        return key
    
    def _get_random_key(self) -> str:
        """Get random API key for load balancing."""
        if not self.api_keys:
            return None
        return random.choice(self.api_keys)
    
    def is_available(self) -> bool:
        """Check if API key is configured."""
        return len(self.api_keys) > 0

    async def _get_profile_async(self, username: str, api_key: str) -> Dict[str, Any]:
        """Async helper to get profile."""
        async with ScrapeBadger(api_key=api_key) as client:
            return await client.twitter.users.get_by_username(username)

    async def _get_tweets_async(self, query: str, limit: int, api_key: str) -> List[Any]:
        """Async helper to get tweets."""
        tweets = []
        async with ScrapeBadger(api_key=api_key) as client:
            async for tweet in client.twitter.tweets.search_all(query, max_items=limit):
                tweets.append(tweet)
        return tweets

    async def _get_following_async(self, username: str, max_users: int, api_key: str) -> List[Any]:
        """Async helper to get users that username follows."""
        users = []
        async with ScrapeBadger(api_key=api_key) as client:
            async for user in client.twitter.users.get_following_all(username, max_items=max_users):
                users.append(user)
        return users

    async def _get_highlights_async(self, user_id: str, api_key: str) -> List[Any]:
        """Async helper to get user highlights/pinned tweets."""
        highlights = []
        async with ScrapeBadger(api_key=api_key) as client:
            async for tweet in client.twitter.users.get_highlights(user_id, max_items=10):
                highlights.append(tweet)
        return highlights

    def get_user_highlights(self, user_id: str, max_items: int = 10) -> str:
        """
        Get highlighted/pinned tweets for a user via ScrapeBadger.
        
        Args:
            user_id: Numeric Twitter user ID (not username)
            max_items: Maximum number of highlights to retrieve
            
        Returns:
            JSON string of highlighted tweets or error message
        """
        if not self.is_available():
            return "Error: ScrapeBadger API key not configured"

        api_key = self._get_next_key()
        logger.info(f"Fetching highlights for user {user_id} via ScrapeBadger...")
        
        try:
            highlights_data = asyncio.run(self._get_highlights_async(user_id, api_key))
            
            all_highlights = []
            for tweet in highlights_data:
                tweet_data = self._extract_tweet_data(tweet)
                all_highlights.append(tweet_data)

            logger.info(f"✅ Retrieved {len(all_highlights)} highlights for user {user_id}")
            return json.dumps(all_highlights, indent=2)

        except Exception as e:
            logger.warning(f"ScrapeBadger highlights fetch failed: {e}")
            return f"Error: {str(e)}"

    def get_enriched_profile(self, username: str, max_tweets: int = 30) -> Dict[str, Any]:
        """
        Get enriched profile data including profile info, highlights, and recent tweets.
        
        This is designed for high-quality skill generation.
        
        Args:
            username: X handle (without @)
            max_tweets: Maximum tweets to fetch
            
        Returns:
            Dict with 'profile', 'highlights', 'tweets' keys or None if failed
        """
        username = username.replace("@", "").strip()
        logger.info(f"Fetching enriched profile for @{username}...")
        
        result = {
            "profile": None,
            "highlights": [],
            "tweets": []
        }
        
        # 1. Get profile info
        profile_json = self.get_user_profile(username)
        if profile_json and "Error" not in profile_json:
            try:
                result["profile"] = json.loads(profile_json)
            except json.JSONDecodeError:
                pass
        
        # 2. Get highlights (need user_id from profile)
        if result["profile"] and result["profile"].get("user_id"):
            user_id = result["profile"]["user_id"]
            highlights_json = self.get_user_highlights(user_id)
            if highlights_json and "Error" not in highlights_json:
                try:
                    result["highlights"] = json.loads(highlights_json)
                except json.JSONDecodeError:
                    pass
        
        # 3. Get recent tweets
        tweets_json = self.get_user_tweets(username, max_tweets=max_tweets)
        if tweets_json and "Error" not in tweets_json:
            try:
                result["tweets"] = json.loads(tweets_json)
            except json.JSONDecodeError:
                pass
        
        return result

    def _extract_tweet_data(self, tweet) -> Dict[str, Any]:
        """Extract tweet data handling different response structures."""
        # Try flattened structure first (from search_all)
        if hasattr(tweet, 'text') or hasattr(tweet, 'full_text'):
            return {
                "id": getattr(tweet, 'id_str', getattr(tweet, 'id', '')),
                "text": getattr(tweet, 'full_text', getattr(tweet, 'text', '')),
                "created_at": getattr(tweet, 'created_at', ''),
                "retweet_count": getattr(tweet, 'retweet_count', 0),
                "like_count": getattr(tweet, 'favorite_count', getattr(tweet, 'like_count', 0)),
                "reply_count": getattr(tweet, 'reply_count', 0),
                "view_count": getattr(tweet, 'view_count', 0),
                "is_reply": getattr(tweet, 'in_reply_to_status_id_str', None) is not None,
                "username": getattr(tweet, 'username', getattr(tweet, 'screen_name', '')),
            }
        # Try legacy nested structure
        elif hasattr(tweet, 'legacy'):
            legacy = tweet.legacy
            return {
                "id": getattr(legacy, 'id_str', ''),
                "text": getattr(legacy, 'full_text', ''),
                "created_at": getattr(legacy, 'created_at', ''),
                "retweet_count": getattr(legacy, 'retweet_count', 0),
                "like_count": getattr(legacy, 'favorite_count', 0),
                "reply_count": getattr(legacy, 'reply_count', 0),
                "view_count": 0,
                "is_reply": getattr(legacy, 'in_reply_to_status_id_str', None) is not None,
                "username": getattr(legacy, 'screen_name', ''),
            }
        # Fallback - try to get whatever we can
        else:
            logger.warning(f"Unknown tweet structure: {type(tweet)}")
            return {
                "id": str(getattr(tweet, 'id', '')),
                "text": str(tweet),
                "created_at": "",
                "retweet_count": 0,
                "like_count": 0,
                "reply_count": 0,
                "view_count": 0,
                "is_reply": False,
                "username": "",
            }

    def get_user_followings(self, username: str, max_users: int = 200, verified_only: bool = False) -> str:
        """
        Get users that the specified user is following via ScrapeBadger.
        
        Args:
            username: X handle (without @)
            max_users: Maximum number of followings to retrieve
            verified_only: If True, only return verified (blue tick) accounts
            
        Returns:
            JSON string of followings with username, name, description, verified status
        """
        if not self.is_available():
            return "Error: ScrapeBadger API key not configured"

        username = username.replace("@", "").strip()
        api_key = self._get_next_key()
        logger.info(f"Fetching followings for @{username} via ScrapeBadger...")
        
        try:
            # Run async code in sync context
            users_data = asyncio.run(self._get_following_async(username, max_users, api_key))
            
            all_followings = []
            for user in users_data:
                # Extract user data - handle both direct attributes and nested legacy structure
                if hasattr(user, 'legacy'):
                    # Nested structure from raw API
                    legacy = user.legacy
                    is_verified = getattr(user, 'is_blue_verified', False)
                    user_data = {
                        "username": legacy.screen_name,
                        "name": legacy.name,
                        "description": getattr(legacy, 'description', ''),
                        "verified": is_verified,
                        "followers_count": getattr(legacy, 'followers_count', 0),
                    }
                else:
                    # Flattened User model from SDK
                    is_verified = getattr(user, 'is_blue_verified', False) or getattr(user, 'verified', False)
                    user_data = {
                        "username": getattr(user, 'username', getattr(user, 'screen_name', '')),
                        "name": getattr(user, 'name', ''),
                        "description": getattr(user, 'description', ''),
                        "verified": is_verified,
                        "followers_count": getattr(user, 'followers_count', 0),
                    }
                
                # Apply verified filter if requested
                if verified_only and not user_data["verified"]:
                    continue
                    
                all_followings.append(user_data)

            logger.info(f"✅ Retrieved {len(all_followings)} followings for @{username}")
            return json.dumps(all_followings, indent=2)

        except Exception as e:
            logger.warning(f"ScrapeBadger followings fetch failed: {e}")
            return f"Error: {str(e)}"

    def get_user_profile(self, username: str) -> str:
        """
        Get user profile information using ScrapeBadger.
        
        Args:
            username: X handle (without @)
            
        Returns:
            JSON string of profile info or error message
        """
        if not self.is_available():
            return "Error: ScrapeBadger API key not configured"

        username = username.replace("@", "").strip()
        api_key = self._get_next_key()
        logger.info(f"Fetching profile for @{username} via ScrapeBadger...")
        
        try:
            # Run async code in sync context
            user = asyncio.run(self._get_profile_async(username, api_key))
            
            profile = {
                "user_id": user.data.user_result.result.rest_id,
                "username": user.data.user_result.result.legacy.screen_name,
                "name": user.data.user_result.result.legacy.name,
                "description": user.data.user_result.result.legacy.description,
                "followers_count": user.data.user_result.result.legacy.followers_count,
                "following_count": user.data.user_result.result.legacy.friends_count,
                "verified": user.data.user_result.result.is_blue_verified,
                "location": user.data.user_result.result.legacy.location,
                "created_at": user.data.user_result.result.legacy.created_at,
            }
            logger.info(f"✅ Retrieved profile for @{username}")
            return json.dumps(profile, indent=2)
            
        except Exception as e:
            logger.warning(f"ScrapeBadger profile fetch failed: {e}")
            return f"Error: {str(e)}"

    def get_user_tweets(self, username: str, max_tweets: int = 20) -> str:
        """
        Get recent tweets from a user using ScrapeBadger.
        
        Args:
            username: X handle (without @)
            max_tweets: Maximum number of tweets to retrieve
            
        Returns:
            JSON string of tweets or error message
        """
        if not self.is_available():
            return "Error: ScrapeBadger API key not configured"

        username = username.replace("@", "").strip()
        api_key = self._get_next_key()
        logger.info(f"Fetching tweets for @{username} via ScrapeBadger...")
        
        try:
            # Run async code in sync context
            # Using search 'from:user' is often more reliable/supported than user timeline in some scrapers
            query = f"from:{username}"
            tweets_data = asyncio.run(self._get_tweets_async(query, max_tweets, api_key))
            
            all_tweets = []
            for tweet in tweets_data:
                tweet_data = self._extract_tweet_data(tweet)
                all_tweets.append(tweet_data)

            logger.info(f"✅ Retrieved {len(all_tweets)} tweets for @{username}")
            return json.dumps(all_tweets, indent=2)

        except Exception as e:
            logger.warning(f"ScrapeBadger tweets fetch failed: {e}")
            return f"Error: {str(e)}"

# Convenience function
def get_scrapebadger_toolkit() -> Optional[ScrapeBadgerToolkit]:
    """Get an initialized ScrapeBadgerToolkit if available."""
    toolkit = ScrapeBadgerToolkit()
    return toolkit if toolkit.is_available() else None

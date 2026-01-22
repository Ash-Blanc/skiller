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
"""
import os
import asyncio
import json
from typing import List, Dict, Any, Optional
from agno.tools import Toolkit
from agno.utils.log import logger
from scrapebadger import ScrapeBadger

class ScrapeBadgerToolkit(Toolkit):
    """
    Toolkit for scraping X/Twitter using ScrapeBadger service.
    
    Requires SCRAPEBADGER_API_KEY environment variable.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="scrapebadger")
        
        self.api_key = api_key or os.getenv("SCRAPEBADGER_API_KEY")
        
        if self.api_key:
            logger.info("✅ ScrapeBadger initialized")
        else:
            logger.info("No SCRAPEBADGER_API_KEY, ScrapeBadger disabled")
        
        # Register tools
        self.register(self.get_user_profile)
        self.register(self.get_user_tweets)
        self.register(self.get_user_followings)
    
    def is_available(self) -> bool:
        """Check if API key is configured."""
        return self.api_key is not None

    async def _get_profile_async(self, username: str) -> Dict[str, Any]:
        """Async helper to get profile."""
        async with ScrapeBadger(api_key=self.api_key) as client:
            return await client.twitter.users.get_by_username(username)

    async def _get_tweets_async(self, query: str, limit: int) -> List[Any]:
        """Async helper to get tweets."""
        tweets = []
        async with ScrapeBadger(api_key=self.api_key) as client:
            async for tweet in client.twitter.tweets.search_all(query, max_items=limit):
                tweets.append(tweet)
        return tweets

    async def _get_following_async(self, username: str, max_users: int) -> List[Any]:
        """Async helper to get users that username follows."""
        users = []
        async with ScrapeBadger(api_key=self.api_key) as client:
            async for user in client.twitter.users.get_following_all(username, max_items=max_users):
                users.append(user)
        return users

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
        logger.info(f"Fetching followings for @{username} via ScrapeBadger...")
        
        try:
            # Run async code in sync context
            users_data = asyncio.run(self._get_following_async(username, max_users))
            
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
        logger.info(f"Fetching profile for @{username} via ScrapeBadger...")
        
        try:
            # Run async code in sync context
            user = asyncio.run(self._get_profile_async(username))
            
            profile = {
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
        logger.info(f"Fetching tweets for @{username} via ScrapeBadger...")
        
        try:
            # Run async code in sync context
            # Using search 'from:user' is often more reliable/supported than user timeline in some scrapers
            query = f"from:{username}"
            tweets_data = asyncio.run(self._get_tweets_async(query, max_tweets))
            
            all_tweets = []
            for tweet in tweets_data:
                legacy = tweet.legacy
                all_tweets.append({
                    "id": legacy.id_str,
                    "text": legacy.full_text,
                    "created_at": legacy.created_at,
                    "retweet_count": legacy.retweet_count,
                    "like_count": legacy.favorite_count,
                    "reply_count": legacy.reply_count,
                    "view_count": 0, # Not always available in legacy object
                    "is_reply": legacy.in_reply_to_status_id_str is not None,
                })

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

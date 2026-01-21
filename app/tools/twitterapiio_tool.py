"""
TwitterAPI.io Toolkit for X/Twitter data extraction.

Uses https://twitterapi.io - a third-party Twitter API that doesn't require
user authentication. Provides reliable endpoints for:
- User profiles
- User tweets
- Followings/Followers lists

Pricing: ~$0.15/1k requests
Docs: https://docs.twitterapi.io
"""
import os
import json
import requests
from typing import List, Dict, Any, Optional
from agno.tools import Toolkit
from agno.utils.log import logger


class TwitterAPIIOToolkit(Toolkit):
    """
    Toolkit for scraping X/Twitter using TwitterAPI.io service.
    
    Requires TWITTER_API_IO_KEY environment variable.
    """
    
    BASE_URL = "https://api.twitterapi.io/twitter"
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="twitterapiio")
        
        self.api_key = api_key or os.getenv("TWITTER_API_IO_KEY")
        
        if self.api_key:
            logger.info("✅ TwitterAPI.io initialized")
        else:
            logger.info("No TWITTER_API_IO_KEY, TwitterAPI.io disabled")
        
        # Register tools
        self.register(self.get_user_info)
        self.register(self.get_user_tweets)
        self.register(self.get_user_followings)
    
    def is_available(self) -> bool:
        """Check if API key is configured."""
        return self.api_key is not None
    
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make authenticated request to TwitterAPI.io."""
        if not self.api_key:
            return {"status": "error", "message": "API key not configured"}
        
        headers = {"x-api-key": self.api_key}
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"TwitterAPI.io request failed: {e}")
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
        
        logger.info(f"Fetching profile for @{username} via TwitterAPI.io...")
        
        result = self._make_request("user/info", {"userName": username})
        
        if result.get("status") == "success" and result.get("data"):
            data = result["data"]
            profile = {
                "username": data.get("userName", username),
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "followers_count": data.get("followers", 0),
                "following_count": data.get("following", 0),
                "verified": data.get("isBlueVerified", False),
                "location": data.get("location", ""),
                "created_at": data.get("createdAt", ""),
            }
            logger.info(f"✅ Retrieved profile for @{username}")
            return json.dumps(profile, indent=2)
        
        error_msg = result.get("message", result.get("msg", "Unknown error"))
        return f"Error: {error_msg}"
    
    def get_user_tweets(self, username: str, max_tweets: int = 20, include_replies: bool = False) -> str:
        """
        Get recent tweets from a user.
        
        Args:
            username: X handle (without @)
            max_tweets: Maximum number of tweets to retrieve (up to 100)
            include_replies: Whether to include replies
            
        Returns:
            JSON string of tweets or error message
        """
        username = username.replace("@", "").strip()
        
        logger.info(f"Fetching tweets for @{username} via TwitterAPI.io...")
        
        all_tweets = []
        cursor = ""
        
        # Paginate to get requested number of tweets (20 per page)
        while len(all_tweets) < max_tweets:
            params = {
                "userName": username,
                "includeReplies": str(include_replies).lower(),
            }
            if cursor:
                params["cursor"] = cursor
            
            result = self._make_request("user/last_tweets", params)
            
            if result.get("status") != "success":
                error_msg = result.get("message", "Unknown error")
                if all_tweets:
                    break  # Return what we have
                return f"Error: {error_msg}"
            
            tweets = result.get("tweets", [])
            if not tweets:
                break
            
            for tweet in tweets:
                if len(all_tweets) >= max_tweets:
                    break
                all_tweets.append({
                    "id": tweet.get("id", ""),
                    "text": tweet.get("text", ""),
                    "created_at": tweet.get("createdAt", ""),
                    "retweet_count": tweet.get("retweetCount", 0),
                    "like_count": tweet.get("likeCount", 0),
                    "reply_count": tweet.get("replyCount", 0),
                    "view_count": tweet.get("viewCount", 0),
                    "is_reply": tweet.get("isReply", False),
                })
            
            if not result.get("has_next_page"):
                break
            cursor = result.get("next_cursor", "")
        
        logger.info(f"✅ Retrieved {len(all_tweets)} tweets for @{username}")
        return json.dumps(all_tweets, indent=2)
    
    def get_user_followings(
        self, 
        username: str, 
        max_users: int = 100,
        verified_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get list of users that a user follows.
        
        Args:
            username: X handle (without @)
            max_users: Maximum number of followings to retrieve
            verified_only: Only return verified (blue checkmark) users
            
        Returns:
            List of user profile dicts
        """
        username = username.replace("@", "").strip()
        
        logger.info(f"Fetching followings for @{username} via TwitterAPI.io...")
        
        all_users = []
        cursor = ""
        
        # Paginate to get requested number (200 per page)
        while len(all_users) < max_users:
            params = {"userName": username, "pageSize": 200}
            if cursor:
                params["cursor"] = cursor
            
            result = self._make_request("user/followings", params)
            
            if result.get("status") != "success":
                error_msg = result.get("message", "Unknown error")
                logger.warning(f"Failed to get followings: {error_msg}")
                break
            
            followings = result.get("followings", [])
            if not followings:
                break
            
            for user in followings:
                if len(all_users) >= max_users:
                    break
                
                # Filter for verified if requested
                if verified_only and not user.get("isBlueVerified", False):
                    continue
                
                all_users.append({
                    "username": user.get("userName", ""),
                    "name": user.get("name", ""),
                    "description": user.get("description", ""),
                    "verified": user.get("isBlueVerified", False),
                    "followers_count": user.get("followers", 0),
                })
            
            if not result.get("has_next_page"):
                break
            cursor = result.get("next_cursor", "")
        
        logger.info(f"✅ Retrieved {len(all_users)} followings for @{username}")
        return all_users


# Convenience function
def get_twitterapiio_toolkit() -> Optional[TwitterAPIIOToolkit]:
    """Get an initialized TwitterAPIIOToolkit if available."""
    toolkit = TwitterAPIIOToolkit()
    return toolkit if toolkit.is_available() else None

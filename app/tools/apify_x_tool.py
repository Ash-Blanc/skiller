"""
Apify X/Twitter Scraping Toolkit.

Uses Apify's pre-built actors for reliable X data extraction.
Primary actors used:
- apidojo/tweet-scraper: Get tweets from user profiles
- apidojo/twitter-user-scraper: Get user profile info and following
"""
import os
import json
from typing import List, Dict, Any, Optional
from agno.tools import Toolkit
from agno.utils.log import logger

try:
    from apify_client import ApifyClient
    APIFY_AVAILABLE = True
except ImportError:
    APIFY_AVAILABLE = False
    logger.warning("apify-client not installed. Run: pip install apify-client")


class ApifyXToolkit(Toolkit):
    """
    Toolkit for scraping X/Twitter using Apify actors.
    
    Requires APIFY_API_TOKEN environment variable.
    """
    
    # Apify actor IDs for X scraping
    TWEET_SCRAPER_ACTOR = "apidojo/tweet-scraper"
    USER_SCRAPER_ACTOR = "apidojo/twitter-user-scraper"
    
    def __init__(self, api_token: Optional[str] = None):
        super().__init__(name="apify_x")
        
        self.api_token = api_token or os.getenv("APIFY_API_TOKEN")
        self.client: Optional[ApifyClient] = None
        
        if APIFY_AVAILABLE and self.api_token:
            try:
                self.client = ApifyClient(self.api_token)
                logger.info("✅ Apify client initialized for X scraping")
            except Exception as e:
                logger.warning(f"Failed to initialize Apify client: {e}")
        else:
            if not APIFY_AVAILABLE:
                logger.info("Apify client not available (not installed)")
            else:
                logger.info("No APIFY_API_TOKEN, Apify X scraping disabled")
        
        # Register tools
        self.register(self.get_user_tweets)
        self.register(self.get_user_profile)
    
    def is_available(self) -> bool:
        """Check if Apify client is available and configured."""
        return self.client is not None
    
    def get_user_tweets(self, username: str, max_tweets: int = 20) -> str:
        """
        Get recent tweets from a user's profile.
        
        Args:
            username: X handle (without @)
            max_tweets: Maximum number of tweets to retrieve
            
        Returns:
            JSON string of tweets or error message
        """
        if not self.client:
            return "Error: Apify client not initialized"
        
        username = username.replace("@", "").strip()
        
        try:
            logger.info(f"Fetching tweets for @{username} via Apify...")
            
            # Run the tweet scraper actor
            run_input = {
                "startUrls": [{"url": f"https://twitter.com/{username}"}],
                "maxTweets": max_tweets,
                "onlyTweets": True,
                "searchMode": "user",
            }
            
            run = self.client.actor(self.TWEET_SCRAPER_ACTOR).call(run_input=run_input)
            
            # Fetch results from the dataset
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            
            if not items:
                return f"No tweets found for @{username}"
            
            # Format results
            tweets = []
            for item in items[:max_tweets]:
                tweet = {
                    "text": item.get("full_text") or item.get("text", ""),
                    "created_at": item.get("created_at", ""),
                    "retweet_count": item.get("retweet_count", 0),
                    "favorite_count": item.get("favorite_count", 0),
                    "reply_count": item.get("reply_count", 0),
                }
                tweets.append(tweet)
            
            logger.info(f"✅ Retrieved {len(tweets)} tweets for @{username}")
            return json.dumps(tweets, indent=2)
            
        except Exception as e:
            error_msg = f"Error fetching tweets for @{username}: {str(e)}"
            logger.warning(error_msg)
            return error_msg
    
    def get_user_profile(self, username: str) -> str:
        """
        Get user profile information.
        
        Args:
            username: X handle (without @)
            
        Returns:
            JSON string of profile info or error message
        """
        if not self.client:
            return "Error: Apify client not initialized"
        
        username = username.replace("@", "").strip()
        
        try:
            logger.info(f"Fetching profile for @{username} via Apify...")
            
            run_input = {
                "startUrls": [{"url": f"https://twitter.com/{username}"}],
                "maxItems": 1,
            }
            
            run = self.client.actor(self.USER_SCRAPER_ACTOR).call(run_input=run_input)
            
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            
            if not items:
                return f"No profile found for @{username}"
            
            profile = items[0]
            result = {
                "username": profile.get("screen_name", username),
                "name": profile.get("name", ""),
                "description": profile.get("description", ""),
                "followers_count": profile.get("followers_count", 0),
                "following_count": profile.get("friends_count", 0),
                "verified": profile.get("verified", False),
            }
            
            logger.info(f"✅ Retrieved profile for @{username}")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            error_msg = f"Error fetching profile for @{username}: {str(e)}"
            logger.warning(error_msg)
            return error_msg


# Convenience function for direct usage
def get_apify_toolkit() -> Optional[ApifyXToolkit]:
    """Get an initialized ApifyXToolkit if available."""
    toolkit = ApifyXToolkit()
    return toolkit if toolkit.is_available() else None

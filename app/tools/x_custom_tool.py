import os
from typing import List, Optional
import tweepy
from agno.tools import Toolkit

class CustomXToolkit(Toolkit):
    def __init__(
        self,
        bearer_token: Optional[str] = None,
        consumer_key: Optional[str] = None,
        consumer_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_token_secret: Optional[str] = None
    ):
        super().__init__(name="custom_x")
        self.bearer_token = bearer_token or os.getenv("X_BEARER_TOKEN")
        self.consumer_key = consumer_key or os.getenv("X_CONSUMER_KEY")
        self.consumer_secret = consumer_secret or os.getenv("X_CONSUMER_SECRET")
        self.access_token = access_token or os.getenv("X_ACCESS_TOKEN")
        self.access_token_secret = access_token_secret or os.getenv("X_ACCESS_TOKEN_SECRET")
        
        self.client = tweepy.Client(
            bearer_token=self.bearer_token,
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            access_token=self.access_token,
            access_token_secret=self.access_token_secret,
            wait_on_rate_limit=True
        )
        
        self.register(self.get_following_handles)
        self.register(self.get_recent_posts)

    def get_following_handles(self, username: str, verified_only: bool = True) -> str:
        """
        Gets the list of X handles that a given user follows.
        :param username: The X handle of the user (without @).
        :param verified_only: If True, only return verified (blue tick) accounts.
        """
        try:
            user = self.client.get_user(username=username)
            if not user.data:
                return f"User {username} not found."
            
            user_id = user.data.id
            # Request verified status via user_fields
            following = self.client.get_users_following(
                id=user_id,
                user_fields=['verified']
            )
            
            if not following.data:
                return f"User {username} is not following anyone or their following list is private."
            
            if verified_only:
                handles = [u.username for u in following.data if getattr(u, 'verified', False)]
            else:
                handles = [u.username for u in following.data]
            
            return ", ".join(handles)
        except Exception as e:
            return f"Error getting following for {username}: {str(e)}"

    def get_recent_posts(self, username: str, count: int = 10) -> str:
        """
        Gets the most recent posts from a specific X user.
        :param username: The X handle of the user (without @).
        :param count: Number of posts to retrieve (max 100).
        """
        try:
            user = self.client.get_user(username=username)
            if not user.data:
                return f"User {username} not found."
            
            user_id = user.data.id
            tweets = self.client.get_users_tweets(
                id=user_id, 
                max_results=count,
                tweet_fields=['created_at', 'public_metrics', 'text']
            )
            
            if not tweets.data:
                return f"No recent posts found for {username}."
            
            posts = []
            for t in tweets.data:
                posts.append(t.text)
            
            return "\n---\n".join(posts)
        except Exception as e:
            return f"Error getting posts for {username}: {str(e)}"

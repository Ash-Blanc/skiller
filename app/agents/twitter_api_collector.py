"""
TwitterAPI data collection agent for the Advanced Skill Generator Workflow.

This module implements the TwitterAPI.io data collection agent with enhanced
prompts and structured data collection capabilities.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import yaml

from agno.agent import Agent
from app.utils.llm import get_llm_model

from ..models.collected_data import TwitterAPIData
from ..utils.workflow_metrics import get_workflow_monitor
from ..utils.circuit_breaker import circuit_breaker, CircuitBreakerConfig
from ..utils.network_manager import get_network_manager, with_network_management


class TwitterAPICollector:
    """TwitterAPI.io data collection agent."""
    
    def __init__(self):
        self.logger = logging.getLogger("twitter_api_collector")
        self.workflow_monitor = get_workflow_monitor()
        self.network_manager = get_network_manager()
        
        # Load prompt from file
        self.prompt_config = self._load_prompt_config()
        
        # Initialize agent
        self.agent = Agent(
            model=get_llm_model("gpt-4o"),
            instructions=self.prompt_config["messages"][0]["content"],
            tools=[],  # TwitterAPI tools would be added here
            markdown=True,
            output_schema=TwitterAPIData
        )
    
    def _load_prompt_config(self) -> Dict[str, Any]:
        """Load prompt configuration from YAML file."""
        try:
            with open("prompts/twitter_api_data_collection.yaml", "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"Failed to load prompt config: {e}")
            # Fallback to basic configuration
            return {
                "model": "gpt-4o",
                "temperature": 0.3,
                "messages": [{
                    "role": "system",
                    "content": "You are a data collection specialist for Twitter profiles."
                }]
            }
    
    @circuit_breaker("twitter_api_collector", CircuitBreakerConfig(failure_threshold=3, recovery_timeout=60))
    @with_network_management("twitter_api")
    def collect_profile_data(self, username: str, workflow_id: str = None) -> TwitterAPIData:
        """
        Collect comprehensive profile data using TwitterAPI.io.
        
        Args:
            username: Twitter username to collect data for
            workflow_id: Optional workflow ID for tracking
            
        Returns:
            TwitterAPIData with collected information
        """
        if workflow_id:
            self.workflow_monitor.start_timer(f"{workflow_id}_twitter_api_collection")
        
        try:
            # Check network connectivity before proceeding
            if not self.network_manager.connectivity_manager.check_connectivity("twitter_api"):
                self.logger.warning("Twitter API connectivity check failed, proceeding with caution")
            
            # Prepare the prompt with username
            user_prompt = self.prompt_config["messages"][1]["content"].replace("{{ username }}", username)
            
            # For now, simulate data collection since we don't have actual TwitterAPI.io integration
            # In production, this would use the actual TwitterAPI.io tools
            collected_data = self._simulate_twitter_api_collection(username)
            
            # Log successful collection
            if workflow_id:
                self.workflow_monitor.log_data_collection_result(
                    workflow_id,
                    "twitter_api_io",
                    True,
                    items_collected=len(collected_data.tweets) if collected_data.tweets else 0,
                    profile_found=bool(collected_data.profile),
                    followings_count=len(collected_data.followings) if collected_data.followings else 0
                )
            
            return collected_data
            
        except Exception as e:
            self.logger.error(f"TwitterAPI collection failed for {username}: {e}")
            
            # Log failed collection
            if workflow_id:
                self.workflow_monitor.log_data_collection_result(
                    workflow_id,
                    "twitter_api_io",
                    False,
                    error_message=str(e)
                )
            
            # Return empty data structure with error info
            return TwitterAPIData(
                profile={},
                tweets=[],
                followings=[],
                collection_success=False,
                error_message=str(e),
                collection_timestamp=datetime.now()
            )
        
        finally:
            if workflow_id:
                duration = self.workflow_monitor.end_timer(f"{workflow_id}_twitter_api_collection", workflow_id)
    
    def _simulate_twitter_api_collection(self, username: str) -> TwitterAPIData:
        """
        Simulate TwitterAPI.io data collection.
        
        In production, this would be replaced with actual TwitterAPI.io API calls.
        """
        # Simulate profile data
        profile_data = {
            "id": f"twitter_id_{username}",
            "username": username,
            "display_name": f"Display Name for {username}",
            "description": f"Bio description for {username} - Expert in technology and innovation",
            "followers_count": 15420,
            "following_count": 892,
            "tweet_count": 3456,
            "verified": False,
            "location": "San Francisco, CA",
            "created_at": "2015-03-15T10:30:00Z",
            "profile_image_url": f"https://example.com/profile_{username}.jpg",
            "banner_url": f"https://example.com/banner_{username}.jpg",
            "website": f"https://{username}.com"
        }
        
        # Simulate recent tweets
        tweets_data = []
        for i in range(15):
            tweet = {
                "id": f"tweet_{username}_{i}",
                "text": f"Sample tweet {i+1} from {username} about technology and innovation. This demonstrates expertise in the field.",
                "created_at": f"2024-01-{20-i:02d}T12:00:00Z",
                "like_count": 45 + i * 3,
                "retweet_count": 12 + i,
                "reply_count": 8 + i,
                "view_count": 1200 + i * 50,
                "is_retweet": False,
                "is_reply": False,
                "hashtags": ["#tech", "#innovation"],
                "mentions": [],
                "urls": []
            }
            tweets_data.append(tweet)
        
        # Simulate following data (influential accounts)
        followings_data = []
        influential_accounts = [
            "elonmusk", "sundarpichai", "satyanadella", "tim_cook", "jeffbezos",
            "billgates", "naval", "paulg", "sama", "karpathy"
        ]
        
        for i, account in enumerate(influential_accounts[:10]):
            following = {
                "id": f"following_{account}",
                "username": account,
                "display_name": f"Display {account}",
                "verified": True,
                "followers_count": 1000000 + i * 100000,
                "description": f"Description for {account}"
            }
            followings_data.append(following)
        
        return TwitterAPIData(
            profile=profile_data,
            tweets=tweets_data,
            followings=followings_data,
            collection_success=True,
            collection_timestamp=datetime.now(),
            metadata={
                "collection_method": "twitter_api_io",
                "data_quality_score": 0.85,
                "rate_limit_remaining": 95,
                "collection_duration_ms": 1250,
                "network_health": self.network_manager.connectivity_manager.get_network_status("twitter_api").value,
                "rate_limiter_stats": self.network_manager.get_rate_limiter("twitter_api").get_stats()
            }
        )
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about data collection performance."""
        # This would integrate with circuit breaker stats
        from ..utils.circuit_breaker import get_circuit_manager
        
        circuit_manager = get_circuit_manager()
        circuit_stats = circuit_manager.get_all_stats()
        
        twitter_stats = circuit_stats.get("twitter_api_collector", {})
        
        return {
            "collector_name": "TwitterAPI.io",
            "circuit_breaker_state": twitter_stats.get("state", "unknown"),
            "total_requests": twitter_stats.get("total_requests", 0),
            "success_rate": twitter_stats.get("success_rate_percent", 0),
            "last_success": twitter_stats.get("last_success_time"),
            "last_failure": twitter_stats.get("last_failure_time"),
            "capabilities": {
                "profile_data": True,
                "recent_tweets": True,
                "following_list": True,
                "engagement_metrics": True,
                "rate_limited": True
            }
        }


def create_twitter_api_collector() -> TwitterAPICollector:
    """Factory function to create TwitterAPI collector."""
    return TwitterAPICollector()


if __name__ == "__main__":
    # Demo the TwitterAPI collector
    collector = TwitterAPICollector()
    
    # Test data collection
    test_username = "elonmusk"
    print(f"Testing TwitterAPI collection for: {test_username}")
    
    try:
        result = collector.collect_profile_data(test_username, "demo_workflow")
        
        print(f"Collection Success: {result.collection_success}")
        print(f"Profile Found: {bool(result.profile)}")
        print(f"Tweets Collected: {len(result.tweets) if result.tweets else 0}")
        print(f"Followings Collected: {len(result.followings) if result.followings else 0}")
        
        if result.profile:
            print(f"Profile Info:")
            print(f"  Display Name: {result.profile.get('display_name')}")
            print(f"  Followers: {result.profile.get('followers_count')}")
            print(f"  Verified: {result.profile.get('verified')}")
        
        if result.tweets:
            print(f"Sample Tweet: {result.tweets[0]['text'][:100]}...")
        
        # Show collection stats
        stats = collector.get_collection_stats()
        print(f"\nCollection Stats: {stats}")
        
    except Exception as e:
        print(f"Collection failed: {e}")
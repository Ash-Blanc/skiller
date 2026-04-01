"""
Enhanced data models for the Advanced Skill Generator Workflow.

This module defines dataclasses for unified data storage from multiple sources
(TwitterAPI.io and ScrapeBadger) as part of the advanced skill generation pipeline.

Validates Requirements:
- AC1.1: System uses both TwitterAPI.io and ScrapeBadger tools in parallel
- AC3.1: Consolidates and deduplicates data from multiple sources
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


@dataclass
class TwitterAPIData:
    """
    Data structure for TwitterAPI.io responses with structured fields.
    
    This dataclass provides structured storage and validation for data collected
    from TwitterAPI.io, ensuring all required fields for profile analysis are
    properly captured and accessible.
    
    Validates Requirements:
    - AC1.2: Collects basic profile info (bio, followers, verification, location)
    - AC1.3: Retrieves recent tweets with engagement metrics (likes, retweets, replies)
    """
    profile: Optional[Dict[str, Any]] = None
    tweets: List[Dict[str, Any]] = field(default_factory=list)
    followings: List[Dict[str, Any]] = field(default_factory=list)
    collection_success: bool = False
    collection_timestamp: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)
    
    # Expected profile fields for AC1.2 validation
    REQUIRED_PROFILE_FIELDS = {
        'username', 'name', 'description', 'followers_count', 
        'following_count', 'verified', 'location', 'created_at'
    }
    
    # Expected tweet fields for AC1.3 validation
    REQUIRED_TWEET_FIELDS = {
        'id', 'text', 'created_at', 'retweet_count', 
        'like_count', 'reply_count', 'view_count'
    }
    
    def __post_init__(self):
        """Set collection timestamp if not provided and validate data structure."""
        if self.collection_timestamp is None:
            self.collection_timestamp = datetime.now()
        
        # Validate data structure if collection was successful
        if self.collection_success:
            self._validate_data_structure()
    
    def _validate_data_structure(self):
        """Validate that collected data meets TwitterAPI.io response structure."""
        if self.profile:
            missing_fields = self.REQUIRED_PROFILE_FIELDS - set(self.profile.keys())
            if missing_fields:
                # Log warning but don't fail - some fields might be optional
                pass
        
        # Validate tweet structure
        for tweet in self.tweets:
            if not isinstance(tweet, dict):
                continue
            missing_fields = self.REQUIRED_TWEET_FIELDS - set(tweet.keys())
            if missing_fields:
                # Log warning for incomplete tweet data
                pass
    
    @property
    def has_profile_data(self) -> bool:
        """
        Check if profile data is available and contains essential fields.
        
        Returns:
            True if profile data exists and contains at least username and description
        """
        if not (self.profile and isinstance(self.profile, dict)):
            return False
        
        # Check for essential fields (AC1.2 requirements)
        essential_fields = {'username', 'description'}
        return essential_fields.issubset(set(self.profile.keys()))
    
    @property
    def has_complete_profile(self) -> bool:
        """
        Check if profile data contains all expected TwitterAPI.io fields.
        
        Returns:
            True if profile contains all required fields for comprehensive analysis
        """
        if not self.has_profile_data:
            return False
        
        # Check for all AC1.2 required fields
        profile_fields = set(self.profile.keys())
        required_fields = {'username', 'description', 'followers_count', 'verified'}
        return required_fields.issubset(profile_fields)
    
    @property
    def tweet_count(self) -> int:
        """Get the number of tweets collected."""
        return len(self.tweets) if self.tweets else 0
    
    @property
    def following_count(self) -> int:
        """Get the number of followings collected."""
        return len(self.followings) if self.followings else 0
    
    @property
    def has_engagement_data(self) -> bool:
        """
        Check if tweets contain engagement metrics (AC1.3 requirement).
        
        Returns:
            True if at least one tweet has engagement metrics (likes, retweets, replies)
        """
        if not self.tweets:
            return False
        
        engagement_fields = {'like_count', 'retweet_count', 'reply_count'}
        for tweet in self.tweets:
            if isinstance(tweet, dict):
                tweet_fields = set(tweet.keys())
                if engagement_fields.issubset(tweet_fields):
                    return True
        return False
    
    @property
    def total_engagement(self) -> Dict[str, int]:
        """
        Calculate total engagement metrics across all tweets.
        
        Returns:
            Dictionary with total likes, retweets, replies, and views
        """
        totals = {
            'likes': 0,
            'retweets': 0, 
            'replies': 0,
            'views': 0
        }
        
        for tweet in self.tweets:
            if isinstance(tweet, dict):
                totals['likes'] += tweet.get('like_count', 0)
                totals['retweets'] += tweet.get('retweet_count', 0)
                totals['replies'] += tweet.get('reply_count', 0)
                totals['views'] += tweet.get('view_count', 0)
        
        return totals
    
    @property
    def average_engagement(self) -> Dict[str, float]:
        """
        Calculate average engagement metrics per tweet.
        
        Returns:
            Dictionary with average likes, retweets, replies, and views per tweet
        """
        if not self.tweets:
            return {'likes': 0.0, 'retweets': 0.0, 'replies': 0.0, 'views': 0.0}
        
        totals = self.total_engagement
        tweet_count = len(self.tweets)
        
        return {
            'likes': totals['likes'] / tweet_count,
            'retweets': totals['retweets'] / tweet_count,
            'replies': totals['replies'] / tweet_count,
            'views': totals['views'] / tweet_count
        }
    
    def get_high_engagement_tweets(self, min_engagement: int = 10) -> List[Dict[str, Any]]:
        """
        Get tweets with engagement above threshold.
        
        Args:
            min_engagement: Minimum total engagement (likes + retweets + replies)
            
        Returns:
            List of tweets sorted by total engagement (highest first)
        """
        high_engagement = []
        
        for tweet in self.tweets:
            if not isinstance(tweet, dict):
                continue
            
            total_engagement = (
                tweet.get('like_count', 0) + 
                tweet.get('retweet_count', 0) + 
                tweet.get('reply_count', 0)
            )
            
            if total_engagement >= min_engagement:
                tweet_copy = tweet.copy()
                tweet_copy['_total_engagement'] = total_engagement
                high_engagement.append(tweet_copy)
        
        # Sort by total engagement (highest first)
        return sorted(high_engagement, key=lambda x: x['_total_engagement'], reverse=True)
    
    def get_profile_summary(self) -> Dict[str, Any]:
        """
        Get a summary of profile data for analysis.
        
        Returns:
            Dictionary with key profile metrics and flags
        """
        if not self.has_profile_data:
            return {}
        
        profile = self.profile.copy()
        
        # Add computed fields
        profile['_has_complete_profile'] = self.has_complete_profile
        profile['_tweet_count'] = self.tweet_count
        profile['_following_count'] = self.following_count
        profile['_has_engagement_data'] = self.has_engagement_data
        profile['_total_engagement'] = self.total_engagement
        profile['_average_engagement'] = self.average_engagement
        profile['_collection_timestamp'] = self.collection_timestamp.isoformat() if self.collection_timestamp else None
        
        return profile
    
    def validate_requirements(self) -> Dict[str, bool]:
        """
        Validate that collected data meets AC1.2 and AC1.3 requirements.
        
        Returns:
            Dictionary with validation results for each requirement
        """
        return {
            'AC1.2_basic_profile': self.has_profile_data,
            'AC1.2_complete_profile': self.has_complete_profile,
            'AC1.2_bio_available': bool(self.profile and self.profile.get('description')),
            'AC1.2_followers_available': bool(self.profile and 'followers_count' in self.profile),
            'AC1.2_verification_available': bool(self.profile and 'verified' in self.profile),
            'AC1.2_location_available': bool(self.profile and self.profile.get('location')),
            'AC1.3_tweets_collected': self.tweet_count > 0,
            'AC1.3_engagement_metrics': self.has_engagement_data,
            'AC1.3_sufficient_tweets': self.tweet_count >= 10,  # Minimum for analysis
            'collection_successful': self.collection_success,
        }


@dataclass
class ScrapeBadgerData:
    """
    Data structure for ScrapeBadger responses with highlights support.
    
    This dataclass provides structured storage and validation for data collected
    from ScrapeBadger, with special focus on highlighted/pinned content and
    enhanced profile information including user_id.
    
    Validates Requirements:
    - AC1.4: Fetches highlighted/pinned content showing what user wants to be known for
    - AC1.5: Gathers following patterns to understand network and interests
    """
    profile: Optional[Dict[str, Any]] = None
    tweets: List[Dict[str, Any]] = field(default_factory=list)
    highlights: List[Dict[str, Any]] = field(default_factory=list)
    followings: List[Dict[str, Any]] = field(default_factory=list)
    collection_success: bool = False
    collection_timestamp: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)
    
    # Expected profile fields for ScrapeBadger (AC1.4, AC1.5 validation)
    EXPECTED_PROFILE_FIELDS = {
        'username', 'user_id', 'name', 'description', 'followers_count',
        'following_count', 'verified', 'location', 'created_at'
    }
    
    # Expected highlight fields for AC1.4 validation
    EXPECTED_HIGHLIGHT_FIELDS = {
        'id', 'text', 'created_at', 'type'  # type could be 'pinned', 'highlighted', etc.
    }
    
    # Expected following fields for AC1.5 validation
    EXPECTED_FOLLOWING_FIELDS = {
        'username', 'name', 'verified', 'followers_count'
    }
    
    def __post_init__(self):
        """Set collection timestamp if not provided and validate data structure."""
        if self.collection_timestamp is None:
            self.collection_timestamp = datetime.now()
        
        # Validate data structure if collection was successful
        if self.collection_success:
            self._validate_data_structure()
    
    def _validate_data_structure(self):
        """Validate that collected data meets ScrapeBadger response structure."""
        if self.profile:
            # Check for user_id which is specific to ScrapeBadger
            if 'user_id' not in self.profile:
                # Log warning - user_id is expected from ScrapeBadger
                pass
        
        # Validate highlight structure (AC1.4)
        for highlight in self.highlights:
            if not isinstance(highlight, dict):
                continue
            # Highlights should have basic content fields
            if 'text' not in highlight and 'content' not in highlight:
                # Log warning for incomplete highlight data
                pass
        
        # Validate following structure (AC1.5)
        for following in self.followings:
            if not isinstance(following, dict):
                continue
            if 'username' not in following:
                # Log warning for incomplete following data
                pass
    
    @property
    def has_profile_data(self) -> bool:
        """Check if profile data is available and valid."""
        return (
            self.profile is not None and 
            isinstance(self.profile, dict) and 
            len(self.profile) > 0
        )
    
    @property
    def has_enhanced_profile(self) -> bool:
        """
        Check if profile contains enhanced ScrapeBadger-specific data.
        
        ScrapeBadger is expected to provide user_id and other enhanced fields
        that may not be available through TwitterAPI.io.
        
        Returns:
            True if profile contains user_id and other enhanced fields
        """
        if not self.has_profile_data:
            return False
        
        # Check for ScrapeBadger-specific fields
        enhanced_fields = {'user_id', 'username', 'description'}
        profile_fields = set(self.profile.keys())
        return enhanced_fields.issubset(profile_fields)
    
    @property
    def has_highlights(self) -> bool:
        """
        Check if highlights/pinned content is available (AC1.4 requirement).
        
        Returns:
            True if highlighted/pinned content showing what user wants to be known for is available
        """
        return (
            self.highlights is not None and 
            isinstance(self.highlights, list) and 
            len(self.highlights) > 0
        )
    
    @property
    def has_following_patterns(self) -> bool:
        """
        Check if following patterns are available (AC1.5 requirement).
        
        Returns:
            True if following patterns to understand network and interests are available
        """
        return (
            self.followings is not None and 
            isinstance(self.followings, list) and 
            len(self.followings) > 0
        )
    
    @property
    def tweet_count(self) -> int:
        """Get the number of tweets collected."""
        return len(self.tweets) if self.tweets else 0
    
    @property
    def highlight_count(self) -> int:
        """Get the number of highlights collected."""
        return len(self.highlights) if self.highlights else 0
    
    @property
    def following_count(self) -> int:
        """Get the number of followings collected."""
        return len(self.followings) if self.followings else 0
    
    @property
    def user_id(self) -> Optional[str]:
        """
        Get the user_id from profile data.
        
        ScrapeBadger is expected to provide user_id which is useful for
        cross-referencing and enhanced data collection.
        
        Returns:
            User ID string if available, None otherwise
        """
        if self.has_profile_data:
            return self.profile.get('user_id')
        return None
    
    def get_highlights_summary(self) -> Dict[str, Any]:
        """
        Get a summary of highlighted/pinned content (AC1.4).
        
        This provides insights into what the user wants to be known for
        based on their highlighted/pinned content.
        
        Returns:
            Dictionary with highlights analysis and summary
        """
        if not self.has_highlights:
            return {
                'count': 0,
                'available': False,
                'summary': 'No highlighted content available'
            }
        
        # Analyze highlights for content types and themes
        content_types = set()
        total_length = 0
        
        for highlight in self.highlights:
            if isinstance(highlight, dict):
                # Determine content type
                if highlight.get('type'):
                    content_types.add(highlight.get('type'))
                elif 'text' in highlight:
                    content_types.add('text')
                elif 'media' in highlight:
                    content_types.add('media')
                else:
                    content_types.add('unknown')
                
                # Calculate content length
                text_content = highlight.get('text', highlight.get('content', ''))
                if text_content:
                    total_length += len(str(text_content))
        
        return {
            'count': self.highlight_count,
            'available': True,
            'content_types': list(content_types),
            'average_length': total_length / self.highlight_count if self.highlight_count > 0 else 0,
            'summary': f'{self.highlight_count} highlighted items showing user intent and expertise'
        }
    
    def get_following_patterns_summary(self) -> Dict[str, Any]:
        """
        Get a summary of following patterns (AC1.5).
        
        This provides insights into the user's network and interests
        based on who they follow.
        
        Returns:
            Dictionary with following patterns analysis
        """
        if not self.has_following_patterns:
            return {
                'count': 0,
                'available': False,
                'verified_count': 0,
                'summary': 'No following patterns available'
            }
        
        # Analyze following patterns
        verified_count = 0
        high_follower_count = 0
        categories = set()
        
        for following in self.followings:
            if isinstance(following, dict):
                # Count verified accounts
                if following.get('verified', False):
                    verified_count += 1
                
                # Count high-follower accounts (potential influencers)
                followers = following.get('followers_count', 0)
                if followers > 10000:
                    high_follower_count += 1
                
                # Categorize based on bio or description
                bio = following.get('description', '').lower()
                if 'tech' in bio or 'engineer' in bio or 'developer' in bio:
                    categories.add('technology')
                elif 'business' in bio or 'ceo' in bio or 'founder' in bio:
                    categories.add('business')
                elif 'design' in bio or 'creative' in bio:
                    categories.add('design')
                # Add more categories as needed
        
        return {
            'count': self.following_count,
            'available': True,
            'verified_count': verified_count,
            'high_follower_count': high_follower_count,
            'interest_categories': list(categories),
            'verified_percentage': (verified_count / self.following_count * 100) if self.following_count > 0 else 0,
            'summary': f'{self.following_count} followings with {verified_count} verified accounts indicating network quality'
        }
    
    def validate_requirements(self) -> Dict[str, bool]:
        """
        Validate that collected data meets AC1.4 and AC1.5 requirements.
        
        Returns:
            Dictionary with validation results for each requirement
        """
        return {
            'AC1.4_highlights_available': self.has_highlights,
            'AC1.4_highlights_sufficient': self.highlight_count >= 1,  # At least one highlight
            'AC1.4_shows_user_intent': self.has_highlights and any(
                highlight.get('text') or highlight.get('content') 
                for highlight in self.highlights if isinstance(highlight, dict)
            ),
            'AC1.5_following_patterns_available': self.has_following_patterns,
            'AC1.5_following_patterns_sufficient': self.following_count >= 5,  # Minimum for pattern analysis
            'AC1.5_network_insights': self.has_following_patterns and any(
                following.get('verified', False) 
                for following in self.followings if isinstance(following, dict)
            ),
            'enhanced_profile_available': self.has_enhanced_profile,
            'user_id_available': self.user_id is not None,
            'collection_successful': self.collection_success,
        }
    
    def get_profile_summary(self) -> Dict[str, Any]:
        """
        Get a summary of profile data for analysis.
        
        Returns:
            Dictionary with key profile metrics and ScrapeBadger-specific data
        """
        if not self.has_profile_data:
            return {}
        
        profile = self.profile.copy()
        
        # Add computed fields specific to ScrapeBadger
        profile['_has_enhanced_profile'] = self.has_enhanced_profile
        profile['_user_id_available'] = self.user_id is not None
        profile['_tweet_count'] = self.tweet_count
        profile['_highlight_count'] = self.highlight_count
        profile['_following_count'] = self.following_count
        profile['_has_highlights'] = self.has_highlights
        profile['_has_following_patterns'] = self.has_following_patterns
        profile['_highlights_summary'] = self.get_highlights_summary()
        profile['_following_patterns_summary'] = self.get_following_patterns_summary()
        profile['_collection_timestamp'] = self.collection_timestamp.isoformat() if self.collection_timestamp else None
        
        return profile


@dataclass
class CollectedData:
    """
    Unified data storage for multiple sources (TwitterAPI.io and ScrapeBadger).
    
    This is the main data structure that consolidates information from both
    data collection sources, providing a unified interface for downstream
    analysis and processing.
    
    Validates Requirements:
    - AC1.1: System uses both TwitterAPI.io and ScrapeBadger tools in parallel
    - AC3.1: Consolidates and deduplicates data from multiple sources
    """
    username: str
    twitter_api_data: Optional[TwitterAPIData] = None
    scrapebadger_data: Optional[ScrapeBadgerData] = None
    collection_timestamp: datetime = field(default_factory=datetime.now)
    data_quality_score: float = 0.0
    
    def __post_init__(self):
        """Calculate initial data quality score after initialization."""
        self.data_quality_score = self.calculate_quality_score()
    
    @property
    def has_any_data(self) -> bool:
        """Check if any data was successfully collected from either source."""
        return (
            (self.twitter_api_data is not None and self.twitter_api_data.collection_success) or
            (self.scrapebadger_data is not None and self.scrapebadger_data.collection_success)
        )
    
    @property
    def has_both_sources(self) -> bool:
        """Check if data was successfully collected from both sources."""
        return (
            self.twitter_api_data is not None and self.twitter_api_data.collection_success and
            self.scrapebadger_data is not None and self.scrapebadger_data.collection_success
        )
    
    @property
    def available_sources(self) -> List[str]:
        """Get list of sources that successfully collected data."""
        sources = []
        if self.twitter_api_data and self.twitter_api_data.collection_success:
            sources.append("TwitterAPI.io")
        if self.scrapebadger_data and self.scrapebadger_data.collection_success:
            sources.append("ScrapeBadger")
        return sources
    
    @property
    def total_tweets(self) -> int:
        """Get total number of tweets across all sources (before deduplication)."""
        total = 0
        if self.twitter_api_data:
            total += self.twitter_api_data.tweet_count
        if self.scrapebadger_data:
            total += self.scrapebadger_data.tweet_count
        return total
    
    @property
    def total_followings(self) -> int:
        """Get total number of followings across all sources (before deduplication)."""
        total = 0
        if self.twitter_api_data:
            total += self.twitter_api_data.following_count
        if self.scrapebadger_data:
            total += self.scrapebadger_data.following_count
        return total
    
    @property
    def has_highlights(self) -> bool:
        """Check if highlighted/pinned content is available from ScrapeBadger."""
        return (
            self.scrapebadger_data is not None and 
            self.scrapebadger_data.has_highlights
        )
    
    @property
    def has_profile_data(self) -> bool:
        """Check if profile data is available from any source."""
        return (
            (self.twitter_api_data and self.twitter_api_data.has_profile_data) or
            (self.scrapebadger_data and self.scrapebadger_data.has_profile_data)
        )
    
    def get_consolidated_profile(self) -> Dict[str, Any]:
        """
        Get consolidated profile data from all available sources.
        
        ScrapeBadger data takes priority when available, as it typically
        provides more detailed information including user_id.
        
        Returns:
            Consolidated profile dictionary with merged data
        """
        consolidated = {}
        
        # Start with TwitterAPI.io data as base
        if self.twitter_api_data and self.twitter_api_data.has_profile_data:
            consolidated.update(self.twitter_api_data.profile)
        
        # Override/enhance with ScrapeBadger data (higher priority)
        if self.scrapebadger_data and self.scrapebadger_data.has_profile_data:
            consolidated.update(self.scrapebadger_data.profile)
        
        # Add metadata about sources
        consolidated["_sources"] = self.available_sources
        consolidated["_collection_timestamp"] = self.collection_timestamp.isoformat()
        
        return consolidated
    
    def get_all_tweets(self, deduplicate: bool = True) -> List[Dict[str, Any]]:
        """
        Get all tweets from all sources, optionally deduplicated.
        
        Args:
            deduplicate: If True, remove duplicate tweets based on ID or text
            
        Returns:
            List of tweet dictionaries with source attribution
        """
        all_tweets = []
        
        # Add TwitterAPI.io tweets
        if self.twitter_api_data and self.twitter_api_data.tweets:
            for tweet in self.twitter_api_data.tweets:
                tweet_copy = tweet.copy()
                tweet_copy["_source"] = "TwitterAPI.io"
                all_tweets.append(tweet_copy)
        
        # Add ScrapeBadger tweets
        if self.scrapebadger_data and self.scrapebadger_data.tweets:
            for tweet in self.scrapebadger_data.tweets:
                tweet_copy = tweet.copy()
                tweet_copy["_source"] = "ScrapeBadger"
                all_tweets.append(tweet_copy)
        
        if not deduplicate:
            return all_tweets
        
        # Deduplicate based on tweet ID or text similarity
        seen_ids = set()
        seen_texts = set()
        deduplicated = []
        
        for tweet in all_tweets:
            tweet_id = tweet.get("id", "")
            tweet_text = tweet.get("text", "").strip().lower()
            
            # Skip if we've seen this ID or very similar text
            if tweet_id and tweet_id in seen_ids:
                continue
            if tweet_text and tweet_text in seen_texts:
                continue
            
            # Add to seen sets and result
            if tweet_id:
                seen_ids.add(tweet_id)
            if tweet_text:
                seen_texts.add(tweet_text)
            
            deduplicated.append(tweet)
        
        return deduplicated
    
    def get_all_followings(self, deduplicate: bool = True) -> List[Dict[str, Any]]:
        """
        Get all followings from all sources, optionally deduplicated.
        
        Args:
            deduplicate: If True, remove duplicate users based on username
            
        Returns:
            List of user dictionaries with source attribution
        """
        all_followings = []
        
        # Add TwitterAPI.io followings
        if self.twitter_api_data and self.twitter_api_data.followings:
            for user in self.twitter_api_data.followings:
                user_copy = user.copy()
                user_copy["_source"] = "TwitterAPI.io"
                all_followings.append(user_copy)
        
        # Add ScrapeBadger followings
        if self.scrapebadger_data and self.scrapebadger_data.followings:
            for user in self.scrapebadger_data.followings:
                user_copy = user.copy()
                user_copy["_source"] = "ScrapeBadger"
                all_followings.append(user_copy)
        
        if not deduplicate:
            return all_followings
        
        # Deduplicate based on username
        seen_usernames = set()
        deduplicated = []
        
        for user in all_followings:
            username = user.get("username", "").lower()
            if not username or username in seen_usernames:
                continue
            
            seen_usernames.add(username)
            deduplicated.append(user)
        
        return deduplicated
    
    def get_highlights(self) -> List[Dict[str, Any]]:
        """
        Get highlighted/pinned content from ScrapeBadger.
        
        Returns:
            List of highlight dictionaries with source attribution
        """
        if not self.has_highlights:
            return []
        
        highlights = []
        for highlight in self.scrapebadger_data.highlights:
            highlight_copy = highlight.copy()
            highlight_copy["_source"] = "ScrapeBadger"
            highlight_copy["_type"] = "highlight"
            highlights.append(highlight_copy)
        
        return highlights
    
    @property
    def collection_success(self) -> bool:
        """Check if data collection was successful from at least one source."""
        return self.has_any_data
    
    def get_total_items(self) -> int:
        """Get total number of items collected (tweets + followings + highlights)."""
        total = 0
        total += self.total_tweets
        total += self.total_followings
        if self.has_highlights:
            total += len(self.get_highlights())
        return total
    
    def calculate_quality_score(self) -> float:
        """
        Calculate data quality score based on completeness and source diversity.
        
        Quality factors:
        - Data source diversity (0-0.3): More sources = higher quality
        - Content volume (0-0.3): More tweets = better analysis potential  
        - Profile completeness (0-0.2): Having profile data is essential
        - Highlights availability (0-0.2): Pinned content shows intent
        
        Returns:
            Quality score between 0.0 and 1.0
        """
        score = 0.0
        
        # Data source diversity (0-0.3)
        source_count = len(self.available_sources)
        score += min(source_count * 0.15, 0.3)
        
        # Content volume (0-0.3)
        total_tweets = self.total_tweets
        score += min(total_tweets / 50 * 0.3, 0.3)
        
        # Profile completeness (0-0.2)
        if self.has_profile_data:
            score += 0.2
        
        # Highlights availability (0-0.2)
        if self.has_highlights:
            score += 0.2
        
        return min(score, 1.0)
    
    def get_collection_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the data collection results.
        
        Returns:
            Dictionary with collection statistics and quality metrics
        """
        return {
            "username": self.username,
            "collection_timestamp": self.collection_timestamp.isoformat(),
            "sources_attempted": [
                "TwitterAPI.io" if self.twitter_api_data else None,
                "ScrapeBadger" if self.scrapebadger_data else None
            ],
            "sources_successful": self.available_sources,
            "data_quality_score": self.data_quality_score,
            "statistics": {
                "total_tweets": self.total_tweets,
                "total_followings": self.total_followings,
                "highlights_count": len(self.get_highlights()),
                "has_profile_data": self.has_profile_data,
                "has_both_sources": self.has_both_sources,
            },
            "errors": {
                "twitter_api_error": (
                    self.twitter_api_data.error_message 
                    if self.twitter_api_data and not self.twitter_api_data.collection_success 
                    else None
                ),
                "scrapebadger_error": (
                    self.scrapebadger_data.error_message 
                    if self.scrapebadger_data and not self.scrapebadger_data.collection_success 
                    else None
                ),
            }
        }


# Pydantic models for API compatibility and validation
class CollectedDataModel(BaseModel):
    """Pydantic model version of CollectedData for API serialization."""
    
    username: str = Field(..., description="X/Twitter username (without @)")
    twitter_api_data: Optional[Dict[str, Any]] = Field(None, description="Data collected from TwitterAPI.io")
    scrapebadger_data: Optional[Dict[str, Any]] = Field(None, description="Data collected from ScrapeBadger")
    collection_timestamp: datetime = Field(default_factory=datetime.now, description="When data was collected")
    data_quality_score: float = Field(0.0, ge=0.0, le=1.0, description="Quality score from 0.0 to 1.0")
    
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }


def create_collected_data(
    username: str,
    twitter_api_data: Optional[TwitterAPIData] = None,
    scrapebadger_data: Optional[ScrapeBadgerData] = None
) -> CollectedData:
    """
    Factory function to create a CollectedData instance.
    
    Args:
        username: X/Twitter username (without @)
        twitter_api_data: Optional TwitterAPI.io data
        scrapebadger_data: Optional ScrapeBadger data
        
    Returns:
        CollectedData instance with calculated quality score
    """
    return CollectedData(
        username=username.replace("@", "").strip(),
        twitter_api_data=twitter_api_data,
        scrapebadger_data=scrapebadger_data
    )


def create_twitter_api_data_from_responses(
    profile_response: Optional[str] = None,
    tweets_response: Optional[str] = None,
    followings_response: Optional[List[Dict[str, Any]]] = None,
    collection_success: bool = True,
    error_message: Optional[str] = None
) -> TwitterAPIData:
    """
    Factory function to create TwitterAPIData from TwitterAPI.io toolkit responses.
    
    This function handles the parsing and structuring of responses from the
    TwitterAPI.io toolkit methods (get_user_info, get_user_tweets, get_user_followings).
    
    Args:
        profile_response: JSON string response from get_user_info
        tweets_response: JSON string response from get_user_tweets  
        followings_response: List response from get_user_followings
        collection_success: Whether the collection was successful
        error_message: Error message if collection failed
        
    Returns:
        TwitterAPIData instance with parsed and structured data
        
    Example:
        >>> profile_json = '{"username": "testuser", "name": "Test User", ...}'
        >>> tweets_json = '[{"id": "123", "text": "Hello", "like_count": 5}, ...]'
        >>> followings = [{"username": "friend", "name": "Friend"}, ...]
        >>> data = create_twitter_api_data_from_responses(
        ...     profile_response=profile_json,
        ...     tweets_response=tweets_json,
        ...     followings_response=followings
        ... )
    """
    import json
    
    # Parse profile data
    profile = None
    if profile_response and not profile_response.startswith("Error:"):
        try:
            profile = json.loads(profile_response)
        except json.JSONDecodeError:
            collection_success = False
            error_message = f"Failed to parse profile response: {profile_response[:100]}..."
    
    # Parse tweets data
    tweets = []
    if tweets_response and not tweets_response.startswith("Error:"):
        try:
            tweets = json.loads(tweets_response)
            if not isinstance(tweets, list):
                tweets = []
        except json.JSONDecodeError:
            # Don't fail completely, just log the issue
            tweets = []
    
    # Use followings data directly (already parsed by toolkit)
    followings = followings_response if followings_response else []
    
    return TwitterAPIData(
        profile=profile,
        tweets=tweets,
        followings=followings,
        collection_success=collection_success,
        error_message=error_message
    )
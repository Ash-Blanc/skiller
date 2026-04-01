"""
Data consolidation implementation for merging multiple data sources.

This module implements data merging, deduplication, and conflict resolution
for TwitterAPI.io and ScrapeBadger data sources in the Advanced Skill Generator Workflow.
"""

import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import hashlib

from ..models.collected_data import CollectedData, TwitterAPIData, ScrapeBadgerData
from ..utils.workflow_metrics import get_workflow_monitor


@dataclass
class ConsolidationResult:
    """Result of data consolidation process."""
    consolidated_profile: Dict[str, Any]
    consolidated_tweets: List[Dict[str, Any]]
    consolidated_followings: List[Dict[str, Any]]
    consolidated_highlights: List[Dict[str, Any]]
    
    # Metadata
    total_items_before: int
    total_items_after: int
    duplicates_removed: int
    conflicts_resolved: int
    source_priority_applied: List[str]
    consolidation_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConflictResolution:
    """Information about a resolved conflict between sources."""
    field_name: str
    twitter_value: Any
    scrapebadger_value: Any
    resolved_value: Any
    resolution_strategy: str
    confidence: float


class DataConsolidator:
    """Consolidates data from multiple sources with deduplication and conflict resolution."""
    
    def __init__(self):
        self.logger = logging.getLogger("data_consolidator")
        self.workflow_monitor = get_workflow_monitor()
        
        # Source priority rules (higher number = higher priority)
        self.source_priorities = {
            'twitter_api': 1.0,
            'scrapebadger': 1.2  # ScrapeBadger gets slight priority for enriched data
        }
        
        # Field-specific priority rules
        self.field_priorities = {
            'username': {'twitter_api': 1.0, 'scrapebadger': 0.8},  # Twitter API more authoritative for username
            'followers_count': {'twitter_api': 1.2, 'scrapebadger': 1.0},  # Twitter API more accurate for counts
            'description': {'twitter_api': 1.0, 'scrapebadger': 1.3},  # ScrapeBadger may have richer descriptions
            'verified': {'twitter_api': 1.5, 'scrapebadger': 1.0},  # Twitter API authoritative for verification
            'location': {'twitter_api': 1.0, 'scrapebadger': 1.1}
        }
    
    def consolidate_data(self, collected_data: CollectedData, 
                        workflow_id: str = None) -> ConsolidationResult:
        """
        Consolidate data from multiple sources with deduplication and conflict resolution.
        
        Args:
            collected_data: The collected data to consolidate
            workflow_id: Optional workflow ID for tracking
            
        Returns:
            ConsolidationResult with merged and deduplicated data
        """
        if workflow_id:
            self.workflow_monitor.start_timer(f"{workflow_id}_data_consolidation")
        
        self.logger.info(f"Starting data consolidation for {collected_data.username}")
        
        # Count initial items
        initial_counts = self._count_initial_items(collected_data)
        
        # Consolidate profile data
        consolidated_profile, profile_conflicts = self._consolidate_profiles(collected_data)
        
        # Consolidate and deduplicate tweets
        consolidated_tweets, tweet_duplicates = self._consolidate_tweets(collected_data)
        
        # Consolidate and deduplicate followings
        consolidated_followings, following_duplicates = self._consolidate_followings(collected_data)
        
        # Consolidate highlights (ScrapeBadger specific)
        consolidated_highlights = self._consolidate_highlights(collected_data)
        
        # Calculate final counts
        final_counts = {
            'tweets': len(consolidated_tweets),
            'followings': len(consolidated_followings),
            'highlights': len(consolidated_highlights)
        }
        
        total_duplicates = tweet_duplicates + following_duplicates
        
        # Create consolidation result
        result = ConsolidationResult(
            consolidated_profile=consolidated_profile,
            consolidated_tweets=consolidated_tweets,
            consolidated_followings=consolidated_followings,
            consolidated_highlights=consolidated_highlights,
            total_items_before=sum(initial_counts.values()),
            total_items_after=sum(final_counts.values()),
            duplicates_removed=total_duplicates,
            conflicts_resolved=len(profile_conflicts),
            source_priority_applied=list(self.source_priorities.keys())
        )
        
        # Log consolidation results
        if workflow_id:
            duration = self.workflow_monitor.end_timer(f"{workflow_id}_data_consolidation", workflow_id)
            self.workflow_monitor.log_step_completion(
                workflow_id,
                "data_consolidation",
                True,
                items_before=result.total_items_before,
                items_after=result.total_items_after,
                duplicates_removed=result.duplicates_removed,
                conflicts_resolved=result.conflicts_resolved,
                deduplication_rate=total_duplicates / result.total_items_before if result.total_items_before > 0 else 0
            )
        
        self.logger.info(
            f"Data consolidation completed: {result.total_items_before} → {result.total_items_after} items, "
            f"{result.duplicates_removed} duplicates removed, {result.conflicts_resolved} conflicts resolved"
        )
        
        return result
    
    def _count_initial_items(self, collected_data: CollectedData) -> Dict[str, int]:
        """Count initial items across all sources."""
        counts = {'tweets': 0, 'followings': 0, 'highlights': 0}
        
        if collected_data.twitter_api_data:
            counts['tweets'] += len(collected_data.twitter_api_data.tweets)
            counts['followings'] += len(collected_data.twitter_api_data.followings)
        
        if collected_data.scrapebadger_data:
            counts['tweets'] += len(collected_data.scrapebadger_data.tweets)
            counts['highlights'] += len(collected_data.scrapebadger_data.highlights)
        
        return counts
    
    def _consolidate_profiles(self, collected_data: CollectedData) -> Tuple[Dict[str, Any], List[ConflictResolution]]:
        """Consolidate profile data from multiple sources."""
        consolidated_profile = {}
        conflicts = []
        
        # Get profiles from both sources
        twitter_profile = collected_data.twitter_api_data.profile if collected_data.twitter_api_data else {}
        scrapebadger_profile = collected_data.scrapebadger_data.profile if collected_data.scrapebadger_data else {}
        
        # Get all unique fields
        all_fields = set(twitter_profile.keys()) | set(scrapebadger_profile.keys())
        
        for field in all_fields:
            twitter_value = twitter_profile.get(field)
            scrapebadger_value = scrapebadger_profile.get(field)
            
            if twitter_value is not None and scrapebadger_value is not None:
                # Both sources have this field - resolve conflict
                resolved_value, resolution = self._resolve_field_conflict(
                    field, twitter_value, scrapebadger_value
                )
                consolidated_profile[field] = resolved_value
                
                if resolution:
                    conflicts.append(resolution)
                    
            elif twitter_value is not None:
                # Only Twitter API has this field
                consolidated_profile[field] = twitter_value
            elif scrapebadger_value is not None:
                # Only ScrapeBadger has this field
                consolidated_profile[field] = scrapebadger_value
        
        # Add consolidation metadata
        consolidated_profile['_consolidation_metadata'] = {
            'sources_used': [
                'twitter_api' if twitter_profile else None,
                'scrapebadger' if scrapebadger_profile else None
            ],
            'conflicts_resolved': len(conflicts),
            'consolidation_timestamp': datetime.now().isoformat()
        }
        
        return consolidated_profile, conflicts
    
    def _resolve_field_conflict(self, field_name: str, twitter_value: Any, 
                              scrapebadger_value: Any) -> Tuple[Any, Optional[ConflictResolution]]:
        """Resolve conflicts between field values from different sources."""
        
        # If values are identical, no conflict
        if twitter_value == scrapebadger_value:
            return twitter_value, None
        
        # Get field-specific priorities
        field_priorities = self.field_priorities.get(field_name, self.source_priorities)
        twitter_priority = field_priorities.get('twitter_api', self.source_priorities['twitter_api'])
        scrapebadger_priority = field_priorities.get('scrapebadger', self.source_priorities['scrapebadger'])
        
        # Resolve based on field type and priorities
        resolved_value, strategy, confidence = self._apply_resolution_strategy(
            field_name, twitter_value, scrapebadger_value, twitter_priority, scrapebadger_priority
        )
        
        conflict = ConflictResolution(
            field_name=field_name,
            twitter_value=twitter_value,
            scrapebadger_value=scrapebadger_value,
            resolved_value=resolved_value,
            resolution_strategy=strategy,
            confidence=confidence
        )
        
        return resolved_value, conflict
    
    def _apply_resolution_strategy(self, field_name: str, twitter_value: Any, 
                                 scrapebadger_value: Any, twitter_priority: float, 
                                 scrapebadger_priority: float) -> Tuple[Any, str, float]:
        """Apply specific resolution strategy based on field type and values."""
        
        # Numeric fields - use more recent or higher priority
        if isinstance(twitter_value, (int, float)) and isinstance(scrapebadger_value, (int, float)):
            if field_name in ['followers_count', 'following_count']:
                # For counts, use the higher value if difference is reasonable (within 20%)
                diff_ratio = abs(twitter_value - scrapebadger_value) / max(twitter_value, scrapebadger_value)
                if diff_ratio <= 0.2:
                    # Values are close, use higher priority source
                    if twitter_priority > scrapebadger_priority:
                        return twitter_value, "priority_based", 0.8
                    else:
                        return scrapebadger_value, "priority_based", 0.8
                else:
                    # Values differ significantly, use higher value (more recent)
                    if twitter_value > scrapebadger_value:
                        return twitter_value, "higher_value", 0.6
                    else:
                        return scrapebadger_value, "higher_value", 0.6
        
        # String fields - use priority or combine
        if isinstance(twitter_value, str) and isinstance(scrapebadger_value, str):
            if field_name == 'description':
                # For descriptions, use the longer, more informative one
                if len(scrapebadger_value) > len(twitter_value) * 1.2:
                    return scrapebadger_value, "longer_description", 0.7
                elif len(twitter_value) > len(scrapebadger_value) * 1.2:
                    return twitter_value, "longer_description", 0.7
                else:
                    # Similar length, use priority
                    if twitter_priority > scrapebadger_priority:
                        return twitter_value, "priority_based", 0.6
                    else:
                        return scrapebadger_value, "priority_based", 0.6
            else:
                # For other string fields, use priority
                if twitter_priority > scrapebadger_priority:
                    return twitter_value, "priority_based", 0.8
                else:
                    return scrapebadger_value, "priority_based", 0.8
        
        # Boolean fields - use higher priority source
        if isinstance(twitter_value, bool) and isinstance(scrapebadger_value, bool):
            if twitter_priority > scrapebadger_priority:
                return twitter_value, "priority_based", 0.9
            else:
                return scrapebadger_value, "priority_based", 0.9
        
        # Default: use higher priority source
        if twitter_priority > scrapebadger_priority:
            return twitter_value, "default_priority", 0.5
        else:
            return scrapebadger_value, "default_priority", 0.5
    
    def _consolidate_tweets(self, collected_data: CollectedData) -> Tuple[List[Dict[str, Any]], int]:
        """Consolidate and deduplicate tweets from multiple sources."""
        all_tweets = []
        
        # Collect tweets from all sources
        if collected_data.twitter_api_data:
            for tweet in collected_data.twitter_api_data.tweets:
                tweet_copy = tweet.copy()
                tweet_copy['_source'] = 'twitter_api'
                all_tweets.append(tweet_copy)
        
        if collected_data.scrapebadger_data:
            for tweet in collected_data.scrapebadger_data.tweets:
                tweet_copy = tweet.copy()
                tweet_copy['_source'] = 'scrapebadger'
                all_tweets.append(tweet_copy)
        
        # Deduplicate tweets
        deduplicated_tweets, duplicates_count = self._deduplicate_tweets(all_tweets)
        
        return deduplicated_tweets, duplicates_count
    
    def _deduplicate_tweets(self, tweets: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """Deduplicate tweets based on content similarity and IDs."""
        if not tweets:
            return [], 0
        
        unique_tweets = []
        seen_ids = set()
        seen_content_hashes = set()
        duplicates_count = 0
        
        for tweet in tweets:
            tweet_id = tweet.get('id')
            tweet_text = tweet.get('text', '')
            
            # Create content hash for similarity detection
            content_hash = hashlib.md5(tweet_text.lower().strip().encode()).hexdigest()
            
            # Check for exact ID match
            if tweet_id and tweet_id in seen_ids:
                duplicates_count += 1
                continue
            
            # Check for content similarity
            if content_hash in seen_content_hashes:
                duplicates_count += 1
                continue
            
            # This is a unique tweet
            unique_tweets.append(tweet)
            if tweet_id:
                seen_ids.add(tweet_id)
            seen_content_hashes.add(content_hash)
        
        # Sort by creation date (most recent first)
        unique_tweets.sort(key=lambda t: t.get('created_at', ''), reverse=True)
        
        return unique_tweets, duplicates_count
    
    def _consolidate_followings(self, collected_data: CollectedData) -> Tuple[List[Dict[str, Any]], int]:
        """Consolidate and deduplicate following data."""
        all_followings = []
        
        # Collect followings from Twitter API (ScrapeBadger doesn't typically provide followings)
        if collected_data.twitter_api_data:
            for following in collected_data.twitter_api_data.followings:
                following_copy = following.copy()
                following_copy['_source'] = 'twitter_api'
                all_followings.append(following_copy)
        
        # Deduplicate followings
        deduplicated_followings, duplicates_count = self._deduplicate_followings(all_followings)
        
        return deduplicated_followings, duplicates_count
    
    def _deduplicate_followings(self, followings: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """Deduplicate followings based on username."""
        if not followings:
            return [], 0
        
        unique_followings = []
        seen_usernames = set()
        duplicates_count = 0
        
        for following in followings:
            username = following.get('username', '').lower()
            
            if username in seen_usernames:
                duplicates_count += 1
                continue
            
            unique_followings.append(following)
            seen_usernames.add(username)
        
        return unique_followings, duplicates_count
    
    def _consolidate_highlights(self, collected_data: CollectedData) -> List[Dict[str, Any]]:
        """Consolidate highlights (primarily from ScrapeBadger)."""
        highlights = []
        
        if collected_data.scrapebadger_data:
            for highlight in collected_data.scrapebadger_data.highlights:
                highlight_copy = highlight.copy()
                highlight_copy['_source'] = 'scrapebadger'
                highlights.append(highlight_copy)
        
        return highlights


def consolidate_collected_data(collected_data: CollectedData, 
                             workflow_id: str = None) -> ConsolidationResult:
    """
    Convenience function for data consolidation.
    
    Args:
        collected_data: The collected data to consolidate
        workflow_id: Optional workflow ID for tracking
        
    Returns:
        ConsolidationResult with consolidated data
    """
    consolidator = DataConsolidator()
    return consolidator.consolidate_data(collected_data, workflow_id)


if __name__ == "__main__":
    # Demo data consolidation
    from ..models.collected_data import create_collected_data, TwitterAPIData, ScrapeBadgerData
    
    # Create sample data with overlaps and conflicts for testing
    twitter_data = TwitterAPIData(
        profile={
            "username": "testuser",
            "display_name": "Test User",
            "description": "Short description",
            "followers_count": 1000,
            "following_count": 500,
            "verified": True,
            "location": "San Francisco"
        },
        tweets=[
            {"id": "1", "text": "First tweet about AI", "like_count": 10, "created_at": "2024-01-15"},
            {"id": "2", "text": "Working on machine learning", "like_count": 5, "created_at": "2024-01-14"},
            {"id": "3", "text": "Duplicate content test", "like_count": 3, "created_at": "2024-01-13"}
        ],
        followings=[
            {"username": "expert1", "verified": True, "followers_count": 10000},
            {"username": "expert2", "verified": False, "followers_count": 5000},
            {"username": "duplicate_user", "verified": True}
        ],
        collection_success=True
    )
    
    scrapebadger_data = ScrapeBadgerData(
        profile={
            "username": "testuser",
            "display_name": "Test User (Enhanced)",
            "description": "Much longer and more detailed description with additional context about expertise",
            "followers_count": 1050,  # Slight difference
            "verified": True,
            "location": "San Francisco, CA"  # More specific
        },
        tweets=[
            {"id": "2", "text": "Working on machine learning", "like_count": 5, "created_at": "2024-01-14"},  # Duplicate
            {"id": "4", "text": "New insights on deep learning", "like_count": 15, "created_at": "2024-01-16"},
            {"id": "5", "text": "duplicate content test", "like_count": 3, "created_at": "2024-01-13"}  # Similar content
        ],
        highlights=[
            {"type": "pinned", "text": "This is my most important work", "id": "pin1"},
            {"type": "featured", "text": "Check out my latest research", "id": "feat1"}
        ],
        collection_success=True
    )
    
    collected_data = create_collected_data("testuser", twitter_data, scrapebadger_data)
    
    print("Data Consolidation Demo")
    print("=" * 50)
    
    print(f"Before Consolidation:")
    print(f"  Twitter tweets: {len(twitter_data.tweets)}")
    print(f"  ScrapeBadger tweets: {len(scrapebadger_data.tweets)}")
    print(f"  Twitter followings: {len(twitter_data.followings)}")
    print(f"  ScrapeBadger highlights: {len(scrapebadger_data.highlights)}")
    
    # Perform consolidation
    consolidator = DataConsolidator()
    result = consolidator.consolidate_data(collected_data, "demo_consolidation_123")
    
    print(f"\nAfter Consolidation:")
    print(f"  Consolidated tweets: {len(result.consolidated_tweets)}")
    print(f"  Consolidated followings: {len(result.consolidated_followings)}")
    print(f"  Consolidated highlights: {len(result.consolidated_highlights)}")
    print(f"  Total items: {result.total_items_before} → {result.total_items_after}")
    print(f"  Duplicates removed: {result.duplicates_removed}")
    print(f"  Conflicts resolved: {result.conflicts_resolved}")
    
    print(f"\nProfile Consolidation:")
    profile = result.consolidated_profile
    print(f"  Username: {profile.get('username')}")
    print(f"  Description: {profile.get('description')[:50]}...")
    print(f"  Followers: {profile.get('followers_count')}")
    print(f"  Location: {profile.get('location')}")
    print(f"  Verified: {profile.get('verified')}")
    
    print(f"\nConsolidated Tweets:")
    for i, tweet in enumerate(result.consolidated_tweets[:3]):
        source = tweet.get('_source', 'unknown')
        print(f"  {i+1}. [{source}] {tweet.get('text', '')[:40]}...")
    
    if result.consolidated_highlights:
        print(f"\nHighlights:")
        for highlight in result.consolidated_highlights:
            print(f"  • {highlight.get('type', 'unknown')}: {highlight.get('text', '')[:40]}...")
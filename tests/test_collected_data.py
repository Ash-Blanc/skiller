"""
Unit tests for CollectedData dataclass and related models.

Tests the unified data storage functionality for multiple sources
as specified in task 1.1 of the Advanced Skill Generator Workflow.
"""

import pytest
from datetime import datetime
from app.models.collected_data import (
    CollectedData,
    TwitterAPIData,
    ScrapeBadgerData,
    create_collected_data
)


class TestTwitterAPIData:
    """Test TwitterAPIData dataclass functionality."""
    
    def test_initialization_with_defaults(self):
        """Test TwitterAPIData initialization with default values."""
        data = TwitterAPIData()
        
        assert data.profile is None
        assert data.tweets == []
        assert data.followings == []
        assert data.collection_success is False
        assert data.error_message is None
        assert isinstance(data.collection_timestamp, datetime)
    
    def test_initialization_with_data(self):
        """Test TwitterAPIData initialization with actual data."""
        profile = {"username": "testuser", "name": "Test User", "description": "Test bio"}
        tweets = [{"id": "123", "text": "Hello world"}]
        followings = [{"username": "friend", "name": "Friend"}]
        
        data = TwitterAPIData(
            profile=profile,
            tweets=tweets,
            followings=followings,
            collection_success=True
        )
        
        assert data.profile == profile
        assert data.tweets == tweets
        assert data.followings == followings
        assert data.collection_success is True
        assert data.has_profile_data is True
        assert data.tweet_count == 1
        assert data.following_count == 1
    
    def test_properties(self):
        """Test TwitterAPIData property methods."""
        # Empty data
        empty_data = TwitterAPIData()
        assert empty_data.has_profile_data is False
        assert empty_data.tweet_count == 0
        assert empty_data.following_count == 0
        
        # With data
        data = TwitterAPIData(
            profile={"username": "test", "description": "test bio"},
            tweets=[{"id": "1"}, {"id": "2"}],
            followings=[{"username": "user1"}]
        )
        assert data.has_profile_data is True
        assert data.tweet_count == 2
        assert data.following_count == 1


class TestScrapeBadgerData:
    """Test ScrapeBadgerData dataclass functionality."""
    
    def test_initialization_with_defaults(self):
        """Test ScrapeBadgerData initialization with default values."""
        data = ScrapeBadgerData()
        
        assert data.profile is None
        assert data.tweets == []
        assert data.highlights == []
        assert data.followings == []
        assert data.collection_success is False
        assert data.error_message is None
        assert isinstance(data.collection_timestamp, datetime)
    
    def test_initialization_with_data(self):
        """Test ScrapeBadgerData initialization with actual data."""
        profile = {"username": "testuser", "user_id": "123456"}
        tweets = [{"id": "123", "text": "Hello world"}]
        highlights = [{"id": "456", "text": "Pinned tweet"}]
        followings = [{"username": "friend", "name": "Friend"}]
        
        data = ScrapeBadgerData(
            profile=profile,
            tweets=tweets,
            highlights=highlights,
            followings=followings,
            collection_success=True
        )
        
        assert data.profile == profile
        assert data.tweets == tweets
        assert data.highlights == highlights
        assert data.followings == followings
        assert data.collection_success is True
        assert data.has_profile_data is True
        assert data.has_highlights is True
        assert data.tweet_count == 1
        assert data.highlight_count == 1
        assert data.following_count == 1
    
    def test_properties(self):
        """Test ScrapeBadgerData property methods."""
        # Empty data
        empty_data = ScrapeBadgerData()
        assert empty_data.has_profile_data is False
        assert empty_data.has_highlights is False
        assert empty_data.tweet_count == 0
        assert empty_data.highlight_count == 0
        assert empty_data.following_count == 0
        
        # With data
        data = ScrapeBadgerData(
            profile={"username": "test"},
            tweets=[{"id": "1"}, {"id": "2"}],
            highlights=[{"id": "h1"}],
            followings=[{"username": "user1"}]
        )
        assert data.has_profile_data is True
        assert data.has_highlights is True
        assert data.tweet_count == 2
        assert data.highlight_count == 1
        assert data.following_count == 1
    
    def test_enhanced_profile_validation(self):
        """Test enhanced profile validation for ScrapeBadger-specific fields."""
        # Profile without user_id (not enhanced)
        basic_profile = ScrapeBadgerData(
            profile={"username": "test", "description": "bio"},
            collection_success=True
        )
        assert basic_profile.has_profile_data is True
        assert basic_profile.has_enhanced_profile is False
        assert basic_profile.user_id is None
        
        # Profile with user_id (enhanced)
        enhanced_profile = ScrapeBadgerData(
            profile={"username": "test", "user_id": "123456", "description": "bio"},
            collection_success=True
        )
        assert enhanced_profile.has_profile_data is True
        assert enhanced_profile.has_enhanced_profile is True
        assert enhanced_profile.user_id == "123456"
    
    def test_following_patterns_validation(self):
        """Test following patterns validation (AC1.5)."""
        # No followings
        no_followings = ScrapeBadgerData()
        assert no_followings.has_following_patterns is False
        
        # With followings
        with_followings = ScrapeBadgerData(
            followings=[
                {"username": "user1", "verified": True, "followers_count": 50000},
                {"username": "user2", "verified": False, "followers_count": 1000}
            ],
            collection_success=True
        )
        assert with_followings.has_following_patterns is True
        assert with_followings.following_count == 2
    
    def test_highlights_summary(self):
        """Test highlights summary generation (AC1.4)."""
        # No highlights
        no_highlights = ScrapeBadgerData()
        summary = no_highlights.get_highlights_summary()
        assert summary['count'] == 0
        assert summary['available'] is False
        
        # With highlights
        with_highlights = ScrapeBadgerData(
            highlights=[
                {"id": "h1", "text": "This is what I'm known for", "type": "pinned"},
                {"id": "h2", "text": "Another highlight", "type": "featured"}
            ],
            collection_success=True
        )
        summary = with_highlights.get_highlights_summary()
        assert summary['count'] == 2
        assert summary['available'] is True
        assert 'pinned' in summary['content_types']
        assert 'featured' in summary['content_types']
        assert summary['average_length'] > 0
    
    def test_following_patterns_summary(self):
        """Test following patterns summary generation (AC1.5)."""
        # No followings
        no_followings = ScrapeBadgerData()
        summary = no_followings.get_following_patterns_summary()
        assert summary['count'] == 0
        assert summary['available'] is False
        assert summary['verified_count'] == 0
        
        # With followings
        with_followings = ScrapeBadgerData(
            followings=[
                {
                    "username": "techleader", 
                    "verified": True, 
                    "followers_count": 100000,
                    "description": "Tech entrepreneur and engineer"
                },
                {
                    "username": "designer", 
                    "verified": False, 
                    "followers_count": 5000,
                    "description": "Creative designer and artist"
                },
                {
                    "username": "businessceo", 
                    "verified": True, 
                    "followers_count": 50000,
                    "description": "CEO and business founder"
                }
            ],
            collection_success=True
        )
        summary = with_followings.get_following_patterns_summary()
        assert summary['count'] == 3
        assert summary['available'] is True
        assert summary['verified_count'] == 2
        assert summary['high_follower_count'] == 2
        assert summary['verified_percentage'] == pytest.approx(66.67, rel=1e-2)
        assert 'technology' in summary['interest_categories']
        assert 'design' in summary['interest_categories']
        assert 'business' in summary['interest_categories']
    
    def test_requirements_validation(self):
        """Test AC1.4 and AC1.5 requirements validation."""
        # Minimal data that doesn't meet requirements
        minimal_data = ScrapeBadgerData(collection_success=True)
        validation = minimal_data.validate_requirements()
        
        assert validation['AC1.4_highlights_available'] is False
        assert validation['AC1.4_highlights_sufficient'] is False
        assert validation['AC1.5_following_patterns_available'] is False
        assert validation['AC1.5_following_patterns_sufficient'] is False
        assert validation['collection_successful'] is True
        
        # Rich data that meets all requirements
        rich_data = ScrapeBadgerData(
            profile={"username": "test", "user_id": "123", "description": "bio"},
            highlights=[{"id": "h1", "text": "My expertise"}],
            followings=[
                {"username": f"user{i}", "verified": i % 2 == 0} 
                for i in range(10)
            ],
            collection_success=True
        )
        validation = rich_data.validate_requirements()
        
        assert validation['AC1.4_highlights_available'] is True
        assert validation['AC1.4_highlights_sufficient'] is True
        assert validation['AC1.4_shows_user_intent'] is True
        assert validation['AC1.5_following_patterns_available'] is True
        assert validation['AC1.5_following_patterns_sufficient'] is True
        assert validation['AC1.5_network_insights'] is True
        assert validation['enhanced_profile_available'] is True
        assert validation['user_id_available'] is True
        assert validation['collection_successful'] is True
    
    def test_profile_summary(self):
        """Test profile summary generation with ScrapeBadger-specific data."""
        data = ScrapeBadgerData(
            profile={"username": "test", "user_id": "123", "description": "bio"},
            tweets=[{"id": "1", "text": "tweet"}],
            highlights=[{"id": "h1", "text": "highlight"}],
            followings=[{"username": "friend", "verified": True}],
            collection_success=True
        )
        
        summary = data.get_profile_summary()
        
        assert summary["username"] == "test"
        assert summary["user_id"] == "123"
        assert summary["_has_enhanced_profile"] is True
        assert summary["_user_id_available"] is True
        assert summary["_tweet_count"] == 1
        assert summary["_highlight_count"] == 1
        assert summary["_following_count"] == 1
        assert summary["_has_highlights"] is True
        assert summary["_has_following_patterns"] is True
        assert "_highlights_summary" in summary
        assert "_following_patterns_summary" in summary
        assert "_collection_timestamp" in summary


class TestCollectedData:
    """Test CollectedData unified data storage functionality."""
    
    def test_initialization_empty(self):
        """Test CollectedData initialization with no data sources."""
        data = CollectedData(username="testuser")
        
        assert data.username == "testuser"
        assert data.twitter_api_data is None
        assert data.scrapebadger_data is None
        assert isinstance(data.collection_timestamp, datetime)
        assert data.data_quality_score == 0.0
        assert data.has_any_data is False
        assert data.has_both_sources is False
        assert data.available_sources == []
    
    def test_initialization_with_twitter_data(self):
        """Test CollectedData with TwitterAPI.io data only."""
        twitter_data = TwitterAPIData(
            profile={"username": "testuser", "description": "test bio"},
            tweets=[{"id": "1", "text": "tweet1"}],
            collection_success=True
        )
        
        data = CollectedData(username="testuser", twitter_api_data=twitter_data)
        
        assert data.has_any_data is True
        assert data.has_both_sources is False
        assert data.available_sources == ["TwitterAPI.io"]
        assert data.total_tweets == 1
        assert data.has_profile_data is True
        assert data.has_highlights is False
        assert data.data_quality_score > 0.0
    
    def test_initialization_with_scrapebadger_data(self):
        """Test CollectedData with ScrapeBadger data only."""
        scrapebadger_data = ScrapeBadgerData(
            profile={"username": "testuser", "user_id": "123"},
            tweets=[{"id": "1", "text": "tweet1"}],
            highlights=[{"id": "h1", "text": "highlight1"}],
            collection_success=True
        )
        
        data = CollectedData(username="testuser", scrapebadger_data=scrapebadger_data)
        
        assert data.has_any_data is True
        assert data.has_both_sources is False
        assert data.available_sources == ["ScrapeBadger"]
        assert data.total_tweets == 1
        assert data.has_profile_data is True
        assert data.has_highlights is True
        assert data.data_quality_score > 0.0
    
    def test_initialization_with_both_sources(self):
        """Test CollectedData with both data sources."""
        twitter_data = TwitterAPIData(
            profile={"username": "testuser", "followers_count": 1000},
            tweets=[{"id": "1", "text": "tweet1"}],
            collection_success=True
        )
        
        scrapebadger_data = ScrapeBadgerData(
            profile={"username": "testuser", "user_id": "123"},
            tweets=[{"id": "2", "text": "tweet2"}],
            highlights=[{"id": "h1", "text": "highlight1"}],
            collection_success=True
        )
        
        data = CollectedData(
            username="testuser",
            twitter_api_data=twitter_data,
            scrapebadger_data=scrapebadger_data
        )
        
        assert data.has_any_data is True
        assert data.has_both_sources is True
        assert data.available_sources == ["TwitterAPI.io", "ScrapeBadger"]
        assert data.total_tweets == 2
        assert data.has_profile_data is True
        assert data.has_highlights is True
        assert data.data_quality_score > 0.5  # Should be high with both sources
    
    def test_get_consolidated_profile(self):
        """Test profile data consolidation from multiple sources."""
        twitter_data = TwitterAPIData(
            profile={"username": "testuser", "description": "test bio", "followers_count": 1000, "location": "NYC"},
            collection_success=True
        )
        
        scrapebadger_data = ScrapeBadgerData(
            profile={"username": "testuser", "user_id": "123", "verified": True},
            collection_success=True
        )
        
        data = CollectedData(
            username="testuser",
            twitter_api_data=twitter_data,
            scrapebadger_data=scrapebadger_data
        )
        
        consolidated = data.get_consolidated_profile()
        
        # Should have data from both sources, with ScrapeBadger taking priority
        assert consolidated["username"] == "testuser"
        assert consolidated["followers_count"] == 1000  # From TwitterAPI
        assert consolidated["location"] == "NYC"  # From TwitterAPI
        assert consolidated["user_id"] == "123"  # From ScrapeBadger
        assert consolidated["verified"] is True  # From ScrapeBadger
        assert consolidated["_sources"] == ["TwitterAPI.io", "ScrapeBadger"]
        assert "_collection_timestamp" in consolidated
    
    def test_get_all_tweets_no_deduplication(self):
        """Test getting all tweets without deduplication."""
        twitter_data = TwitterAPIData(
            tweets=[{"id": "1", "text": "tweet1"}],
            collection_success=True
        )
        
        scrapebadger_data = ScrapeBadgerData(
            tweets=[{"id": "2", "text": "tweet2"}],
            collection_success=True
        )
        
        data = CollectedData(
            username="testuser",
            twitter_api_data=twitter_data,
            scrapebadger_data=scrapebadger_data
        )
        
        all_tweets = data.get_all_tweets(deduplicate=False)
        
        assert len(all_tweets) == 2
        assert all_tweets[0]["_source"] == "TwitterAPI.io"
        assert all_tweets[1]["_source"] == "ScrapeBadger"
    
    def test_get_all_tweets_with_deduplication(self):
        """Test getting all tweets with deduplication."""
        # Same tweet ID in both sources
        twitter_data = TwitterAPIData(
            tweets=[{"id": "1", "text": "tweet1"}],
            collection_success=True
        )
        
        scrapebadger_data = ScrapeBadgerData(
            tweets=[{"id": "1", "text": "tweet1"}],  # Duplicate ID
            collection_success=True
        )
        
        data = CollectedData(
            username="testuser",
            twitter_api_data=twitter_data,
            scrapebadger_data=scrapebadger_data
        )
        
        all_tweets = data.get_all_tweets(deduplicate=True)
        
        assert len(all_tweets) == 1  # Deduplicated
        assert all_tweets[0]["_source"] == "TwitterAPI.io"  # First one kept
    
    def test_get_all_followings_with_deduplication(self):
        """Test getting all followings with deduplication."""
        twitter_data = TwitterAPIData(
            followings=[{"username": "user1", "name": "User One"}],
            collection_success=True
        )
        
        scrapebadger_data = ScrapeBadgerData(
            followings=[
                {"username": "user1", "name": "User One Updated"},  # Duplicate
                {"username": "user2", "name": "User Two"}
            ],
            collection_success=True
        )
        
        data = CollectedData(
            username="testuser",
            twitter_api_data=twitter_data,
            scrapebadger_data=scrapebadger_data
        )
        
        all_followings = data.get_all_followings(deduplicate=True)
        
        assert len(all_followings) == 2  # user1 deduplicated, user2 kept
        usernames = [user["username"] for user in all_followings]
        assert "user1" in usernames
        assert "user2" in usernames
    
    def test_get_highlights(self):
        """Test getting highlights from ScrapeBadger data."""
        scrapebadger_data = ScrapeBadgerData(
            highlights=[{"id": "h1", "text": "highlight1"}],
            collection_success=True
        )
        
        data = CollectedData(username="testuser", scrapebadger_data=scrapebadger_data)
        
        highlights = data.get_highlights()
        
        assert len(highlights) == 1
        assert highlights[0]["_source"] == "ScrapeBadger"
        assert highlights[0]["_type"] == "highlight"
        assert highlights[0]["text"] == "highlight1"
    
    def test_calculate_quality_score(self):
        """Test quality score calculation algorithm."""
        # Test with no data
        empty_data = CollectedData(username="testuser")
        assert empty_data.calculate_quality_score() == 0.0
        
        # Test with single source, minimal data
        twitter_data = TwitterAPIData(
            profile={"username": "testuser"},
            collection_success=True
        )
        single_source = CollectedData(username="testuser", twitter_api_data=twitter_data)
        score1 = single_source.calculate_quality_score()
        assert 0.0 < score1 < 1.0
        
        # Test with both sources, rich data
        scrapebadger_data = ScrapeBadgerData(
            profile={"username": "testuser"},
            tweets=[{"id": str(i), "text": f"tweet{i}"} for i in range(20)],
            highlights=[{"id": "h1", "text": "highlight"}],
            collection_success=True
        )
        rich_data = CollectedData(
            username="testuser",
            twitter_api_data=twitter_data,
            scrapebadger_data=scrapebadger_data
        )
        score2 = rich_data.calculate_quality_score()
        assert score2 > score1  # Rich data should have higher score
        assert score2 <= 1.0
    
    def test_get_collection_summary(self):
        """Test collection summary generation."""
        twitter_data = TwitterAPIData(
            profile={"username": "testuser", "description": "test bio"},
            tweets=[{"id": "1", "text": "tweet1"}],
            collection_success=True
        )
        
        data = CollectedData(username="testuser", twitter_api_data=twitter_data)
        summary = data.get_collection_summary()
        
        assert summary["username"] == "testuser"
        assert "collection_timestamp" in summary
        assert summary["sources_successful"] == ["TwitterAPI.io"]
        assert summary["data_quality_score"] > 0.0
        assert summary["statistics"]["total_tweets"] == 1
        assert summary["statistics"]["has_profile_data"] is True
        assert summary["errors"]["twitter_api_error"] is None


class TestFactoryFunction:
    """Test the create_collected_data factory function."""
    
    def test_create_collected_data(self):
        """Test factory function creates CollectedData correctly."""
        twitter_data = TwitterAPIData(collection_success=True)
        scrapebadger_data = ScrapeBadgerData(collection_success=True)
        
        data = create_collected_data(
            username="@testuser",  # With @ symbol
            twitter_api_data=twitter_data,
            scrapebadger_data=scrapebadger_data
        )
        
        assert data.username == "testuser"  # @ removed
        assert data.twitter_api_data == twitter_data
        assert data.scrapebadger_data == scrapebadger_data
        assert isinstance(data.collection_timestamp, datetime)
        assert data.data_quality_score >= 0.0
    
    def test_create_collected_data_minimal(self):
        """Test factory function with minimal parameters."""
        data = create_collected_data(username="testuser")
        
        assert data.username == "testuser"
        assert data.twitter_api_data is None
        assert data.scrapebadger_data is None
        assert data.data_quality_score == 0.0


if __name__ == "__main__":
    pytest.main([__file__])
#!/usr/bin/env python3
"""
Validation script for enhanced TwitterAPIData functionality.
Tests the new features added to meet AC1.2 and AC1.3 requirements.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.collected_data import TwitterAPIData, create_twitter_api_data_from_responses
from datetime import datetime


def test_basic_functionality():
    """Test basic TwitterAPIData functionality."""
    print("Testing basic TwitterAPIData functionality...")
    
    # Test with empty data
    data = TwitterAPIData()
    assert data.profile is None
    assert data.tweets == []
    assert data.followings == []
    assert data.collection_success is False
    assert isinstance(data.collection_timestamp, datetime)
    print("✅ Basic initialization works")
    
    # Test with sample data
    profile = {
        "username": "testuser",
        "name": "Test User", 
        "description": "A test user for validation",
        "followers_count": 1000,
        "following_count": 500,
        "verified": True,
        "location": "Test City",
        "created_at": "2020-01-01"
    }
    
    tweets = [
        {
            "id": "123",
            "text": "Hello world!",
            "created_at": "2024-01-01",
            "like_count": 10,
            "retweet_count": 5,
            "reply_count": 2,
            "view_count": 100
        },
        {
            "id": "124", 
            "text": "Another tweet",
            "created_at": "2024-01-02",
            "like_count": 20,
            "retweet_count": 8,
            "reply_count": 3,
            "view_count": 200
        }
    ]
    
    followings = [
        {"username": "friend1", "name": "Friend One", "verified": True},
        {"username": "friend2", "name": "Friend Two", "verified": False}
    ]
    
    data = TwitterAPIData(
        profile=profile,
        tweets=tweets,
        followings=followings,
        collection_success=True
    )
    
    print("✅ Data initialization with sample data works")
    return data


def test_enhanced_properties(data):
    """Test enhanced properties for AC1.2 and AC1.3 validation."""
    print("\nTesting enhanced properties...")
    
    # Test profile properties (AC1.2)
    assert data.has_profile_data is True
    assert data.has_complete_profile is True
    print("✅ Profile data validation works")
    
    # Test tweet properties (AC1.3)
    assert data.tweet_count == 2
    assert data.has_engagement_data is True
    print("✅ Tweet data validation works")
    
    # Test engagement calculations
    total_engagement = data.total_engagement
    assert total_engagement['likes'] == 30  # 10 + 20
    assert total_engagement['retweets'] == 13  # 5 + 8
    assert total_engagement['replies'] == 5  # 2 + 3
    assert total_engagement['views'] == 300  # 100 + 200
    print("✅ Engagement calculations work")
    
    # Test average engagement
    avg_engagement = data.average_engagement
    assert avg_engagement['likes'] == 15.0  # 30 / 2
    assert avg_engagement['retweets'] == 6.5  # 13 / 2
    print("✅ Average engagement calculations work")
    
    # Test high engagement tweets
    high_engagement = data.get_high_engagement_tweets(min_engagement=15)
    assert len(high_engagement) == 2  # Both tweets have >15 total engagement
    assert high_engagement[0]['_total_engagement'] == 31  # 20+8+3 (highest first)
    assert high_engagement[1]['_total_engagement'] == 17  # 10+5+2
    print("✅ High engagement tweet filtering works")


def test_requirements_validation(data):
    """Test AC1.2 and AC1.3 requirements validation."""
    print("\nTesting requirements validation...")
    
    validation = data.validate_requirements()
    
    # AC1.2 requirements
    assert validation['AC1.2_basic_profile'] is True
    assert validation['AC1.2_complete_profile'] is True
    assert validation['AC1.2_bio_available'] is True
    assert validation['AC1.2_followers_available'] is True
    assert validation['AC1.2_verification_available'] is True
    assert validation['AC1.2_location_available'] is True
    print("✅ AC1.2 requirements validation works")
    
    # AC1.3 requirements
    assert validation['AC1.3_tweets_collected'] is True
    assert validation['AC1.3_engagement_metrics'] is True
    assert validation['AC1.3_sufficient_tweets'] is False  # Only 2 tweets, need 10+
    print("✅ AC1.3 requirements validation works")
    
    assert validation['collection_successful'] is True
    print("✅ Overall collection validation works")


def test_factory_function():
    """Test the factory function for creating TwitterAPIData from responses."""
    print("\nTesting factory function...")
    
    # Sample responses from TwitterAPI.io toolkit
    profile_response = '{"username": "testuser", "name": "Test User", "description": "Bio", "followers_count": 1000, "verified": true}'
    tweets_response = '[{"id": "123", "text": "Hello", "like_count": 5, "retweet_count": 2, "reply_count": 1, "view_count": 50}]'
    followings_response = [{"username": "friend", "name": "Friend"}]
    
    data = create_twitter_api_data_from_responses(
        profile_response=profile_response,
        tweets_response=tweets_response,
        followings_response=followings_response,
        collection_success=True
    )
    
    assert data.collection_success is True
    assert data.has_profile_data is True
    assert data.tweet_count == 1
    assert data.following_count == 1
    assert data.profile['username'] == 'testuser'
    assert data.tweets[0]['id'] == '123'
    print("✅ Factory function works correctly")
    
    # Test error handling
    error_data = create_twitter_api_data_from_responses(
        profile_response="Error: User not found",
        collection_success=False,
        error_message="User not found"
    )
    
    assert error_data.collection_success is False
    assert error_data.error_message == "User not found"
    assert error_data.profile is None
    print("✅ Error handling works correctly")


def test_profile_summary():
    """Test profile summary generation."""
    print("\nTesting profile summary...")
    
    data = test_basic_functionality()
    summary = data.get_profile_summary()
    
    assert summary['username'] == 'testuser'
    assert summary['_has_complete_profile'] is True
    assert summary['_tweet_count'] == 2
    assert summary['_has_engagement_data'] is True
    assert '_total_engagement' in summary
    assert '_average_engagement' in summary
    print("✅ Profile summary generation works")


def main():
    """Run all validation tests."""
    print("🚀 Starting TwitterAPIData validation tests...\n")
    
    try:
        # Test basic functionality
        data = test_basic_functionality()
        
        # Test enhanced properties
        test_enhanced_properties(data)
        
        # Test requirements validation
        test_requirements_validation(data)
        
        # Test factory function
        test_factory_function()
        
        # Test profile summary
        test_profile_summary()
        
        print("\n🎉 All tests passed! TwitterAPIData enhancements are working correctly.")
        print("\n✅ Requirements validated:")
        print("   - AC1.2: Collects basic profile info (bio, followers, verification, location)")
        print("   - AC1.3: Retrieves recent tweets with engagement metrics (likes, retweets, replies)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
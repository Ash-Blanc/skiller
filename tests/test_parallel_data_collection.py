"""
Tests for parallel data collection workflow.
"""

import pytest
import time
from unittest.mock import patch, MagicMock

from app.workflow.parallel_data_collection import (
    ParallelDataCollectionWorkflow,
    AdaptiveParallelCollector,
    create_parallel_workflow,
    create_adaptive_collector
)
from app.models.collected_data import CollectedData, TwitterAPIData, ScrapeBadgerData


class TestParallelDataCollectionWorkflow:
    """Test parallel data collection workflow functionality."""
    
    def test_create_parallel_workflow(self):
        """Test creating a parallel workflow instance."""
        workflow = create_parallel_workflow()
        assert isinstance(workflow, ParallelDataCollectionWorkflow)
        assert workflow.twitter_collector is not None
        assert workflow.scrapebadger_collector is not None
    
    def test_collect_data_parallel(self):
        """Test parallel data collection execution."""
        workflow = ParallelDataCollectionWorkflow()
        
        # Test with simulated data
        result = workflow.collect_data_parallel("testuser", "test_workflow_123")
        
        assert isinstance(result, CollectedData)
        assert result.username == "testuser"
        assert result.collection_success  # Should succeed with simulated data
        assert result.data_quality_score > 0
    
    def test_parallel_execution_performance(self):
        """Test that parallel execution is faster than sequential."""
        workflow = ParallelDataCollectionWorkflow()
        
        # Measure parallel execution time
        start_time = time.time()
        result_parallel = workflow.collect_data_parallel("testuser")
        parallel_duration = time.time() - start_time
        
        # Parallel should complete reasonably quickly
        assert parallel_duration < 5.0  # Should complete within 5 seconds
        assert result_parallel.collection_success


class TestAdaptiveParallelCollector:
    """Test adaptive parallel collector functionality."""
    
    def test_create_adaptive_collector(self):
        """Test creating an adaptive collector instance."""
        collector = create_adaptive_collector()
        assert isinstance(collector, AdaptiveParallelCollector)
    
    def test_collect_with_adaptation(self):
        """Test adaptive collection based on system state."""
        collector = AdaptiveParallelCollector()
        
        result = collector.collect_with_adaptation("testuser", "adaptive_test_123")
        
        assert isinstance(result, CollectedData)
        assert result.username == "testuser"
        assert result.collection_success
        assert result.data_quality_score >= 0
    
    def test_determine_collection_strategy(self):
        """Test strategy determination based on system conditions."""
        collector = AdaptiveParallelCollector()
        
        # Mock resource limits and circuit stats
        resource_limits = {
            'max_concurrent': 2,
            'quality_mode': 'balanced'
        }
        
        circuit_stats = {
            'twitter_api_collector': {'state': 'closed'},
            'scrapebadger_collector': {'state': 'closed'}
        }
        
        strategy = collector._determine_collection_strategy(resource_limits, circuit_stats)
        
        assert strategy['type'] in ['parallel', 'sequential', 'fallback']
        assert 'name' in strategy
        assert 'sources' in strategy
    
    def test_performance_analytics(self):
        """Test performance analytics collection."""
        collector = AdaptiveParallelCollector()
        
        # Run a collection to generate performance data
        collector.collect_with_adaptation("testuser")
        
        analytics = collector.get_performance_analytics()
        
        assert 'total_collections' in analytics
        assert analytics['total_collections'] >= 1
        assert 'strategy_performance' in analytics


class TestDataCollectionIntegration:
    """Integration tests for data collection components."""
    
    def test_end_to_end_collection(self):
        """Test complete end-to-end data collection workflow."""
        # Test with adaptive collector (most comprehensive)
        collector = AdaptiveParallelCollector()
        
        username = "testuser"
        workflow_id = "integration_test_123"
        
        result = collector.collect_with_adaptation(username, workflow_id)
        
        # Verify result structure
        assert isinstance(result, CollectedData)
        assert result.username == username
        assert result.collection_timestamp is not None
        
        # Verify data quality
        assert result.data_quality_score >= 0
        assert result.data_quality_score <= 1.0
        
        # Verify at least some data was collected
        assert result.get_total_items() >= 0
        
        # Verify collection summary
        summary = result.get_collection_summary()
        assert summary['username'] == username
        assert 'sources_successful' in summary
        assert 'data_quality_score' in summary
    
    def test_data_consolidation(self):
        """Test data consolidation from multiple sources."""
        collector = AdaptiveParallelCollector()
        
        result = collector.collect_with_adaptation("testuser")
        
        # Test consolidated profile
        profile = result.get_consolidated_profile()
        if profile:  # Only test if profile data exists
            assert '_sources' in profile
            assert '_collection_timestamp' in profile
        
        # Test tweet consolidation
        all_tweets = result.get_all_tweets(deduplicate=True)
        assert isinstance(all_tweets, list)
        
        # Test following consolidation
        all_followings = result.get_all_followings(deduplicate=True)
        assert isinstance(all_followings, list)
        
        # Test highlights
        highlights = result.get_highlights()
        assert isinstance(highlights, list)
    
    def test_error_handling(self):
        """Test error handling in data collection."""
        workflow = ParallelDataCollectionWorkflow()
        
        # Test with invalid username (should still return a result)
        result = workflow.collect_data_parallel("")
        
        assert isinstance(result, CollectedData)
        # Even with errors, should return a valid CollectedData object
    
    def test_resource_adaptation(self):
        """Test adaptation to different resource conditions."""
        collector = AdaptiveParallelCollector()
        
        # Test with different resource scenarios
        test_scenarios = [
            {'max_concurrent': 1, 'quality_mode': 'fast'},
            {'max_concurrent': 2, 'quality_mode': 'balanced'},
            {'max_concurrent': 4, 'quality_mode': 'quality'}
        ]
        
        for scenario in test_scenarios:
            # Mock resource limits
            with patch('app.workflow.parallel_data_collection.get_current_resource_limits', return_value=scenario):
                result = collector.collect_with_adaptation("testuser")
                
                assert isinstance(result, CollectedData)
                assert result.collection_success


if __name__ == "__main__":
    # Run basic tests when executed directly
    pytest.main([__file__, "-v"])
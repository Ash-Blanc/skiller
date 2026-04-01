"""
Tests for network connectivity and rate limit compliance.

This module tests the comprehensive network management features including
rate limiting, retry logic, connectivity monitoring, and adaptive throttling.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import requests

from app.utils.network_manager import (
    NetworkManager, RateLimiter, NetworkConnectivityManager, RetryManager,
    RateLimitConfig, RetryConfig, NetworkHealthMetrics, NetworkStatus,
    RateLimitStrategy, get_network_manager, with_network_management
)


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    def test_token_bucket_rate_limiting(self):
        """Test token bucket rate limiting strategy."""
        config = RateLimitConfig(
            requests_per_minute=60,
            burst_limit=10,
            strategy=RateLimitStrategy.TOKEN_BUCKET
        )
        
        rate_limiter = RateLimiter(config)
        
        # Should allow burst requests up to limit
        for i in range(10):
            assert rate_limiter.acquire(), f"Request {i+1} should be allowed"
        
        # Should deny next request (burst limit exceeded)
        assert not rate_limiter.acquire(), "Request should be rate limited"
        
        # Wait for token refill and try again
        time.sleep(1.1)  # Allow some tokens to refill
        assert rate_limiter.acquire(), "Request should be allowed after token refill"
    
    def test_sliding_window_rate_limiting(self):
        """Test sliding window rate limiting strategy."""
        config = RateLimitConfig(
            requests_per_minute=5,  # Low limit for testing
            strategy=RateLimitStrategy.SLIDING_WINDOW
        )
        
        rate_limiter = RateLimiter(config)
        
        # Should allow requests up to limit
        for i in range(5):
            assert rate_limiter.acquire(), f"Request {i+1} should be allowed"
        
        # Should deny next request (limit exceeded)
        assert not rate_limiter.acquire(), "Request should be rate limited"
        
        # Check wait time
        wait_time = rate_limiter.get_wait_time()
        assert wait_time > 0, "Should have positive wait time"
    
    def test_adaptive_rate_limiting(self):
        """Test adaptive rate limiting with rate limit history."""
        config = RateLimitConfig(
            requests_per_minute=10,
            strategy=RateLimitStrategy.ADAPTIVE
        )
        
        rate_limiter = RateLimiter(config)
        
        # Record some rate limits
        rate_limiter.record_rate_limit()
        rate_limiter.record_rate_limit()
        
        # Adaptive strategy should be more restrictive
        allowed_count = 0
        for i in range(20):
            if rate_limiter.acquire():
                allowed_count += 1
        
        # Should allow fewer requests due to adaptive throttling
        assert allowed_count < 10, "Adaptive throttling should reduce allowed requests"
    
    def test_rate_limiter_stats(self):
        """Test rate limiter statistics."""
        config = RateLimitConfig(requests_per_minute=60, burst_limit=10)
        rate_limiter = RateLimiter(config)
        
        # Make some requests
        for _ in range(5):
            rate_limiter.acquire()
        
        stats = rate_limiter.get_stats()
        
        assert stats['strategy'] == RateLimitStrategy.TOKEN_BUCKET.value
        assert stats['requests_last_minute'] == 5
        assert 'limits' in stats
        assert stats['limits']['requests_per_minute'] == 60


class TestNetworkConnectivityManager:
    """Test network connectivity monitoring."""
    
    @patch('requests.Session.head')
    def test_connectivity_check_success(self, mock_head):
        """Test successful connectivity check."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response
        
        manager = NetworkConnectivityManager()
        result = manager.check_connectivity("test_service")
        
        assert result is True
        assert "test_service" in manager.health_metrics
        assert manager.health_metrics["test_service"].successful_requests == 1
    
    @patch('requests.Session.head')
    def test_connectivity_check_failure(self, mock_head):
        """Test failed connectivity check."""
        mock_head.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        manager = NetworkConnectivityManager()
        result = manager.check_connectivity("test_service")
        
        assert result is False
        assert "test_service" in manager.health_metrics
        assert manager.health_metrics["test_service"].failed_requests == 1
    
    def test_health_metrics_tracking(self):
        """Test health metrics tracking."""
        manager = NetworkConnectivityManager()
        
        # Record some successful requests
        for _ in range(5):
            manager._record_health_metric("test_service", True, 0.1)
        
        # Record some failures
        for _ in range(2):
            manager._record_health_metric("test_service", False, 1.0)
        
        metrics = manager.get_health_metrics("test_service")
        
        assert metrics.total_requests == 7
        assert metrics.successful_requests == 5
        assert metrics.failed_requests == 2
        assert metrics.status in [NetworkStatus.HEALTHY, NetworkStatus.DEGRADED]
    
    def test_network_status_calculation(self):
        """Test network status calculation based on metrics."""
        manager = NetworkConnectivityManager()
        
        # Test healthy status (high success rate)
        for _ in range(20):
            manager._record_health_metric("healthy_service", True, 0.1)
        
        assert manager.get_network_status("healthy_service") == NetworkStatus.HEALTHY
        
        # Test unhealthy status (low success rate)
        for _ in range(10):
            manager._record_health_metric("unhealthy_service", False, 1.0)
        
        assert manager.get_network_status("unhealthy_service") == NetworkStatus.UNHEALTHY


class TestRetryManager:
    """Test retry logic with exponential backoff."""
    
    def test_successful_retry(self):
        """Test successful execution without retries."""
        config = RetryConfig(max_attempts=3)
        retry_manager = RetryManager(config)
        
        def successful_function():
            return "success"
        
        result = retry_manager.execute_with_retry(successful_function)
        assert result == "success"
    
    def test_retry_with_eventual_success(self):
        """Test retry logic with eventual success."""
        config = RetryConfig(max_attempts=3, base_delay=0.1)
        retry_manager = RetryManager(config)
        
        call_count = 0
        
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests.exceptions.ConnectionError("Connection failed")
            return "success"
        
        start_time = time.time()
        result = retry_manager.execute_with_retry(flaky_function)
        end_time = time.time()
        
        assert result == "success"
        assert call_count == 3
        # Should have some delay due to retries
        assert end_time - start_time > 0.1
    
    def test_retry_exhaustion(self):
        """Test retry exhaustion with persistent failures."""
        config = RetryConfig(max_attempts=2, base_delay=0.1)
        retry_manager = RetryManager(config)
        
        def always_fail():
            raise requests.exceptions.ConnectionError("Always fails")
        
        with pytest.raises(requests.exceptions.ConnectionError):
            retry_manager.execute_with_retry(always_fail)
    
    def test_non_retryable_exception(self):
        """Test that non-retryable exceptions are not retried."""
        config = RetryConfig(max_attempts=3)
        retry_manager = RetryManager(config)
        
        call_count = 0
        
        def non_retryable_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-retryable error")
        
        with pytest.raises(ValueError):
            retry_manager.execute_with_retry(non_retryable_function)
        
        # Should only be called once (no retries)
        assert call_count == 1
    
    def test_rate_limit_retry_with_retry_after(self):
        """Test retry logic with rate limit and Retry-After header."""
        config = RetryConfig(max_attempts=2, base_delay=0.1)
        retry_manager = RetryManager(config)
        
        call_count = 0
        
        def rate_limited_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Simulate rate limit with Retry-After header
                response = Mock()
                response.status_code = 429
                response.headers = {'Retry-After': '1'}
                
                error = requests.exceptions.HTTPError("Rate limited")
                error.response = response
                raise error
            return "success"
        
        start_time = time.time()
        result = retry_manager.execute_with_retry(rate_limited_function)
        end_time = time.time()
        
        assert result == "success"
        assert call_count == 2
        # Should respect Retry-After header (at least 1 second delay)
        assert end_time - start_time >= 1.0


class TestNetworkManager:
    """Test comprehensive network management."""
    
    def test_network_manager_initialization(self):
        """Test network manager initialization."""
        manager = NetworkManager()
        
        assert manager.connectivity_manager is not None
        assert manager.retry_manager is not None
        assert len(manager.service_configs) > 0
        assert "twitter_api" in manager.service_configs
        assert "scrapebadger" in manager.service_configs
    
    def test_rate_limiter_creation(self):
        """Test rate limiter creation for services."""
        manager = NetworkManager()
        
        # Get rate limiter for Twitter API
        twitter_limiter = manager.get_rate_limiter("twitter_api")
        assert twitter_limiter is not None
        
        # Should reuse existing limiter
        twitter_limiter2 = manager.get_rate_limiter("twitter_api")
        assert twitter_limiter is twitter_limiter2
        
        # Different service should get different limiter
        scrapebadger_limiter = manager.get_rate_limiter("scrapebadger")
        assert scrapebadger_limiter is not twitter_limiter
    
    @patch('app.utils.network_manager.NetworkConnectivityManager.check_connectivity')
    def test_execute_with_network_management_success(self, mock_connectivity):
        """Test successful execution with network management."""
        mock_connectivity.return_value = True
        
        manager = NetworkManager()
        
        def test_function(arg1, arg2):
            return f"result: {arg1}, {arg2}"
        
        result = manager.execute_with_network_management(
            "test_service", test_function, "hello", arg2="world"
        )
        
        assert result == "result: hello, world"
    
    @patch('app.utils.network_manager.NetworkConnectivityManager.check_connectivity')
    def test_execute_with_rate_limiting(self, mock_connectivity):
        """Test execution with rate limiting."""
        mock_connectivity.return_value = True
        
        manager = NetworkManager()
        
        # Configure very restrictive rate limiting for testing
        manager.service_configs["test_service"] = RateLimitConfig(
            requests_per_minute=2,
            burst_limit=1,
            strategy=RateLimitStrategy.TOKEN_BUCKET
        )
        
        def test_function():
            return "success"
        
        # First call should succeed
        result1 = manager.execute_with_network_management("test_service", test_function)
        assert result1 == "success"
        
        # Second call should be rate limited and raise exception
        with pytest.raises(Exception, match="Rate limit exceeded"):
            manager.execute_with_network_management("test_service", test_function)
    
    def test_network_health_report(self):
        """Test network health report generation."""
        manager = NetworkManager()
        
        # Make some requests to generate data
        manager.get_rate_limiter("twitter_api")
        manager.get_rate_limiter("scrapebadger")
        
        health_report = manager.get_network_health_report()
        
        assert "timestamp" in health_report
        assert "overall_status" in health_report
        assert "services" in health_report
        assert "recommendations" in health_report
        
        # Should have some basic structure even without real data
        assert isinstance(health_report["recommendations"], list)


class TestNetworkManagementDecorator:
    """Test network management decorator."""
    
    def test_decorator_application(self):
        """Test that decorator properly applies network management."""
        
        @with_network_management("test_service")
        def decorated_function(value):
            return f"processed: {value}"
        
        # Mock the network manager to avoid actual network calls
        with patch('app.utils.network_manager.get_network_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.execute_with_network_management.return_value = "mocked result"
            mock_get_manager.return_value = mock_manager
            
            result = decorated_function("test")
            
            assert result == "mocked result"
            mock_manager.execute_with_network_management.assert_called_once()


class TestNetworkManagerIntegration:
    """Integration tests for network management with collectors."""
    
    @patch('app.utils.network_manager.NetworkConnectivityManager.check_connectivity')
    @patch('requests.Session.head')
    def test_twitter_collector_with_network_management(self, mock_head, mock_connectivity):
        """Test Twitter collector with network management integration."""
        # Mock successful connectivity
        mock_connectivity.return_value = True
        mock_response = Mock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response
        
        from app.agents.twitter_api_collector import TwitterAPICollector
        
        collector = TwitterAPICollector()
        
        # Test that network manager is properly initialized
        assert collector.network_manager is not None
        
        # Test data collection (will use simulated data)
        result = collector.collect_profile_data("test_user", "test_workflow")
        
        assert result is not None
        assert result.collection_success is True
        
        # Check that network health information is included in metadata
        if result.metadata:
            assert "network_health" in result.metadata
            assert "rate_limiter_stats" in result.metadata
    
    @patch('app.utils.network_manager.NetworkConnectivityManager.check_connectivity')
    @patch('requests.Session.head')
    def test_scrapebadger_collector_with_network_management(self, mock_head, mock_connectivity):
        """Test ScrapeBadger collector with network management integration."""
        # Mock successful connectivity
        mock_connectivity.return_value = True
        mock_response = Mock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response
        
        from app.agents.scrapebadger_collector import ScrapeBadgerCollector
        
        collector = ScrapeBadgerCollector()
        
        # Test that network manager is properly initialized
        assert collector.network_manager is not None
        
        # Test data collection (will use simulated data)
        result = collector.collect_enriched_data("test_user", "test_workflow")
        
        assert result is not None
        assert result.collection_success is True
        
        # Check that network health information is included in metadata
        if result.metadata:
            assert "network_health" in result.metadata
            assert "rate_limiter_stats" in result.metadata


class TestNetworkManagerConcurrency:
    """Test network manager under concurrent load."""
    
    def test_concurrent_rate_limiting(self):
        """Test rate limiting under concurrent access."""
        manager = NetworkManager()
        
        # Configure restrictive rate limiting
        manager.service_configs["concurrent_test"] = RateLimitConfig(
            requests_per_minute=10,
            burst_limit=5,
            strategy=RateLimitStrategy.TOKEN_BUCKET
        )
        
        results = []
        errors = []
        
        def make_request(request_id):
            try:
                def test_func():
                    return f"request_{request_id}"
                
                result = manager.execute_with_network_management(
                    "concurrent_test", test_func
                )
                results.append(result)
            except Exception as e:
                errors.append(str(e))
        
        # Launch concurrent requests
        threads = []
        for i in range(20):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should have some successful requests and some rate limited
        assert len(results) > 0, "Should have some successful requests"
        assert len(errors) > 0, "Should have some rate limited requests"
        
        # Check that rate limit errors are properly identified
        rate_limit_errors = [e for e in errors if "Rate limit exceeded" in e]
        assert len(rate_limit_errors) > 0, "Should have rate limit errors"


if __name__ == "__main__":
    # Run basic functionality tests
    print("Testing Network Connectivity and Rate Limiting")
    print("=" * 50)
    
    # Test rate limiter
    print("Testing Rate Limiter...")
    config = RateLimitConfig(requests_per_minute=5, burst_limit=3)
    rate_limiter = RateLimiter(config)
    
    for i in range(10):
        if rate_limiter.acquire():
            print(f"Request {i+1}: Allowed")
        else:
            wait_time = rate_limiter.get_wait_time()
            print(f"Request {i+1}: Rate limited, wait {wait_time:.2f}s")
    
    print(f"Rate limiter stats: {rate_limiter.get_stats()}")
    
    # Test network manager
    print("\nTesting Network Manager...")
    manager = get_network_manager()
    
    def test_function():
        return "Network management test successful"
    
    try:
        result = manager.execute_with_network_management("test", test_function)
        print(f"Network management result: {result}")
    except Exception as e:
        print(f"Network management error: {e}")
    
    # Show health report
    health_report = manager.get_network_health_report()
    print(f"\nNetwork Health Report:")
    print(f"Overall Status: {health_report['overall_status']}")
    print(f"Recommendations: {health_report['recommendations']}")
    
    print("\nNetwork connectivity and rate limiting tests completed!")
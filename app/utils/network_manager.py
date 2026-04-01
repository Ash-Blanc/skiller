"""
Network connectivity and rate limit compliance manager.

This module provides comprehensive network management including rate limiting,
retry logic with exponential backoff, connection monitoring, and adaptive
throttling for the Advanced Skill Generator Workflow.
"""

import time
import logging
import asyncio
import threading
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import random
import json
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import functools


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    ADAPTIVE = "adaptive"


class NetworkStatus(Enum):
    """Network connectivity status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10
    strategy: RateLimitStrategy = RateLimitStrategy.ADAPTIVE
    backoff_factor: float = 2.0
    max_backoff: float = 300.0  # 5 minutes
    jitter: bool = True
    respect_retry_after: bool = True


@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    retryable_status_codes: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])
    retryable_exceptions: List[type] = field(default_factory=lambda: [
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.RequestException
    ])


@dataclass
class NetworkHealthMetrics:
    """Network health metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limited_requests: int = 0
    avg_response_time: float = 0.0
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    status: NetworkStatus = NetworkStatus.UNKNOWN


class RateLimiter:
    """Advanced rate limiter with multiple strategies."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.logger = logging.getLogger(f"rate_limiter")
        
        # Token bucket implementation
        self.tokens = config.burst_limit
        self.last_refill = time.time()
        self.lock = threading.Lock()
        
        # Request tracking for adaptive strategy
        self.request_history = []
        self.rate_limit_history = []
        
        # Sliding window tracking
        self.minute_requests = []
        self.hour_requests = []
    
    def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens for rate limiting.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens acquired, False if rate limited
        """
        with self.lock:
            current_time = time.time()
            
            if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                return self._acquire_token_bucket(tokens, current_time)
            elif self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                return self._acquire_sliding_window(tokens, current_time)
            elif self.config.strategy == RateLimitStrategy.ADAPTIVE:
                return self._acquire_adaptive(tokens, current_time)
            else:  # FIXED_WINDOW
                return self._acquire_fixed_window(tokens, current_time)
    
    def _acquire_token_bucket(self, tokens: int, current_time: float) -> bool:
        """Token bucket rate limiting."""
        # Refill tokens based on time elapsed
        time_elapsed = current_time - self.last_refill
        tokens_to_add = time_elapsed * (self.config.requests_per_minute / 60.0)
        
        self.tokens = min(self.config.burst_limit, self.tokens + tokens_to_add)
        self.last_refill = current_time
        
        # Check if we have enough tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False
    
    def _acquire_sliding_window(self, tokens: int, current_time: float) -> bool:
        """Sliding window rate limiting."""
        # Clean old requests
        minute_cutoff = current_time - 60
        hour_cutoff = current_time - 3600
        
        self.minute_requests = [t for t in self.minute_requests if t > minute_cutoff]
        self.hour_requests = [t for t in self.hour_requests if t > hour_cutoff]
        
        # Check limits
        if (len(self.minute_requests) + tokens <= self.config.requests_per_minute and
            len(self.hour_requests) + tokens <= self.config.requests_per_hour):
            
            # Add current request
            for _ in range(tokens):
                self.minute_requests.append(current_time)
                self.hour_requests.append(current_time)
            
            return True
        
        return False
    
    def _acquire_adaptive(self, tokens: int, current_time: float) -> bool:
        """Adaptive rate limiting based on recent rate limit responses."""
        # Start with sliding window as base
        if not self._acquire_sliding_window(tokens, current_time):
            return False
        
        # Apply adaptive throttling based on recent rate limits
        recent_rate_limits = [t for t in self.rate_limit_history if current_time - t < 300]  # 5 minutes
        
        if recent_rate_limits:
            # Reduce rate based on recent rate limits
            throttle_factor = min(len(recent_rate_limits) * 0.2, 0.8)  # Up to 80% reduction
            
            # Random throttling to spread load
            if random.random() < throttle_factor:
                self.logger.debug(f"Adaptive throttling applied: {throttle_factor:.2f}")
                return False
        
        return True
    
    def _acquire_fixed_window(self, tokens: int, current_time: float) -> bool:
        """Fixed window rate limiting."""
        window_start = int(current_time // 60) * 60  # 1-minute windows
        
        # Clean old requests
        self.minute_requests = [t for t in self.minute_requests if t >= window_start]
        
        if len(self.minute_requests) + tokens <= self.config.requests_per_minute:
            for _ in range(tokens):
                self.minute_requests.append(current_time)
            return True
        
        return False
    
    def record_rate_limit(self, retry_after: Optional[int] = None):
        """Record a rate limit response."""
        current_time = time.time()
        self.rate_limit_history.append(current_time)
        
        # Clean old rate limit history
        cutoff = current_time - 3600  # Keep 1 hour of history
        self.rate_limit_history = [t for t in self.rate_limit_history if t > cutoff]
        
        if retry_after and self.config.respect_retry_after:
            # Adjust rate limiting based on retry-after header
            self.logger.info(f"Rate limited, retry after: {retry_after}s")
            # Could implement more sophisticated retry-after handling here
    
    def get_wait_time(self) -> float:
        """Get recommended wait time before next request."""
        with self.lock:
            current_time = time.time()
            
            if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                if self.tokens < 1:
                    return (1 - self.tokens) / (self.config.requests_per_minute / 60.0)
            
            elif self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                minute_cutoff = current_time - 60
                self.minute_requests = [t for t in self.minute_requests if t > minute_cutoff]
                
                if len(self.minute_requests) >= self.config.requests_per_minute:
                    # Wait until oldest request expires
                    return self.minute_requests[0] + 60 - current_time
            
            # For adaptive and fixed window, use base calculation
            recent_rate_limits = [t for t in self.rate_limit_history if current_time - t < 300]
            if recent_rate_limits:
                # Exponential backoff based on recent rate limits
                backoff = min(self.config.backoff_factor ** len(recent_rate_limits), self.config.max_backoff)
                if self.config.jitter:
                    backoff *= (0.5 + random.random() * 0.5)  # Add jitter
                return backoff
        
        return 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        with self.lock:
            current_time = time.time()
            
            # Clean old data
            minute_cutoff = current_time - 60
            hour_cutoff = current_time - 3600
            
            recent_minute = [t for t in self.minute_requests if t > minute_cutoff]
            recent_hour = [t for t in self.hour_requests if t > hour_cutoff]
            recent_rate_limits = [t for t in self.rate_limit_history if t > hour_cutoff]
            
            return {
                "strategy": self.config.strategy.value,
                "tokens_available": self.tokens if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET else None,
                "requests_last_minute": len(recent_minute),
                "requests_last_hour": len(recent_hour),
                "rate_limits_last_hour": len(recent_rate_limits),
                "limits": {
                    "requests_per_minute": self.config.requests_per_minute,
                    "requests_per_hour": self.config.requests_per_hour,
                    "burst_limit": self.config.burst_limit
                },
                "recommended_wait_time": self.get_wait_time()
            }


class NetworkConnectivityManager:
    """Manages network connectivity and health monitoring."""
    
    def __init__(self):
        self.logger = logging.getLogger("network_connectivity")
        self.health_metrics: Dict[str, NetworkHealthMetrics] = {}
        self.lock = threading.Lock()
        
        # Connection pool configuration
        self.session = requests.Session()
        
        # Configure retry strategy for the session
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Health check endpoints
        self.health_check_endpoints = {
            "twitter_api": "https://api.twitter.com/2/tweets/sample/stream",
            "scrapebadger": "https://api.scrapebadger.com/health",
            "general": "https://httpbin.org/status/200"
        }
    
    def check_connectivity(self, service: str = "general", timeout: float = 10.0) -> bool:
        """
        Check network connectivity to a service.
        
        Args:
            service: Service name to check
            timeout: Request timeout in seconds
            
        Returns:
            True if connectivity is good, False otherwise
        """
        endpoint = self.health_check_endpoints.get(service, self.health_check_endpoints["general"])
        
        try:
            start_time = time.time()
            response = self.session.head(endpoint, timeout=timeout)
            response_time = time.time() - start_time
            
            success = response.status_code < 400
            self._record_health_metric(service, success, response_time)
            
            if success:
                self.logger.debug(f"Connectivity check passed for {service}: {response_time:.2f}s")
            else:
                self.logger.warning(f"Connectivity check failed for {service}: HTTP {response.status_code}")
            
            return success
            
        except Exception as e:
            response_time = time.time() - start_time if 'start_time' in locals() else timeout
            self._record_health_metric(service, False, response_time, str(e))
            self.logger.error(f"Connectivity check failed for {service}: {e}")
            return False
    
    def _record_health_metric(self, service: str, success: bool, response_time: float, error: str = None):
        """Record health metrics for a service."""
        with self.lock:
            if service not in self.health_metrics:
                self.health_metrics[service] = NetworkHealthMetrics()
            
            metrics = self.health_metrics[service]
            metrics.total_requests += 1
            
            if success:
                metrics.successful_requests += 1
                metrics.consecutive_successes += 1
                metrics.consecutive_failures = 0
                metrics.last_success_time = datetime.now()
                
                # Update average response time
                total_successful = metrics.successful_requests
                metrics.avg_response_time = (
                    (metrics.avg_response_time * (total_successful - 1) + response_time) / total_successful
                )
            else:
                metrics.failed_requests += 1
                metrics.consecutive_failures += 1
                metrics.consecutive_successes = 0
                metrics.last_failure_time = datetime.now()
            
            # Determine network status
            success_rate = metrics.successful_requests / metrics.total_requests
            
            if success_rate >= 0.95 and metrics.consecutive_failures == 0:
                metrics.status = NetworkStatus.HEALTHY
            elif success_rate >= 0.80 or metrics.consecutive_failures <= 2:
                metrics.status = NetworkStatus.DEGRADED
            else:
                metrics.status = NetworkStatus.UNHEALTHY
    
    def get_network_status(self, service: str = None) -> Union[NetworkStatus, Dict[str, NetworkStatus]]:
        """Get network status for a service or all services."""
        with self.lock:
            if service:
                return self.health_metrics.get(service, NetworkHealthMetrics()).status
            else:
                return {svc: metrics.status for svc, metrics in self.health_metrics.items()}
    
    def get_health_metrics(self, service: str = None) -> Union[NetworkHealthMetrics, Dict[str, NetworkHealthMetrics]]:
        """Get health metrics for a service or all services."""
        with self.lock:
            if service:
                return self.health_metrics.get(service, NetworkHealthMetrics())
            else:
                return self.health_metrics.copy()
    
    def is_service_healthy(self, service: str) -> bool:
        """Check if a service is healthy."""
        status = self.get_network_status(service)
        return status in [NetworkStatus.HEALTHY, NetworkStatus.DEGRADED]


class RetryManager:
    """Manages retry logic with exponential backoff."""
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self.logger = logging.getLogger("retry_manager")
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with retry logic and exponential backoff.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retry attempts fail
        """
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                result = func(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(f"Function succeeded on attempt {attempt + 1}")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if exception is retryable
                if not self._is_retryable_exception(e):
                    self.logger.error(f"Non-retryable exception: {e}")
                    raise e
                
                # Check if we have more attempts
                if attempt == self.config.max_attempts - 1:
                    self.logger.error(f"All {self.config.max_attempts} attempts failed")
                    break
                
                # Calculate delay with exponential backoff
                delay = self._calculate_delay(attempt, e)
                
                self.logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                
                time.sleep(delay)
        
        # All attempts failed
        raise last_exception
    
    def _is_retryable_exception(self, exception: Exception) -> bool:
        """Check if an exception is retryable."""
        # Check by exception type
        for exc_type in self.config.retryable_exceptions:
            if isinstance(exception, exc_type):
                return True
        
        # Check by HTTP status code if it's a requests exception
        if hasattr(exception, 'response') and exception.response is not None:
            status_code = exception.response.status_code
            return status_code in self.config.retryable_status_codes
        
        # Check for rate limit indicators in exception message
        error_msg = str(exception).lower()
        rate_limit_indicators = ['rate limit', 'too many requests', '429', 'quota exceeded']
        
        return any(indicator in error_msg for indicator in rate_limit_indicators)
    
    def _calculate_delay(self, attempt: int, exception: Exception = None) -> float:
        """Calculate delay for next retry attempt."""
        # Base exponential backoff
        delay = min(
            self.config.base_delay * (self.config.backoff_factor ** attempt),
            self.config.max_delay
        )
        
        # Check for Retry-After header in HTTP exceptions
        if (hasattr(exception, 'response') and 
            exception.response is not None and 
            'Retry-After' in exception.response.headers):
            
            try:
                retry_after = int(exception.response.headers['Retry-After'])
                delay = max(delay, retry_after)
                self.logger.info(f"Using Retry-After header: {retry_after}s")
            except (ValueError, TypeError):
                pass
        
        # Add jitter to prevent thundering herd
        if self.config.jitter:
            jitter_factor = 0.1  # 10% jitter
            jitter = delay * jitter_factor * (random.random() * 2 - 1)  # ±10%
            delay += jitter
        
        return max(delay, 0.1)  # Minimum 100ms delay


class NetworkManager:
    """Comprehensive network management with rate limiting and connectivity monitoring."""
    
    def __init__(self):
        self.logger = logging.getLogger("network_manager")
        
        # Initialize components
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.connectivity_manager = NetworkConnectivityManager()
        self.retry_manager = RetryManager()
        
        # Default configurations
        self.default_rate_limit_config = RateLimitConfig()
        self.default_retry_config = RetryConfig()
        
        # Service-specific configurations
        self.service_configs = {
            "twitter_api": RateLimitConfig(
                requests_per_minute=15,  # Conservative for Twitter API
                requests_per_hour=300,
                burst_limit=5,
                strategy=RateLimitStrategy.ADAPTIVE
            ),
            "scrapebadger": RateLimitConfig(
                requests_per_minute=30,
                requests_per_hour=1000,
                burst_limit=10,
                strategy=RateLimitStrategy.SLIDING_WINDOW
            )
        }
    
    def get_rate_limiter(self, service: str) -> RateLimiter:
        """Get or create a rate limiter for a service."""
        if service not in self.rate_limiters:
            config = self.service_configs.get(service, self.default_rate_limit_config)
            self.rate_limiters[service] = RateLimiter(config)
            self.logger.info(f"Created rate limiter for {service}")
        
        return self.rate_limiters[service]
    
    def execute_with_network_management(self, service: str, func: Callable, 
                                      *args, **kwargs) -> Any:
        """
        Execute a function with comprehensive network management.
        
        Args:
            service: Service name for rate limiting and monitoring
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        rate_limiter = self.get_rate_limiter(service)
        
        # Check network connectivity first
        if not self.connectivity_manager.is_service_healthy(service):
            self.logger.warning(f"Service {service} appears unhealthy, proceeding with caution")
        
        # Apply rate limiting
        if not rate_limiter.acquire():
            wait_time = rate_limiter.get_wait_time()
            self.logger.info(f"Rate limited for {service}, waiting {wait_time:.2f}s")
            time.sleep(wait_time)
            
            # Try again after waiting
            if not rate_limiter.acquire():
                raise Exception(f"Rate limit exceeded for {service}")
        
        # Execute with retry logic
        def wrapped_func():
            try:
                result = func(*args, **kwargs)
                
                # Record successful network operation
                self.connectivity_manager._record_health_metric(service, True, 0.0)
                
                return result
                
            except Exception as e:
                # Check if it's a rate limit error
                if self._is_rate_limit_error(e):
                    retry_after = self._extract_retry_after(e)
                    rate_limiter.record_rate_limit(retry_after)
                
                # Record failed network operation
                self.connectivity_manager._record_health_metric(service, False, 0.0, str(e))
                
                raise e
        
        return self.retry_manager.execute_with_retry(wrapped_func)
    
    def _is_rate_limit_error(self, exception: Exception) -> bool:
        """Check if an exception indicates a rate limit error."""
        if hasattr(exception, 'response') and exception.response is not None:
            return exception.response.status_code == 429
        
        error_msg = str(exception).lower()
        rate_limit_indicators = ['rate limit', 'too many requests', 'quota exceeded']
        
        return any(indicator in error_msg for indicator in rate_limit_indicators)
    
    def _extract_retry_after(self, exception: Exception) -> Optional[int]:
        """Extract retry-after value from exception."""
        if (hasattr(exception, 'response') and 
            exception.response is not None and 
            'Retry-After' in exception.response.headers):
            
            try:
                return int(exception.response.headers['Retry-After'])
            except (ValueError, TypeError):
                pass
        
        return None
    
    def get_network_health_report(self) -> Dict[str, Any]:
        """Get comprehensive network health report."""
        health_metrics = self.connectivity_manager.get_health_metrics()
        rate_limiter_stats = {
            service: limiter.get_stats() 
            for service, limiter in self.rate_limiters.items()
        }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": self._calculate_overall_status(health_metrics),
            "services": {
                service: {
                    "health": metrics.__dict__ if hasattr(metrics, '__dict__') else str(metrics),
                    "rate_limiting": rate_limiter_stats.get(service, {})
                }
                for service, metrics in health_metrics.items()
            },
            "recommendations": self._generate_recommendations(health_metrics, rate_limiter_stats)
        }
    
    def _calculate_overall_status(self, health_metrics: Dict[str, NetworkHealthMetrics]) -> str:
        """Calculate overall network status."""
        if not health_metrics:
            return "unknown"
        
        statuses = [metrics.status for metrics in health_metrics.values()]
        
        if all(status == NetworkStatus.HEALTHY for status in statuses):
            return "healthy"
        elif any(status == NetworkStatus.UNHEALTHY for status in statuses):
            return "unhealthy"
        else:
            return "degraded"
    
    def _generate_recommendations(self, health_metrics: Dict[str, NetworkHealthMetrics], 
                                rate_limiter_stats: Dict[str, Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on network health."""
        recommendations = []
        
        for service, metrics in health_metrics.items():
            if metrics.status == NetworkStatus.UNHEALTHY:
                recommendations.append(f"Service {service} is unhealthy - consider using fallback")
            elif metrics.consecutive_failures > 3:
                recommendations.append(f"Service {service} has {metrics.consecutive_failures} consecutive failures")
        
        for service, stats in rate_limiter_stats.items():
            if stats.get("rate_limits_last_hour", 0) > 5:
                recommendations.append(f"Service {service} has frequent rate limits - consider reducing request rate")
            
            wait_time = stats.get("recommended_wait_time", 0)
            if wait_time > 60:
                recommendations.append(f"Service {service} requires {wait_time:.0f}s wait - consider using alternative")
        
        return recommendations


# Global network manager instance
_network_manager = None


def get_network_manager() -> NetworkManager:
    """Get the global network manager instance."""
    global _network_manager
    if _network_manager is None:
        _network_manager = NetworkManager()
    return _network_manager


def with_network_management(service: str):
    """Decorator to add network management to functions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            manager = get_network_manager()
            return manager.execute_with_network_management(service, func, *args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    # Demo network management functionality
    import time
    
    def simulate_api_call(service: str, should_fail: bool = False):
        """Simulate an API call."""
        print(f"Making API call to {service}...")
        time.sleep(0.1)  # Simulate network delay
        
        if should_fail:
            raise requests.exceptions.RequestException(f"Simulated failure for {service}")
        
        return f"Success response from {service}"
    
    # Test network manager
    manager = get_network_manager()
    
    print("Testing Network Management")
    print("=" * 40)
    
    # Test successful calls
    for i in range(5):
        try:
            result = manager.execute_with_network_management(
                "twitter_api", 
                simulate_api_call, 
                "twitter_api"
            )
            print(f"Call {i+1}: {result}")
        except Exception as e:
            print(f"Call {i+1}: Failed - {e}")
        
        time.sleep(0.5)
    
    # Test rate limiting
    print("\nTesting Rate Limiting...")
    rate_limiter = manager.get_rate_limiter("test_service")
    
    for i in range(10):
        if rate_limiter.acquire():
            print(f"Request {i+1}: Allowed")
        else:
            wait_time = rate_limiter.get_wait_time()
            print(f"Request {i+1}: Rate limited, wait {wait_time:.2f}s")
    
    # Show network health report
    health_report = manager.get_network_health_report()
    print(f"\nNetwork Health Report:")
    print(json.dumps(health_report, indent=2, default=str))
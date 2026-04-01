"""
Circuit breaker pattern implementation for tool reliability and fallback.

This module provides circuit breaker functionality to handle tool failures
gracefully and implement fallback mechanisms for the Advanced Skill Generator Workflow.
"""

import time
import logging
import threading
from typing import Callable, Any, Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import functools


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if service is back


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5  # Number of failures before opening
    recovery_timeout: int = 60  # Seconds before trying half-open
    success_threshold: int = 3  # Successes needed to close from half-open
    timeout: float = 30.0  # Request timeout in seconds
    expected_exception: type = Exception  # Exception type to catch


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changes: int = 0


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """Circuit breaker implementation for handling service failures."""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self._lock = threading.Lock()
        self._last_failure_time = 0
        
        self.logger = logging.getLogger(f"circuit_breaker.{name}")
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        with self._lock:
            self.stats.total_requests += 1
            
            # Check if circuit should be opened
            if self.state == CircuitState.CLOSED:
                if self.stats.consecutive_failures >= self.config.failure_threshold:
                    self._open_circuit()
            
            # Check if circuit should transition to half-open
            elif self.state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self.config.recovery_timeout:
                    self._half_open_circuit()
            
            # Fail fast if circuit is open
            if self.state == CircuitState.OPEN:
                self.logger.warning(f"Circuit breaker {self.name} is OPEN - failing fast")
                raise CircuitBreakerError(f"Circuit breaker {self.name} is open")
        
        # Execute the function
        try:
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Check for timeout
            if duration > self.config.timeout:
                raise TimeoutError(f"Function execution exceeded timeout of {self.config.timeout}s")
            
            self._record_success()
            return result
            
        except self.config.expected_exception as e:
            self._record_failure()
            raise e
    
    def _record_success(self):
        """Record a successful call."""
        with self._lock:
            self.stats.successful_requests += 1
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0
            self.stats.last_success_time = datetime.now()
            
            # Close circuit if enough successes in half-open state
            if (self.state == CircuitState.HALF_OPEN and 
                self.stats.consecutive_successes >= self.config.success_threshold):
                self._close_circuit()
            
            self.logger.debug(f"Circuit breaker {self.name} recorded success")
    
    def _record_failure(self):
        """Record a failed call."""
        with self._lock:
            self.stats.failed_requests += 1
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = datetime.now()
            self._last_failure_time = time.time()
            
            # Open circuit if too many failures
            if (self.state == CircuitState.CLOSED and 
                self.stats.consecutive_failures >= self.config.failure_threshold):
                self._open_circuit()
            elif self.state == CircuitState.HALF_OPEN:
                self._open_circuit()
            
            self.logger.warning(f"Circuit breaker {self.name} recorded failure")
    
    def _open_circuit(self):
        """Open the circuit."""
        if self.state != CircuitState.OPEN:
            self.state = CircuitState.OPEN
            self.stats.state_changes += 1
            self.logger.error(f"Circuit breaker {self.name} opened after {self.stats.consecutive_failures} failures")
    
    def _half_open_circuit(self):
        """Transition to half-open state."""
        if self.state != CircuitState.HALF_OPEN:
            self.state = CircuitState.HALF_OPEN
            self.stats.state_changes += 1
            self.stats.consecutive_successes = 0
            self.logger.info(f"Circuit breaker {self.name} transitioned to half-open")
    
    def _close_circuit(self):
        """Close the circuit."""
        if self.state != CircuitState.CLOSED:
            self.state = CircuitState.CLOSED
            self.stats.state_changes += 1
            self.logger.info(f"Circuit breaker {self.name} closed after {self.stats.consecutive_successes} successes")
    
    def reset(self):
        """Reset the circuit breaker to closed state."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.stats = CircuitBreakerStats()
            self._last_failure_time = 0
            self.logger.info(f"Circuit breaker {self.name} reset")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        with self._lock:
            success_rate = 0.0
            if self.stats.total_requests > 0:
                success_rate = (self.stats.successful_requests / self.stats.total_requests) * 100
            
            return {
                "name": self.name,
                "state": self.state.value,
                "total_requests": self.stats.total_requests,
                "successful_requests": self.stats.successful_requests,
                "failed_requests": self.stats.failed_requests,
                "success_rate_percent": round(success_rate, 2),
                "consecutive_failures": self.stats.consecutive_failures,
                "consecutive_successes": self.stats.consecutive_successes,
                "state_changes": self.stats.state_changes,
                "last_failure_time": self.stats.last_failure_time.isoformat() if self.stats.last_failure_time else None,
                "last_success_time": self.stats.last_success_time.isoformat() if self.stats.last_success_time else None,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "recovery_timeout": self.config.recovery_timeout,
                    "success_threshold": self.config.success_threshold,
                    "timeout": self.config.timeout
                }
            }


class CircuitBreakerManager:
    """Manages multiple circuit breakers for different tools/services."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
        self.logger = logging.getLogger("circuit_breaker_manager")
    
    def get_circuit_breaker(self, name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """Get or create a circuit breaker for a service."""
        with self._lock:
            if name not in self.circuit_breakers:
                self.circuit_breakers[name] = CircuitBreaker(name, config)
                self.logger.info(f"Created circuit breaker for {name}")
            return self.circuit_breakers[name]
    
    def call_with_circuit_breaker(self, service_name: str, func: Callable, 
                                 config: CircuitBreakerConfig = None, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        circuit_breaker = self.get_circuit_breaker(service_name, config)
        return circuit_breaker.call(func, *args, **kwargs)
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers."""
        with self._lock:
            return {name: cb.get_stats() for name, cb in self.circuit_breakers.items()}
    
    def reset_circuit_breaker(self, name: str):
        """Reset a specific circuit breaker."""
        with self._lock:
            if name in self.circuit_breakers:
                self.circuit_breakers[name].reset()
                self.logger.info(f"Reset circuit breaker for {name}")
    
    def reset_all_circuit_breakers(self):
        """Reset all circuit breakers."""
        with self._lock:
            for cb in self.circuit_breakers.values():
                cb.reset()
            self.logger.info("Reset all circuit breakers")


class ToolFallbackManager:
    """Manages fallback strategies for tools when primary tools fail."""
    
    def __init__(self):
        self.fallback_chains: Dict[str, List[str]] = {}
        self.tool_functions: Dict[str, Callable] = {}
        self.circuit_manager = CircuitBreakerManager()
        self.logger = logging.getLogger("tool_fallback_manager")
    
    def register_tool(self, name: str, func: Callable, fallbacks: List[str] = None):
        """Register a tool with optional fallback chain."""
        self.tool_functions[name] = func
        if fallbacks:
            self.fallback_chains[name] = fallbacks
        self.logger.info(f"Registered tool {name} with fallbacks: {fallbacks or 'none'}")
    
    def call_with_fallback(self, primary_tool: str, *args, **kwargs) -> Any:
        """Call a tool with automatic fallback on failure."""
        tools_to_try = [primary_tool] + self.fallback_chains.get(primary_tool, [])
        
        last_error = None
        for tool_name in tools_to_try:
            if tool_name not in self.tool_functions:
                self.logger.warning(f"Tool {tool_name} not registered, skipping")
                continue
            
            try:
                self.logger.info(f"Attempting to call tool: {tool_name}")
                
                # Create circuit breaker config for this tool
                config = CircuitBreakerConfig(
                    failure_threshold=3,
                    recovery_timeout=30,
                    success_threshold=2
                )
                
                result = self.circuit_manager.call_with_circuit_breaker(
                    tool_name, 
                    self.tool_functions[tool_name], 
                    config,
                    *args, 
                    **kwargs
                )
                
                self.logger.info(f"Successfully called tool: {tool_name}")
                return result
                
            except (CircuitBreakerError, Exception) as e:
                last_error = e
                self.logger.warning(f"Tool {tool_name} failed: {str(e)}")
                continue
        
        # All tools failed
        self.logger.error(f"All tools failed for {primary_tool}. Last error: {last_error}")
        raise Exception(f"All fallback tools failed for {primary_tool}. Last error: {last_error}")
    
    def get_tool_health(self) -> Dict[str, Any]:
        """Get health status of all tools."""
        circuit_stats = self.circuit_manager.get_all_stats()
        
        tool_health = {}
        for tool_name in self.tool_functions.keys():
            if tool_name in circuit_stats:
                stats = circuit_stats[tool_name]
                health_status = "healthy"
                
                if stats["state"] == "open":
                    health_status = "unhealthy"
                elif stats["state"] == "half_open":
                    health_status = "recovering"
                elif stats["success_rate_percent"] < 80:
                    health_status = "degraded"
                
                tool_health[tool_name] = {
                    "status": health_status,
                    "state": stats["state"],
                    "success_rate": stats["success_rate_percent"],
                    "total_requests": stats["total_requests"],
                    "fallbacks": self.fallback_chains.get(tool_name, [])
                }
            else:
                tool_health[tool_name] = {
                    "status": "unknown",
                    "state": "not_used",
                    "success_rate": 0,
                    "total_requests": 0,
                    "fallbacks": self.fallback_chains.get(tool_name, [])
                }
        
        return tool_health


# Global instances
_circuit_manager = None
_fallback_manager = None


def get_circuit_manager() -> CircuitBreakerManager:
    """Get the global circuit breaker manager."""
    global _circuit_manager
    if _circuit_manager is None:
        _circuit_manager = CircuitBreakerManager()
    return _circuit_manager


def get_fallback_manager() -> ToolFallbackManager:
    """Get the global tool fallback manager."""
    global _fallback_manager
    if _fallback_manager is None:
        _fallback_manager = ToolFallbackManager()
    return _fallback_manager


def circuit_breaker(name: str, config: CircuitBreakerConfig = None):
    """Decorator to add circuit breaker protection to functions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            manager = get_circuit_manager()
            return manager.call_with_circuit_breaker(name, func, config, *args, **kwargs)
        return wrapper
    return decorator


def with_fallback(primary_tool: str, fallbacks: List[str] = None):
    """Decorator to add fallback capability to tool functions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            manager = get_fallback_manager()
            
            # Register the tool if not already registered
            if primary_tool not in manager.tool_functions:
                manager.register_tool(primary_tool, func, fallbacks)
            
            return manager.call_with_fallback(primary_tool, *args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    # Demo circuit breaker functionality
    import random
    
    def unreliable_service():
        """Simulate an unreliable service."""
        if random.random() < 0.7:  # 70% failure rate
            raise Exception("Service temporarily unavailable")
        return "Success!"
    
    def fallback_service():
        """Simulate a fallback service."""
        if random.random() < 0.2:  # 20% failure rate
            raise Exception("Fallback service failed")
        return "Fallback success!"
    
    # Test circuit breaker
    manager = get_circuit_manager()
    config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=5)
    
    print("Testing circuit breaker...")
    for i in range(10):
        try:
            result = manager.call_with_circuit_breaker("test_service", unreliable_service, config)
            print(f"Call {i+1}: {result}")
        except Exception as e:
            print(f"Call {i+1}: Failed - {e}")
        
        time.sleep(0.5)
    
    # Show stats
    stats = manager.get_all_stats()
    print(f"\nCircuit Breaker Stats: {stats}")
    
    # Test fallback manager
    fallback_manager = get_fallback_manager()
    fallback_manager.register_tool("primary", unreliable_service, ["fallback"])
    fallback_manager.register_tool("fallback", fallback_service)
    
    print("\nTesting fallback mechanism...")
    for i in range(5):
        try:
            result = fallback_manager.call_with_fallback("primary")
            print(f"Fallback call {i+1}: {result}")
        except Exception as e:
            print(f"Fallback call {i+1}: Failed - {e}")
    
    # Show tool health
    health = fallback_manager.get_tool_health()
    print(f"\nTool Health: {health}")
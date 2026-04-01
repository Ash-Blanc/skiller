"""
Integration module for resource monitoring with Agno workflows.

This module provides decorators and utilities to integrate resource monitoring
with the Advanced Skill Generator Workflow execution.
"""

import functools
import time
import logging
from typing import Any, Callable, Dict, Optional, Tuple
from contextlib import contextmanager
import uuid

from .resource_monitor import get_resource_monitor, get_workflow_manager
from .resource_config import get_current_config

logger = logging.getLogger(__name__)


class ResourceConstraintError(Exception):
    """Raised when resource constraints prevent workflow execution."""
    pass


def with_resource_monitoring(workflow_name: str = None):
    """
    Decorator to add resource monitoring to workflow functions.
    
    Args:
        workflow_name: Optional name for the workflow (defaults to function name)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate workflow ID
            workflow_id = f"{workflow_name or func.__name__}_{uuid.uuid4().hex[:8]}"
            
            # Get resource manager
            workflow_manager = get_workflow_manager()
            
            # Check if workflow can start
            can_start, reason = workflow_manager.can_start_workflow(workflow_id)
            if not can_start:
                raise ResourceConstraintError(f"Cannot start workflow {workflow_id}: {reason}")
            
            # Register workflow start
            workflow_manager.register_workflow_start(workflow_id)
            
            try:
                # Execute the workflow
                start_time = time.time()
                result = func(*args, **kwargs)
                end_time = time.time()
                
                # Log performance metrics
                duration = end_time - start_time
                logger.info(f"Workflow {workflow_id} completed successfully in {duration:.2f}s")
                
                return result
                
            except Exception as e:
                logger.error(f"Workflow {workflow_id} failed: {str(e)}")
                raise
                
            finally:
                # Always unregister workflow
                workflow_manager.register_workflow_end(workflow_id)
        
        return wrapper
    return decorator


@contextmanager
def resource_managed_execution(workflow_id: str = None):
    """
    Context manager for resource-managed workflow execution.
    
    Args:
        workflow_id: Optional workflow ID (auto-generated if not provided)
    """
    if workflow_id is None:
        workflow_id = f"workflow_{uuid.uuid4().hex[:8]}"
    
    workflow_manager = get_workflow_manager()
    
    # Check if workflow can start
    can_start, reason = workflow_manager.can_start_workflow(workflow_id)
    if not can_start:
        raise ResourceConstraintError(f"Cannot start workflow {workflow_id}: {reason}")
    
    # Register workflow start
    workflow_manager.register_workflow_start(workflow_id)
    
    try:
        yield workflow_id
    finally:
        # Always unregister workflow
        workflow_manager.register_workflow_end(workflow_id)


class AdaptiveResourceManager:
    """
    Adaptive resource manager that adjusts workflow behavior based on system load.
    """
    
    def __init__(self):
        self.monitor = get_resource_monitor()
        self.config = get_current_config()
        self._last_adjustment = 0
        self._adjustment_interval = 30  # seconds
    
    def get_optimal_batch_size(self) -> int:
        """Get optimal batch size based on current system resources."""
        current_metrics = self.monitor.get_current_metrics()
        base_batch_size = self.config.parallel_config.batch_size
        
        # Adjust based on CPU usage
        if current_metrics.cpu_percent > 85:
            return max(1, base_batch_size // 2)
        elif current_metrics.cpu_percent < 50:
            return min(base_batch_size * 2, self.config.parallel_config.max_concurrent_workflows)
        
        return base_batch_size
    
    def get_optimal_concurrency(self) -> int:
        """Get optimal concurrency level based on current system resources."""
        current_metrics = self.monitor.get_current_metrics()
        max_concurrent = self.config.parallel_config.max_concurrent_workflows
        
        # Adjust based on memory usage
        if current_metrics.memory_percent > 85:
            return max(1, max_concurrent // 2)
        elif current_metrics.memory_percent < 60:
            return max_concurrent
        
        # Adjust based on CPU usage
        if current_metrics.cpu_percent > 80:
            return max(1, max_concurrent * 3 // 4)
        
        return max_concurrent
    
    def should_enable_caching(self) -> bool:
        """Determine if caching should be enabled based on memory availability."""
        current_metrics = self.monitor.get_current_metrics()
        
        # Disable caching if memory is tight
        if current_metrics.memory_percent > 80:
            return False
        
        return self.config.parallel_config.enable_caching
    
    def get_quality_mode(self) -> str:
        """Get appropriate quality mode based on system load."""
        current_metrics = self.monitor.get_current_metrics()
        base_mode = self.config.parallel_config.quality_mode
        
        # Switch to fast mode under high load
        if (current_metrics.cpu_percent > 85 or 
            current_metrics.memory_percent > 85):
            return "fast"
        
        # Switch to quality mode under low load
        if (current_metrics.cpu_percent < 40 and 
            current_metrics.memory_percent < 60):
            return "quality"
        
        return base_mode
    
    def get_adaptive_config(self) -> Dict[str, Any]:
        """Get adaptive configuration based on current system state."""
        return {
            "batch_size": self.get_optimal_batch_size(),
            "max_concurrent": self.get_optimal_concurrency(),
            "enable_caching": self.should_enable_caching(),
            "quality_mode": self.get_quality_mode(),
            "memory_limit_mb": self.config.parallel_config.memory_limit_mb,
            "timeout_seconds": self.config.parallel_config.timeout_seconds,
        }
    
    def log_resource_status(self):
        """Log current resource status and adaptive settings."""
        current_metrics = self.monitor.get_current_metrics()
        adaptive_config = self.get_adaptive_config()
        
        logger.info(
            f"Resource Status - "
            f"CPU: {current_metrics.cpu_percent:.1f}%, "
            f"Memory: {current_metrics.memory_percent:.1f}%, "
            f"Available: {current_metrics.memory_available_gb:.1f}GB"
        )
        
        logger.info(
            f"Adaptive Config - "
            f"Batch: {adaptive_config['batch_size']}, "
            f"Concurrent: {adaptive_config['max_concurrent']}, "
            f"Quality: {adaptive_config['quality_mode']}, "
            f"Caching: {adaptive_config['enable_caching']}"
        )


def check_resource_health() -> Tuple[bool, Dict[str, Any]]:
    """
    Check overall resource health for workflow execution.
    
    Returns:
        Tuple of (is_healthy, health_info)
    """
    monitor = get_resource_monitor()
    workflow_manager = get_workflow_manager()
    config = get_current_config()
    
    current_metrics = monitor.get_current_metrics()
    validation_result = monitor.validate_resources(config.resource_requirements)
    
    # Health checks
    is_healthy = True
    issues = []
    
    # Check CPU usage
    if current_metrics.cpu_percent > 90:
        is_healthy = False
        issues.append(f"High CPU usage: {current_metrics.cpu_percent:.1f}%")
    
    # Check memory usage
    if current_metrics.memory_percent > 90:
        is_healthy = False
        issues.append(f"High memory usage: {current_metrics.memory_percent:.1f}%")
    
    # Check available memory
    if current_metrics.memory_available_gb < 0.5:
        is_healthy = False
        issues.append(f"Low available memory: {current_metrics.memory_available_gb:.1f}GB")
    
    # Check disk space
    if current_metrics.disk_free_gb < 1.0:
        is_healthy = False
        issues.append(f"Low disk space: {current_metrics.disk_free_gb:.1f}GB")
    
    # Check if resource requirements are met
    if not validation_result.is_sufficient:
        is_healthy = False
        issues.extend(validation_result.warnings)
    
    health_info = {
        "is_healthy": is_healthy,
        "issues": issues,
        "current_metrics": {
            "cpu_percent": current_metrics.cpu_percent,
            "memory_percent": current_metrics.memory_percent,
            "memory_available_gb": current_metrics.memory_available_gb,
            "disk_free_gb": current_metrics.disk_free_gb,
        },
        "active_workflows": workflow_manager.get_active_workflow_count(),
        "max_safe_concurrent": validation_result.max_safe_concurrent_workflows,
        "recommendations": validation_result.recommendations,
    }
    
    return is_healthy, health_info


def wait_for_resources(max_wait_seconds: int = 300, check_interval: int = 5) -> bool:
    """
    Wait for sufficient resources to become available.
    
    Args:
        max_wait_seconds: Maximum time to wait in seconds
        check_interval: How often to check resources in seconds
        
    Returns:
        True if resources became available, False if timeout
    """
    start_time = time.time()
    
    while time.time() - start_time < max_wait_seconds:
        is_healthy, health_info = check_resource_health()
        
        if is_healthy:
            return True
        
        logger.info(f"Waiting for resources... Issues: {', '.join(health_info['issues'])}")
        time.sleep(check_interval)
    
    logger.warning(f"Timeout waiting for resources after {max_wait_seconds}s")
    return False


# Global adaptive resource manager
_adaptive_manager = None


def get_adaptive_manager() -> AdaptiveResourceManager:
    """Get the global adaptive resource manager instance."""
    global _adaptive_manager
    if _adaptive_manager is None:
        _adaptive_manager = AdaptiveResourceManager()
    return _adaptive_manager


# Convenience functions for workflow integration
def get_current_resource_limits() -> Dict[str, Any]:
    """Get current resource limits for workflow execution."""
    adaptive_manager = get_adaptive_manager()
    return adaptive_manager.get_adaptive_config()


def log_workflow_resources():
    """Log current workflow resource status."""
    adaptive_manager = get_adaptive_manager()
    adaptive_manager.log_resource_status()


if __name__ == "__main__":
    # Test resource integration
    print("Testing resource integration...")
    
    # Check resource health
    is_healthy, health_info = check_resource_health()
    print(f"Resource Health: {'✅ Healthy' if is_healthy else '❌ Issues'}")
    
    if health_info['issues']:
        print("Issues:")
        for issue in health_info['issues']:
            print(f"  • {issue}")
    
    # Show adaptive configuration
    adaptive_manager = get_adaptive_manager()
    config = adaptive_manager.get_adaptive_config()
    print(f"\nAdaptive Configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")
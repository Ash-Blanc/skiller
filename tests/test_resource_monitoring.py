"""
Tests for resource monitoring and parallel processing capabilities.
"""

import pytest
import time
import threading
from unittest.mock import patch, MagicMock

from app.utils.resource_monitor import (
    ResourceMonitor,
    ResourceRequirements,
    ResourceMetrics,
    WorkflowResourceManager,
    validate_parallel_processing_resources
)
from app.utils.resource_config import (
    ResourceConfigManager,
    ParallelProcessingConfig,
    EnvironmentConfig,
    auto_configure_resources
)
from app.utils.workflow_resource_integration import (
    with_resource_monitoring,
    resource_managed_execution,
    AdaptiveResourceManager,
    check_resource_health,
    ResourceConstraintError
)


class TestResourceMonitor:
    """Test resource monitoring functionality."""
    
    def test_get_current_metrics(self):
        """Test getting current system metrics."""
        monitor = ResourceMonitor()
        metrics = monitor.get_current_metrics()
        
        assert isinstance(metrics, ResourceMetrics)
        assert metrics.cpu_percent >= 0
        assert metrics.memory_percent >= 0
        assert metrics.memory_available_gb >= 0
        assert metrics.disk_free_gb >= 0
        assert metrics.active_processes > 0
    
    def test_validate_resources(self):
        """Test resource validation."""
        monitor = ResourceMonitor()
        requirements = ResourceRequirements(
            min_cpu_cores=1,
            min_memory_gb=0.5,
            min_disk_free_gb=0.1,
            max_concurrent_workflows=2
        )
        
        result = monitor.validate_resources(requirements)
        
        assert hasattr(result, 'is_sufficient')
        assert hasattr(result, 'current_resources')
        assert hasattr(result, 'max_safe_concurrent_workflows')
        assert result.max_safe_concurrent_workflows >= 1
    
    def test_resource_summary(self):
        """Test getting resource summary."""
        monitor = ResourceMonitor()
        summary = monitor.get_resource_summary()
        
        assert 'system_capabilities' in summary
        assert 'current_usage' in summary
        assert 'parallel_processing' in summary
        assert 'performance_estimates' in summary
        
        assert summary['system_capabilities']['cpu_cores'] > 0
        assert summary['system_capabilities']['memory_total_gb'] > 0


class TestWorkflowResourceManager:
    """Test workflow resource management."""
    
    def test_workflow_lifecycle(self):
        """Test workflow registration and cleanup."""
        monitor = ResourceMonitor()
        manager = WorkflowResourceManager(monitor)
        
        # Test starting a workflow
        can_start, reason = manager.can_start_workflow("test_workflow")
        assert isinstance(can_start, bool)
        assert isinstance(reason, str)
        
        if can_start:
            # Register workflow
            manager.register_workflow_start("test_workflow")
            assert manager.get_active_workflow_count() == 1
            
            # End workflow
            manager.register_workflow_end("test_workflow")
            assert manager.get_active_workflow_count() == 0
    
    def test_concurrent_workflow_limits(self):
        """Test concurrent workflow limits."""
        monitor = ResourceMonitor()
        manager = WorkflowResourceManager(monitor)
        
        # Get maximum allowed workflows
        validation_result = monitor.validate_resources()
        max_workflows = validation_result.max_safe_concurrent_workflows
        
        # Start workflows up to the limit
        workflow_ids = []
        for i in range(max_workflows):
            workflow_id = f"test_workflow_{i}"
            can_start, _ = manager.can_start_workflow(workflow_id)
            
            if can_start:
                manager.register_workflow_start(workflow_id)
                workflow_ids.append(workflow_id)
        
        # Try to start one more (should fail)
        can_start, reason = manager.can_start_workflow("overflow_workflow")
        if len(workflow_ids) >= max_workflows:
            assert not can_start
            assert "Maximum concurrent workflows" in reason
        
        # Clean up
        for workflow_id in workflow_ids:
            manager.register_workflow_end(workflow_id)


class TestResourceConfiguration:
    """Test resource configuration management."""
    
    def test_default_configs(self):
        """Test default configuration generation."""
        manager = ResourceConfigManager()
        configs = manager.get_default_configs()
        
        assert 'development' in configs
        assert 'staging' in configs
        assert 'production' in configs
        
        dev_config = configs['development']
        assert dev_config.environment == 'development'
        assert dev_config.resource_requirements.min_cpu_cores >= 1
        assert dev_config.parallel_config.max_concurrent_workflows >= 1
    
    def test_auto_configure(self):
        """Test auto-configuration based on system resources."""
        config = auto_configure_resources()
        
        assert isinstance(config, EnvironmentConfig)
        assert config.environment in ['development', 'staging', 'production']
        assert config.parallel_config.max_concurrent_workflows >= 1
        assert config.parallel_config.memory_limit_mb > 0


class TestWorkflowIntegration:
    """Test workflow integration with resource monitoring."""
    
    def test_resource_monitoring_decorator(self):
        """Test the resource monitoring decorator."""
        
        @with_resource_monitoring("test_workflow")
        def sample_workflow():
            time.sleep(0.1)  # Simulate work
            return "completed"
        
        # This should work if resources are available
        try:
            result = sample_workflow()
            assert result == "completed"
        except ResourceConstraintError:
            # This is acceptable if system resources are truly insufficient
            pytest.skip("Insufficient system resources for test")
    
    def test_resource_managed_execution(self):
        """Test resource managed execution context manager."""
        try:
            with resource_managed_execution("test_context") as workflow_id:
                assert workflow_id.startswith("test_context")
                time.sleep(0.1)  # Simulate work
        except ResourceConstraintError:
            # This is acceptable if system resources are truly insufficient
            pytest.skip("Insufficient system resources for test")
    
    def test_adaptive_resource_manager(self):
        """Test adaptive resource management."""
        manager = AdaptiveResourceManager()
        
        # Test getting adaptive configuration
        config = manager.get_adaptive_config()
        
        assert 'batch_size' in config
        assert 'max_concurrent' in config
        assert 'enable_caching' in config
        assert 'quality_mode' in config
        
        assert config['batch_size'] >= 1
        assert config['max_concurrent'] >= 1
        assert config['quality_mode'] in ['fast', 'balanced', 'quality']
    
    def test_resource_health_check(self):
        """Test resource health checking."""
        is_healthy, health_info = check_resource_health()
        
        assert isinstance(is_healthy, bool)
        assert isinstance(health_info, dict)
        
        assert 'is_healthy' in health_info
        assert 'issues' in health_info
        assert 'current_metrics' in health_info
        assert 'active_workflows' in health_info


class TestResourceValidation:
    """Test resource validation functionality."""
    
    def test_validate_parallel_processing_resources(self):
        """Test the main validation function."""
        result = validate_parallel_processing_resources()
        
        assert hasattr(result, 'is_sufficient')
        assert hasattr(result, 'current_resources')
        assert hasattr(result, 'max_safe_concurrent_workflows')
        
        # Should always allow at least 1 workflow
        assert result.max_safe_concurrent_workflows >= 1


@pytest.mark.integration
class TestResourceIntegration:
    """Integration tests for resource monitoring."""
    
    def test_full_resource_workflow(self):
        """Test a complete resource monitoring workflow."""
        # Get current configuration
        config = auto_configure_resources()
        
        # Validate resources
        validation_result = validate_parallel_processing_resources()
        
        # Check health
        is_healthy, health_info = check_resource_health()
        
        # Test workflow execution if resources are sufficient
        if validation_result.is_sufficient:
            @with_resource_monitoring("integration_test")
            def test_workflow():
                return "success"
            
            result = test_workflow()
            assert result == "success"
        else:
            pytest.skip("Insufficient resources for integration test")


if __name__ == "__main__":
    # Run basic tests when executed directly
    pytest.main([__file__, "-v"])
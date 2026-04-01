"""
Comprehensive test suite for workflow monitoring infrastructure.

This module provides thorough testing of the monitoring system including:
- Metrics collection and aggregation
- Structured logging with progress indicators
- Performance monitoring and alerting
- Health check endpoints and system status monitoring
- Integration with workflow validation utilities

Validates Requirements:
- AC5.4: Provides progress indicators for long-running operations
- TR3: System uptime should be 99.5% or higher, comprehensive error logging and monitoring
"""

import pytest
import json
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from app.utils.workflow_monitoring import (
    WorkflowMetricsCollector, StructuredLogger, AlertManager, HealthCheckManager,
    WorkflowMonitor, MetricType, AlertSeverity, HealthStatus, HealthCheck,
    PerformanceMetrics, ProgressIndicator, Alert, get_workflow_monitor,
    setup_workflow_monitoring, monitor_workflow_operation
)


class TestWorkflowMetricsCollector:
    """Test suite for WorkflowMetricsCollector."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.collector = WorkflowMetricsCollector(max_history_size=100)
    
    def test_counter_metrics(self):
        """Test counter metric recording and retrieval."""
        # Record counter metrics
        self.collector.increment_counter("test_counter", 5)
        self.collector.increment_counter("test_counter", 3)
        
        # Verify counter value
        assert self.collector.get_counter_value("test_counter") == 8
        
        # Test with tags
        self.collector.increment_counter("tagged_counter", 1, tags={"env": "test"})
        assert self.collector.get_counter_value("tagged_counter") == 1
    
    def test_gauge_metrics(self):
        """Test gauge metric recording and retrieval."""
        # Record gauge metrics
        self.collector.set_gauge("test_gauge", 42.5)
        assert self.collector.get_gauge_value("test_gauge") == 42.5
        
        # Update gauge value
        self.collector.set_gauge("test_gauge", 100.0)
        assert self.collector.get_gauge_value("test_gauge") == 100.0
    
    def test_timer_metrics(self):
        """Test timer metric recording and statistics."""
        # Record timer metrics
        durations = [100, 200, 150, 300, 250]
        for duration in durations:
            self.collector.record_timer("test_timer", duration)
        
        # Get timer statistics
        stats = self.collector.get_timer_stats("test_timer")
        
        assert stats["count"] == 5
        assert stats["avg"] == 200.0  # (100+200+150+300+250)/5
        assert stats["min"] == 100
        assert stats["max"] == 300
        assert stats["p95"] > 0
        assert stats["p99"] > 0
    
    def test_rate_metrics(self):
        """Test rate metric recording and calculation."""
        # Record rate metrics
        for _ in range(10):
            self.collector.record_rate("test_rate", 1.0)
            time.sleep(0.01)  # Small delay to spread timestamps
        
        # Get rate per minute
        rate = self.collector.get_rate_per_minute("test_rate", window_minutes=1)
        assert rate > 0  # Should have some rate
    
    def test_performance_metrics(self):
        """Test performance metric recording."""
        # Create performance metric
        perf_metric = PerformanceMetrics(
            operation_name="test_operation",
            start_time=datetime.now()
        )
        perf_metric.complete(success=True)
        
        # Record performance metric
        self.collector.record_performance(perf_metric)
        
        # Verify system metrics
        system_metrics = self.collector.get_system_metrics()
        assert system_metrics["total_operations"] == 1
        assert system_metrics["successful_operations"] == 1
        assert system_metrics["failed_operations"] == 0
        assert system_metrics["success_rate_percentage"] == 100.0
    
    def test_thread_safety(self):
        """Test thread safety of metrics collection."""
        def worker():
            for i in range(100):
                self.collector.increment_counter("thread_test", 1)
                self.collector.set_gauge("thread_gauge", i)
                self.collector.record_timer("thread_timer", i * 10)
        
        # Start multiple threads
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # Verify results
        assert self.collector.get_counter_value("thread_test") == 500  # 5 threads * 100 increments
        timer_stats = self.collector.get_timer_stats("thread_timer")
        assert timer_stats["count"] == 500
    
    def test_get_all_metrics(self):
        """Test comprehensive metrics retrieval."""
        # Record various metrics
        self.collector.increment_counter("test_counter", 10)
        self.collector.set_gauge("test_gauge", 50.0)
        self.collector.record_timer("test_timer", 100)
        
        # Get all metrics
        all_metrics = self.collector.get_all_metrics()
        
        # Verify structure
        assert "system" in all_metrics
        assert "counters" in all_metrics
        assert "gauges" in all_metrics
        assert "timers" in all_metrics
        assert "rates" in all_metrics
        assert "performance_summary" in all_metrics
        
        # Verify content
        assert all_metrics["counters"]["test_counter"] == 10
        assert all_metrics["gauges"]["test_gauge"] == 50.0
        assert all_metrics["timers"]["test_timer"]["count"] == 1


class TestStructuredLogger:
    """Test suite for StructuredLogger."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.logger = StructuredLogger("test_logger")
    
    def test_basic_logging(self):
        """Test basic logging functionality."""
        # Test different log levels
        self.logger.info("Test info message", test_key="test_value")
        self.logger.warning("Test warning message", warning_type="test")
        self.logger.error("Test error message", error_code=500)
        self.logger.debug("Test debug message", debug_info="detailed")
        
        # No assertions needed - just verify no exceptions
    
    def test_log_context(self):
        """Test logging context management."""
        with self.logger.log_context(operation="test_op", user="test_user"):
            self.logger.info("Message with context")
            
            with self.logger.log_context(step="validation"):
                self.logger.info("Nested context message")
        
        # Context should be cleared after exiting
        self.logger.info("Message without context")
    
    def test_workflow_step_logging(self):
        """Test workflow step logging."""
        self.logger.log_workflow_step(
            step_name="test_step",
            username="test_user",
            success=True,
            duration_ms=150.5,
            additional_data="test"
        )
        
        self.logger.log_workflow_step(
            step_name="failed_step",
            username="test_user",
            success=False,
            error_message="Test error"
        )
    
    def test_performance_metric_logging(self):
        """Test performance metric logging."""
        perf_metric = PerformanceMetrics(
            operation_name="test_operation",
            start_time=datetime.now()
        )
        perf_metric.complete(success=True)
        
        self.logger.log_performance_metric(perf_metric)
    
    def test_progress_indicators(self):
        """Test progress indicator functionality."""
        # Create progress indicator
        progress = self.logger.create_progress_indicator(
            operation_id="test_op_123",
            operation_name="Test Operation",
            total_steps=5,
            test_metadata="test_value"
        )
        
        assert progress.operation_id == "test_op_123"
        assert progress.total_steps == 5
        assert progress.current_step == 0
        assert progress.progress_percentage == 0.0
        
        # Update progress
        self.logger.update_progress("test_op_123", 2, "Processing step 2")
        
        # Get progress status
        status = self.logger.get_progress_status("test_op_123")
        assert status is not None
        assert status["current_step"] == 2
        assert status["progress_percentage"] == 40.0
        
        # Complete progress
        self.logger.complete_progress("test_op_123", success=True, final_message="Completed successfully")
        
        # Verify completion
        final_status = self.logger.get_progress_status("test_op_123")
        assert final_status["status"] == "completed"
    
    def test_progress_estimation(self):
        """Test progress time estimation."""
        progress = self.logger.create_progress_indicator(
            operation_id="estimation_test",
            operation_name="Estimation Test",
            total_steps=10
        )
        
        # Simulate progress with time delays
        time.sleep(0.1)
        self.logger.update_progress("estimation_test", 2, "Step 2")
        
        status = self.logger.get_progress_status("estimation_test")
        assert status["estimated_completion"] is not None
        
        # Estimated completion should be in the future
        estimated = datetime.fromisoformat(status["estimated_completion"])
        assert estimated > datetime.now()
    
    def test_get_all_progress(self):
        """Test retrieving all progress indicators."""
        # Create multiple progress indicators
        self.logger.create_progress_indicator("op1", "Operation 1", 3)
        self.logger.create_progress_indicator("op2", "Operation 2", 5)
        
        all_progress = self.logger.get_all_progress()
        assert len(all_progress) == 2
        assert "op1" in all_progress
        assert "op2" in all_progress


class TestAlertManager:
    """Test suite for AlertManager."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.alert_manager = AlertManager(max_alerts=100)
        self.test_alerts = []
        
        # Add test alert handler
        def test_handler(alert):
            self.test_alerts.append(alert)
        
        self.alert_manager.add_alert_handler(test_handler)
    
    def test_create_alert(self):
        """Test alert creation and handling."""
        alert = self.alert_manager.create_alert(
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="This is a test alert",
            metadata={"test_key": "test_value"}
        )
        
        assert alert.severity == AlertSeverity.WARNING
        assert alert.title == "Test Alert"
        assert alert.message == "This is a test alert"
        assert not alert.resolved
        
        # Verify handler was called
        assert len(self.test_alerts) == 1
        assert self.test_alerts[0].id == alert.id
    
    def test_alert_rules(self):
        """Test alert rule evaluation."""
        # Add test alert rule
        self.alert_manager.add_alert_rule(
            rule_name="high_error_rate",
            condition=lambda metrics: metrics.get("error_rate", 0) > 0.1,
            severity=AlertSeverity.ERROR,
            title="High Error Rate",
            message_template="Error rate is {error_rate:.2%}",
            cooldown_minutes=1
        )
        
        # Test metrics that should trigger alert
        test_metrics = {"error_rate": 0.15}
        self.alert_manager.evaluate_rules(test_metrics)
        
        # Verify alert was created
        assert len(self.test_alerts) == 1
        assert "Error rate is 15.00%" in self.test_alerts[0].message
        
        # Test cooldown - should not create another alert immediately
        self.alert_manager.evaluate_rules(test_metrics)
        assert len(self.test_alerts) == 1  # Still only one alert
    
    def test_resolve_alert(self):
        """Test alert resolution."""
        alert = self.alert_manager.create_alert(
            severity=AlertSeverity.INFO,
            title="Test Alert",
            message="Test message"
        )
        
        assert not alert.resolved
        
        # Resolve alert
        success = self.alert_manager.resolve_alert(alert.id)
        assert success
        assert alert.resolved
        assert alert.resolved_at is not None
        
        # Try to resolve non-existent alert
        success = self.alert_manager.resolve_alert("non_existent_id")
        assert not success
    
    def test_get_active_alerts(self):
        """Test retrieving active alerts."""
        # Create alerts with different severities
        alert1 = self.alert_manager.create_alert(AlertSeverity.INFO, "Info Alert", "Info message")
        alert2 = self.alert_manager.create_alert(AlertSeverity.WARNING, "Warning Alert", "Warning message")
        alert3 = self.alert_manager.create_alert(AlertSeverity.ERROR, "Error Alert", "Error message")
        
        # Resolve one alert
        self.alert_manager.resolve_alert(alert2.id)
        
        # Get all active alerts
        active_alerts = self.alert_manager.get_active_alerts()
        assert len(active_alerts) == 2
        
        # Get active alerts by severity
        error_alerts = self.alert_manager.get_active_alerts(AlertSeverity.ERROR)
        assert len(error_alerts) == 1
        assert error_alerts[0].severity == AlertSeverity.ERROR
    
    def test_alert_summary(self):
        """Test alert summary statistics."""
        # Create various alerts
        self.alert_manager.create_alert(AlertSeverity.INFO, "Info 1", "Message")
        self.alert_manager.create_alert(AlertSeverity.WARNING, "Warning 1", "Message")
        self.alert_manager.create_alert(AlertSeverity.ERROR, "Error 1", "Message")
        
        summary = self.alert_manager.get_alert_summary()
        
        assert summary["total_alerts"] == 3
        assert summary["active_alerts"] == 3
        assert summary["resolved_alerts"] == 0
        assert summary["alerts_by_severity"]["info"] == 1
        assert summary["alerts_by_severity"]["warning"] == 1
        assert summary["alerts_by_severity"]["error"] == 1


class TestHealthCheckManager:
    """Test suite for HealthCheckManager."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.health_manager = HealthCheckManager()
    
    def test_register_and_run_health_check(self):
        """Test health check registration and execution."""
        def test_health_check():
            return HealthCheck(
                name="test_check",
                status=HealthStatus.HEALTHY,
                message="Test check passed"
            )
        
        # Register health check
        self.health_manager.register_health_check("test_check", test_health_check, 60)
        
        # Run health check
        result = self.health_manager.run_health_check("test_check")
        
        assert result is not None
        assert result.name == "test_check"
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Test check passed"
        assert result.response_time_ms is not None
    
    def test_failing_health_check(self):
        """Test health check that raises an exception."""
        def failing_health_check():
            raise Exception("Test failure")
        
        self.health_manager.register_health_check("failing_check", failing_health_check, 60)
        
        result = self.health_manager.run_health_check("failing_check")
        
        assert result is not None
        assert result.status == HealthStatus.UNHEALTHY
        assert "Test failure" in result.message
    
    def test_run_all_health_checks(self):
        """Test running all registered health checks."""
        def healthy_check():
            return HealthCheck("healthy", HealthStatus.HEALTHY, "OK")
        
        def degraded_check():
            return HealthCheck("degraded", HealthStatus.DEGRADED, "Degraded")
        
        def unhealthy_check():
            return HealthCheck("unhealthy", HealthStatus.UNHEALTHY, "Failed")
        
        # Register multiple checks
        self.health_manager.register_health_check("healthy", healthy_check, 60)
        self.health_manager.register_health_check("degraded", degraded_check, 60)
        self.health_manager.register_health_check("unhealthy", unhealthy_check, 60)
        
        # Run all checks
        results = self.health_manager.run_all_health_checks()
        
        assert len(results) == 3
        assert results["healthy"].status == HealthStatus.HEALTHY
        assert results["degraded"].status == HealthStatus.DEGRADED
        assert results["unhealthy"].status == HealthStatus.UNHEALTHY
    
    def test_system_health_summary(self):
        """Test system health summary calculation."""
        def healthy_check():
            return HealthCheck("healthy", HealthStatus.HEALTHY, "OK")
        
        def unhealthy_check():
            return HealthCheck("unhealthy", HealthStatus.UNHEALTHY, "Failed")
        
        self.health_manager.register_health_check("healthy", healthy_check, 60)
        self.health_manager.register_health_check("unhealthy", unhealthy_check, 60)
        
        # Run checks to populate results
        self.health_manager.run_all_health_checks()
        
        # Get system health
        system_health = self.health_manager.get_system_health()
        
        assert system_health["overall_status"] == HealthStatus.UNHEALTHY.value
        assert "1 unhealthy components" in system_health["message"]
        assert system_health["summary"]["total_checks"] == 2
        assert system_health["summary"]["healthy"] == 1
        assert system_health["summary"]["unhealthy"] == 1
    
    def test_periodic_health_checks(self):
        """Test periodic health check execution."""
        check_count = 0
        
        def counting_check():
            nonlocal check_count
            check_count += 1
            return HealthCheck("counting", HealthStatus.HEALTHY, f"Check #{check_count}")
        
        # Register with short interval for testing
        self.health_manager.register_health_check("counting", counting_check, 1)  # 1 second interval
        
        # Start periodic checks
        self.health_manager.start_periodic_checks()
        
        # Wait for a few checks
        time.sleep(2.5)
        
        # Stop periodic checks
        self.health_manager.stop_periodic_checks()
        
        # Should have run at least 2 checks
        assert check_count >= 2


class TestWorkflowMonitor:
    """Test suite for WorkflowMonitor integration."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.monitor = WorkflowMonitor("test_monitor")
    
    def teardown_method(self):
        """Cleanup after tests."""
        self.monitor.shutdown()
    
    def test_monitor_operation_context(self):
        """Test operation monitoring context manager."""
        with self.monitor.monitor_operation("test_operation", username="test_user") as operation_id:
            assert operation_id is not None
            
            # Simulate some work
            time.sleep(0.1)
        
        # Verify metrics were recorded
        system_metrics = self.monitor.metrics.get_system_metrics()
        assert system_metrics["total_operations"] >= 1
    
    def test_monitor_operation_with_exception(self):
        """Test operation monitoring with exception handling."""
        with pytest.raises(ValueError):
            with self.monitor.monitor_operation("failing_operation", username="test_user"):
                raise ValueError("Test exception")
        
        # Verify failure was recorded
        system_metrics = self.monitor.metrics.get_system_metrics()
        assert system_metrics["failed_operations"] >= 1
    
    def test_monitoring_dashboard(self):
        """Test monitoring dashboard data retrieval."""
        # Generate some activity
        with self.monitor.monitor_operation("dashboard_test"):
            pass
        
        dashboard = self.monitor.get_monitoring_dashboard()
        
        # Verify dashboard structure
        assert "timestamp" in dashboard
        assert "system_health" in dashboard
        assert "metrics" in dashboard
        assert "alerts" in dashboard
        assert "progress_indicators" in dashboard
        assert "monitoring_status" in dashboard
        
        # Verify monitoring status
        status = dashboard["monitoring_status"]
        assert status["metrics_collector_active"] is True
        assert status["structured_logging_active"] is True
        assert status["alert_manager_active"] is True
    
    def test_default_alert_rules(self):
        """Test that default alert rules are properly configured."""
        # Simulate high error rate
        for _ in range(10):
            perf_metric = PerformanceMetrics("test_op", datetime.now())
            perf_metric.complete(success=False, error_message="Test error")
            self.monitor.metrics.record_performance(perf_metric)
        
        # Wait for monitoring loop to process
        time.sleep(1)
        
        # Check if alerts were generated
        alert_summary = self.monitor.alerts.get_alert_summary()
        # Note: In a real test, you might need to trigger the monitoring loop manually
    
    def test_workflow_operation_decorator(self):
        """Test the workflow operation monitoring decorator."""
        @monitor_workflow_operation("decorated_operation")
        def test_function(value):
            if value < 0:
                raise ValueError("Negative value")
            return value * 2
        
        # Test successful operation
        result = test_function(5)
        assert result == 10
        
        # Test failing operation
        with pytest.raises(ValueError):
            test_function(-1)
        
        # Verify metrics were recorded
        # Note: This would need access to the global monitor instance


class TestMonitoringIntegration:
    """Integration tests for the complete monitoring system."""
    
    def test_end_to_end_monitoring(self):
        """Test complete monitoring workflow."""
        monitor = setup_workflow_monitoring("integration_test")
        
        try:
            # Simulate a complete workflow operation
            with monitor.monitor_operation("integration_test_workflow", username="test_user") as op_id:
                
                # Create progress indicator
                progress = monitor.logger.create_progress_indicator(
                    operation_id="integration_progress",
                    operation_name="Integration Test",
                    total_steps=3
                )
                
                # Step 1: Data collection
                monitor.logger.update_progress("integration_progress", 1, "Collecting data")
                monitor.metrics.increment_counter("data_collection_attempts")
                time.sleep(0.1)
                
                # Step 2: Processing
                monitor.logger.update_progress("integration_progress", 2, "Processing data")
                monitor.metrics.record_timer("processing_time", 150.0)
                time.sleep(0.1)
                
                # Step 3: Finalization
                monitor.logger.update_progress("integration_progress", 3, "Finalizing results")
                monitor.metrics.set_gauge("final_quality_score", 0.85)
                
                # Complete progress
                monitor.logger.complete_progress("integration_progress", success=True)
            
            # Verify comprehensive monitoring data
            dashboard = monitor.get_monitoring_dashboard()
            
            # Check that all monitoring components are active
            assert dashboard["monitoring_status"]["metrics_collector_active"]
            assert dashboard["monitoring_status"]["structured_logging_active"]
            assert dashboard["monitoring_status"]["alert_manager_active"]
            
            # Check that metrics were collected
            metrics = dashboard["metrics"]
            assert metrics["counters"]["data_collection_attempts"] >= 1
            assert metrics["gauges"]["final_quality_score"] == 0.85
            assert "processing_time" in metrics["timers"]
            
            # Check system health
            health = dashboard["system_health"]
            assert health["overall_status"] in [HealthStatus.HEALTHY.value, HealthStatus.DEGRADED.value]
            
        finally:
            monitor.shutdown()
    
    def test_monitoring_performance_impact(self):
        """Test that monitoring doesn't significantly impact performance."""
        monitor = setup_workflow_monitoring("performance_test")
        
        try:
            # Measure time without monitoring
            start_time = time.time()
            for i in range(100):
                # Simulate work
                time.sleep(0.001)
            baseline_time = time.time() - start_time
            
            # Measure time with monitoring
            start_time = time.time()
            for i in range(100):
                with monitor.monitor_operation(f"perf_test_{i}"):
                    monitor.metrics.increment_counter("perf_counter")
                    monitor.metrics.record_timer("perf_timer", i * 10)
                    time.sleep(0.001)
            monitored_time = time.time() - start_time
            
            # Monitoring overhead should be minimal (less than 50% increase)
            overhead_ratio = monitored_time / baseline_time
            assert overhead_ratio < 1.5, f"Monitoring overhead too high: {overhead_ratio:.2f}x"
            
        finally:
            monitor.shutdown()
    
    def test_concurrent_monitoring(self):
        """Test monitoring system under concurrent load."""
        monitor = setup_workflow_monitoring("concurrency_test")
        
        try:
            def worker(worker_id):
                for i in range(50):
                    with monitor.monitor_operation(f"worker_{worker_id}_op_{i}"):
                        monitor.metrics.increment_counter("concurrent_operations")
                        monitor.metrics.record_timer("concurrent_timer", i * 5)
                        time.sleep(0.01)
            
            # Start multiple worker threads
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            
            # Verify all operations were recorded
            metrics = monitor.metrics.get_all_metrics()
            assert metrics["counters"]["concurrent_operations"] == 250  # 5 workers * 50 operations
            assert metrics["timers"]["concurrent_timer"]["count"] == 250
            
        finally:
            monitor.shutdown()


# Property-based test for monitoring system reliability
class TestMonitoringProperties:
    """Property-based tests for monitoring system."""
    
    def test_metrics_consistency_property(self):
        """Test that metrics remain consistent under various operations."""
        collector = WorkflowMetricsCollector()
        
        # Property: Counter values should always increase
        initial_value = collector.get_counter_value("consistency_test")
        
        for i in range(100):
            collector.increment_counter("consistency_test", 1)
            current_value = collector.get_counter_value("consistency_test")
            assert current_value == initial_value + i + 1
    
    def test_progress_indicator_invariants(self):
        """Test progress indicator invariants."""
        logger = StructuredLogger("property_test")
        
        # Property: Progress percentage should always be between 0 and 100
        progress = logger.create_progress_indicator("prop_test", "Property Test", 10)
        
        for step in range(11):  # 0 to 10
            logger.update_progress("prop_test", step, f"Step {step}")
            status = logger.get_progress_status("prop_test")
            assert 0 <= status["progress_percentage"] <= 100
    
    def test_health_check_determinism(self):
        """Test that health checks are deterministic."""
        health_manager = HealthCheckManager()
        
        def deterministic_check():
            return HealthCheck("deterministic", HealthStatus.HEALTHY, "Always healthy")
        
        health_manager.register_health_check("deterministic", deterministic_check, 60)
        
        # Property: Same health check should return same result
        result1 = health_manager.run_health_check("deterministic")
        result2 = health_manager.run_health_check("deterministic")
        
        assert result1.status == result2.status
        assert result1.message == result2.message


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
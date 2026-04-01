#!/usr/bin/env python3
"""
Demo script for Workflow Monitoring Infrastructure.

This script demonstrates the comprehensive monitoring capabilities including:
- Real-time metrics collection and visualization
- Structured logging with progress indicators
- Performance monitoring and alerting
- Health check endpoints and system status monitoring
- Integration with workflow operations

Usage:
    python examples/workflow_monitoring_demo.py
"""

import os
import sys
import time
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any
from dotenv import load_dotenv

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.workflow_monitoring import (
    setup_workflow_monitoring, WorkflowMonitor, AlertSeverity, HealthStatus,
    PerformanceMetrics, monitor_workflow_operation
)


class MonitoringDemo:
    """Comprehensive demonstration of workflow monitoring capabilities."""
    
    def __init__(self):
        """Initialize the monitoring demo."""
        self.monitor = setup_workflow_monitoring("monitoring_demo")
        self.demo_data = {
            "users_processed": 0,
            "operations_completed": 0,
            "errors_encountered": 0
        }
        
        # Setup demo-specific alert handlers
        self._setup_demo_alerts()
        
        # Setup demo health checks
        self._setup_demo_health_checks()
    
    def _setup_demo_alerts(self):
        """Setup demo-specific alert handlers and rules."""
        
        def console_alert_handler(alert):
            """Enhanced console alert handler for demo."""
            timestamp = alert.timestamp.strftime("%H:%M:%S")
            severity_colors = {
                "info": "\033[94m",      # Blue
                "warning": "\033[93m",   # Yellow
                "error": "\033[91m",     # Red
                "critical": "\033[95m"   # Magenta
            }
            reset_color = "\033[0m"
            
            color = severity_colors.get(alert.severity.value, "")
            print(f"{color}[{timestamp}] {alert.severity.value.upper()}: {alert.title}{reset_color}")
            print(f"  {alert.message}")
            if alert.metadata:
                print(f"  Metadata: {json.dumps(alert.metadata, indent=2)}")
            print()
        
        self.monitor.alerts.add_alert_handler(console_alert_handler)
        
        # Add demo-specific alert rules
        self.monitor.alerts.add_alert_rule(
            "demo_high_error_rate",
            lambda metrics: self.demo_data["errors_encountered"] > 5,
            AlertSeverity.WARNING,
            "Demo: High Error Rate",
            "Demo has encountered {errors_encountered} errors",
            cooldown_minutes=1
        )
        
        self.monitor.alerts.add_alert_rule(
            "demo_processing_milestone",
            lambda metrics: self.demo_data["users_processed"] > 0 and self.demo_data["users_processed"] % 10 == 0,
            AlertSeverity.INFO,
            "Demo: Processing Milestone",
            "Demo has processed {users_processed} users successfully",
            cooldown_minutes=1
        )
    
    def _setup_demo_health_checks(self):
        """Setup demo-specific health checks."""
        
        def check_demo_system():
            """Check demo system health."""
            try:
                if self.demo_data["errors_encountered"] > 10:
                    return {
                        "name": "demo_system",
                        "status": HealthStatus.UNHEALTHY,
                        "message": f"Too many errors: {self.demo_data['errors_encountered']}",
                        "metadata": self.demo_data
                    }
                elif self.demo_data["errors_encountered"] > 3:
                    return {
                        "name": "demo_system",
                        "status": HealthStatus.DEGRADED,
                        "message": f"Some errors detected: {self.demo_data['errors_encountered']}",
                        "metadata": self.demo_data
                    }
                else:
                    return {
                        "name": "demo_system",
                        "status": HealthStatus.HEALTHY,
                        "message": f"Demo system operational: {self.demo_data['operations_completed']} operations completed",
                        "metadata": self.demo_data
                    }
            except Exception as e:
                return {
                    "name": "demo_system",
                    "status": HealthStatus.UNHEALTHY,
                    "message": f"Demo health check failed: {str(e)}",
                    "metadata": {"error": str(e)}
                }
        
        from app.utils.workflow_monitoring import HealthCheck
        
        def demo_health_wrapper():
            result_dict = check_demo_system()
            return HealthCheck(**result_dict)
        
        self.monitor.health.register_health_check("demo_system", demo_health_wrapper, 30)
    
    def print_header(self, title: str):
        """Print a formatted header."""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    
    def print_section(self, title: str):
        """Print a formatted section header."""
        print(f"\n{'-'*40}")
        print(f"  {title}")
        print(f"{'-'*40}")
    
    def demonstrate_basic_monitoring(self):
        """Demonstrate basic monitoring capabilities."""
        self.print_section("Basic Monitoring Capabilities")
        
        print("📊 Recording various metrics...")
        
        # Counter metrics
        self.monitor.metrics.increment_counter("demo_page_views", 100)
        self.monitor.metrics.increment_counter("demo_api_calls", 50)
        self.monitor.metrics.increment_counter("demo_user_signups", 5)
        
        # Gauge metrics
        self.monitor.metrics.set_gauge("demo_active_users", 25)
        self.monitor.metrics.set_gauge("demo_cpu_usage", 45.5)
        self.monitor.metrics.set_gauge("demo_memory_usage", 67.8)
        
        # Timer metrics
        for i in range(10):
            response_time = 100 + (i * 20) + (i % 3 * 50)  # Simulate varying response times
            self.monitor.metrics.record_timer("demo_response_time", response_time)
        
        # Rate metrics
        for i in range(5):
            self.monitor.metrics.record_rate("demo_requests_per_second", 2.5)
            time.sleep(0.1)
        
        print("✅ Metrics recorded successfully!")
        
        # Display current metrics
        print("\n📈 Current Metrics Summary:")
        metrics = self.monitor.metrics.get_all_metrics()
        
        print(f"  Counters:")
        for name, value in metrics["counters"].items():
            print(f"    {name}: {value}")
        
        print(f"  Gauges:")
        for name, value in metrics["gauges"].items():
            print(f"    {name}: {value}")
        
        print(f"  Timer Stats (demo_response_time):")
        timer_stats = metrics["timers"].get("demo_response_time", {})
        for stat, value in timer_stats.items():
            print(f"    {stat}: {value:.2f}" if isinstance(value, float) else f"    {stat}: {value}")
    
    def demonstrate_structured_logging(self):
        """Demonstrate structured logging capabilities."""
        self.print_section("Structured Logging with Context")
        
        print("📝 Demonstrating structured logging...")
        
        # Basic logging
        self.monitor.logger.info("Demo started", demo_version="1.0", environment="development")
        
        # Logging with context
        with self.monitor.logger.log_context(operation="user_processing", batch_id="batch_001"):
            self.monitor.logger.info("Starting user batch processing")
            
            with self.monitor.logger.log_context(user_id="user_123"):
                self.monitor.logger.info("Processing individual user")
                self.monitor.logger.warning("User has incomplete profile", missing_fields=["email", "phone"])
            
            self.monitor.logger.info("Batch processing completed", users_processed=50)
        
        # Workflow step logging
        self.monitor.logger.log_workflow_step(
            step_name="data_validation",
            username="demo_user",
            success=True,
            duration_ms=150.5,
            validation_rules_applied=5,
            validation_errors=0
        )
        
        # Performance metric logging
        perf_metric = PerformanceMetrics(
            operation_name="demo_data_processing",
            start_time=datetime.now() - timedelta(seconds=2)
        )
        perf_metric.complete(success=True)
        self.monitor.logger.log_performance_metric(perf_metric)
        
        print("✅ Structured logging demonstrated!")
    
    def demonstrate_progress_tracking(self):
        """Demonstrate progress tracking for long-running operations."""
        self.print_section("Progress Tracking for Long-Running Operations")
        
        print("⏳ Simulating long-running operation with progress tracking...")
        
        # Create progress indicator
        progress = self.monitor.logger.create_progress_indicator(
            operation_id="demo_bulk_processing",
            operation_name="Demo Bulk User Processing",
            total_steps=10,
            batch_size=100,
            estimated_duration="2 minutes"
        )
        
        print(f"📋 Created progress indicator: {progress.operation_id}")
        
        # Simulate processing steps
        for step in range(1, 11):
            # Simulate work
            time.sleep(0.3)
            
            # Update progress
            details = f"Processing batch {step}/10 (users {(step-1)*10 + 1}-{step*10})"
            self.monitor.logger.update_progress(
                progress.operation_id,
                step,
                details,
                current_batch=step,
                users_processed=step * 10
            )
            
            # Display progress
            status = self.monitor.logger.get_progress_status(progress.operation_id)
            print(f"  📊 Progress: {status['progress_percentage']:.1f}% - {details}")
            
            if status['estimated_completion']:
                eta = datetime.fromisoformat(status['estimated_completion'])
                print(f"     ETA: {eta.strftime('%H:%M:%S')}")
        
        # Complete progress
        self.monitor.logger.complete_progress(
            progress.operation_id,
            success=True,
            final_message="All 100 users processed successfully"
        )
        
        print("✅ Long-running operation completed with full progress tracking!")
    
    @monitor_workflow_operation("demo_monitored_operation")
    def demonstrate_operation_monitoring(self):
        """Demonstrate automatic operation monitoring."""
        self.print_section("Automatic Operation Monitoring")
        
        print("🔍 Demonstrating automatic operation monitoring...")
        
        # This method is decorated with @monitor_workflow_operation
        # All metrics, logging, and error handling are automatic
        
        # Simulate some work
        time.sleep(0.5)
        
        # Record some operation-specific metrics
        self.monitor.metrics.increment_counter("demo_operations_completed")
        self.monitor.metrics.record_timer("demo_operation_duration", 500)
        
        self.demo_data["operations_completed"] += 1
        
        print("✅ Operation completed with automatic monitoring!")
        
        return {"status": "success", "data_processed": 42}
    
    def demonstrate_error_handling_and_alerts(self):
        """Demonstrate error handling and alerting."""
        self.print_section("Error Handling and Alerting")
        
        print("🚨 Demonstrating error handling and alert generation...")
        
        # Simulate some errors to trigger alerts
        for i in range(3):
            try:
                with self.monitor.monitor_operation(f"demo_error_prone_operation_{i}"):
                    if i == 1:
                        # Simulate an error
                        raise ValueError(f"Demo error #{i + 1}")
                    
                    # Successful operation
                    time.sleep(0.1)
                    self.demo_data["users_processed"] += 1
                    
            except ValueError as e:
                self.demo_data["errors_encountered"] += 1
                print(f"  ❌ Caught error: {e}")
        
        # Create a manual alert
        self.monitor.alerts.create_alert(
            severity=AlertSeverity.WARNING,
            title="Demo Manual Alert",
            message="This is a manually created alert for demonstration purposes",
            metadata={
                "demo_context": "manual_alert_demo",
                "timestamp": datetime.now().isoformat()
            }
        )
        
        # Trigger alert rule evaluation
        self.monitor.alerts.evaluate_rules(self.demo_data)
        
        print("✅ Error handling and alerting demonstrated!")
    
    def demonstrate_health_monitoring(self):
        """Demonstrate health monitoring capabilities."""
        self.print_section("Health Monitoring")
        
        print("🏥 Demonstrating health monitoring...")
        
        # Run all health checks
        health_results = self.monitor.health.run_all_health_checks()
        
        print("📋 Health Check Results:")
        for name, result in health_results.items():
            status_emoji = {
                HealthStatus.HEALTHY: "✅",
                HealthStatus.DEGRADED: "⚠️",
                HealthStatus.UNHEALTHY: "❌",
                HealthStatus.UNKNOWN: "❓"
            }
            
            emoji = status_emoji.get(result.status, "❓")
            print(f"  {emoji} {name}: {result.status.value} - {result.message}")
            if result.response_time_ms:
                print(f"     Response time: {result.response_time_ms:.2f}ms")
        
        # Get system health summary
        system_health = self.monitor.health.get_system_health()
        print(f"\n🏥 Overall System Health: {system_health['overall_status'].upper()}")
        print(f"   {system_health['message']}")
        
        summary = system_health['summary']
        print(f"   Total checks: {summary['total_checks']}")
        print(f"   Healthy: {summary['healthy']}, Degraded: {summary['degraded']}")
        print(f"   Unhealthy: {summary['unhealthy']}, Unknown: {summary['unknown']}")
        
        print("✅ Health monitoring demonstrated!")
    
    def demonstrate_monitoring_dashboard(self):
        """Demonstrate comprehensive monitoring dashboard."""
        self.print_section("Comprehensive Monitoring Dashboard")
        
        print("📊 Generating comprehensive monitoring dashboard...")
        
        dashboard = self.monitor.get_monitoring_dashboard()
        
        print("🖥️  Monitoring Dashboard Summary:")
        print(f"   Timestamp: {dashboard['timestamp']}")
        
        # System health
        health = dashboard['system_health']
        print(f"   System Health: {health['overall_status']} - {health['message']}")
        
        # Metrics summary
        metrics = dashboard['metrics']
        system_metrics = metrics['system']
        print(f"   System Uptime: {system_metrics['uptime_formatted']}")
        print(f"   Total Operations: {system_metrics['total_operations']}")
        print(f"   Success Rate: {system_metrics['success_rate_percentage']:.1f}%")
        
        # Alert summary
        alerts = dashboard['alerts']
        print(f"   Active Alerts: {alerts['active_alerts']}")
        print(f"   Total Alerts: {alerts['total_alerts']}")
        
        # Progress indicators
        progress = dashboard['progress_indicators']
        print(f"   Active Progress Indicators: {len(progress)}")
        
        # Monitoring status
        status = dashboard['monitoring_status']
        active_components = sum(1 for v in status.values() if v)
        print(f"   Active Monitoring Components: {active_components}/{len(status)}")
        
        print("\n📈 Detailed Metrics:")
        print(f"   Counters: {len(metrics['counters'])} metrics")
        for name, value in list(metrics['counters'].items())[:5]:  # Show first 5
            print(f"     {name}: {value}")
        
        print(f"   Gauges: {len(metrics['gauges'])} metrics")
        for name, value in list(metrics['gauges'].items())[:5]:  # Show first 5
            print(f"     {name}: {value}")
        
        print(f"   Timers: {len(metrics['timers'])} metrics")
        for name, stats in list(metrics['timers'].items())[:3]:  # Show first 3
            print(f"     {name}: avg={stats.get('avg', 0):.2f}ms, count={stats.get('count', 0)}")
        
        print("✅ Monitoring dashboard generated!")
    
    def demonstrate_performance_impact(self):
        """Demonstrate monitoring performance impact."""
        self.print_section("Monitoring Performance Impact Analysis")
        
        print("⚡ Analyzing monitoring performance impact...")
        
        # Measure baseline performance (without monitoring)
        iterations = 1000
        
        print(f"🔬 Running {iterations} operations to measure performance impact...")
        
        # Baseline measurement
        start_time = time.time()
        for i in range(iterations):
            # Simulate lightweight operation
            result = i * 2 + 1
            time.sleep(0.0001)  # Tiny delay to simulate work
        baseline_time = time.time() - start_time
        
        # Monitored measurement
        start_time = time.time()
        for i in range(iterations):
            with self.monitor.monitor_operation(f"perf_test_{i % 10}"):  # Reuse operation names
                self.monitor.metrics.increment_counter("perf_test_counter")
                self.monitor.metrics.record_timer("perf_test_timer", i * 0.1)
                result = i * 2 + 1
                time.sleep(0.0001)
        monitored_time = time.time() - start_time
        
        # Calculate overhead
        overhead_ms = (monitored_time - baseline_time) * 1000
        overhead_percentage = ((monitored_time - baseline_time) / baseline_time) * 100
        
        print(f"📊 Performance Impact Results:")
        print(f"   Baseline time: {baseline_time:.4f}s")
        print(f"   Monitored time: {monitored_time:.4f}s")
        print(f"   Overhead: {overhead_ms:.2f}ms ({overhead_percentage:.2f}%)")
        print(f"   Per-operation overhead: {overhead_ms/iterations:.4f}ms")
        
        if overhead_percentage < 10:
            print("   ✅ Monitoring overhead is minimal and acceptable")
        elif overhead_percentage < 25:
            print("   ⚠️  Monitoring overhead is moderate")
        else:
            print("   ❌ Monitoring overhead is high - optimization needed")
        
        print("✅ Performance impact analysis completed!")
    
    def run_complete_demo(self):
        """Run the complete monitoring demonstration."""
        self.print_header("Workflow Monitoring Infrastructure Demo")
        
        print("🚀 Welcome to the Workflow Monitoring Infrastructure Demo!")
        print("This demonstration showcases comprehensive monitoring capabilities including:")
        print("  • Real-time metrics collection and aggregation")
        print("  • Structured logging with progress indicators")
        print("  • Performance monitoring and alerting")
        print("  • Health check endpoints and system status monitoring")
        print("  • Integration with workflow operations")
        
        try:
            # Run all demonstrations
            self.demonstrate_basic_monitoring()
            self.demonstrate_structured_logging()
            self.demonstrate_progress_tracking()
            self.demonstrate_operation_monitoring()
            self.demonstrate_error_handling_and_alerts()
            self.demonstrate_health_monitoring()
            self.demonstrate_monitoring_dashboard()
            self.demonstrate_performance_impact()
            
            self.print_header("Demo Completed Successfully!")
            
            print("🎉 All monitoring capabilities have been demonstrated!")
            print("\n📋 Summary of demonstrated features:")
            print("  ✅ Metrics collection (counters, gauges, timers, rates)")
            print("  ✅ Structured logging with contextual information")
            print("  ✅ Progress tracking for long-running operations")
            print("  ✅ Automatic operation monitoring with decorators")
            print("  ✅ Error handling and alerting system")
            print("  ✅ Health monitoring and status checks")
            print("  ✅ Comprehensive monitoring dashboard")
            print("  ✅ Performance impact analysis")
            
            print("\n🔧 Next steps for production deployment:")
            print("  1. Configure environment variables for API keys")
            print("  2. Set up persistent storage for metrics and logs")
            print("  3. Configure alert notification channels (email, Slack, etc.)")
            print("  4. Set up monitoring dashboards (Grafana, custom UI)")
            print("  5. Configure log aggregation and analysis tools")
            print("  6. Set up automated health check monitoring")
            
            # Final dashboard display
            print("\n📊 Final Monitoring Dashboard:")
            dashboard = self.monitor.get_monitoring_dashboard()
            print(json.dumps({
                "timestamp": dashboard["timestamp"],
                "system_health": dashboard["system_health"]["overall_status"],
                "total_operations": dashboard["metrics"]["system"]["total_operations"],
                "success_rate": f"{dashboard['metrics']['system']['success_rate_percentage']:.1f}%",
                "active_alerts": dashboard["alerts"]["active_alerts"],
                "monitoring_components_active": sum(1 for v in dashboard["monitoring_status"].values() if v)
            }, indent=2))
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Demo interrupted by user")
        except Exception as e:
            print(f"\n\n❌ Demo failed with error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("\n🔄 Shutting down monitoring system...")
            self.monitor.shutdown()
            print("✅ Monitoring system shutdown complete")


def main():
    """Main demo function."""
    # Load environment variables
    load_dotenv()
    
    # Check if this is an interactive demo
    interactive = "--interactive" in sys.argv
    
    if interactive:
        print("🎮 Interactive Mode: Press Enter to continue between sections...")
        input("Press Enter to start the demo...")
    
    # Create and run demo
    demo = MonitoringDemo()
    
    if interactive:
        # Run sections individually with user input
        sections = [
            ("Basic Monitoring", demo.demonstrate_basic_monitoring),
            ("Structured Logging", demo.demonstrate_structured_logging),
            ("Progress Tracking", demo.demonstrate_progress_tracking),
            ("Operation Monitoring", demo.demonstrate_operation_monitoring),
            ("Error Handling & Alerts", demo.demonstrate_error_handling_and_alerts),
            ("Health Monitoring", demo.demonstrate_health_monitoring),
            ("Monitoring Dashboard", demo.demonstrate_monitoring_dashboard),
            ("Performance Impact", demo.demonstrate_performance_impact)
        ]
        
        demo.print_header("Interactive Workflow Monitoring Demo")
        
        for section_name, section_func in sections:
            input(f"\nPress Enter to run: {section_name}")
            try:
                section_func()
            except Exception as e:
                print(f"❌ Section failed: {e}")
        
        input("\nPress Enter to view final summary...")
        demo.demonstrate_monitoring_dashboard()
        demo.monitor.shutdown()
    else:
        # Run complete demo
        demo.run_complete_demo()


if __name__ == "__main__":
    main()
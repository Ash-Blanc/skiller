#!/usr/bin/env python3
"""
Resource Monitoring Demo

This script demonstrates the resource monitoring and parallel processing
capabilities of the Advanced Skill Generator Workflow.
"""

import time
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.resource_monitor import (
    get_resource_monitor,
    get_workflow_manager,
    print_resource_report,
    validate_parallel_processing_resources
)
from app.utils.resource_config import (
    get_current_config,
    auto_configure_resources
)
from app.utils.workflow_resource_integration import (
    with_resource_monitoring,
    resource_managed_execution,
    get_adaptive_manager,
    check_resource_health,
    ResourceConstraintError
)


def demo_basic_monitoring():
    """Demonstrate basic resource monitoring."""
    print("=" * 60)
    print("BASIC RESOURCE MONITORING DEMO")
    print("=" * 60)
    
    # Get current system metrics
    monitor = get_resource_monitor()
    metrics = monitor.get_current_metrics()
    
    print(f"Current System Status:")
    print(f"  CPU Usage: {metrics.cpu_percent:.1f}%")
    print(f"  Memory Usage: {metrics.memory_percent:.1f}%")
    print(f"  Available Memory: {metrics.memory_available_gb:.1f}GB")
    print(f"  Free Disk Space: {metrics.disk_free_gb:.1f}GB")
    print(f"  Active Processes: {metrics.active_processes}")
    
    # Validate resources
    print(f"\nResource Validation:")
    validation_result = validate_parallel_processing_resources()
    
    if validation_result.is_sufficient:
        print(f"  ✅ Resources are sufficient for parallel processing")
        print(f"  📊 Max concurrent workflows: {validation_result.max_safe_concurrent_workflows}")
    else:
        print(f"  ❌ Insufficient resources for optimal parallel processing")
        print(f"  ⚠️  Warnings: {', '.join(validation_result.warnings)}")


def demo_configuration():
    """Demonstrate configuration management."""
    print("\n" + "=" * 60)
    print("CONFIGURATION MANAGEMENT DEMO")
    print("=" * 60)
    
    # Show current configuration
    config = get_current_config()
    print(f"Current Environment: {config.environment}")
    print(f"Parallel Processing Settings:")
    print(f"  Max Concurrent Workflows: {config.parallel_config.max_concurrent_workflows}")
    print(f"  Memory Limit per Workflow: {config.parallel_config.memory_limit_mb}MB")
    print(f"  Batch Size: {config.parallel_config.batch_size}")
    print(f"  Quality Mode: {config.parallel_config.quality_mode}")
    print(f"  Caching Enabled: {config.parallel_config.enable_caching}")
    
    # Show auto-configured settings
    print(f"\nAuto-Configured Settings:")
    auto_config = auto_configure_resources()
    print(f"  Recommended Environment: {auto_config.environment}")
    print(f"  Optimized Concurrent Workflows: {auto_config.parallel_config.max_concurrent_workflows}")
    print(f"  Optimized Memory Limit: {auto_config.parallel_config.memory_limit_mb}MB")


def demo_adaptive_management():
    """Demonstrate adaptive resource management."""
    print("\n" + "=" * 60)
    print("ADAPTIVE RESOURCE MANAGEMENT DEMO")
    print("=" * 60)
    
    adaptive_manager = get_adaptive_manager()
    
    # Get adaptive configuration
    adaptive_config = adaptive_manager.get_adaptive_config()
    
    print(f"Adaptive Configuration (based on current load):")
    print(f"  Optimal Batch Size: {adaptive_config['batch_size']}")
    print(f"  Optimal Concurrency: {adaptive_config['max_concurrent']}")
    print(f"  Quality Mode: {adaptive_config['quality_mode']}")
    print(f"  Caching Enabled: {adaptive_config['enable_caching']}")
    print(f"  Memory Limit: {adaptive_config['memory_limit_mb']}MB")
    
    # Check resource health
    is_healthy, health_info = check_resource_health()
    print(f"\nResource Health Check:")
    print(f"  Status: {'✅ Healthy' if is_healthy else '❌ Issues Detected'}")
    print(f"  Active Workflows: {health_info['active_workflows']}")
    print(f"  Max Safe Concurrent: {health_info['max_safe_concurrent']}")
    
    if health_info['issues']:
        print(f"  Issues:")
        for issue in health_info['issues']:
            print(f"    • {issue}")
    
    if health_info['recommendations']:
        print(f"  Recommendations:")
        for rec in health_info['recommendations']:
            print(f"    • {rec}")


@with_resource_monitoring("demo_workflow")
def demo_workflow_execution():
    """Demonstrate workflow execution with resource monitoring."""
    print("\n" + "=" * 60)
    print("WORKFLOW EXECUTION DEMO")
    print("=" * 60)
    
    print("Executing sample workflow with resource monitoring...")
    
    # Simulate workflow steps
    steps = [
        "Validating input parameters",
        "Collecting data from multiple sources",
        "Processing and analyzing data",
        "Generating skill profile",
        "Validating results"
    ]
    
    for i, step in enumerate(steps, 1):
        print(f"  Step {i}: {step}")
        time.sleep(0.5)  # Simulate processing time
        
        # Check resources during execution
        if i == 3:  # Check resources mid-workflow
            monitor = get_resource_monitor()
            metrics = monitor.get_current_metrics()
            print(f"    Resource check - CPU: {metrics.cpu_percent:.1f}%, Memory: {metrics.memory_percent:.1f}%")
    
    print("  ✅ Workflow completed successfully!")
    return "demo_result"


def demo_parallel_execution():
    """Demonstrate parallel workflow execution."""
    print("\n" + "=" * 60)
    print("PARALLEL EXECUTION DEMO")
    print("=" * 60)
    
    workflow_manager = get_workflow_manager()
    
    # Simulate multiple workflows
    workflow_ids = ["profile_1", "profile_2", "profile_3"]
    active_workflows = []
    
    print("Starting multiple workflows...")
    
    for workflow_id in workflow_ids:
        can_start, reason = workflow_manager.can_start_workflow(workflow_id)
        
        if can_start:
            print(f"  ✅ Starting workflow: {workflow_id}")
            workflow_manager.register_workflow_start(workflow_id)
            active_workflows.append(workflow_id)
        else:
            print(f"  ❌ Cannot start workflow {workflow_id}: {reason}")
    
    print(f"\nActive workflows: {len(active_workflows)}")
    print(f"System capacity: {workflow_manager.get_active_workflow_count()} workflows running")
    
    # Simulate workflow completion
    time.sleep(1)
    
    print("\nCompleting workflows...")
    for workflow_id in active_workflows:
        workflow_manager.register_workflow_end(workflow_id)
        print(f"  ✅ Completed workflow: {workflow_id}")
    
    print(f"Final active workflows: {workflow_manager.get_active_workflow_count()}")


def demo_context_manager():
    """Demonstrate resource-managed execution context."""
    print("\n" + "=" * 60)
    print("CONTEXT MANAGER DEMO")
    print("=" * 60)
    
    try:
        with resource_managed_execution("context_demo") as workflow_id:
            print(f"Executing workflow with ID: {workflow_id}")
            print("Simulating data collection and analysis...")
            
            # Simulate some work
            for i in range(3):
                print(f"  Processing step {i+1}/3...")
                time.sleep(0.3)
            
            print("  ✅ Context-managed workflow completed!")
            
    except ResourceConstraintError as e:
        print(f"  ❌ Resource constraint prevented execution: {e}")


def main():
    """Run all demos."""
    print("🚀 Resource Monitoring and Parallel Processing Demo")
    print("This demo showcases the resource monitoring capabilities")
    print("of the Advanced Skill Generator Workflow system.\n")
    
    try:
        # Run all demo functions
        demo_basic_monitoring()
        demo_configuration()
        demo_adaptive_management()
        
        # Try workflow execution demos
        try:
            result = demo_workflow_execution()
            print(f"Workflow result: {result}")
        except ResourceConstraintError as e:
            print(f"Workflow execution skipped due to resource constraints: {e}")
        
        demo_parallel_execution()
        demo_context_manager()
        
        # Final resource report
        print("\n" + "=" * 60)
        print("FINAL RESOURCE REPORT")
        print("=" * 60)
        print_resource_report()
        
        print("\n🎉 Demo completed successfully!")
        print("\nNext steps:")
        print("  • Run 'uv run python scripts/validate_resources.py' for detailed validation")
        print("  • Use '--auto-configure' to optimize settings for your system")
        print("  • Check 'docs/RESOURCE_MONITORING.md' for detailed documentation")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        print("This might indicate insufficient system resources or configuration issues.")
        print("Try running 'uv run python scripts/validate_resources.py --auto-configure'")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
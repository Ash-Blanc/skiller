#!/usr/bin/env python3
"""
Resource validation script for the Advanced Skill Generator Workflow.

This script validates that the system has sufficient compute resources
for parallel processing and provides recommendations for optimization.
"""

import sys
import os
import argparse
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.resource_monitor import (
    ResourceMonitor, 
    ResourceRequirements, 
    print_resource_report,
    validate_parallel_processing_resources
)
from app.utils.resource_config import (
    ResourceConfigManager,
    auto_configure_resources,
    get_current_config
)


def validate_resources(environment: str = None, verbose: bool = False) -> bool:
    """
    Validate system resources for the specified environment.
    
    Args:
        environment: Target environment (development, staging, production)
        verbose: Enable verbose output
        
    Returns:
        True if resources are sufficient, False otherwise
    """
    print("🔍 Validating system resources for parallel processing...")
    print()
    
    # Get configuration for the target environment
    config_manager = ResourceConfigManager()
    if environment:
        config = config_manager.get_config_for_environment(environment)
        print(f"📋 Target Environment: {config.environment}")
    else:
        config = get_current_config()
        print(f"📋 Current Environment: {config.environment}")
    
    print(f"📋 Resource Requirements:")
    req = config.resource_requirements
    print(f"   • Min CPU Cores: {req.min_cpu_cores} (Recommended: {req.recommended_cpu_cores})")
    print(f"   • Min Memory: {req.min_memory_gb}GB (Recommended: {req.recommended_memory_gb}GB)")
    print(f"   • Min Disk Space: {req.min_disk_free_gb}GB")
    print(f"   • Max Concurrent Workflows: {req.max_concurrent_workflows}")
    print(f"   • Memory per Workflow: {req.max_memory_per_workflow_mb}MB")
    print()
    
    # Validate resources
    monitor = ResourceMonitor()
    validation_result = monitor.validate_resources(req)
    
    # Print detailed report if verbose
    if verbose:
        print_resource_report()
        print()
    
    # Summary
    if validation_result.is_sufficient:
        print("✅ VALIDATION PASSED")
        print(f"   System has sufficient resources for parallel processing")
        print(f"   Max safe concurrent workflows: {validation_result.max_safe_concurrent_workflows}")
        
        # Performance estimates
        profiles_per_hour = validation_result.max_safe_concurrent_workflows * 120  # 30s per profile
        print(f"   Estimated throughput: {profiles_per_hour} profiles/hour")
        
    else:
        print("❌ VALIDATION FAILED")
        print("   System does not meet minimum resource requirements")
    
    # Warnings
    if validation_result.warnings:
        print()
        print("⚠️  WARNINGS:")
        for warning in validation_result.warnings:
            print(f"   • {warning}")
    
    # Recommendations
    if validation_result.recommendations:
        print()
        print("💡 RECOMMENDATIONS:")
        for rec in validation_result.recommendations:
            print(f"   • {rec}")
    
    return validation_result.is_sufficient


def auto_configure(save: bool = False) -> None:
    """
    Auto-configure resources based on current system capabilities.
    
    Args:
        save: Whether to save the configuration to file
    """
    print("🔧 Auto-configuring resources based on system capabilities...")
    print()
    
    config = auto_configure_resources()
    
    print(f"📋 Auto-configured settings:")
    print(f"   • Environment: {config.environment}")
    print(f"   • Max Concurrent Workflows: {config.parallel_config.max_concurrent_workflows}")
    print(f"   • Memory Limit per Workflow: {config.parallel_config.memory_limit_mb}MB")
    print(f"   • Batch Size: {config.parallel_config.batch_size}")
    print(f"   • Quality Mode: {config.parallel_config.quality_mode}")
    
    if save:
        config_manager = ResourceConfigManager()
        config_manager.save_config(config, f"auto_configured_{config.environment}.yaml")
        print(f"   • Configuration saved to: config/auto_configured_{config.environment}.yaml")


def benchmark_parallel_processing() -> None:
    """Run a simple benchmark to test parallel processing capabilities."""
    import time
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    print("🏃 Running parallel processing benchmark...")
    print()
    
    def cpu_intensive_task(task_id: int, duration: float = 1.0) -> dict:
        """Simulate a CPU-intensive task."""
        start_time = time.time()
        
        # Simulate work (calculate prime numbers)
        count = 0
        num = 2
        while time.time() - start_time < duration:
            is_prime = True
            for i in range(2, int(num ** 0.5) + 1):
                if num % i == 0:
                    is_prime = False
                    break
            if is_prime:
                count += 1
            num += 1
        
        end_time = time.time()
        return {
            "task_id": task_id,
            "duration": end_time - start_time,
            "primes_found": count
        }
    
    # Test different levels of parallelism
    config = get_current_config()
    max_workers = config.parallel_config.max_concurrent_workflows
    
    print(f"Testing with up to {max_workers} parallel workers...")
    
    for num_workers in [1, min(2, max_workers), min(4, max_workers), max_workers]:
        if num_workers <= 0:
            continue
            
        print(f"\n📊 Testing with {num_workers} worker(s):")
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit tasks
            futures = [executor.submit(cpu_intensive_task, i, 0.5) for i in range(num_workers)]
            
            # Wait for completion
            results = []
            for future in as_completed(futures):
                results.append(future.result())
        
        end_time = time.time()
        total_time = end_time - start_time
        
        total_primes = sum(r["primes_found"] for r in results)
        avg_primes = total_primes / len(results)
        
        print(f"   • Total time: {total_time:.2f}s")
        print(f"   • Average primes per task: {avg_primes:.0f}")
        print(f"   • Throughput: {total_primes/total_time:.1f} primes/second")
        
        if num_workers == 1:
            baseline_time = total_time
            baseline_throughput = total_primes/total_time
        else:
            speedup = baseline_time / total_time
            efficiency = speedup / num_workers * 100
            print(f"   • Speedup: {speedup:.2f}x")
            print(f"   • Efficiency: {efficiency:.1f}%")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate system resources for Advanced Skill Generator Workflow"
    )
    
    parser.add_argument(
        "--environment", "-e",
        choices=["development", "staging", "production"],
        help="Target environment to validate against"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output with detailed resource report"
    )
    
    parser.add_argument(
        "--auto-configure", "-a",
        action="store_true",
        help="Auto-configure resources based on system capabilities"
    )
    
    parser.add_argument(
        "--save-config", "-s",
        action="store_true",
        help="Save auto-configured settings to file"
    )
    
    parser.add_argument(
        "--benchmark", "-b",
        action="store_true",
        help="Run parallel processing benchmark"
    )
    
    parser.add_argument(
        "--init-configs",
        action="store_true",
        help="Initialize default configuration files"
    )
    
    args = parser.parse_args()
    
    if args.init_configs:
        config_manager = ResourceConfigManager()
        config_manager.initialize_default_configs()
        return
    
    if args.auto_configure:
        auto_configure(save=args.save_config)
        return
    
    if args.benchmark:
        benchmark_parallel_processing()
        return
    
    # Default action: validate resources
    success = validate_resources(args.environment, args.verbose)
    
    if not success:
        print()
        print("💡 Consider running with --auto-configure to optimize settings")
        print("💡 Or use --benchmark to test parallel processing performance")
        sys.exit(1)
    
    print()
    print("🎉 System is ready for parallel processing!")


if __name__ == "__main__":
    main()
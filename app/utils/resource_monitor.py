"""
Resource monitoring and validation utilities for parallel processing.

This module provides functionality to monitor system resources and validate
that the environment has sufficient compute resources for parallel processing
of the Advanced Skill Generator Workflow.
"""

import psutil
import time
import logging
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import os

logger = logging.getLogger(__name__)


@dataclass
class ResourceMetrics:
    """System resource metrics at a point in time."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    memory_used_gb: float
    disk_free_gb: float
    active_processes: int
    load_average: Optional[Tuple[float, float, float]] = None


@dataclass
class ResourceRequirements:
    """Resource requirements for the workflow."""
    min_cpu_cores: int = 4
    min_memory_gb: float = 2.0
    min_disk_free_gb: float = 1.0
    max_memory_per_workflow_mb: int = 500
    max_concurrent_workflows: int = 10
    recommended_cpu_cores: int = 8
    recommended_memory_gb: float = 8.0


@dataclass
class ResourceValidationResult:
    """Result of resource validation."""
    is_sufficient: bool
    current_resources: ResourceMetrics
    requirements: ResourceRequirements
    warnings: List[str]
    recommendations: List[str]
    max_safe_concurrent_workflows: int


class ResourceMonitor:
    """Monitor system resources for parallel processing optimization."""
    
    def __init__(self, monitoring_interval: float = 1.0):
        self.monitoring_interval = monitoring_interval
        self.is_monitoring = False
        self.metrics_history: List[ResourceMetrics] = []
        self.max_history_size = 1000
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
    
    def get_current_metrics(self) -> ResourceMetrics:
        """Get current system resource metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_available_gb = memory.available / (1024**3)
            memory_used_gb = memory.used / (1024**3)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_free_gb = disk.free / (1024**3)
            
            # Process count
            active_processes = len(psutil.pids())
            
            # Load average (Unix-like systems only)
            load_average = None
            try:
                if hasattr(os, 'getloadavg'):
                    load_average = os.getloadavg()
            except (OSError, AttributeError):
                pass
            
            return ResourceMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_available_gb=memory_available_gb,
                memory_used_gb=memory_used_gb,
                disk_free_gb=disk_free_gb,
                active_processes=active_processes,
                load_average=load_average
            )
        except Exception as e:
            logger.error(f"Error getting resource metrics: {e}")
            raise
    
    def validate_resources(self, requirements: Optional[ResourceRequirements] = None) -> ResourceValidationResult:
        """Validate that system has sufficient resources for parallel processing."""
        if requirements is None:
            requirements = ResourceRequirements()
        
        current_metrics = self.get_current_metrics()
        warnings = []
        recommendations = []
        
        # Get system capabilities
        cpu_count = psutil.cpu_count()
        memory_total_gb = psutil.virtual_memory().total / (1024**3)
        
        # Validate CPU cores
        if cpu_count < requirements.min_cpu_cores:
            warnings.append(f"CPU cores ({cpu_count}) below minimum requirement ({requirements.min_cpu_cores})")
        elif cpu_count < requirements.recommended_cpu_cores:
            recommendations.append(f"Consider upgrading to {requirements.recommended_cpu_cores}+ CPU cores for optimal performance")
        
        # Validate memory
        if memory_total_gb < requirements.min_memory_gb:
            warnings.append(f"Total memory ({memory_total_gb:.1f}GB) below minimum requirement ({requirements.min_memory_gb}GB)")
        elif memory_total_gb < requirements.recommended_memory_gb:
            recommendations.append(f"Consider upgrading to {requirements.recommended_memory_gb}GB+ memory for optimal performance")
        
        # Validate available memory
        if current_metrics.memory_available_gb < requirements.min_memory_gb:
            warnings.append(f"Available memory ({current_metrics.memory_available_gb:.1f}GB) below minimum requirement")
        
        # Validate disk space
        if current_metrics.disk_free_gb < requirements.min_disk_free_gb:
            warnings.append(f"Free disk space ({current_metrics.disk_free_gb:.1f}GB) below minimum requirement")
        
        # Calculate maximum safe concurrent workflows
        memory_limited = int(current_metrics.memory_available_gb * 1024 / requirements.max_memory_per_workflow_mb)
        cpu_limited = max(1, cpu_count - 2)  # Reserve 2 cores for system
        max_safe_concurrent = min(memory_limited, cpu_limited, requirements.max_concurrent_workflows)
        
        # Check current system load
        if current_metrics.cpu_percent > 80:
            warnings.append(f"High CPU usage ({current_metrics.cpu_percent:.1f}%) may impact performance")
        
        if current_metrics.memory_percent > 85:
            warnings.append(f"High memory usage ({current_metrics.memory_percent:.1f}%) may impact performance")
        
        # Overall assessment
        is_sufficient = (
            cpu_count >= requirements.min_cpu_cores and
            memory_total_gb >= requirements.min_memory_gb and
            current_metrics.memory_available_gb >= requirements.min_memory_gb and
            current_metrics.disk_free_gb >= requirements.min_disk_free_gb and
            max_safe_concurrent >= 1
        )
        
        return ResourceValidationResult(
            is_sufficient=is_sufficient,
            current_resources=current_metrics,
            requirements=requirements,
            warnings=warnings,
            recommendations=recommendations,
            max_safe_concurrent_workflows=max_safe_concurrent
        )
    
    def start_monitoring(self):
        """Start continuous resource monitoring."""
        if self.is_monitoring:
            logger.warning("Resource monitoring already started")
            return
        
        self.is_monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Resource monitoring started")
    
    def stop_monitoring(self):
        """Stop continuous resource monitoring."""
        self.is_monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        logger.info("Resource monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                metrics = self.get_current_metrics()
                
                with self._lock:
                    self.metrics_history.append(metrics)
                    # Keep history size manageable
                    if len(self.metrics_history) > self.max_history_size:
                        self.metrics_history = self.metrics_history[-self.max_history_size:]
                
                time.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.monitoring_interval)
    
    def get_metrics_history(self, duration_minutes: int = 10) -> List[ResourceMetrics]:
        """Get resource metrics history for the specified duration."""
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        
        with self._lock:
            return [m for m in self.metrics_history if m.timestamp >= cutoff_time]
    
    def get_resource_summary(self) -> Dict:
        """Get a summary of current system resources and capabilities."""
        current_metrics = self.get_current_metrics()
        validation_result = self.validate_resources()
        
        # System capabilities
        cpu_count = psutil.cpu_count()
        memory_total_gb = psutil.virtual_memory().total / (1024**3)
        
        return {
            "system_capabilities": {
                "cpu_cores": cpu_count,
                "memory_total_gb": round(memory_total_gb, 2),
                "disk_total_gb": round(psutil.disk_usage('/').total / (1024**3), 2)
            },
            "current_usage": {
                "cpu_percent": current_metrics.cpu_percent,
                "memory_percent": current_metrics.memory_percent,
                "memory_available_gb": round(current_metrics.memory_available_gb, 2),
                "disk_free_gb": round(current_metrics.disk_free_gb, 2)
            },
            "parallel_processing": {
                "is_sufficient": validation_result.is_sufficient,
                "max_safe_concurrent_workflows": validation_result.max_safe_concurrent_workflows,
                "warnings": validation_result.warnings,
                "recommendations": validation_result.recommendations
            },
            "performance_estimates": {
                "estimated_profiles_per_hour": validation_result.max_safe_concurrent_workflows * 120,  # 30s per profile
                "memory_per_workflow_mb": validation_result.requirements.max_memory_per_workflow_mb,
                "recommended_batch_size": min(validation_result.max_safe_concurrent_workflows, 10)
            }
        }


class WorkflowResourceManager:
    """Manage resources for workflow execution."""
    
    def __init__(self, monitor: ResourceMonitor):
        self.monitor = monitor
        self.active_workflows: Dict[str, datetime] = {}
        self._lock = threading.Lock()
    
    def can_start_workflow(self, workflow_id: str) -> Tuple[bool, str]:
        """Check if a new workflow can be started based on current resources."""
        validation_result = self.monitor.validate_resources()
        
        with self._lock:
            current_active = len(self.active_workflows)
        
        if not validation_result.is_sufficient:
            return False, "Insufficient system resources for workflow execution"
        
        if current_active >= validation_result.max_safe_concurrent_workflows:
            return False, f"Maximum concurrent workflows ({validation_result.max_safe_concurrent_workflows}) reached"
        
        # Check current system load
        current_metrics = self.monitor.get_current_metrics()
        if current_metrics.cpu_percent > 90:
            return False, "System CPU usage too high"
        
        if current_metrics.memory_percent > 90:
            return False, "System memory usage too high"
        
        return True, "Resources available"
    
    def register_workflow_start(self, workflow_id: str):
        """Register that a workflow has started."""
        with self._lock:
            self.active_workflows[workflow_id] = datetime.now()
        logger.info(f"Workflow {workflow_id} started. Active workflows: {len(self.active_workflows)}")
    
    def register_workflow_end(self, workflow_id: str):
        """Register that a workflow has ended."""
        with self._lock:
            if workflow_id in self.active_workflows:
                start_time = self.active_workflows.pop(workflow_id)
                duration = datetime.now() - start_time
                logger.info(f"Workflow {workflow_id} completed in {duration.total_seconds():.1f}s. Active workflows: {len(self.active_workflows)}")
    
    def get_active_workflow_count(self) -> int:
        """Get the number of currently active workflows."""
        with self._lock:
            return len(self.active_workflows)
    
    def cleanup_stale_workflows(self, max_age_hours: int = 2):
        """Clean up workflows that have been running too long (likely stale)."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._lock:
            stale_workflows = [wid for wid, start_time in self.active_workflows.items() 
                             if start_time < cutoff_time]
            
            for workflow_id in stale_workflows:
                logger.warning(f"Cleaning up stale workflow: {workflow_id}")
                del self.active_workflows[workflow_id]
        
        return len(stale_workflows)


# Global instances
_resource_monitor = None
_workflow_manager = None


def get_resource_monitor() -> ResourceMonitor:
    """Get the global resource monitor instance."""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
    return _resource_monitor


def get_workflow_manager() -> WorkflowResourceManager:
    """Get the global workflow resource manager instance."""
    global _workflow_manager
    if _workflow_manager is None:
        _workflow_manager = WorkflowResourceManager(get_resource_monitor())
    return _workflow_manager


def validate_parallel_processing_resources() -> ResourceValidationResult:
    """Validate that the system has sufficient resources for parallel processing."""
    monitor = get_resource_monitor()
    return monitor.validate_resources()


def print_resource_report():
    """Print a comprehensive resource report."""
    monitor = get_resource_monitor()
    summary = monitor.get_resource_summary()
    
    print("\n" + "="*60)
    print("PARALLEL PROCESSING RESOURCE REPORT")
    print("="*60)
    
    print(f"\nSystem Capabilities:")
    print(f"  CPU Cores: {summary['system_capabilities']['cpu_cores']}")
    print(f"  Total Memory: {summary['system_capabilities']['memory_total_gb']}GB")
    print(f"  Total Disk: {summary['system_capabilities']['disk_total_gb']}GB")
    
    print(f"\nCurrent Usage:")
    print(f"  CPU Usage: {summary['current_usage']['cpu_percent']:.1f}%")
    print(f"  Memory Usage: {summary['current_usage']['memory_percent']:.1f}%")
    print(f"  Available Memory: {summary['current_usage']['memory_available_gb']}GB")
    print(f"  Free Disk: {summary['current_usage']['disk_free_gb']}GB")
    
    print(f"\nParallel Processing Assessment:")
    status = "✅ SUFFICIENT" if summary['parallel_processing']['is_sufficient'] else "❌ INSUFFICIENT"
    print(f"  Resource Status: {status}")
    print(f"  Max Concurrent Workflows: {summary['parallel_processing']['max_safe_concurrent_workflows']}")
    
    if summary['parallel_processing']['warnings']:
        print(f"\n⚠️  Warnings:")
        for warning in summary['parallel_processing']['warnings']:
            print(f"    • {warning}")
    
    if summary['parallel_processing']['recommendations']:
        print(f"\n💡 Recommendations:")
        for rec in summary['parallel_processing']['recommendations']:
            print(f"    • {rec}")
    
    print(f"\nPerformance Estimates:")
    print(f"  Estimated Profiles/Hour: {summary['performance_estimates']['estimated_profiles_per_hour']}")
    print(f"  Memory per Workflow: {summary['performance_estimates']['memory_per_workflow_mb']}MB")
    print(f"  Recommended Batch Size: {summary['performance_estimates']['recommended_batch_size']}")
    
    print("="*60)


if __name__ == "__main__":
    # Run resource validation when executed directly
    print_resource_report()
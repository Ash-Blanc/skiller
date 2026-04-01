"""
Workflow metrics and logging infrastructure for monitoring.

This module provides comprehensive metrics collection, logging, and monitoring
capabilities for the Advanced Skill Generator Workflow.
"""

import time
import logging
import structlog
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import threading
from collections import defaultdict, deque
import uuid


class WorkflowStatus(Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MetricType(Enum):
    """Types of metrics collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class WorkflowMetric:
    """Individual workflow metric."""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""


@dataclass
class WorkflowExecution:
    """Workflow execution tracking."""
    workflow_id: str
    workflow_name: str
    status: WorkflowStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    metrics: List[WorkflowMetric] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "metrics_count": len(self.metrics)
        }


class WorkflowMetricsCollector:
    """Collects and manages workflow metrics."""
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.executions: Dict[str, WorkflowExecution] = {}
        self.execution_history: deque = deque(maxlen=max_history)
        self.metrics: Dict[str, List[WorkflowMetric]] = defaultdict(list)
        self._lock = threading.Lock()
        
        # Performance counters
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        
    def start_workflow(self, workflow_id: str, workflow_name: str, metadata: Dict[str, Any] = None) -> WorkflowExecution:
        """Start tracking a workflow execution."""
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            status=WorkflowStatus.RUNNING,
            start_time=datetime.now(),
            metadata=metadata or {}
        )
        
        with self._lock:
            self.executions[workflow_id] = execution
            self.increment_counter("workflows_started")
            self.set_gauge("active_workflows", len([e for e in self.executions.values() if e.status == WorkflowStatus.RUNNING]))
        
        return execution
    
    def complete_workflow(self, workflow_id: str, success: bool = True, error_message: str = None):
        """Mark a workflow as completed."""
        with self._lock:
            if workflow_id not in self.executions:
                return
            
            execution = self.executions[workflow_id]
            execution.end_time = datetime.now()
            execution.duration_seconds = (execution.end_time - execution.start_time).total_seconds()
            execution.status = WorkflowStatus.COMPLETED if success else WorkflowStatus.FAILED
            execution.error_message = error_message
            
            # Move to history
            self.execution_history.append(execution)
            del self.executions[workflow_id]
            
            # Update counters
            if success:
                self.increment_counter("workflows_completed")
            else:
                self.increment_counter("workflows_failed")
            
            self.add_histogram_value("workflow_duration_seconds", execution.duration_seconds)
            self.set_gauge("active_workflows", len([e for e in self.executions.values() if e.status == WorkflowStatus.RUNNING]))
    
    def add_metric(self, workflow_id: str, name: str, value: float, metric_type: MetricType, 
                   labels: Dict[str, str] = None, unit: str = ""):
        """Add a metric to a workflow."""
        metric = WorkflowMetric(
            name=name,
            value=value,
            metric_type=metric_type,
            timestamp=datetime.now(),
            labels=labels or {},
            unit=unit
        )
        
        with self._lock:
            if workflow_id in self.executions:
                self.executions[workflow_id].metrics.append(metric)
            
            self.metrics[name].append(metric)
            
            # Update aggregated metrics
            if metric_type == MetricType.COUNTER:
                self.counters[name] += value
            elif metric_type == MetricType.GAUGE:
                self.gauges[name] = value
            elif metric_type == MetricType.HISTOGRAM:
                self.histograms[name].append(value)
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Dict[str, str] = None):
        """Increment a counter metric."""
        self.add_metric("", name, value, MetricType.COUNTER, labels)
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge metric."""
        self.add_metric("", name, value, MetricType.GAUGE, labels)
    
    def add_histogram_value(self, name: str, value: float, labels: Dict[str, str] = None):
        """Add a value to a histogram metric."""
        self.add_metric("", name, value, MetricType.HISTOGRAM, labels)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        with self._lock:
            active_workflows = len([e for e in self.executions.values() if e.status == WorkflowStatus.RUNNING])
            total_executions = len(self.execution_history)
            
            # Calculate success rate
            completed_workflows = [e for e in self.execution_history if e.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]]
            success_rate = 0.0
            if completed_workflows:
                successful = len([e for e in completed_workflows if e.status == WorkflowStatus.COMPLETED])
                success_rate = successful / len(completed_workflows) * 100
            
            # Calculate average duration
            durations = [e.duration_seconds for e in self.execution_history if e.duration_seconds is not None]
            avg_duration = sum(durations) / len(durations) if durations else 0.0
            
            return {
                "active_workflows": active_workflows,
                "total_executions": total_executions,
                "success_rate_percent": round(success_rate, 2),
                "average_duration_seconds": round(avg_duration, 2),
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "histogram_stats": {
                    name: {
                        "count": len(values),
                        "min": min(values) if values else 0,
                        "max": max(values) if values else 0,
                        "avg": sum(values) / len(values) if values else 0
                    }
                    for name, values in self.histograms.items()
                }
            }
    
    def get_workflow_stats(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get workflow statistics for a time window."""
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        
        with self._lock:
            recent_executions = [
                e for e in self.execution_history 
                if e.start_time >= cutoff_time
            ]
            
            if not recent_executions:
                return {"message": "No executions in the specified time window"}
            
            # Calculate statistics
            total_count = len(recent_executions)
            successful_count = len([e for e in recent_executions if e.status == WorkflowStatus.COMPLETED])
            failed_count = len([e for e in recent_executions if e.status == WorkflowStatus.FAILED])
            
            durations = [e.duration_seconds for e in recent_executions if e.duration_seconds is not None]
            
            return {
                "time_window_minutes": time_window_minutes,
                "total_executions": total_count,
                "successful_executions": successful_count,
                "failed_executions": failed_count,
                "success_rate_percent": round(successful_count / total_count * 100, 2) if total_count > 0 else 0,
                "duration_stats": {
                    "count": len(durations),
                    "min_seconds": min(durations) if durations else 0,
                    "max_seconds": max(durations) if durations else 0,
                    "avg_seconds": round(sum(durations) / len(durations), 2) if durations else 0
                },
                "throughput_per_hour": round(total_count / (time_window_minutes / 60), 2) if time_window_minutes > 0 else 0
            }


class StructuredLogger:
    """Structured logging for workflows."""
    
    def __init__(self, logger_name: str = "workflow"):
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        self.logger = structlog.get_logger(logger_name)
    
    def log_workflow_start(self, workflow_id: str, workflow_name: str, username: str = None, **kwargs):
        """Log workflow start."""
        self.logger.info(
            "workflow_started",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            username=username,
            **kwargs
        )
    
    def log_workflow_step(self, workflow_id: str, step_name: str, status: str, duration: float = None, **kwargs):
        """Log workflow step completion."""
        self.logger.info(
            "workflow_step",
            workflow_id=workflow_id,
            step_name=step_name,
            status=status,
            duration_seconds=duration,
            **kwargs
        )
    
    def log_workflow_complete(self, workflow_id: str, workflow_name: str, success: bool, 
                            duration: float, **kwargs):
        """Log workflow completion."""
        self.logger.info(
            "workflow_completed",
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            success=success,
            duration_seconds=duration,
            **kwargs
        )
    
    def log_workflow_error(self, workflow_id: str, error: str, step_name: str = None, **kwargs):
        """Log workflow error."""
        self.logger.error(
            "workflow_error",
            workflow_id=workflow_id,
            error_message=error,
            step_name=step_name,
            **kwargs
        )
    
    def log_data_collection(self, workflow_id: str, source: str, success: bool, 
                          items_collected: int = None, **kwargs):
        """Log data collection results."""
        self.logger.info(
            "data_collection",
            workflow_id=workflow_id,
            source=source,
            success=success,
            items_collected=items_collected,
            **kwargs
        )
    
    def log_analysis_result(self, workflow_id: str, analysis_type: str, confidence_score: float = None, **kwargs):
        """Log analysis results."""
        self.logger.info(
            "analysis_result",
            workflow_id=workflow_id,
            analysis_type=analysis_type,
            confidence_score=confidence_score,
            **kwargs
        )


class WorkflowMonitor:
    """Comprehensive workflow monitoring."""
    
    def __init__(self):
        self.metrics_collector = WorkflowMetricsCollector()
        self.logger = StructuredLogger()
        self._timers: Dict[str, float] = {}
    
    def start_workflow_monitoring(self, workflow_id: str, workflow_name: str, 
                                username: str = None, metadata: Dict[str, Any] = None) -> WorkflowExecution:
        """Start monitoring a workflow."""
        execution = self.metrics_collector.start_workflow(workflow_id, workflow_name, metadata)
        self.logger.log_workflow_start(workflow_id, workflow_name, username, **(metadata or {}))
        return execution
    
    def complete_workflow_monitoring(self, workflow_id: str, success: bool = True, 
                                   error_message: str = None, **kwargs):
        """Complete workflow monitoring."""
        self.metrics_collector.complete_workflow(workflow_id, success, error_message)
        
        # Get execution details for logging
        execution_history = list(self.metrics_collector.execution_history)
        execution = next((e for e in execution_history if e.workflow_id == workflow_id), None)
        
        if execution:
            self.logger.log_workflow_complete(
                workflow_id, 
                execution.workflow_name, 
                success, 
                execution.duration_seconds or 0,
                **kwargs
            )
        
        if not success and error_message:
            self.logger.log_workflow_error(workflow_id, error_message, **kwargs)
    
    def start_timer(self, timer_name: str):
        """Start a timer for measuring step duration."""
        self._timers[timer_name] = time.time()
    
    def end_timer(self, timer_name: str, workflow_id: str = None) -> float:
        """End a timer and optionally record as metric."""
        if timer_name not in self._timers:
            return 0.0
        
        duration = time.time() - self._timers[timer_name]
        del self._timers[timer_name]
        
        if workflow_id:
            self.metrics_collector.add_metric(
                workflow_id, 
                f"{timer_name}_duration", 
                duration, 
                MetricType.TIMER,
                unit="seconds"
            )
        
        return duration
    
    def log_step_completion(self, workflow_id: str, step_name: str, success: bool, **kwargs):
        """Log completion of a workflow step."""
        timer_name = f"{workflow_id}_{step_name}"
        duration = self.end_timer(timer_name, workflow_id) if timer_name in self._timers else None
        
        status = "success" if success else "failed"
        self.logger.log_workflow_step(workflow_id, step_name, status, duration, **kwargs)
        
        # Record step metrics
        self.metrics_collector.increment_counter(f"steps_{status}")
        if duration:
            self.metrics_collector.add_histogram_value(f"step_duration_{step_name}", duration)
    
    def log_data_collection_result(self, workflow_id: str, source: str, success: bool, 
                                 items_collected: int = None, **kwargs):
        """Log data collection results."""
        self.logger.log_data_collection(workflow_id, source, success, items_collected, **kwargs)
        
        # Record data collection metrics
        self.metrics_collector.increment_counter(f"data_collection_{source}_{'success' if success else 'failed'}")
        if items_collected is not None:
            self.metrics_collector.add_histogram_value(f"items_collected_{source}", items_collected)
    
    def log_analysis_result(self, workflow_id: str, analysis_type: str, confidence_score: float = None, **kwargs):
        """Log analysis results."""
        self.logger.log_analysis_result(workflow_id, analysis_type, confidence_score, **kwargs)
        
        # Record analysis metrics
        self.metrics_collector.increment_counter(f"analysis_{analysis_type}_completed")
        if confidence_score is not None:
            self.metrics_collector.add_histogram_value(f"confidence_score_{analysis_type}", confidence_score)
    
    def get_monitoring_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive monitoring dashboard data."""
        metrics_summary = self.metrics_collector.get_metrics_summary()
        recent_stats = self.metrics_collector.get_workflow_stats(60)  # Last hour
        
        return {
            "timestamp": datetime.now().isoformat(),
            "metrics_summary": metrics_summary,
            "recent_stats": recent_stats,
            "system_health": {
                "active_workflows": metrics_summary["active_workflows"],
                "success_rate": metrics_summary["success_rate_percent"],
                "avg_duration": metrics_summary["average_duration_seconds"],
                "throughput_per_hour": recent_stats.get("throughput_per_hour", 0)
            }
        }


# Global monitor instance
_workflow_monitor = None


def get_workflow_monitor() -> WorkflowMonitor:
    """Get the global workflow monitor instance."""
    global _workflow_monitor
    if _workflow_monitor is None:
        _workflow_monitor = WorkflowMonitor()
    return _workflow_monitor


def workflow_monitoring_decorator(workflow_name: str = None):
    """Decorator to add monitoring to workflow functions."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            monitor = get_workflow_monitor()
            workflow_id = f"{workflow_name or func.__name__}_{uuid.uuid4().hex[:8]}"
            
            # Extract username if available
            username = None
            if args and isinstance(args[0], str):
                username = args[0]
            elif 'username' in kwargs:
                username = kwargs['username']
            
            # Start monitoring
            monitor.start_workflow_monitoring(workflow_id, workflow_name or func.__name__, username)
            
            try:
                result = func(*args, **kwargs)
                monitor.complete_workflow_monitoring(workflow_id, success=True)
                return result
            except Exception as e:
                monitor.complete_workflow_monitoring(workflow_id, success=False, error_message=str(e))
                raise
        
        return wrapper
    return decorator


if __name__ == "__main__":
    # Demo the monitoring system
    monitor = get_workflow_monitor()
    
    # Simulate workflow execution
    workflow_id = "demo_workflow_123"
    monitor.start_workflow_monitoring(workflow_id, "skill_generation", "test_user")
    
    # Simulate steps
    monitor.start_timer(f"{workflow_id}_data_collection")
    time.sleep(0.1)
    monitor.log_step_completion(workflow_id, "data_collection", True, items_collected=25)
    
    monitor.start_timer(f"{workflow_id}_analysis")
    time.sleep(0.1)
    monitor.log_analysis_result(workflow_id, "expertise_extraction", confidence_score=0.85)
    monitor.log_step_completion(workflow_id, "analysis", True)
    
    monitor.complete_workflow_monitoring(workflow_id, success=True)
    
    # Show dashboard
    dashboard = monitor.get_monitoring_dashboard()
    print("Monitoring Dashboard:")
    print(json.dumps(dashboard, indent=2))
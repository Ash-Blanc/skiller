"""
Workflow Metrics and Logging Infrastructure for Advanced Skill Generator Workflow.

This module provides comprehensive monitoring capabilities including:
- Real-time metrics collection and aggregation
- Structured logging with progress indicators
- Performance monitoring and alerting
- Health check endpoints and system status monitoring
- Integration with existing workflow validation utilities

Validates Requirements:
- AC5.4: Provides progress indicators for long-running operations
- TR3: System uptime should be 99.5% or higher, comprehensive error logging and monitoring, automatic retry mechanisms
"""

import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
import logging
import structlog
from contextlib import contextmanager
import asyncio
from concurrent.futures import ThreadPoolExecutor


class MetricType(Enum):
    """Types of metrics that can be collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    RATE = "rate"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class MetricPoint:
    """Individual metric data point."""
    name: str
    value: Union[int, float]
    metric_type: MetricType
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance metrics for workflow operations."""
    operation_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def complete(self, success: bool = True, error_message: Optional[str] = None):
        """Mark the operation as complete."""
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.success = success
        self.error_message = error_message


@dataclass
class ProgressIndicator:
    """Progress tracking for long-running operations."""
    operation_id: str
    operation_name: str
    total_steps: int
    current_step: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    estimated_completion: Optional[datetime] = None
    status: str = "running"
    details: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_steps == 0:
            return 0.0
        return min(100.0, (self.current_step / self.total_steps) * 100.0)
    
    @property
    def elapsed_time(self) -> timedelta:
        """Calculate elapsed time."""
        return datetime.now() - self.start_time
    
    def update_progress(self, current_step: int, details: str = "", metadata: Dict[str, Any] = None):
        """Update progress information."""
        self.current_step = current_step
        self.details = details
        if metadata:
            self.metadata.update(metadata)
        
        # Estimate completion time based on current progress
        if current_step > 0 and self.total_steps > 0:
            elapsed = self.elapsed_time.total_seconds()
            estimated_total = (elapsed / current_step) * self.total_steps
            self.estimated_completion = self.start_time + timedelta(seconds=estimated_total)


@dataclass
class Alert:
    """Alert notification."""
    id: str
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "workflow_monitoring"
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class HealthCheck:
    """Health check result."""
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    response_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowMetricsCollector:
    """
    Comprehensive metrics collection system for workflow monitoring.
    
    Provides real-time metrics collection, aggregation, and reporting
    for workflow operations with thread-safe operations.
    """
    
    def __init__(self, max_history_size: int = 10000):
        """
        Initialize the metrics collector.
        
        Args:
            max_history_size: Maximum number of metric points to keep in memory
        """
        self.max_history_size = max_history_size
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history_size))
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._timers: Dict[str, List[float]] = defaultdict(list)
        self._rates: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._lock = threading.RLock()
        
        # Performance tracking
        self._performance_metrics: deque = deque(maxlen=max_history_size)
        
        # System metrics
        self._system_start_time = datetime.now()
        self._total_operations = 0
        self._successful_operations = 0
        self._failed_operations = 0
    
    def record_metric(self, name: str, value: Union[int, float], 
                     metric_type: MetricType, tags: Dict[str, str] = None,
                     metadata: Dict[str, Any] = None) -> None:
        """
        Record a metric point.
        
        Args:
            name: Metric name
            value: Metric value
            metric_type: Type of metric
            tags: Optional tags for the metric
            metadata: Optional metadata
        """
        with self._lock:
            metric_point = MetricPoint(
                name=name,
                value=value,
                metric_type=metric_type,
                tags=tags or {},
                metadata=metadata or {}
            )
            
            self._metrics[name].append(metric_point)
            
            # Update type-specific storage
            if metric_type == MetricType.COUNTER:
                self._counters[name] += value
            elif metric_type == MetricType.GAUGE:
                self._gauges[name] = value
            elif metric_type == MetricType.TIMER:
                self._timers[name].append(value)
                # Keep only recent timer values
                if len(self._timers[name]) > 1000:
                    self._timers[name] = self._timers[name][-1000:]
            elif metric_type == MetricType.RATE:
                self._rates[name].append((datetime.now(), value))
    
    def increment_counter(self, name: str, value: int = 1, 
                         tags: Dict[str, str] = None) -> None:
        """Increment a counter metric."""
        self.record_metric(name, value, MetricType.COUNTER, tags)
    
    def set_gauge(self, name: str, value: float, 
                  tags: Dict[str, str] = None) -> None:
        """Set a gauge metric value."""
        self.record_metric(name, value, MetricType.GAUGE, tags)
    
    def record_timer(self, name: str, duration_ms: float, 
                    tags: Dict[str, str] = None) -> None:
        """Record a timer metric."""
        self.record_metric(name, duration_ms, MetricType.TIMER, tags)
    
    def record_rate(self, name: str, value: float = 1.0, 
                   tags: Dict[str, str] = None) -> None:
        """Record a rate metric."""
        self.record_metric(name, value, MetricType.RATE, tags)
    
    def record_performance(self, performance_metric: PerformanceMetrics) -> None:
        """Record a performance metric."""
        with self._lock:
            self._performance_metrics.append(performance_metric)
            self._total_operations += 1
            
            if performance_metric.success:
                self._successful_operations += 1
            else:
                self._failed_operations += 1
    
    def get_counter_value(self, name: str) -> int:
        """Get current counter value."""
        with self._lock:
            return self._counters.get(name, 0)
    
    def get_gauge_value(self, name: str) -> float:
        """Get current gauge value."""
        with self._lock:
            return self._gauges.get(name, 0.0)
    
    def get_timer_stats(self, name: str) -> Dict[str, float]:
        """Get timer statistics."""
        with self._lock:
            values = self._timers.get(name, [])
            if not values:
                return {"count": 0, "avg": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0, "p99": 0.0}
            
            sorted_values = sorted(values)
            count = len(sorted_values)
            
            return {
                "count": count,
                "avg": sum(sorted_values) / count,
                "min": sorted_values[0],
                "max": sorted_values[-1],
                "p95": sorted_values[int(count * 0.95)] if count > 0 else 0.0,
                "p99": sorted_values[int(count * 0.99)] if count > 0 else 0.0
            }
    
    def get_rate_per_minute(self, name: str, window_minutes: int = 5) -> float:
        """Calculate rate per minute over a time window."""
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=window_minutes)
            
            rate_points = self._rates.get(name, deque())
            recent_points = [point for timestamp, point in rate_points if timestamp >= cutoff]
            
            if not recent_points:
                return 0.0
            
            return sum(recent_points) / window_minutes
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get overall system metrics."""
        with self._lock:
            uptime = datetime.now() - self._system_start_time
            success_rate = (
                (self._successful_operations / self._total_operations * 100) 
                if self._total_operations > 0 else 0.0
            )
            
            return {
                "uptime_seconds": uptime.total_seconds(),
                "uptime_formatted": str(uptime),
                "total_operations": self._total_operations,
                "successful_operations": self._successful_operations,
                "failed_operations": self._failed_operations,
                "success_rate_percentage": success_rate,
                "operations_per_minute": self.get_rate_per_minute("operations", 5),
                "system_start_time": self._system_start_time.isoformat(),
                "metrics_collected": sum(len(metrics) for metrics in self._metrics.values()),
                "unique_metrics": len(self._metrics)
            }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics."""
        with self._lock:
            return {
                "system": self.get_system_metrics(),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "timers": {name: self.get_timer_stats(name) for name in self._timers},
                "rates": {name: self.get_rate_per_minute(name) for name in self._rates},
                "performance_summary": self._get_performance_summary()
            }
    
    def _get_performance_summary(self) -> Dict[str, Any]:
        """Get performance metrics summary."""
        if not self._performance_metrics:
            return {"total_operations": 0}
        
        recent_metrics = list(self._performance_metrics)
        successful = [m for m in recent_metrics if m.success]
        failed = [m for m in recent_metrics if not m.success]
        
        durations = [m.duration_ms for m in recent_metrics if m.duration_ms is not None]
        
        summary = {
            "total_operations": len(recent_metrics),
            "successful_operations": len(successful),
            "failed_operations": len(failed),
            "success_rate": len(successful) / len(recent_metrics) * 100 if recent_metrics else 0.0
        }
        
        if durations:
            sorted_durations = sorted(durations)
            summary.update({
                "avg_duration_ms": sum(durations) / len(durations),
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "p95_duration_ms": sorted_durations[int(len(sorted_durations) * 0.95)],
                "p99_duration_ms": sorted_durations[int(len(sorted_durations) * 0.99)]
            })
        
        return summary


class StructuredLogger:
    """
    Structured logging system with progress indicators and contextual information.
    
    Provides structured logging capabilities with automatic context enrichment,
    progress tracking, and integration with monitoring systems.
    """
    
    def __init__(self, logger_name: str = "workflow_monitoring"):
        """
        Initialize the structured logger.
        
        Args:
            logger_name: Name of the logger
        """
        self.logger_name = logger_name
        
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
        self._context_stack = []
        
        # Progress tracking
        self._progress_indicators: Dict[str, ProgressIndicator] = {}
        self._lock = threading.RLock()
    
    @contextmanager
    def log_context(self, **context):
        """Add context to all log messages within this block."""
        self._context_stack.append(context)
        try:
            yield
        finally:
            self._context_stack.pop()
    
    def _get_enriched_context(self, **kwargs) -> Dict[str, Any]:
        """Get enriched context from stack and kwargs."""
        context = {}
        
        # Add context from stack
        for ctx in self._context_stack:
            context.update(ctx)
        
        # Add provided context
        context.update(kwargs)
        
        # Add automatic context
        context.update({
            "timestamp": datetime.now().isoformat(),
            "thread_id": threading.current_thread().ident,
            "logger_name": self.logger_name
        })
        
        return context
    
    def info(self, message: str, **kwargs):
        """Log info message with enriched context."""
        context = self._get_enriched_context(**kwargs)
        self.logger.info(message, **context)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with enriched context."""
        context = self._get_enriched_context(**kwargs)
        self.logger.warning(message, **context)
    
    def error(self, message: str, **kwargs):
        """Log error message with enriched context."""
        context = self._get_enriched_context(**kwargs)
        self.logger.error(message, **context)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with enriched context."""
        context = self._get_enriched_context(**kwargs)
        self.logger.critical(message, **context)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with enriched context."""
        context = self._get_enriched_context(**kwargs)
        self.logger.debug(message, **context)
    
    def log_workflow_step(self, step_name: str, username: str, success: bool, 
                         duration_ms: Optional[float] = None, **kwargs):
        """Log workflow step completion with standard format."""
        context = self._get_enriched_context(
            step_name=step_name,
            username=username,
            success=success,
            duration_ms=duration_ms,
            **kwargs
        )
        
        level = "info" if success else "error"
        message = f"Workflow step '{step_name}' {'completed' if success else 'failed'} for @{username}"
        
        getattr(self.logger, level)(message, **context)
    
    def log_performance_metric(self, performance_metric: PerformanceMetrics):
        """Log performance metric with structured format."""
        context = self._get_enriched_context(
            operation_name=performance_metric.operation_name,
            duration_ms=performance_metric.duration_ms,
            success=performance_metric.success,
            error_message=performance_metric.error_message,
            **performance_metric.metadata
        )
        
        level = "info" if performance_metric.success else "error"
        message = f"Operation '{performance_metric.operation_name}' {'completed' if performance_metric.success else 'failed'}"
        
        getattr(self.logger, level)(message, **context)
    
    def create_progress_indicator(self, operation_id: str, operation_name: str, 
                                total_steps: int, **metadata) -> ProgressIndicator:
        """Create a new progress indicator for long-running operations."""
        with self._lock:
            progress = ProgressIndicator(
                operation_id=operation_id,
                operation_name=operation_name,
                total_steps=total_steps,
                metadata=metadata
            )
            
            self._progress_indicators[operation_id] = progress
            
            self.info(
                f"Started operation '{operation_name}'",
                operation_id=operation_id,
                total_steps=total_steps,
                **metadata
            )
            
            return progress
    
    def update_progress(self, operation_id: str, current_step: int, 
                       details: str = "", **metadata):
        """Update progress for a long-running operation."""
        with self._lock:
            if operation_id not in self._progress_indicators:
                self.warning(f"Progress indicator not found for operation {operation_id}")
                return
            
            progress = self._progress_indicators[operation_id]
            progress.update_progress(current_step, details, metadata)
            
            self.info(
                f"Progress update for '{progress.operation_name}': {progress.progress_percentage:.1f}%",
                operation_id=operation_id,
                current_step=current_step,
                total_steps=progress.total_steps,
                progress_percentage=progress.progress_percentage,
                details=details,
                estimated_completion=progress.estimated_completion.isoformat() if progress.estimated_completion else None,
                **metadata
            )
    
    def complete_progress(self, operation_id: str, success: bool = True, 
                         final_message: str = ""):
        """Complete a progress indicator."""
        with self._lock:
            if operation_id not in self._progress_indicators:
                self.warning(f"Progress indicator not found for operation {operation_id}")
                return
            
            progress = self._progress_indicators[operation_id]
            progress.status = "completed" if success else "failed"
            progress.current_step = progress.total_steps if success else progress.current_step
            
            level = "info" if success else "error"
            message = f"Operation '{progress.operation_name}' {'completed successfully' if success else 'failed'}"
            if final_message:
                message += f": {final_message}"
            
            getattr(self.logger, level)(
                message,
                operation_id=operation_id,
                operation_name=progress.operation_name,
                total_duration=progress.elapsed_time.total_seconds(),
                final_progress=progress.progress_percentage,
                success=success
            )
            
            # Keep completed progress for a while for monitoring
            # In production, you might want to move this to a separate storage
    
    def get_progress_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get current progress status for an operation."""
        with self._lock:
            if operation_id not in self._progress_indicators:
                return None
            
            progress = self._progress_indicators[operation_id]
            return {
                "operation_id": progress.operation_id,
                "operation_name": progress.operation_name,
                "current_step": progress.current_step,
                "total_steps": progress.total_steps,
                "progress_percentage": progress.progress_percentage,
                "status": progress.status,
                "details": progress.details,
                "elapsed_time": progress.elapsed_time.total_seconds(),
                "estimated_completion": progress.estimated_completion.isoformat() if progress.estimated_completion else None,
                "metadata": progress.metadata
            }
    
    def get_all_progress(self) -> Dict[str, Dict[str, Any]]:
        """Get all current progress indicators."""
        with self._lock:
            return {
                operation_id: self.get_progress_status(operation_id)
                for operation_id in self._progress_indicators
            }


class AlertManager:
    """
    Alert management system for workflow monitoring.
    
    Provides alert generation, management, and notification capabilities
    with configurable thresholds and escalation policies.
    """
    
    def __init__(self, max_alerts: int = 1000):
        """
        Initialize the alert manager.
        
        Args:
            max_alerts: Maximum number of alerts to keep in memory
        """
        self.max_alerts = max_alerts
        self._alerts: deque = deque(maxlen=max_alerts)
        self._alert_handlers: List[Callable[[Alert], None]] = []
        self._alert_rules: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        
        # Alert statistics
        self._alert_counts = defaultdict(int)
        self._last_alert_times = {}
    
    def add_alert_handler(self, handler: Callable[[Alert], None]):
        """Add an alert handler function."""
        self._alert_handlers.append(handler)
    
    def add_alert_rule(self, rule_name: str, condition: Callable[[Dict[str, Any]], bool],
                      severity: AlertSeverity, title: str, message_template: str,
                      cooldown_minutes: int = 5):
        """
        Add an alert rule.
        
        Args:
            rule_name: Unique name for the rule
            condition: Function that takes metrics and returns True if alert should fire
            severity: Alert severity level
            title: Alert title
            message_template: Message template (can use {metric_name} placeholders)
            cooldown_minutes: Minimum time between alerts of this type
        """
        self._alert_rules[rule_name] = {
            "condition": condition,
            "severity": severity,
            "title": title,
            "message_template": message_template,
            "cooldown_minutes": cooldown_minutes
        }
    
    def create_alert(self, severity: AlertSeverity, title: str, message: str,
                    source: str = "workflow_monitoring", metadata: Dict[str, Any] = None) -> Alert:
        """Create and process a new alert."""
        with self._lock:
            alert = Alert(
                id=f"alert_{int(time.time() * 1000)}_{len(self._alerts)}",
                severity=severity,
                title=title,
                message=message,
                source=source,
                metadata=metadata or {}
            )
            
            self._alerts.append(alert)
            self._alert_counts[severity.value] += 1
            
            # Notify handlers
            for handler in self._alert_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    # Don't let handler errors break alert processing
                    logging.getLogger(__name__).error(f"Alert handler error: {e}")
            
            return alert
    
    def evaluate_rules(self, metrics: Dict[str, Any]):
        """Evaluate all alert rules against current metrics."""
        with self._lock:
            now = datetime.now()
            
            for rule_name, rule in self._alert_rules.items():
                try:
                    # Check cooldown
                    last_alert_time = self._last_alert_times.get(rule_name)
                    if last_alert_time:
                        cooldown = timedelta(minutes=rule["cooldown_minutes"])
                        if now - last_alert_time < cooldown:
                            continue
                    
                    # Evaluate condition
                    if rule["condition"](metrics):
                        # Format message
                        message = rule["message_template"].format(**metrics)
                        
                        # Create alert
                        self.create_alert(
                            severity=rule["severity"],
                            title=rule["title"],
                            message=message,
                            source=f"rule_{rule_name}",
                            metadata={"rule_name": rule_name, "metrics": metrics}
                        )
                        
                        self._last_alert_times[rule_name] = now
                
                except Exception as e:
                    logging.getLogger(__name__).error(f"Error evaluating alert rule {rule_name}: {e}")
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert by ID."""
        with self._lock:
            for alert in self._alerts:
                if alert.id == alert_id and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                    return True
            return False
    
    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Get all active (unresolved) alerts."""
        with self._lock:
            alerts = [alert for alert in self._alerts if not alert.resolved]
            
            if severity:
                alerts = [alert for alert in alerts if alert.severity == severity]
            
            return sorted(alerts, key=lambda a: a.timestamp, reverse=True)
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary statistics."""
        with self._lock:
            active_alerts = self.get_active_alerts()
            
            return {
                "total_alerts": len(self._alerts),
                "active_alerts": len(active_alerts),
                "resolved_alerts": len(self._alerts) - len(active_alerts),
                "alerts_by_severity": dict(self._alert_counts),
                "active_by_severity": {
                    severity.value: len([a for a in active_alerts if a.severity == severity])
                    for severity in AlertSeverity
                },
                "recent_alerts": [
                    {
                        "id": alert.id,
                        "severity": alert.severity.value,
                        "title": alert.title,
                        "timestamp": alert.timestamp.isoformat(),
                        "resolved": alert.resolved
                    }
                    for alert in list(self._alerts)[-10:]  # Last 10 alerts
                ]
            }


class HealthCheckManager:
    """
    Health check system for monitoring system components and dependencies.
    
    Provides comprehensive health monitoring with configurable checks,
    automatic execution, and status reporting.
    """
    
    def __init__(self):
        """Initialize the health check manager."""
        self._health_checks: Dict[str, Callable[[], HealthCheck]] = {}
        self._last_results: Dict[str, HealthCheck] = {}
        self._check_intervals: Dict[str, int] = {}  # seconds
        self._executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="health_check")
        self._lock = threading.RLock()
        self._running = False
        self._check_thread = None
    
    def register_health_check(self, name: str, check_func: Callable[[], HealthCheck],
                            interval_seconds: int = 60):
        """
        Register a health check function.
        
        Args:
            name: Unique name for the health check
            check_func: Function that returns a HealthCheck result
            interval_seconds: How often to run this check
        """
        with self._lock:
            self._health_checks[name] = check_func
            self._check_intervals[name] = interval_seconds
    
    def run_health_check(self, name: str) -> Optional[HealthCheck]:
        """Run a specific health check."""
        with self._lock:
            if name not in self._health_checks:
                return None
            
            check_func = self._health_checks[name]
        
        try:
            start_time = time.time()
            result = check_func()
            end_time = time.time()
            
            result.response_time_ms = (end_time - start_time) * 1000
            
            with self._lock:
                self._last_results[name] = result
            
            return result
            
        except Exception as e:
            error_result = HealthCheck(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                response_time_ms=None,
                metadata={"error": str(e), "exception_type": type(e).__name__}
            )
            
            with self._lock:
                self._last_results[name] = error_result
            
            return error_result
    
    def run_all_health_checks(self) -> Dict[str, HealthCheck]:
        """Run all registered health checks."""
        results = {}
        
        # Run checks in parallel
        futures = {}
        for name in self._health_checks:
            future = self._executor.submit(self.run_health_check, name)
            futures[name] = future
        
        # Collect results
        for name, future in futures.items():
            try:
                result = future.result(timeout=30)  # 30 second timeout per check
                if result:
                    results[name] = result
            except Exception as e:
                results[name] = HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check timeout or error: {str(e)}",
                    metadata={"error": str(e)}
                )
        
        return results
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        with self._lock:
            if not self._last_results:
                return {
                    "overall_status": HealthStatus.UNKNOWN.value,
                    "message": "No health checks have been run",
                    "checks": {},
                    "summary": {
                        "total_checks": 0,
                        "healthy": 0,
                        "degraded": 0,
                        "unhealthy": 0,
                        "unknown": 0
                    }
                }
            
            results = dict(self._last_results)
        
        # Calculate overall status
        statuses = [check.status for check in results.values()]
        status_counts = {status: statuses.count(status) for status in HealthStatus}
        
        if status_counts[HealthStatus.UNHEALTHY] > 0:
            overall_status = HealthStatus.UNHEALTHY
            message = f"{status_counts[HealthStatus.UNHEALTHY]} unhealthy components"
        elif status_counts[HealthStatus.DEGRADED] > 0:
            overall_status = HealthStatus.DEGRADED
            message = f"{status_counts[HealthStatus.DEGRADED]} degraded components"
        elif status_counts[HealthStatus.UNKNOWN] > 0:
            overall_status = HealthStatus.UNKNOWN
            message = f"{status_counts[HealthStatus.UNKNOWN]} unknown components"
        else:
            overall_status = HealthStatus.HEALTHY
            message = "All components healthy"
        
        return {
            "overall_status": overall_status.value,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "checks": {
                name: {
                    "status": check.status.value,
                    "message": check.message,
                    "timestamp": check.timestamp.isoformat(),
                    "response_time_ms": check.response_time_ms,
                    "metadata": check.metadata
                }
                for name, check in results.items()
            },
            "summary": {
                "total_checks": len(results),
                "healthy": status_counts[HealthStatus.HEALTHY],
                "degraded": status_counts[HealthStatus.DEGRADED],
                "unhealthy": status_counts[HealthStatus.UNHEALTHY],
                "unknown": status_counts[HealthStatus.UNKNOWN]
            }
        }
    
    def start_periodic_checks(self):
        """Start periodic health check execution."""
        if self._running:
            return
        
        self._running = True
        self._check_thread = threading.Thread(target=self._periodic_check_loop, daemon=True)
        self._check_thread.start()
    
    def stop_periodic_checks(self):
        """Stop periodic health check execution."""
        self._running = False
        if self._check_thread:
            self._check_thread.join(timeout=5)
    
    def _periodic_check_loop(self):
        """Periodic health check execution loop."""
        last_check_times = {}
        
        while self._running:
            try:
                now = time.time()
                
                for name, interval in self._check_intervals.items():
                    last_check = last_check_times.get(name, 0)
                    
                    if now - last_check >= interval:
                        self._executor.submit(self.run_health_check, name)
                        last_check_times[name] = now
                
                time.sleep(1)  # Check every second
                
            except Exception as e:
                logging.getLogger(__name__).error(f"Error in health check loop: {e}")
                time.sleep(5)  # Wait before retrying


class WorkflowMonitor:
    """
    Comprehensive workflow monitoring system.
    
    Integrates metrics collection, structured logging, alerting, and health checks
    into a unified monitoring solution for the Advanced Skill Generator Workflow.
    """
    
    def __init__(self, logger_name: str = "workflow_monitoring"):
        """
        Initialize the workflow monitor.
        
        Args:
            logger_name: Name for the structured logger
        """
        self.metrics = WorkflowMetricsCollector()
        self.logger = StructuredLogger(logger_name)
        self.alerts = AlertManager()
        self.health = HealthCheckManager()
        
        # Setup default alert rules
        self._setup_default_alert_rules()
        
        # Setup default health checks
        self._setup_default_health_checks()
        
        # Start periodic monitoring
        self.health.start_periodic_checks()
        
        # Monitoring thread for alert evaluation
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_running = True
        self._monitoring_thread.start()
    
    def _setup_default_alert_rules(self):
        """Setup default alert rules for common issues."""
        
        # High error rate alert
        self.alerts.add_alert_rule(
            "high_error_rate",
            lambda metrics: metrics.get("system", {}).get("success_rate_percentage", 100) < 90,
            AlertSeverity.WARNING,
            "High Error Rate Detected",
            "Success rate dropped to {success_rate_percentage:.1f}%",
            cooldown_minutes=10
        )
        
        # Critical error rate alert
        self.alerts.add_alert_rule(
            "critical_error_rate",
            lambda metrics: metrics.get("system", {}).get("success_rate_percentage", 100) < 75,
            AlertSeverity.CRITICAL,
            "Critical Error Rate",
            "Success rate critically low at {success_rate_percentage:.1f}%",
            cooldown_minutes=5
        )
        
        # High response time alert
        self.alerts.add_alert_rule(
            "high_response_time",
            lambda metrics: metrics.get("performance_summary", {}).get("p95_duration_ms", 0) > 30000,
            AlertSeverity.WARNING,
            "High Response Time",
            "95th percentile response time is {p95_duration_ms:.0f}ms",
            cooldown_minutes=15
        )
        
        # System uptime alert
        self.alerts.add_alert_rule(
            "low_uptime",
            lambda metrics: metrics.get("system", {}).get("uptime_seconds", 0) < 3600,  # Less than 1 hour
            AlertSeverity.INFO,
            "System Recently Started",
            "System uptime is only {uptime_formatted}",
            cooldown_minutes=60
        )
    
    def _setup_default_health_checks(self):
        """Setup default health checks for system components."""
        
        def check_metrics_collection():
            """Check if metrics are being collected properly."""
            try:
                system_metrics = self.metrics.get_system_metrics()
                
                if system_metrics["total_operations"] == 0:
                    return HealthCheck(
                        name="metrics_collection",
                        status=HealthStatus.DEGRADED,
                        message="No operations recorded yet",
                        metadata=system_metrics
                    )
                
                return HealthCheck(
                    name="metrics_collection",
                    status=HealthStatus.HEALTHY,
                    message=f"Metrics collection active: {system_metrics['total_operations']} operations recorded",
                    metadata=system_metrics
                )
                
            except Exception as e:
                return HealthCheck(
                    name="metrics_collection",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Metrics collection error: {str(e)}",
                    metadata={"error": str(e)}
                )
        
        def check_logging_system():
            """Check if logging system is working."""
            try:
                # Test log message
                test_message = f"Health check test at {datetime.now().isoformat()}"
                self.logger.debug("Health check test message", test_type="health_check")
                
                return HealthCheck(
                    name="logging_system",
                    status=HealthStatus.HEALTHY,
                    message="Logging system operational",
                    metadata={"test_message": test_message}
                )
                
            except Exception as e:
                return HealthCheck(
                    name="logging_system",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Logging system error: {str(e)}",
                    metadata={"error": str(e)}
                )
        
        def check_alert_system():
            """Check if alert system is working."""
            try:
                alert_summary = self.alerts.get_alert_summary()
                
                # Check for too many active alerts
                if alert_summary["active_alerts"] > 50:
                    return HealthCheck(
                        name="alert_system",
                        status=HealthStatus.DEGRADED,
                        message=f"High number of active alerts: {alert_summary['active_alerts']}",
                        metadata=alert_summary
                    )
                
                return HealthCheck(
                    name="alert_system",
                    status=HealthStatus.HEALTHY,
                    message=f"Alert system operational: {alert_summary['active_alerts']} active alerts",
                    metadata=alert_summary
                )
                
            except Exception as e:
                return HealthCheck(
                    name="alert_system",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Alert system error: {str(e)}",
                    metadata={"error": str(e)}
                )
        
        # Register health checks
        self.health.register_health_check("metrics_collection", check_metrics_collection, 30)
        self.health.register_health_check("logging_system", check_logging_system, 60)
        self.health.register_health_check("alert_system", check_alert_system, 120)
    
    def _monitoring_loop(self):
        """Main monitoring loop for alert evaluation."""
        while self._monitoring_running:
            try:
                # Get current metrics
                metrics = self.metrics.get_all_metrics()
                
                # Evaluate alert rules
                self.alerts.evaluate_rules(metrics)
                
                # Sleep for 30 seconds
                time.sleep(30)
                
            except Exception as e:
                logging.getLogger(__name__).error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    @contextmanager
    def monitor_operation(self, operation_name: str, username: str = "", **metadata):
        """
        Context manager for monitoring workflow operations.
        
        Automatically tracks performance metrics, logs operation lifecycle,
        and handles errors with proper monitoring integration.
        """
        operation_id = f"{operation_name}_{int(time.time() * 1000)}"
        performance_metric = PerformanceMetrics(
            operation_name=operation_name,
            start_time=datetime.now(),
            metadata={**metadata, "username": username}
        )
        
        # Start logging context
        with self.logger.log_context(operation_name=operation_name, operation_id=operation_id, username=username):
            self.logger.info(f"Starting operation '{operation_name}'", **metadata)
            
            # Record operation start
            self.metrics.increment_counter("operations_started", tags={"operation": operation_name})
            
            try:
                yield operation_id
                
                # Operation completed successfully
                performance_metric.complete(success=True)
                self.metrics.increment_counter("operations_completed", tags={"operation": operation_name})
                self.metrics.record_timer(f"operation_duration_{operation_name}", performance_metric.duration_ms)
                
                self.logger.info(
                    f"Operation '{operation_name}' completed successfully",
                    duration_ms=performance_metric.duration_ms
                )
                
            except Exception as e:
                # Operation failed
                performance_metric.complete(success=False, error_message=str(e))
                self.metrics.increment_counter("operations_failed", tags={"operation": operation_name})
                
                self.logger.error(
                    f"Operation '{operation_name}' failed",
                    error_message=str(e),
                    duration_ms=performance_metric.duration_ms,
                    exception_type=type(e).__name__
                )
                
                # Create alert for operation failure
                self.alerts.create_alert(
                    severity=AlertSeverity.ERROR,
                    title=f"Operation Failed: {operation_name}",
                    message=f"Operation '{operation_name}' failed: {str(e)}",
                    metadata={
                        "operation_name": operation_name,
                        "username": username,
                        "error_message": str(e),
                        "duration_ms": performance_metric.duration_ms
                    }
                )
                
                raise
            
            finally:
                # Record performance metric
                self.metrics.record_performance(performance_metric)
                self.logger.log_performance_metric(performance_metric)
    
    def get_monitoring_dashboard(self) -> Dict[str, Any]:
        """
        Get comprehensive monitoring dashboard data.
        
        Returns all monitoring information in a format suitable for
        dashboard display or API responses.
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "system_health": self.health.get_system_health(),
            "metrics": self.metrics.get_all_metrics(),
            "alerts": self.alerts.get_alert_summary(),
            "progress_indicators": self.logger.get_all_progress(),
            "monitoring_status": {
                "metrics_collector_active": True,
                "structured_logging_active": True,
                "alert_manager_active": True,
                "health_checks_active": self.health._running,
                "monitoring_loop_active": self._monitoring_running
            }
        }
    
    def shutdown(self):
        """Shutdown the monitoring system gracefully."""
        self.logger.info("Shutting down workflow monitoring system")
        
        # Stop monitoring loop
        self._monitoring_running = False
        if self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=5)
        
        # Stop health checks
        self.health.stop_periodic_checks()
        
        # Shutdown executor
        self.health._executor.shutdown(wait=True, timeout=10)
        
        self.logger.info("Workflow monitoring system shutdown complete")


# Global monitoring instance
_global_monitor: Optional[WorkflowMonitor] = None


def get_workflow_monitor() -> WorkflowMonitor:
    """Get the global workflow monitor instance."""
    global _global_monitor
    
    if _global_monitor is None:
        _global_monitor = WorkflowMonitor()
    
    return _global_monitor


def setup_workflow_monitoring(logger_name: str = "workflow_monitoring") -> WorkflowMonitor:
    """
    Setup and configure workflow monitoring system.
    
    Args:
        logger_name: Name for the structured logger
        
    Returns:
        Configured WorkflowMonitor instance
    """
    global _global_monitor
    
    if _global_monitor is not None:
        _global_monitor.shutdown()
    
    _global_monitor = WorkflowMonitor(logger_name)
    
    # Setup console alert handler for development
    def console_alert_handler(alert: Alert):
        """Simple console alert handler for development."""
        print(f"[ALERT {alert.severity.value.upper()}] {alert.title}: {alert.message}")
    
    _global_monitor.alerts.add_alert_handler(console_alert_handler)
    
    return _global_monitor


# Decorator for automatic operation monitoring
def monitor_workflow_operation(operation_name: str = None):
    """
    Decorator for automatic workflow operation monitoring.
    
    Args:
        operation_name: Name of the operation (defaults to function name)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            monitor = get_workflow_monitor()
            
            # Extract username if available
            username = ""
            if args and hasattr(args[0], 'username'):
                username = args[0].username
            elif 'username' in kwargs:
                username = kwargs['username']
            
            with monitor.monitor_operation(op_name, username=username):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator
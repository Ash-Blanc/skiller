"""
Error handling and partial success scenarios with graceful degradation.

This module implements comprehensive error handling for the Advanced Skill Generator Workflow,
ensuring graceful degradation when tools fail and partial success scenarios are handled properly.
"""

import logging
import traceback
from typing import Dict, Any, List, Optional, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..models.collected_data import CollectedData, TwitterAPIData, ScrapeBadgerData
from ..utils.workflow_metrics import get_workflow_monitor
from ..utils.circuit_breaker import get_circuit_manager


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""
    NETWORK = "network"
    API_LIMIT = "api_limit"
    AUTHENTICATION = "authentication"
    DATA_FORMAT = "data_format"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass
class WorkflowError:
    """Structured error information."""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    source: str  # Which component/tool caused the error
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    recovery_suggestions: List[str] = field(default_factory=list)


@dataclass
class PartialSuccessResult:
    """Result of partial success scenario."""
    overall_success: bool
    successful_components: List[str]
    failed_components: List[str]
    collected_data: Optional[CollectedData]
    errors: List[WorkflowError]
    degradation_level: str  # "none", "minimal", "moderate", "severe"
    quality_impact: float  # 0.0 to 1.0, how much quality was impacted


class GracefulDegradationHandler:
    """Handles graceful degradation scenarios for workflow failures."""
    
    def __init__(self):
        self.logger = logging.getLogger("graceful_degradation")
        self.workflow_monitor = get_workflow_monitor()
        self.circuit_manager = get_circuit_manager()
        
        # Error classification patterns
        self.error_patterns = {
            ErrorCategory.NETWORK: [
                "connection", "network", "dns", "timeout", "unreachable"
            ],
            ErrorCategory.API_LIMIT: [
                "rate limit", "quota", "too many requests", "429"
            ],
            ErrorCategory.AUTHENTICATION: [
                "unauthorized", "forbidden", "401", "403", "api key", "token"
            ],
            ErrorCategory.DATA_FORMAT: [
                "json", "parse", "format", "invalid response", "malformed"
            ],
            ErrorCategory.TIMEOUT: [
                "timeout", "timed out", "deadline", "slow"
            ],
            ErrorCategory.VALIDATION: [
                "validation", "invalid", "missing", "required"
            ]
        }
    
    def handle_collection_errors(self, username: str, twitter_result: Optional[Exception], 
                                scrapebadger_result: Optional[Exception], 
                                workflow_id: str = None) -> PartialSuccessResult:
        """
        Handle errors from data collection and determine graceful degradation strategy.
        
        Args:
            username: Username being processed
            twitter_result: Exception from TwitterAPI collection or None if successful
            scrapebadger_result: Exception from ScrapeBadger collection or None if successful
            workflow_id: Optional workflow ID for tracking
            
        Returns:
            PartialSuccessResult with degradation strategy and available data
        """
        errors = []
        successful_components = []
        failed_components = []
        
        # Analyze TwitterAPI result
        if twitter_result is None:
            successful_components.append("TwitterAPI.io")
        else:
            failed_components.append("TwitterAPI.io")
            error = self._classify_error(twitter_result, "TwitterAPI.io")
            errors.append(error)
        
        # Analyze ScrapeBadger result
        if scrapebadger_result is None:
            successful_components.append("ScrapeBadger")
        else:
            failed_components.append("ScrapeBadger")
            error = self._classify_error(scrapebadger_result, "ScrapeBadger")
            errors.append(error)
        
        # Determine degradation level and strategy
        degradation_level, quality_impact = self._assess_degradation(
            successful_components, failed_components, errors
        )
        
        # Create partial success result
        overall_success = len(successful_components) > 0
        
        # Generate fallback data if needed
        collected_data = self._generate_fallback_data(
            username, successful_components, failed_components, errors
        )
        
        result = PartialSuccessResult(
            overall_success=overall_success,
            successful_components=successful_components,
            failed_components=failed_components,
            collected_data=collected_data,
            errors=errors,
            degradation_level=degradation_level,
            quality_impact=quality_impact
        )
        
        # Log the partial success scenario
        if workflow_id:
            self.workflow_monitor.log_step_completion(
                workflow_id,
                "error_handling",
                overall_success,
                degradation_level=degradation_level,
                successful_components=len(successful_components),
                failed_components=len(failed_components),
                quality_impact=quality_impact
            )
        
        return result
    
    def _classify_error(self, error: Exception, source: str) -> WorkflowError:
        """Classify an error and determine its category and severity."""
        error_message = str(error).lower()
        
        # Determine category
        category = ErrorCategory.UNKNOWN
        for cat, patterns in self.error_patterns.items():
            if any(pattern in error_message for pattern in patterns):
                category = cat
                break
        
        # Determine severity based on category and content
        severity = self._determine_severity(category, error_message)
        
        # Generate recovery suggestions
        recovery_suggestions = self._generate_recovery_suggestions(category, source)
        
        return WorkflowError(
            error_id=f"{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            category=category,
            severity=severity,
            message=str(error),
            source=source,
            timestamp=datetime.now(),
            details={
                "error_type": type(error).__name__,
                "error_class": error.__class__.__module__
            },
            stack_trace=traceback.format_exc(),
            recovery_suggestions=recovery_suggestions
        )
    
    def _determine_severity(self, category: ErrorCategory, message: str) -> ErrorSeverity:
        """Determine error severity based on category and message content."""
        
        # Critical errors that prevent any functionality
        if category == ErrorCategory.AUTHENTICATION:
            return ErrorSeverity.CRITICAL
        
        # High severity errors that significantly impact functionality
        if category in [ErrorCategory.SYSTEM, ErrorCategory.VALIDATION]:
            return ErrorSeverity.HIGH
        
        # Medium severity errors that can be worked around
        if category in [ErrorCategory.API_LIMIT, ErrorCategory.TIMEOUT]:
            return ErrorSeverity.MEDIUM
        
        # Low severity errors that have minimal impact
        if category in [ErrorCategory.NETWORK, ErrorCategory.DATA_FORMAT]:
            return ErrorSeverity.LOW
        
        return ErrorSeverity.MEDIUM  # Default
    
    def _generate_recovery_suggestions(self, category: ErrorCategory, source: str) -> List[str]:
        """Generate recovery suggestions based on error category."""
        
        suggestions = {
            ErrorCategory.NETWORK: [
                "Check internet connectivity",
                "Verify service endpoints are accessible",
                "Try again in a few minutes"
            ],
            ErrorCategory.API_LIMIT: [
                "Wait for rate limit reset",
                "Use alternative data source",
                "Reduce request frequency"
            ],
            ErrorCategory.AUTHENTICATION: [
                "Verify API keys are correct",
                "Check API key permissions",
                "Regenerate API credentials"
            ],
            ErrorCategory.DATA_FORMAT: [
                "Check API response format",
                "Verify data parsing logic",
                "Use fallback data structure"
            ],
            ErrorCategory.TIMEOUT: [
                "Increase timeout duration",
                "Retry with exponential backoff",
                "Use cached data if available"
            ],
            ErrorCategory.VALIDATION: [
                "Check input parameters",
                "Verify data format requirements",
                "Use default values where appropriate"
            ],
            ErrorCategory.SYSTEM: [
                "Check system resources",
                "Restart the service",
                "Contact system administrator"
            ]
        }
        
        base_suggestions = suggestions.get(category, ["Retry the operation", "Contact support"])
        
        # Add source-specific suggestions
        if source == "TwitterAPI.io":
            base_suggestions.append("Try using ScrapeBadger as alternative")
        elif source == "ScrapeBadger":
            base_suggestions.append("Try using TwitterAPI.io as alternative")
        
        return base_suggestions
    
    def _assess_degradation(self, successful: List[str], failed: List[str], 
                          errors: List[WorkflowError]) -> tuple[str, float]:
        """Assess the level of degradation and quality impact."""
        
        total_components = len(successful) + len(failed)
        success_rate = len(successful) / total_components if total_components > 0 else 0
        
        # Determine degradation level
        if success_rate >= 1.0:
            degradation_level = "none"
            quality_impact = 0.0
        elif success_rate >= 0.75:
            degradation_level = "minimal"
            quality_impact = 0.1
        elif success_rate >= 0.5:
            degradation_level = "moderate"
            quality_impact = 0.3
        elif success_rate > 0:
            degradation_level = "severe"
            quality_impact = 0.6
        else:
            degradation_level = "critical"
            quality_impact = 0.9
        
        # Adjust based on error severity
        critical_errors = [e for e in errors if e.severity == ErrorSeverity.CRITICAL]
        if critical_errors:
            quality_impact = min(quality_impact + 0.2, 1.0)
        
        return degradation_level, quality_impact
    
    def _generate_fallback_data(self, username: str, successful: List[str], 
                              failed: List[str], errors: List[WorkflowError]) -> CollectedData:
        """Generate fallback data structure for partial success scenarios."""
        
        # Create minimal data structure
        twitter_data = None
        scrapebadger_data = None
        
        # If both sources failed, create minimal fallback data
        if not successful:
            twitter_data = TwitterAPIData(
                profile={
                    "username": username,
                    "display_name": username,
                    "description": f"Profile for {username} (limited data - service unavailable)",
                    "followers_count": 0,
                    "following_count": 0,
                    "verified": False
                },
                tweets=[],
                followings=[],
                collection_success=False,
                error_message="All data collection services unavailable",
                metadata={
                    "fallback_mode": True,
                    "degradation_reason": "service_unavailable"
                }
            )
        
        # Create collected data with available information
        collected_data = CollectedData(
            username=username,
            twitter_api_data=twitter_data,
            scrapebadger_data=scrapebadger_data,
            collection_timestamp=datetime.now()
        )
        
        return collected_data
    
    def create_error_report(self, errors: List[WorkflowError]) -> Dict[str, Any]:
        """Create a comprehensive error report."""
        
        if not errors:
            return {"status": "no_errors", "summary": "No errors to report"}
        
        # Categorize errors
        by_category = {}
        by_severity = {}
        
        for error in errors:
            category = error.category.value
            severity = error.severity.value
            
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(error)
            
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(error)
        
        # Generate summary
        total_errors = len(errors)
        critical_count = len(by_severity.get("critical", []))
        high_count = len(by_severity.get("high", []))
        
        return {
            "status": "errors_detected",
            "summary": {
                "total_errors": total_errors,
                "critical_errors": critical_count,
                "high_severity_errors": high_count,
                "most_common_category": max(by_category.keys(), key=lambda k: len(by_category[k])) if by_category else None
            },
            "errors_by_category": {
                cat: len(errs) for cat, errs in by_category.items()
            },
            "errors_by_severity": {
                sev: len(errs) for sev, errs in by_severity.items()
            },
            "recovery_actions": self._generate_recovery_plan(errors),
            "detailed_errors": [
                {
                    "id": error.error_id,
                    "category": error.category.value,
                    "severity": error.severity.value,
                    "source": error.source,
                    "message": error.message,
                    "timestamp": error.timestamp.isoformat(),
                    "suggestions": error.recovery_suggestions
                }
                for error in errors
            ]
        }
    
    def _generate_recovery_plan(self, errors: List[WorkflowError]) -> List[str]:
        """Generate a prioritized recovery plan based on errors."""
        
        recovery_plan = []
        
        # Handle critical errors first
        critical_errors = [e for e in errors if e.severity == ErrorSeverity.CRITICAL]
        if critical_errors:
            recovery_plan.append("CRITICAL: Address authentication and system errors immediately")
            for error in critical_errors:
                recovery_plan.extend(error.recovery_suggestions[:2])  # Top 2 suggestions
        
        # Handle high severity errors
        high_errors = [e for e in errors if e.severity == ErrorSeverity.HIGH]
        if high_errors:
            recovery_plan.append("HIGH: Resolve system and validation issues")
        
        # Handle API limits and timeouts
        api_errors = [e for e in errors if e.category == ErrorCategory.API_LIMIT]
        if api_errors:
            recovery_plan.append("Wait for API rate limits to reset before retrying")
        
        # General recovery suggestions
        if len(errors) > 1:
            recovery_plan.append("Consider using alternative data sources")
            recovery_plan.append("Implement exponential backoff for retries")
        
        return recovery_plan


def handle_workflow_errors(func: Callable) -> Callable:
    """Decorator to add comprehensive error handling to workflow functions."""
    
    def wrapper(*args, **kwargs):
        handler = GracefulDegradationHandler()
        
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log the error
            handler.logger.error(f"Workflow function {func.__name__} failed: {e}")
            
            # Create error classification
            error = handler._classify_error(e, func.__name__)
            
            # Return partial success result
            return PartialSuccessResult(
                overall_success=False,
                successful_components=[],
                failed_components=[func.__name__],
                collected_data=None,
                errors=[error],
                degradation_level="critical",
                quality_impact=1.0
            )
    
    return wrapper


def create_graceful_degradation_handler() -> GracefulDegradationHandler:
    """Factory function to create a graceful degradation handler."""
    return GracefulDegradationHandler()


if __name__ == "__main__":
    # Demo error handling
    handler = GracefulDegradationHandler()
    
    # Simulate different error scenarios
    test_errors = [
        Exception("Connection timeout after 30 seconds"),
        Exception("Rate limit exceeded - 429 Too Many Requests"),
        Exception("Unauthorized access - invalid API key"),
        Exception("Invalid JSON response format")
    ]
    
    print("Error Handling Demo")
    print("=" * 40)
    
    for i, error in enumerate(test_errors):
        print(f"\nTest Error {i+1}: {error}")
        
        # Simulate partial success scenario
        twitter_error = error if i % 2 == 0 else None
        scrapebadger_error = error if i % 2 == 1 else None
        
        result = handler.handle_collection_errors(
            "testuser", twitter_error, scrapebadger_error
        )
        
        print(f"Overall Success: {result.overall_success}")
        print(f"Degradation Level: {result.degradation_level}")
        print(f"Quality Impact: {result.quality_impact:.1%}")
        print(f"Successful: {result.successful_components}")
        print(f"Failed: {result.failed_components}")
        
        if result.errors:
            error_info = result.errors[0]
            print(f"Error Category: {error_info.category.value}")
            print(f"Error Severity: {error_info.severity.value}")
            print(f"Recovery Suggestions: {error_info.recovery_suggestions[:2]}")
    
    # Generate comprehensive error report
    all_errors = [handler._classify_error(e, f"source_{i}") for i, e in enumerate(test_errors)]
    report = handler.create_error_report(all_errors)
    
    print(f"\n" + "=" * 40)
    print("Error Report Summary")
    print("=" * 40)
    print(f"Total Errors: {report['summary']['total_errors']}")
    print(f"Critical Errors: {report['summary']['critical_errors']}")
    print(f"Recovery Actions: {len(report['recovery_actions'])}")
    
    for action in report['recovery_actions'][:3]:
        print(f"  • {action}")
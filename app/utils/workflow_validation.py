"""
Workflow validation and error handling utilities for Advanced Skill Generator Workflow.

This module provides comprehensive validation and error handling capabilities including:
- API rate limit handling with exponential backoff (AC4.1)
- Private/suspended account scenario management (AC4.2)  
- Meaningful responses for insufficient data cases (AC4.3)
- Robust error recovery and fallback mechanisms

Validates Requirements:
- AC4.1: Handles API rate limits with exponential backoff
- AC4.2: Manages private or suspended account scenarios
- AC4.3: Provides meaningful responses for insufficient data cases
"""

import time
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from functools import wraps

# Configure logging
logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Types of errors that can occur in the workflow."""
    RATE_LIMIT = "rate_limit"
    PRIVATE_ACCOUNT = "private_account"
    SUSPENDED_ACCOUNT = "suspended_account"
    INSUFFICIENT_DATA = "insufficient_data"
    API_ERROR = "api_error"
    NETWORK_ERROR = "network_error"
    AUTHENTICATION_ERROR = "authentication_error"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_ERROR = "unknown_error"


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    
    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented
    
    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented
    
    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented
    
    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented


@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None
    severity: ErrorSeverity = ErrorSeverity.LOW
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ValidationResult to a JSON-serializable dictionary."""
        return {
            "is_valid": self.is_valid,
            "error_type": self.error_type.value if self.error_type else None,
            "error_message": self.error_message,
            "severity": self.severity.value,
            "suggestions": self.suggestions,
            "metadata": self.metadata
        }


@dataclass
class RetryConfig:
    """Configuration for retry logic with exponential backoff."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number."""
        delay = min(self.base_delay * (self.exponential_base ** attempt), self.max_delay)
        
        if self.jitter:
            # Add random jitter to prevent thundering herd
            delay *= (0.5 + random.random() * 0.5)
        
        return delay


@dataclass
class ErrorContext:
    """Context information for error handling."""
    username: str
    step_name: str
    tool_name: Optional[str] = None
    attempt_number: int = 1
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class RateLimitHandler:
    """
    Handles API rate limits with exponential backoff (AC4.1).
    
    This class implements sophisticated rate limiting detection and handling
    with exponential backoff, jitter, and adaptive retry strategies.
    """
    
    def __init__(self, retry_config: Optional[RetryConfig] = None):
        """Initialize rate limit handler with configuration."""
        self.retry_config = retry_config or RetryConfig()
        self.rate_limit_windows: Dict[str, datetime] = {}
        self.consecutive_failures: Dict[str, int] = {}
    
    def is_rate_limited(self, error_message: str, status_code: Optional[int] = None) -> bool:
        """
        Detect if an error is due to rate limiting.
        
        Args:
            error_message: Error message from API
            status_code: HTTP status code if available
            
        Returns:
            True if the error indicates rate limiting
        """
        rate_limit_indicators = [
            "rate limit",
            "too many requests",
            "quota exceeded",
            "throttled",
            "429",
            "rate_limit_exceeded"
        ]
        
        # Check status code
        if status_code == 429:
            return True
        
        # Check error message
        error_lower = error_message.lower()
        return any(indicator in error_lower for indicator in rate_limit_indicators)
    
    def handle_rate_limit(self, tool_name: str, error_context: ErrorContext) -> ValidationResult:
        """
        Handle rate limit error with exponential backoff.
        
        Args:
            tool_name: Name of the tool that hit rate limit
            error_context: Context information about the error
            
        Returns:
            ValidationResult with retry instructions
        """
        attempt = error_context.attempt_number
        delay = self.retry_config.calculate_delay(attempt - 1)
        
        # Track consecutive failures
        self.consecutive_failures[tool_name] = self.consecutive_failures.get(tool_name, 0) + 1
        
        # Set rate limit window
        self.rate_limit_windows[tool_name] = datetime.now() + timedelta(seconds=delay)
        
        logger.warning(
            f"Rate limit hit for {tool_name} (attempt {attempt}). "
            f"Waiting {delay:.2f} seconds before retry."
        )
        
        suggestions = [
            f"Wait {delay:.2f} seconds before retrying",
            f"Consider using alternative data source if available",
            f"Reduce request frequency for {tool_name}"
        ]
        
        if attempt >= self.retry_config.max_attempts:
            suggestions.append("Maximum retry attempts reached - consider manual intervention")
        
        return ValidationResult(
            is_valid=False,
            error_type=ErrorType.RATE_LIMIT,
            error_message=f"Rate limit exceeded for {tool_name}. Retry in {delay:.2f} seconds.",
            severity=ErrorSeverity.MEDIUM,
            suggestions=suggestions,
            metadata={
                "tool_name": tool_name,
                "retry_delay": delay,
                "attempt_number": attempt,
                "max_attempts": self.retry_config.max_attempts,
                "consecutive_failures": self.consecutive_failures[tool_name]
            }
        )
    
    def can_retry(self, tool_name: str) -> bool:
        """
        Check if a tool can be retried based on rate limit windows.
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            True if the tool can be retried now
        """
        if tool_name not in self.rate_limit_windows:
            return True
        
        return datetime.now() >= self.rate_limit_windows[tool_name]
    
    def reset_failures(self, tool_name: str):
        """Reset consecutive failure count for a tool."""
        self.consecutive_failures.pop(tool_name, None)
        self.rate_limit_windows.pop(tool_name, None)


class AccountAccessValidator:
    """
    Validates account access and handles private/suspended accounts (AC4.2).
    
    This class provides comprehensive validation for different account states
    and provides appropriate handling strategies for each scenario.
    """
    
    def __init__(self):
        """Initialize account access validator."""
        self.known_private_accounts: set = set()
        self.known_suspended_accounts: set = set()
    
    def validate_account_access(self, username: str, error_message: str, 
                              response_data: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """
        Validate account access and detect private/suspended accounts.
        
        Args:
            username: Username being accessed
            error_message: Error message from API
            response_data: Response data if available
            
        Returns:
            ValidationResult with account access status
        """
        # Check for private account indicators
        if self._is_private_account(error_message, response_data):
            return self._handle_private_account(username, error_message)
        
        # Check for suspended account indicators
        if self._is_suspended_account(error_message, response_data):
            return self._handle_suspended_account(username, error_message)
        
        # Check for non-existent account
        if self._is_nonexistent_account(error_message, response_data):
            return self._handle_nonexistent_account(username, error_message)
        
        # Account appears accessible
        return ValidationResult(
            is_valid=True,
            metadata={"username": username, "access_status": "accessible"}
        )
    
    def _is_private_account(self, error_message: str, response_data: Optional[Dict[str, Any]]) -> bool:
        """Check if error indicates a private account."""
        private_indicators = [
            "private",
            "protected",
            "not authorized",
            "access denied",
            "unauthorized",
            "forbidden"
        ]
        
        error_lower = error_message.lower()
        return any(indicator in error_lower for indicator in private_indicators)
    
    def _is_suspended_account(self, error_message: str, response_data: Optional[Dict[str, Any]]) -> bool:
        """Check if error indicates a suspended account."""
        suspended_indicators = [
            "suspended",
            "banned",
            "deactivated",
            "account suspended",
            "user suspended",
            "temporarily restricted"
        ]
        
        error_lower = error_message.lower()
        return any(indicator in error_lower for indicator in suspended_indicators)
    
    def _is_nonexistent_account(self, error_message: str, response_data: Optional[Dict[str, Any]]) -> bool:
        """Check if error indicates a non-existent account."""
        nonexistent_indicators = [
            "not found",
            "does not exist",
            "user not found",
            "no user exists",
            "no user found",
            "invalid user",
            "404"
        ]
        
        error_lower = error_message.lower()
        return any(indicator in error_lower for indicator in nonexistent_indicators)
    
    def _handle_private_account(self, username: str, error_message: str) -> ValidationResult:
        """Handle private account scenario (AC4.2)."""
        self.known_private_accounts.add(username)
        
        logger.info(f"Account @{username} is private - limited data collection possible")
        
        return ValidationResult(
            is_valid=False,
            error_type=ErrorType.PRIVATE_ACCOUNT,
            error_message=f"Account @{username} is private. Limited public data available.",
            severity=ErrorSeverity.MEDIUM,
            suggestions=[
                "Use only publicly available profile information",
                "Focus on bio and public metrics if available",
                "Consider alternative data sources",
                "Generate profile with lower confidence score",
                "Inform user about limited data availability"
            ],
            metadata={
                "username": username,
                "account_status": "private",
                "data_collection_strategy": "public_only"
            }
        )
    
    def _handle_suspended_account(self, username: str, error_message: str) -> ValidationResult:
        """Handle suspended account scenario (AC4.2)."""
        self.known_suspended_accounts.add(username)
        
        logger.warning(f"Account @{username} is suspended - no data collection possible")
        
        return ValidationResult(
            is_valid=False,
            error_type=ErrorType.SUSPENDED_ACCOUNT,
            error_message=f"Account @{username} is suspended or deactivated.",
            severity=ErrorSeverity.HIGH,
            suggestions=[
                "Cannot generate skill profile for suspended account",
                "Inform user that account is not accessible",
                "Suggest alternative username if available",
                "Check if account was recently suspended"
            ],
            metadata={
                "username": username,
                "account_status": "suspended",
                "data_collection_possible": False
            }
        )
    
    def _handle_nonexistent_account(self, username: str, error_message: str) -> ValidationResult:
        """Handle non-existent account scenario."""
        logger.info(f"Account @{username} does not exist")
        
        return ValidationResult(
            is_valid=False,
            error_type=ErrorType.VALIDATION_ERROR,
            error_message=f"Account @{username} does not exist.",
            severity=ErrorSeverity.HIGH,
            suggestions=[
                "Verify username spelling",
                "Check if account was recently deleted",
                "Suggest similar usernames if available",
                "Cannot proceed with skill profile generation"
            ],
            metadata={
                "username": username,
                "account_status": "nonexistent",
                "data_collection_possible": False
            }
        )


class DataQualityValidator:
    """
    Validates data quality and provides meaningful responses for insufficient data (AC4.3).
    
    This class implements comprehensive data quality assessment and provides
    actionable feedback when data is insufficient for profile generation.
    """
    
    def __init__(self):
        """Initialize data quality validator."""
        self.quality_thresholds = {
            "min_tweets": 5,
            "min_profile_fields": 3,
            "min_quality_score": 0.3,
            "recommended_tweets": 15,
            "recommended_quality_score": 0.6
        }
    
    def validate_data_sufficiency(self, collected_data: Dict[str, Any], 
                                username: str) -> ValidationResult:
        """
        Validate if collected data is sufficient for profile generation (AC4.3).
        
        Args:
            collected_data: Data collected from various sources
            username: Username being processed
            
        Returns:
            ValidationResult with data sufficiency assessment
        """
        # Extract data metrics
        total_tweets = collected_data.get("total_tweets", 0)
        has_profile_data = collected_data.get("has_profile_data", False)
        quality_score = collected_data.get("quality_score", 0.0)
        sources_count = len(collected_data.get("sources", []))
        has_highlights = collected_data.get("has_highlights", False)
        
        # Perform quality checks
        quality_issues = []
        severity = ErrorSeverity.LOW
        
        # Critical issues (prevent profile generation)
        if not has_profile_data:
            quality_issues.append("No profile data available")
            severity = ErrorSeverity.CRITICAL
        
        if total_tweets < self.quality_thresholds["min_tweets"]:
            quality_issues.append(f"Insufficient tweets ({total_tweets} < {self.quality_thresholds['min_tweets']})")
            severity = max(severity, ErrorSeverity.HIGH)
        
        if quality_score < self.quality_thresholds["min_quality_score"]:
            quality_issues.append(f"Quality score too low ({quality_score:.2f} < {self.quality_thresholds['min_quality_score']})")
            severity = max(severity, ErrorSeverity.HIGH)
        
        # Warning issues (allow profile generation with caveats)
        if total_tweets < self.quality_thresholds["recommended_tweets"]:
            quality_issues.append(f"Below recommended tweet count ({total_tweets} < {self.quality_thresholds['recommended_tweets']})")
            severity = max(severity, ErrorSeverity.MEDIUM)
        
        if quality_score < self.quality_thresholds["recommended_quality_score"]:
            quality_issues.append(f"Below recommended quality score ({quality_score:.2f} < {self.quality_thresholds['recommended_quality_score']})")
            severity = max(severity, ErrorSeverity.MEDIUM)
        
        if sources_count < 2:
            quality_issues.append("Single data source - limited validation possible")
            severity = max(severity, ErrorSeverity.MEDIUM)
        
        if not has_highlights:
            quality_issues.append("No highlighted content available - may miss key insights")
            severity = max(severity, ErrorSeverity.LOW)
        
        # Generate result
        if severity == ErrorSeverity.CRITICAL:
            return self._handle_insufficient_data(username, quality_issues, collected_data)
        elif quality_issues:
            return self._handle_quality_warnings(username, quality_issues, collected_data, severity)
        else:
            return ValidationResult(
                is_valid=True,
                metadata={
                    "username": username,
                    "quality_assessment": "sufficient",
                    "quality_score": quality_score,
                    "data_metrics": collected_data
                }
            )
    
    def _handle_insufficient_data(self, username: str, issues: List[str], 
                                collected_data: Dict[str, Any]) -> ValidationResult:
        """Handle insufficient data scenario (AC4.3)."""
        logger.warning(f"Insufficient data for @{username}: {', '.join(issues)}")
        
        suggestions = [
            "Cannot generate reliable skill profile with current data",
            "Try collecting data again after some time",
            "Check if account has sufficient public content",
            "Consider using alternative data sources"
        ]
        
        # Add specific suggestions based on issues
        if "No profile data" in str(issues):
            suggestions.extend([
                "Verify account exists and is accessible",
                "Check API credentials and permissions"
            ])
        
        if any("tweets" in issue for issue in issues):
            suggestions.extend([
                "Account may be new or inactive",
                "Look for accounts with more posting history"
            ])
        
        return ValidationResult(
            is_valid=False,
            error_type=ErrorType.INSUFFICIENT_DATA,
            error_message=f"Insufficient data to generate skill profile for @{username}. Issues: {', '.join(issues)}",
            severity=ErrorSeverity.CRITICAL,
            suggestions=suggestions,
            metadata={
                "username": username,
                "quality_issues": issues,
                "data_metrics": collected_data,
                "can_generate_profile": False
            }
        )
    
    def _handle_quality_warnings(self, username: str, issues: List[str], 
                               collected_data: Dict[str, Any], 
                               severity: ErrorSeverity) -> ValidationResult:
        """Handle data quality warnings (AC4.3)."""
        logger.info(f"Quality warnings for @{username}: {', '.join(issues)}")
        
        suggestions = [
            "Profile can be generated but with reduced confidence",
            "Consider collecting additional data if possible",
            "Generated profile may have limited insights"
        ]
        
        # Add specific suggestions
        if any("tweet count" in issue for issue in issues):
            suggestions.append("Look for more recent tweets or increase collection period")
        
        if "Single data source" in str(issues):
            suggestions.append("Try enabling additional data collection tools")
        
        if "highlighted content" in str(issues):
            suggestions.append("Profile may miss key insights user wants to highlight")
        
        return ValidationResult(
            is_valid=True,  # Can proceed but with warnings
            error_type=ErrorType.INSUFFICIENT_DATA,
            error_message=f"Data quality warnings for @{username}: {', '.join(issues)}",
            severity=severity,
            suggestions=suggestions,
            metadata={
                "username": username,
                "quality_issues": issues,
                "data_metrics": collected_data,
                "can_generate_profile": True,
                "expected_confidence_reduction": 0.2
            }
        )


class WorkflowValidator:
    """
    Main workflow validation orchestrator.
    
    This class coordinates all validation and error handling components
    to provide comprehensive workflow step validation.
    """
    
    def __init__(self, retry_config: Optional[RetryConfig] = None):
        """Initialize workflow validator with all components."""
        self.rate_limit_handler = RateLimitHandler(retry_config)
        self.account_validator = AccountAccessValidator()
        self.data_quality_validator = DataQualityValidator()
        self.validation_history: List[ValidationResult] = []
    
    def validate_step_execution(self, step_name: str, error_context: ErrorContext, 
                              error_message: str, response_data: Optional[Dict[str, Any]] = None,
                              status_code: Optional[int] = None) -> ValidationResult:
        """
        Comprehensive validation of step execution with error handling.
        
        Args:
            step_name: Name of the workflow step
            error_context: Context information about the error
            error_message: Error message from the step
            response_data: Response data if available
            status_code: HTTP status code if available
            
        Returns:
            ValidationResult with comprehensive error analysis and suggestions
        """
        # Check for rate limiting (AC4.1)
        if self.rate_limit_handler.is_rate_limited(error_message, status_code):
            result = self.rate_limit_handler.handle_rate_limit(
                error_context.tool_name or step_name, error_context
            )
            self.validation_history.append(result)
            return result
        
        # Check for account access issues (AC4.2) - only for data collection tools
        if error_context.tool_name and any(tool in error_context.tool_name.lower() for tool in ["twitter", "scrapebadger"]):
            result = self.account_validator.validate_account_access(
                error_context.username, error_message, response_data
            )
            if not result.is_valid:
                self.validation_history.append(result)
                return result
        
        # Handle other API errors
        if any(indicator in error_message.lower() for indicator in ["api", "authentication", "unauthorized"]):
            result = ValidationResult(
                is_valid=False,
                error_type=ErrorType.API_ERROR,
                error_message=f"API error in {step_name}: {error_message}",
                severity=ErrorSeverity.HIGH,
                suggestions=[
                    "Check API credentials and permissions",
                    "Verify API endpoint availability",
                    "Consider using alternative data source",
                    "Retry after checking configuration"
                ],
                metadata={
                    "step_name": step_name,
                    "tool_name": error_context.tool_name,
                    "error_details": error_message
                }
            )
            self.validation_history.append(result)
            return result
        
        # Generic error handling
        result = ValidationResult(
            is_valid=False,
            error_type=ErrorType.UNKNOWN_ERROR,
            error_message=f"Unknown error in {step_name}: {error_message}",
            severity=ErrorSeverity.MEDIUM,
            suggestions=[
                "Check step configuration and inputs",
                "Review error logs for more details",
                "Consider retrying the operation",
                "Contact support if error persists"
            ],
            metadata={
                "step_name": step_name,
                "error_details": error_message,
                "context": error_context.__dict__
            }
        )
        self.validation_history.append(result)
        return result
    
    def validate_data_quality(self, collected_data: Dict[str, Any], 
                            username: str) -> ValidationResult:
        """
        Validate data quality for profile generation (AC4.3).
        
        Args:
            collected_data: Data collected from various sources
            username: Username being processed
            
        Returns:
            ValidationResult with data quality assessment
        """
        result = self.data_quality_validator.validate_data_sufficiency(collected_data, username)
        self.validation_history.append(result)
        return result
    
    def can_retry_tool(self, tool_name: str) -> bool:
        """Check if a tool can be retried based on rate limiting."""
        return self.rate_limit_handler.can_retry(tool_name)
    
    def reset_tool_failures(self, tool_name: str):
        """Reset failure tracking for a tool after successful execution."""
        self.rate_limit_handler.reset_failures(tool_name)
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of all validation results."""
        if not self.validation_history:
            return {"total_validations": 0, "summary": "No validations performed"}
        
        error_counts = {}
        severity_counts = {}
        
        for result in self.validation_history:
            if result.error_type:
                error_counts[result.error_type.value] = error_counts.get(result.error_type.value, 0) + 1
            severity_counts[result.severity.value] = severity_counts.get(result.severity.value, 0) + 1
        
        return {
            "total_validations": len(self.validation_history),
            "error_type_counts": error_counts,
            "severity_counts": severity_counts,
            "last_validation": self.validation_history[-1].__dict__ if self.validation_history else None
        }


def with_retry_and_validation(validator: WorkflowValidator, 
                            retry_config: Optional[RetryConfig] = None):
    """
    Decorator for workflow steps that adds retry logic and validation.
    
    Args:
        validator: WorkflowValidator instance
        retry_config: Optional retry configuration
        
    Returns:
        Decorator function
    """
    if retry_config is None:
        retry_config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            step_name = func.__name__
            username = kwargs.get('username', 'unknown')
            
            for attempt in range(1, retry_config.max_attempts + 1):
                try:
                    # Create error context
                    error_context = ErrorContext(
                        username=username,
                        step_name=step_name,
                        attempt_number=attempt
                    )
                    
                    # Execute the function
                    result = func(*args, **kwargs)
                    
                    # Reset failures on success
                    if hasattr(result, 'success') and result.success:
                        validator.reset_tool_failures(step_name)
                    
                    return result
                    
                except Exception as e:
                    error_message = str(e)
                    
                    # Create error context
                    error_context = ErrorContext(
                        username=username,
                        step_name=step_name,
                        attempt_number=attempt
                    )
                    
                    # Validate the error
                    validation_result = validator.validate_step_execution(
                        step_name, error_context, error_message
                    )
                    
                    # If it's a rate limit, wait and retry
                    if (validation_result.error_type == ErrorType.RATE_LIMIT and 
                        attempt < retry_config.max_attempts):
                        delay = validation_result.metadata.get('retry_delay', 1.0)
                        time.sleep(delay)
                        continue
                    
                    # If it's a critical error or max attempts reached, raise
                    if (validation_result.severity == ErrorSeverity.CRITICAL or 
                        attempt >= retry_config.max_attempts):
                        raise Exception(f"Step {step_name} failed: {validation_result.error_message}")
                    
                    # For other errors, wait briefly and retry
                    time.sleep(retry_config.calculate_delay(attempt - 1))
            
            # Should not reach here, but just in case
            raise Exception(f"Step {step_name} failed after {retry_config.max_attempts} attempts")
        
        return wrapper
    return decorator


# Factory functions for easy instantiation
def create_workflow_validator(retry_config: Optional[RetryConfig] = None) -> WorkflowValidator:
    """Create a WorkflowValidator with default configuration."""
    return WorkflowValidator(retry_config)


def create_retry_config(max_attempts: int = 3, base_delay: float = 1.0, 
                       max_delay: float = 60.0) -> RetryConfig:
    """Create a RetryConfig with custom parameters."""
    return RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay
    )

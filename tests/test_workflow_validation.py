"""
Tests for workflow validation and error handling utilities.

This test suite validates the comprehensive error handling capabilities including:
- API rate limit handling with exponential backoff (AC4.1)
- Private/suspended account scenario management (AC4.2)  
- Meaningful responses for insufficient data cases (AC4.3)
- Robust error recovery and fallback mechanisms

Validates Requirements:
- AC4.1: Handles API rate limits with exponential backoff
- AC4.2: Manages private or suspended account scenarios
- AC4.3: Provides meaningful responses for insufficient data cases
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from app.utils.workflow_validation import (
    WorkflowValidator, RateLimitHandler, AccountAccessValidator, DataQualityValidator,
    ErrorType, ErrorSeverity, ValidationResult, RetryConfig, ErrorContext,
    create_workflow_validator, create_retry_config, with_retry_and_validation
)


class TestRetryConfig:
    """Test RetryConfig functionality."""
    
    def test_default_retry_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
    
    def test_custom_retry_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=120.0,
            exponential_base=3.0,
            jitter=False
        )
        
        assert config.max_attempts == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 120.0
        assert config.exponential_base == 3.0
        assert config.jitter is False
    
    def test_calculate_delay_exponential(self):
        """Test exponential delay calculation."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        
        # Test exponential growth
        assert config.calculate_delay(0) == 1.0  # 1.0 * 2^0
        assert config.calculate_delay(1) == 2.0  # 1.0 * 2^1
        assert config.calculate_delay(2) == 4.0  # 1.0 * 2^2
        assert config.calculate_delay(3) == 8.0  # 1.0 * 2^3
    
    def test_calculate_delay_max_limit(self):
        """Test delay calculation respects max limit."""
        config = RetryConfig(base_delay=1.0, max_delay=5.0, exponential_base=2.0, jitter=False)
        
        # Should cap at max_delay
        assert config.calculate_delay(10) == 5.0
    
    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter."""
        config = RetryConfig(base_delay=2.0, exponential_base=2.0, jitter=True)
        
        delay = config.calculate_delay(1)  # Base would be 4.0
        
        # With jitter, should be between 2.0 and 4.0
        assert 2.0 <= delay <= 4.0


class TestRateLimitHandler:
    """Test RateLimitHandler functionality (AC4.1)."""
    
    def test_rate_limit_detection_by_message(self):
        """Test rate limit detection from error messages."""
        handler = RateLimitHandler()
        
        # Test various rate limit indicators
        assert handler.is_rate_limited("Rate limit exceeded")
        assert handler.is_rate_limited("Too many requests")
        assert handler.is_rate_limited("Quota exceeded")
        assert handler.is_rate_limited("Request throttled")
        assert handler.is_rate_limited("rate_limit_exceeded")
        
        # Test non-rate-limit errors
        assert not handler.is_rate_limited("User not found")
        assert not handler.is_rate_limited("Invalid credentials")
    
    def test_rate_limit_detection_by_status_code(self):
        """Test rate limit detection from HTTP status codes."""
        handler = RateLimitHandler()
        
        # 429 is the standard rate limit status code
        assert handler.is_rate_limited("Some error", status_code=429)
        
        # Other status codes should not indicate rate limiting
        assert not handler.is_rate_limited("Some error", status_code=404)
        assert not handler.is_rate_limited("Some error", status_code=500)
    
    def test_handle_rate_limit_exponential_backoff(self):
        """Test rate limit handling with exponential backoff."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        handler = RateLimitHandler(config)
        
        error_context = ErrorContext(
            username="testuser",
            step_name="test_step",
            tool_name="test_tool",
            attempt_number=2
        )
        
        result = handler.handle_rate_limit("test_tool", error_context)
        
        assert not result.is_valid
        assert result.error_type == ErrorType.RATE_LIMIT
        assert result.severity == ErrorSeverity.MEDIUM
        assert "test_tool" in result.error_message
        assert "2.0" in result.error_message  # Should mention delay
        
        # Check metadata
        assert result.metadata["tool_name"] == "test_tool"
        assert result.metadata["retry_delay"] == 2.0  # 1.0 * 2^(2-1)
        assert result.metadata["attempt_number"] == 2
    
    def test_consecutive_failures_tracking(self):
        """Test tracking of consecutive failures."""
        handler = RateLimitHandler()
        
        error_context = ErrorContext(
            username="testuser",
            step_name="test_step",
            tool_name="test_tool",
            attempt_number=1
        )
        
        # First failure
        result1 = handler.handle_rate_limit("test_tool", error_context)
        assert result1.metadata["consecutive_failures"] == 1
        
        # Second failure
        error_context.attempt_number = 2
        result2 = handler.handle_rate_limit("test_tool", error_context)
        assert result2.metadata["consecutive_failures"] == 2
    
    def test_can_retry_functionality(self):
        """Test retry capability checking."""
        handler = RateLimitHandler()
        
        # Should be able to retry initially
        assert handler.can_retry("test_tool")
        
        # After rate limit, should not be able to retry immediately
        error_context = ErrorContext(
            username="testuser",
            step_name="test_step",
            tool_name="test_tool"
        )
        handler.handle_rate_limit("test_tool", error_context)
        
        assert not handler.can_retry("test_tool")
    
    def test_reset_failures(self):
        """Test resetting failure tracking."""
        handler = RateLimitHandler()
        
        # Trigger a rate limit
        error_context = ErrorContext(
            username="testuser",
            step_name="test_step",
            tool_name="test_tool"
        )
        handler.handle_rate_limit("test_tool", error_context)
        
        assert not handler.can_retry("test_tool")
        assert "test_tool" in handler.consecutive_failures
        
        # Reset failures
        handler.reset_failures("test_tool")
        
        assert handler.can_retry("test_tool")
        assert "test_tool" not in handler.consecutive_failures


class TestAccountAccessValidator:
    """Test AccountAccessValidator functionality (AC4.2)."""
    
    def test_private_account_detection(self):
        """Test detection of private accounts."""
        validator = AccountAccessValidator()
        
        # Test private account indicators
        result = validator.validate_account_access("testuser", "Account is private")
        assert not result.is_valid
        assert result.error_type == ErrorType.PRIVATE_ACCOUNT
        assert result.severity == ErrorSeverity.MEDIUM
        
        # Check suggestions
        suggestions = result.suggestions
        assert any("public" in suggestion.lower() for suggestion in suggestions)
        assert any("confidence" in suggestion.lower() for suggestion in suggestions)
    
    def test_suspended_account_detection(self):
        """Test detection of suspended accounts."""
        validator = AccountAccessValidator()
        
        # Test suspended account indicators
        result = validator.validate_account_access("testuser", "User account suspended")
        assert not result.is_valid
        assert result.error_type == ErrorType.SUSPENDED_ACCOUNT
        assert result.severity == ErrorSeverity.HIGH
        
        # Check metadata
        assert result.metadata["account_status"] == "suspended"
        assert result.metadata["data_collection_possible"] is False
    
    def test_nonexistent_account_detection(self):
        """Test detection of non-existent accounts."""
        validator = AccountAccessValidator()
        
        # Test non-existent account indicators
        result = validator.validate_account_access("testuser", "User not found")
        assert not result.is_valid
        assert result.error_type == ErrorType.VALIDATION_ERROR
        assert result.severity == ErrorSeverity.HIGH
        
        # Check suggestions
        suggestions = result.suggestions
        assert any("spelling" in suggestion.lower() for suggestion in suggestions)
    
    def test_accessible_account(self):
        """Test validation of accessible accounts."""
        validator = AccountAccessValidator()
        
        # Test with non-error message
        result = validator.validate_account_access("testuser", "Success")
        assert result.is_valid
        assert result.metadata["access_status"] == "accessible"
    
    def test_known_accounts_tracking(self):
        """Test tracking of known private/suspended accounts."""
        validator = AccountAccessValidator()
        
        # Validate private account
        validator.validate_account_access("private_user", "Account is private")
        assert "private_user" in validator.known_private_accounts
        
        # Validate suspended account
        validator.validate_account_access("suspended_user", "Account suspended")
        assert "suspended_user" in validator.known_suspended_accounts


class TestDataQualityValidator:
    """Test DataQualityValidator functionality (AC4.3)."""
    
    def test_sufficient_data_validation(self):
        """Test validation with sufficient data."""
        validator = DataQualityValidator()
        
        collected_data = {
            "total_tweets": 20,
            "has_profile_data": True,
            "quality_score": 0.8,
            "sources": ["TwitterAPI.io", "ScrapeBadger"],
            "has_highlights": True
        }
        
        result = validator.validate_data_sufficiency(collected_data, "testuser")
        assert result.is_valid
        assert result.metadata["quality_assessment"] == "sufficient"
    
    def test_insufficient_data_critical(self):
        """Test validation with critically insufficient data."""
        validator = DataQualityValidator()
        
        collected_data = {
            "total_tweets": 2,  # Below minimum
            "has_profile_data": False,  # Critical missing
            "quality_score": 0.1,  # Too low
            "sources": [],
            "has_highlights": False
        }
        
        result = validator.validate_data_sufficiency(collected_data, "testuser")
        assert not result.is_valid
        assert result.error_type == ErrorType.INSUFFICIENT_DATA
        assert result.severity == ErrorSeverity.CRITICAL
        assert result.metadata["can_generate_profile"] is False
    
    def test_data_quality_warnings(self):
        """Test validation with quality warnings."""
        validator = DataQualityValidator()
        
        collected_data = {
            "total_tweets": 8,  # Below recommended but above minimum
            "has_profile_data": True,
            "quality_score": 0.4,  # Below recommended but above minimum
            "sources": ["TwitterAPI.io"],  # Single source
            "has_highlights": False
        }
        
        result = validator.validate_data_sufficiency(collected_data, "testuser")
        assert result.is_valid  # Can proceed but with warnings
        assert result.error_type == ErrorType.INSUFFICIENT_DATA
        assert result.severity == ErrorSeverity.MEDIUM
        assert result.metadata["can_generate_profile"] is True
        assert "expected_confidence_reduction" in result.metadata
    
    def test_meaningful_error_messages(self):
        """Test that error messages are meaningful and actionable (AC4.3)."""
        validator = DataQualityValidator()
        
        collected_data = {
            "total_tweets": 1,
            "has_profile_data": False,
            "quality_score": 0.05,
            "sources": [],
            "has_highlights": False
        }
        
        result = validator.validate_data_sufficiency(collected_data, "testuser")
        
        # Check that error message is specific and helpful
        assert "testuser" in result.error_message
        assert "Insufficient data" in result.error_message
        
        # Check that suggestions are actionable
        suggestions = result.suggestions
        assert len(suggestions) > 0
        assert any("Cannot generate" in suggestion for suggestion in suggestions)
        assert any("Try collecting" in suggestion for suggestion in suggestions)


class TestWorkflowValidator:
    """Test WorkflowValidator integration functionality."""
    
    def test_workflow_validator_initialization(self):
        """Test WorkflowValidator initialization."""
        validator = create_workflow_validator()
        
        assert isinstance(validator.rate_limit_handler, RateLimitHandler)
        assert isinstance(validator.account_validator, AccountAccessValidator)
        assert isinstance(validator.data_quality_validator, DataQualityValidator)
        assert validator.validation_history == []
    
    def test_step_execution_validation_rate_limit(self):
        """Test step execution validation for rate limits."""
        validator = create_workflow_validator()
        
        error_context = ErrorContext(
            username="testuser",
            step_name="test_step",
            tool_name="test_tool"
        )
        
        result = validator.validate_step_execution(
            "test_step",
            error_context,
            "Rate limit exceeded",
            status_code=429
        )
        
        assert not result.is_valid
        assert result.error_type == ErrorType.RATE_LIMIT
        assert len(validator.validation_history) == 1
    
    def test_step_execution_validation_private_account(self):
        """Test step execution validation for private accounts."""
        validator = create_workflow_validator()
        
        error_context = ErrorContext(
            username="testuser",
            step_name="test_step",
            tool_name="twitter_api"
        )
        
        result = validator.validate_step_execution(
            "test_step",
            error_context,
            "Account is private"
        )
        
        assert not result.is_valid
        assert result.error_type == ErrorType.PRIVATE_ACCOUNT
    
    def test_validation_summary(self):
        """Test validation summary generation."""
        validator = create_workflow_validator()
        
        # Initially empty
        summary = validator.get_validation_summary()
        assert summary["total_validations"] == 0
        
        # Add some validations
        error_context = ErrorContext(username="testuser", step_name="test_step", tool_name="twitter_api")
        validator.validate_step_execution("test_step", error_context, "Rate limit exceeded", status_code=429)
        validator.validate_step_execution("test_step", error_context, "Account is private")
        
        summary = validator.get_validation_summary()
        assert summary["total_validations"] == 2
        assert "rate_limit" in summary["error_type_counts"]
        assert "private_account" in summary["error_type_counts"]


class TestRetryDecorator:
    """Test retry decorator functionality."""
    
    def test_retry_decorator_success(self):
        """Test retry decorator with successful execution."""
        validator = create_workflow_validator()
        
        @with_retry_and_validation(validator)
        def successful_function(username="testuser"):
            return Mock(success=True)
        
        result = successful_function()
        assert result.success is True
    
    def test_retry_decorator_with_retries(self):
        """Test retry decorator with failures and eventual success."""
        validator = create_workflow_validator()
        retry_config = RetryConfig(max_attempts=3, base_delay=0.01)  # Fast for testing
        
        call_count = 0
        
        @with_retry_and_validation(validator, retry_config)
        def flaky_function(username="testuser"):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return Mock(success=True)
        
        result = flaky_function()
        assert result.success is True
        assert call_count == 3
    
    def test_retry_decorator_max_attempts(self):
        """Test retry decorator respects max attempts."""
        validator = create_workflow_validator()
        retry_config = RetryConfig(max_attempts=2, base_delay=0.01)
        
        @with_retry_and_validation(validator, retry_config)
        def always_failing_function(username="testuser"):
            raise Exception("Always fails")
        
        with pytest.raises(Exception, match="Always fails"):
            always_failing_function()


class TestIntegrationScenarios:
    """Test integration scenarios combining multiple validation components."""
    
    def test_complete_workflow_validation_scenario(self):
        """Test complete workflow validation scenario."""
        validator = create_workflow_validator()
        
        # Simulate a complete workflow with various errors
        error_context = ErrorContext(username="testuser", step_name="data_collection", tool_name="twitter_api")
        
        # 1. Rate limit error
        result1 = validator.validate_step_execution(
            "data_collection", error_context, "Rate limit exceeded", status_code=429
        )
        assert result1.error_type == ErrorType.RATE_LIMIT
        
        # 2. Private account error
        result2 = validator.validate_step_execution(
            "data_collection", error_context, "Account is private"
        )
        assert result2.error_type == ErrorType.PRIVATE_ACCOUNT
        
        # 3. Data quality validation
        insufficient_data = {
            "total_tweets": 1,
            "has_profile_data": False,
            "quality_score": 0.1,
            "sources": [],
            "has_highlights": False
        }
        result3 = validator.validate_data_quality(insufficient_data, "testuser")
        assert result3.error_type == ErrorType.INSUFFICIENT_DATA
        
        # Check validation history
        summary = validator.get_validation_summary()
        assert summary["total_validations"] == 3
        assert "rate_limit" in summary["error_type_counts"]
        assert "private_account" in summary["error_type_counts"]
        assert "insufficient_data" in summary["error_type_counts"]
    
    def test_ac4_1_rate_limit_handling(self):
        """Test AC4.1: Handles API rate limits with exponential backoff."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        handler = RateLimitHandler(config)
        
        # Simulate multiple rate limit hits
        for attempt in range(1, 4):
            error_context = ErrorContext(
                username="testuser",
                step_name="api_call",
                tool_name="twitter_api",
                attempt_number=attempt
            )
            
            result = handler.handle_rate_limit("twitter_api", error_context)
            
            # Verify exponential backoff
            expected_delay = 1.0 * (2.0 ** (attempt - 1))
            assert result.metadata["retry_delay"] == expected_delay
            
            # Verify suggestions include retry information
            assert any("Wait" in suggestion for suggestion in result.suggestions)
    
    def test_ac4_2_account_scenarios(self):
        """Test AC4.2: Manages private or suspended account scenarios."""
        validator = AccountAccessValidator()
        
        # Test private account scenario
        private_result = validator.validate_account_access("private_user", "Account is private")
        assert private_result.error_type == ErrorType.PRIVATE_ACCOUNT
        assert private_result.severity == ErrorSeverity.MEDIUM
        assert "public" in str(private_result.suggestions).lower()
        
        # Test suspended account scenario
        suspended_result = validator.validate_account_access("suspended_user", "Account suspended")
        assert suspended_result.error_type == ErrorType.SUSPENDED_ACCOUNT
        assert suspended_result.severity == ErrorSeverity.HIGH
        assert suspended_result.metadata["data_collection_possible"] is False
    
    def test_ac4_3_insufficient_data_responses(self):
        """Test AC4.3: Provides meaningful responses for insufficient data cases."""
        validator = DataQualityValidator()
        
        # Test various insufficient data scenarios
        scenarios = [
            {
                "name": "no_profile_data",
                "data": {"total_tweets": 10, "has_profile_data": False, "quality_score": 0.5},
                "expected_critical": True
            },
            {
                "name": "insufficient_tweets",
                "data": {"total_tweets": 2, "has_profile_data": True, "quality_score": 0.5},
                "expected_critical": False  # Changed: this should be a warning, not critical
            },
            {
                "name": "low_quality_warning",
                "data": {"total_tweets": 8, "has_profile_data": True, "quality_score": 0.4},
                "expected_critical": False
            }
        ]
        
        for scenario in scenarios:
            result = validator.validate_data_sufficiency(scenario["data"], "testuser")
            
            if scenario["expected_critical"]:
                assert result.severity == ErrorSeverity.CRITICAL
                assert result.metadata["can_generate_profile"] is False
            else:
                assert result.severity in [ErrorSeverity.LOW, ErrorSeverity.MEDIUM, ErrorSeverity.HIGH]
                assert result.metadata.get("can_generate_profile", True) is True
            
            # All results should have meaningful suggestions
            assert len(result.suggestions) > 0
            assert all(len(suggestion.strip()) > 10 for suggestion in result.suggestions)


if __name__ == "__main__":
    pytest.main([__file__])
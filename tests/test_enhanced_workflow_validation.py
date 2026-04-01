"""
Comprehensive tests for enhanced workflow validation and error handling utilities.

This test suite validates the implementation of task 2.2:
- AC4.1: Handles API rate limits with exponential backoff
- AC4.2: Manages private or suspended account scenarios  
- AC4.3: Provides meaningful responses for insufficient data cases

Tests cover:
- Rate limit detection and exponential backoff
- Private/suspended account handling
- Data quality validation
- Comprehensive error scenarios
- Mistral AI integration
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from app.agents.advanced_skill_generator_workflow import (
    AdvancedSkillGeneratorWorkflow,
    create_advanced_skill_generator_workflow,
    validate_workflow_configuration
)
from app.utils.workflow_validation import (
    WorkflowValidator, ErrorContext, ValidationResult, ErrorType, ErrorSeverity,
    RetryConfig, RateLimitHandler, AccountAccessValidator, DataQualityValidator,
    create_workflow_validator, with_retry_and_validation
)
from app.models.collected_data import CollectedData, TwitterAPIData, ScrapeBadgerData


class TestRateLimitHandling:
    """Test rate limit detection and exponential backoff (AC4.1)."""
    
    def test_rate_limit_detection(self):
        """Test detection of various rate limit error patterns."""
        handler = RateLimitHandler()
        
        # Test various rate limit error messages
        rate_limit_errors = [
            "Rate limit exceeded",
            "Too many requests",
            "Quota exceeded", 
            "Request throttled",
            "rate_limit_exceeded",
            "HTTP 429: Too Many Requests"
        ]
        
        for error_msg in rate_limit_errors:
            assert handler.is_rate_limited(error_msg), f"Should detect rate limit in: {error_msg}"
        
        # Test status code detection
        assert handler.is_rate_limited("Some error", status_code=429)
        
        # Test non-rate-limit errors
        normal_errors = [
            "Network connection failed",
            "Invalid API key",
            "User not found",
            "Internal server error"
        ]
        
        for error_msg in normal_errors:
            assert not handler.is_rate_limited(error_msg), f"Should not detect rate limit in: {error_msg}"
    
    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=False  # Disable jitter for predictable testing
        )
        
        expected_delays = [1.0, 2.0, 4.0, 8.0, 16.0]
        
        for attempt, expected in enumerate(expected_delays):
            delay = config.calculate_delay(attempt)
            assert delay == expected, f"Attempt {attempt}: expected {expected}, got {delay}"
        
        # Test max delay cap
        delay = config.calculate_delay(10)  # Very high attempt
        assert delay == config.max_delay
    
    def test_rate_limit_handler_workflow(self):
        """Test complete rate limit handling workflow."""
        handler = RateLimitHandler(RetryConfig(base_delay=0.1, jitter=False))  # Fast for testing
        
        error_context = ErrorContext(
            username="testuser",
            step_name="api_call",
            tool_name="twitter_api",
            attempt_number=1
        )
        
        # Handle rate limit
        result = handler.handle_rate_limit("twitter_api", error_context)
        
        assert not result.is_valid
        assert result.error_type == ErrorType.RATE_LIMIT
        assert result.severity == ErrorSeverity.MEDIUM
        assert "retry_delay" in result.metadata
        assert result.metadata["attempt_number"] == 1
        
        # Check that tool is marked as rate limited
        assert not handler.can_retry("twitter_api")
        
        # Wait for rate limit window to pass
        time.sleep(0.2)  # Wait longer than base_delay
        
        # Should be able to retry now
        assert handler.can_retry("twitter_api")
    
    def test_consecutive_failures_tracking(self):
        """Test tracking of consecutive failures for escalating delays."""
        handler = RateLimitHandler(RetryConfig(base_delay=0.1, jitter=False))
        
        error_context = ErrorContext(
            username="testuser",
            step_name="api_call",
            tool_name="twitter_api"
        )
        
        # First failure
        error_context.attempt_number = 1
        result1 = handler.handle_rate_limit("twitter_api", error_context)
        
        # Second failure
        error_context.attempt_number = 2
        result2 = handler.handle_rate_limit("twitter_api", error_context)
        
        # Delays should increase
        delay1 = result1.metadata["retry_delay"]
        delay2 = result2.metadata["retry_delay"]
        assert delay2 > delay1, "Second failure should have longer delay"
        
        # Consecutive failures should be tracked
        assert result2.metadata["consecutive_failures"] == 2


class TestAccountAccessValidation:
    """Test private and suspended account handling (AC4.2)."""
    
    def test_private_account_detection(self):
        """Test detection of private account scenarios."""
        validator = AccountAccessValidator()
        
        private_errors = [
            "User has protected tweets",
            "Not authorized to access this resource",
            "Access denied - private account",
            "Forbidden: User profile is private",
            "Unauthorized access to protected user"
        ]
        
        for error_msg in private_errors:
            result = validator.validate_account_access("testuser", error_msg)
            assert not result.is_valid
            assert result.error_type == ErrorType.PRIVATE_ACCOUNT
            assert result.severity == ErrorSeverity.MEDIUM
            assert "private" in result.error_message.lower()
            assert len(result.suggestions) > 0
    
    def test_suspended_account_detection(self):
        """Test detection of suspended account scenarios."""
        validator = AccountAccessValidator()
        
        suspended_errors = [
            "User has been suspended",
            "Account suspended for violating terms",
            "User account is temporarily restricted",
            "Account deactivated by user",
            "User banned from platform"
        ]
        
        for error_msg in suspended_errors:
            result = validator.validate_account_access("testuser", error_msg)
            assert not result.is_valid
            assert result.error_type == ErrorType.SUSPENDED_ACCOUNT
            assert result.severity == ErrorSeverity.HIGH
            assert "suspended" in result.error_message.lower() or "deactivated" in result.error_message.lower()
            assert len(result.suggestions) > 0
    
    def test_nonexistent_account_detection(self):
        """Test detection of non-existent account scenarios."""
        validator = AccountAccessValidator()
        
        nonexistent_errors = [
            "User not found",
            "No user exists with that username",
            "404: User does not exist",
            "Invalid user identifier"
        ]
        
        for error_msg in nonexistent_errors:
            result = validator.validate_account_access("testuser", error_msg)
            assert not result.is_valid
            assert result.error_type == ErrorType.VALIDATION_ERROR
            assert result.severity == ErrorSeverity.HIGH
            assert "not exist" in result.error_message.lower() or "not found" in result.error_message.lower()
    
    def test_accessible_account(self):
        """Test validation of accessible accounts."""
        validator = AccountAccessValidator()
        
        # Normal errors that don't indicate access issues
        normal_errors = [
            "Network timeout",
            "Internal server error",
            "Invalid API key format"
        ]
        
        for error_msg in normal_errors:
            result = validator.validate_account_access("testuser", error_msg)
            assert result.is_valid, f"Should consider account accessible for error: {error_msg}"


class TestDataQualityValidation:
    """Test data quality validation and insufficient data handling (AC4.3)."""
    
    def test_sufficient_data_validation(self):
        """Test validation of sufficient data for profile generation."""
        validator = DataQualityValidator()
        
        # High quality data
        good_data = {
            "total_tweets": 25,
            "has_profile_data": True,
            "quality_score": 0.8,
            "sources": ["TwitterAPI.io", "ScrapeBadger"],
            "has_highlights": True
        }
        
        result = validator.validate_data_sufficiency(good_data, "testuser")
        assert result.is_valid
        assert "sufficient" in result.metadata.get("quality_assessment", "")
    
    def test_insufficient_data_critical(self):
        """Test handling of critically insufficient data."""
        validator = DataQualityValidator()
        
        # Critical issues - no profile data
        critical_data = {
            "total_tweets": 0,
            "has_profile_data": False,
            "quality_score": 0.1,
            "sources": [],
            "has_highlights": False
        }
        
        result = validator.validate_data_sufficiency(critical_data, "testuser")
        assert not result.is_valid
        assert result.error_type == ErrorType.INSUFFICIENT_DATA
        assert result.severity == ErrorSeverity.CRITICAL
        assert not result.metadata["can_generate_profile"]
        assert len(result.suggestions) > 0
    
    def test_data_quality_warnings(self):
        """Test handling of data quality warnings."""
        validator = DataQualityValidator()
        
        # Warning level issues - can proceed but with caveats
        warning_data = {
            "total_tweets": 8,  # Below recommended but above minimum
            "has_profile_data": True,
            "quality_score": 0.4,  # Below recommended
            "sources": ["TwitterAPI.io"],  # Single source
            "has_highlights": False
        }
        
        result = validator.validate_data_sufficiency(warning_data, "testuser")
        assert result.is_valid  # Can proceed
        assert result.error_type == ErrorType.INSUFFICIENT_DATA
        assert result.severity in [ErrorSeverity.MEDIUM, ErrorSeverity.LOW]
        assert result.metadata["can_generate_profile"]
        assert "expected_confidence_reduction" in result.metadata
    
    def test_quality_thresholds_customization(self):
        """Test customization of quality thresholds."""
        validator = DataQualityValidator()
        
        # Modify thresholds
        validator.quality_thresholds["min_tweets"] = 20
        validator.quality_thresholds["min_quality_score"] = 0.5
        
        # Data that would pass default thresholds but fail custom ones
        borderline_data = {
            "total_tweets": 15,
            "has_profile_data": True,
            "quality_score": 0.4,
            "sources": ["TwitterAPI.io"],
            "has_highlights": True
        }
        
        result = validator.validate_data_sufficiency(borderline_data, "testuser")
        # Should have warnings due to stricter thresholds
        assert result.severity >= ErrorSeverity.MEDIUM


class TestWorkflowValidatorIntegration:
    """Test integrated workflow validation functionality."""
    
    def test_workflow_validator_creation(self):
        """Test creation of workflow validator with configuration."""
        retry_config = RetryConfig(max_attempts=5, base_delay=2.0)
        validator = create_workflow_validator(retry_config)
        
        assert isinstance(validator, WorkflowValidator)
        assert validator.rate_limit_handler.retry_config.max_attempts == 5
        assert validator.rate_limit_handler.retry_config.base_delay == 2.0
    
    def test_comprehensive_step_validation(self):
        """Test comprehensive step execution validation."""
        validator = create_workflow_validator()
        
        error_context = ErrorContext(
            username="testuser",
            step_name="data_collection",
            tool_name="twitter_api"
        )
        
        # Test rate limit error
        rate_limit_result = validator.validate_step_execution(
            "data_collection", error_context, "Rate limit exceeded", status_code=429
        )
        assert rate_limit_result.error_type == ErrorType.RATE_LIMIT
        
        # Test private account error
        private_result = validator.validate_step_execution(
            "data_collection", error_context, "User has protected tweets", status_code=401
        )
        assert private_result.error_type == ErrorType.PRIVATE_ACCOUNT
        
        # Test API error
        api_result = validator.validate_step_execution(
            "data_collection", error_context, "Invalid API key", status_code=403
        )
        assert api_result.error_type == ErrorType.API_ERROR
    
    def test_validation_history_tracking(self):
        """Test tracking of validation history."""
        validator = create_workflow_validator()
        
        error_context = ErrorContext(
            username="testuser",
            step_name="test_step"
        )
        
        # Perform multiple validations
        validator.validate_step_execution("test_step", error_context, "Error 1")
        validator.validate_step_execution("test_step", error_context, "Error 2")
        
        summary = validator.get_validation_summary()
        assert summary["total_validations"] == 2
        assert "error_type_counts" in summary
        assert "last_validation" in summary
    
    def test_retry_decorator_functionality(self):
        """Test retry decorator with validation."""
        validator = create_workflow_validator()
        retry_config = RetryConfig(max_attempts=3, base_delay=0.01)  # Fast for testing
        
        call_count = 0
        
        @with_retry_and_validation(validator, retry_config)
        def failing_function(username="testuser"):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        # Should succeed after retries
        result = failing_function()
        assert result == "success"
        assert call_count == 3


class TestAdvancedSkillGeneratorWorkflow:
    """Test the enhanced Advanced Skill Generator Workflow."""
    
    @pytest.fixture
    def workflow(self):
        """Create a workflow instance for testing."""
        with patch('app.agents.advanced_skill_generator_workflow.TwitterAPIIOToolkit'), \
             patch('app.agents.advanced_skill_generator_workflow.ScrapeBadgerToolkit'), \
             patch('app.agents.advanced_skill_generator_workflow.get_shared_skill_knowledge'):
            return create_advanced_skill_generator_workflow()
    
    def test_workflow_creation_with_mistral(self, workflow):
        """Test workflow creation with Mistral AI configuration."""
        assert workflow.model_id == "mistral-large-latest"
        assert isinstance(workflow.validator, WorkflowValidator)
        assert workflow.twitter_api_agent.model.__class__.__name__ == "MistralChat"
    
    def test_enhanced_error_handling(self, workflow):
        """Test enhanced error handling in workflow methods."""
        # Test API error handling
        result = workflow.handle_api_error(
            "twitter_api", "testuser", "Rate limit exceeded", status_code=429
        )
        assert result.error_type == ErrorType.RATE_LIMIT
        assert result.severity == ErrorSeverity.MEDIUM
        
        # Test private account handling
        result = workflow.handle_api_error(
            "twitter_api", "testuser", "User has protected tweets", status_code=401
        )
        assert result.error_type == ErrorType.PRIVATE_ACCOUNT
    
    def test_tool_retry_checking(self, workflow):
        """Test enhanced tool retry checking."""
        # Initially should be able to retry
        assert workflow.can_retry_tool("twitter_api")
        
        # Simulate rate limit
        error_context = ErrorContext(
            username="testuser",
            step_name="api_call",
            tool_name="twitter_api"
        )
        workflow.validator.rate_limit_handler.handle_rate_limit("twitter_api", error_context)
        
        # Should not be able to retry immediately
        assert not workflow.can_retry_tool("twitter_api")
    
    def test_enhanced_validation_summary(self, workflow):
        """Test enhanced validation summary with comprehensive metrics."""
        summary = workflow.get_enhanced_validation_summary()
        
        assert "workflow_metrics" in summary
        assert "tool_status" in summary
        assert "recent_errors" in summary
        assert "enhanced_features" in summary
        
        # Check enhanced features
        features = summary["enhanced_features"]
        assert features["exponential_backoff"]
        assert features["private_account_handling"]
        assert features["suspended_account_handling"]
        assert features["insufficient_data_handling"]
        assert features["comprehensive_validation"]
        assert features["mistral_ai_integration"]
    
    def test_profile_generation_error_scenarios(self, workflow):
        """Test profile generation with various error scenarios."""
        # Test invalid username
        with pytest.raises(ValueError, match="Invalid username format"):
            workflow.generate_skill_profile("invalid@username!")
        
        # Test empty username
        with pytest.raises(ValueError, match="Username cannot be empty"):
            workflow.generate_skill_profile("")
    
    @patch('app.agents.advanced_skill_generator_workflow.MistralChat')
    def test_mistral_ai_integration(self, mock_mistral):
        """Test Mistral AI integration in workflow."""
        mock_mistral.return_value = Mock()
        
        with patch('app.agents.advanced_skill_generator_workflow.TwitterAPIIOToolkit'), \
             patch('app.agents.advanced_skill_generator_workflow.ScrapeBadgerToolkit'), \
             patch('app.agents.advanced_skill_generator_workflow.get_shared_skill_knowledge'):
            
            workflow = create_advanced_skill_generator_workflow("mistral-medium")
            
            # Verify Mistral model is used
            assert workflow.model_id == "mistral-medium"
            
            # Verify all agents use Mistral
            mock_mistral.assert_called()
            call_args = [call[1] for call in mock_mistral.call_args_list]
            assert all(args.get('id') == 'mistral-medium' for args in call_args)


class TestWorkflowConfigurationValidation:
    """Test workflow configuration validation utilities."""
    
    @patch.dict('os.environ', {
        'MISTRAL_API_KEY': 'test_key',
        'TWITTER_API_IO_KEYS': 'test_key1,test_key2',
        'SCRAPEBADGER_API_KEYS': 'test_key3',
        'LANGWATCH_API_KEY': 'test_key4'
    })
    def test_complete_configuration(self):
        """Test validation with complete configuration."""
        result = validate_workflow_configuration()
        
        assert result["mistral_ai_configured"]
        assert result["twitter_api_configured"]
        assert result["scrapebadger_configured"]
        assert result["langwatch_configured"]
        assert result["configuration_score"] == 1.0
        assert result["ready_for_production"]
    
    @patch.dict('os.environ', {
        'MISTRAL_API_KEY': 'test_key',
        'TWITTER_API_IO_KEYS': 'test_key1'
        # Missing other keys
    }, clear=True)
    def test_partial_configuration(self):
        """Test validation with partial configuration."""
        result = validate_workflow_configuration()
        
        assert result["mistral_ai_configured"]
        assert result["twitter_api_configured"]
        assert not result["scrapebadger_configured"]
        assert not result["langwatch_configured"]
        assert 0.5 <= result["configuration_score"] < 1.0
    
    @patch.dict('os.environ', {}, clear=True)
    def test_missing_configuration(self):
        """Test validation with missing configuration."""
        result = validate_workflow_configuration()
        
        assert not result["mistral_ai_configured"]
        assert not result["twitter_api_configured"]
        assert not result["scrapebadger_configured"]
        assert not result["langwatch_configured"]
        assert result["configuration_score"] < 0.75
        assert not result["ready_for_production"]


class TestRealAPIIntegration:
    """Integration tests with real API calls (when keys are available)."""
    
    @pytest.mark.integration
    def test_real_rate_limit_handling(self):
        """Test rate limit handling with real API calls."""
        # This test would only run when real API keys are available
        # and would test actual rate limiting scenarios
        pytest.skip("Integration test - requires real API keys and rate limiting")
    
    @pytest.mark.integration  
    def test_real_private_account_handling(self):
        """Test private account handling with real API calls."""
        # This test would test against known private accounts
        pytest.skip("Integration test - requires real API keys and private test accounts")
    
    @pytest.mark.integration
    def test_real_workflow_execution(self):
        """Test complete workflow execution with real APIs."""
        # This test would run the complete workflow end-to-end
        pytest.skip("Integration test - requires real API keys and network access")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])

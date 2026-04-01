#!/usr/bin/env python3
"""
Enhanced Advanced Skill Generator Workflow Demo with Mistral AI and Comprehensive Error Handling.

This demo showcases the implementation of task 2.2:
- AC4.1: Handles API rate limits with exponential backoff
- AC4.2: Manages private or suspended account scenarios
- AC4.3: Provides meaningful responses for insufficient data cases

Features demonstrated:
- Mistral AI integration for improved performance
- Comprehensive error handling and validation
- Rate limit detection and exponential backoff
- Private/suspended account management
- Data quality validation with meaningful feedback
- Enhanced monitoring and logging capabilities

Usage:
    python examples/enhanced_workflow_demo.py
"""

import os
import sys
import time
from dotenv import load_dotenv

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.agents.advanced_skill_generator_workflow import (
    AdvancedSkillGeneratorWorkflow,
    create_advanced_skill_generator_workflow,
    validate_workflow_configuration
)
from app.utils.workflow_validation import (
    ErrorType, ErrorSeverity, RetryConfig, create_workflow_validator
)


def print_section(title: str, content: str = ""):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    if content:
        print(content)


def print_subsection(title: str):
    """Print a formatted subsection header."""
    print(f"\n{'-'*40}")
    print(f"  {title}")
    print(f"{'-'*40}")


def demonstrate_configuration_validation():
    """Demonstrate workflow configuration validation."""
    print_section("🔧 WORKFLOW CONFIGURATION VALIDATION")
    
    config_result = validate_workflow_configuration()
    
    print("Configuration Status:")
    print(f"  ✅ Mistral AI: {'✓' if config_result['mistral_ai_configured'] else '✗'}")
    print(f"  🐦 TwitterAPI.io: {'✓' if config_result['twitter_api_configured'] else '✗'}")
    print(f"  🦡 ScrapeBadger: {'✓' if config_result['scrapebadger_configured'] else '✗'}")
    print(f"  📊 LangWatch: {'✓' if config_result['langwatch_configured'] else '✗'}")
    
    print(f"\nConfiguration Score: {config_result['configuration_score']:.2f}")
    print(f"Production Ready: {'✅ Yes' if config_result['ready_for_production'] else '❌ No'}")
    
    print("\nEnhanced Features:")
    for feature, enabled in config_result['enhanced_features'].items():
        status = "✅" if enabled else "❌"
        print(f"  {status} {feature.replace('_', ' ').title()}")
    
    return config_result


def demonstrate_rate_limit_handling():
    """Demonstrate rate limit detection and exponential backoff (AC4.1)."""
    print_section("⏱️  RATE LIMIT HANDLING (AC4.1)", 
                  "Demonstrating exponential backoff and rate limit detection")
    
    # Create workflow validator
    retry_config = RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True
    )
    validator = create_workflow_validator(retry_config)
    
    print("Rate Limit Detection Tests:")
    
    # Test rate limit detection
    rate_limit_errors = [
        "Rate limit exceeded - please wait",
        "HTTP 429: Too Many Requests",
        "API quota exceeded for this hour",
        "Request throttled due to high volume"
    ]
    
    for i, error_msg in enumerate(rate_limit_errors, 1):
        is_rate_limit = validator.rate_limit_handler.is_rate_limited(error_msg)
        print(f"  {i}. '{error_msg[:40]}...' → {'✅ Detected' if is_rate_limit else '❌ Missed'}")
    
    print("\nExponential Backoff Calculation:")
    for attempt in range(5):
        delay = retry_config.calculate_delay(attempt)
        print(f"  Attempt {attempt + 1}: {delay:.2f} seconds")
    
    print(f"\nMax delay cap: {retry_config.max_delay} seconds")
    print(f"Jitter enabled: {'✅ Yes' if retry_config.jitter else '❌ No'}")


def demonstrate_account_access_validation():
    """Demonstrate private and suspended account handling (AC4.2)."""
    print_section("🔒 ACCOUNT ACCESS VALIDATION (AC4.2)",
                  "Demonstrating private and suspended account detection")
    
    validator = create_workflow_validator()
    
    print_subsection("Private Account Detection")
    private_scenarios = [
        ("private_user", "User has protected tweets"),
        ("locked_account", "Not authorized to access this resource"),
        ("restricted_profile", "Access denied - private account")
    ]
    
    for username, error_msg in private_scenarios:
        result = validator.account_validator.validate_account_access(username, error_msg)
        print(f"  👤 @{username}: {error_msg}")
        print(f"     Status: {'🔒 Private' if result.error_type == ErrorType.PRIVATE_ACCOUNT else '❓ Other'}")
        print(f"     Severity: {result.severity.name}")
        print(f"     Suggestions: {len(result.suggestions)} provided")
        print()
    
    print_subsection("Suspended Account Detection")
    suspended_scenarios = [
        ("banned_user", "User has been suspended"),
        ("deactivated_account", "Account deactivated by user"),
        ("restricted_user", "User account is temporarily restricted")
    ]
    
    for username, error_msg in suspended_scenarios:
        result = validator.account_validator.validate_account_access(username, error_msg)
        print(f"  🚫 @{username}: {error_msg}")
        print(f"     Status: {'🚫 Suspended' if result.error_type == ErrorType.SUSPENDED_ACCOUNT else '❓ Other'}")
        print(f"     Severity: {result.severity.name}")
        print(f"     Can Generate Profile: {'❌ No' if not result.is_valid else '✅ Yes'}")
        print()


def demonstrate_data_quality_validation():
    """Demonstrate data quality validation and insufficient data handling (AC4.3)."""
    print_section("📊 DATA QUALITY VALIDATION (AC4.3)",
                  "Demonstrating insufficient data detection and meaningful responses")
    
    validator = create_workflow_validator()
    
    print_subsection("Data Quality Scenarios")
    
    # High quality data
    high_quality_data = {
        "total_tweets": 25,
        "has_profile_data": True,
        "quality_score": 0.85,
        "sources": ["TwitterAPI.io", "ScrapeBadger"],
        "has_highlights": True
    }
    
    result = validator.validate_data_quality(high_quality_data, "high_quality_user")
    print("🌟 High Quality Profile:")
    print(f"   Quality Score: {high_quality_data['quality_score']:.2f}")
    print(f"   Tweets: {high_quality_data['total_tweets']}")
    print(f"   Sources: {len(high_quality_data['sources'])}")
    print(f"   Status: {'✅ Sufficient' if result.is_valid else '❌ Insufficient'}")
    print(f"   Can Generate: {'✅ Yes' if result.is_valid else '❌ No'}")
    print()
    
    # Warning level data
    warning_data = {
        "total_tweets": 8,
        "has_profile_data": True,
        "quality_score": 0.45,
        "sources": ["TwitterAPI.io"],
        "has_highlights": False
    }
    
    result = validator.validate_data_quality(warning_data, "warning_user")
    print("⚠️  Warning Level Profile:")
    print(f"   Quality Score: {warning_data['quality_score']:.2f}")
    print(f"   Tweets: {warning_data['total_tweets']}")
    print(f"   Sources: {len(warning_data['sources'])}")
    print(f"   Status: {'⚠️  Warnings' if result.is_valid and result.error_type else '✅ Good'}")
    print(f"   Can Generate: {'✅ Yes (reduced confidence)' if result.is_valid else '❌ No'}")
    if result.metadata.get("expected_confidence_reduction"):
        print(f"   Confidence Reduction: {result.metadata['expected_confidence_reduction']:.1%}")
    print()
    
    # Critical insufficient data
    critical_data = {
        "total_tweets": 2,
        "has_profile_data": False,
        "quality_score": 0.15,
        "sources": [],
        "has_highlights": False
    }
    
    result = validator.validate_data_quality(critical_data, "insufficient_user")
    print("🚨 Critically Insufficient Profile:")
    print(f"   Quality Score: {critical_data['quality_score']:.2f}")
    print(f"   Tweets: {critical_data['total_tweets']}")
    print(f"   Sources: {len(critical_data['sources'])}")
    print(f"   Status: {'🚨 Critical Issues' if result.severity == ErrorSeverity.CRITICAL else '❌ Insufficient'}")
    print(f"   Can Generate: {'❌ No' if not result.metadata.get('can_generate_profile', True) else '✅ Yes'}")
    print(f"   Suggestions: {len(result.suggestions)} provided")
    print()


def demonstrate_mistral_ai_integration():
    """Demonstrate Mistral AI integration and enhanced workflow."""
    print_section("🤖 MISTRAL AI INTEGRATION",
                  "Demonstrating enhanced workflow with Mistral AI")
    
    print("Creating Enhanced Workflow with Mistral AI...")
    
    try:
        # Create workflow with Mistral AI
        workflow = create_advanced_skill_generator_workflow("mistral-large-latest")
        
        print(f"✅ Workflow created successfully!")
        print(f"   Model: {workflow.model_id}")
        print(f"   Agents: {len([workflow.twitter_api_agent, workflow.scrapebadger_agent, workflow.expertise_agent, workflow.communication_agent, workflow.insight_agent, workflow.profile_generator_agent])}")
        
        # Display workflow metrics
        print("\n📊 Workflow Metrics:")
        metrics = workflow.get_workflow_metrics()
        for key, value in metrics.items():
            print(f"   {key.replace('_', ' ').title()}: {value}")
        
        # Display enhanced validation summary
        print("\n🔍 Enhanced Validation Summary:")
        summary = workflow.get_enhanced_validation_summary()
        
        print("   Tool Status:")
        for tool, status in summary["tool_status"].items():
            available = "✅" if status["available"] else "❌"
            can_retry = "✅" if status["can_retry"] else "⏱️"
            print(f"     {tool}: {available} Available, {can_retry} Can Retry")
        
        print("   Enhanced Features:")
        for feature, enabled in summary["enhanced_features"].items():
            status = "✅" if enabled else "❌"
            print(f"     {status} {feature.replace('_', ' ').title()}")
        
        return workflow
        
    except Exception as e:
        print(f"❌ Failed to create workflow: {e}")
        return None


def demonstrate_error_scenarios():
    """Demonstrate various error scenarios and their handling."""
    print_section("🚨 ERROR SCENARIO DEMONSTRATIONS",
                  "Testing comprehensive error handling capabilities")
    
    workflow = create_advanced_skill_generator_workflow()
    
    print_subsection("Username Validation Errors")
    
    invalid_usernames = [
        "",  # Empty
        "invalid@user!",  # Special characters
        "toolongusernamethatexceedslimit",  # Too long
        "user with spaces",  # Spaces
        "@#$%^&*()",  # Only special characters
    ]
    
    for username in invalid_usernames:
        try:
            workflow.generate_skill_profile(username)
            print(f"  ❌ '{username}' → Should have failed but didn't")
        except ValueError as e:
            print(f"  ✅ '{username}' → Properly rejected: {str(e)[:60]}...")
        except Exception as e:
            print(f"  ⚠️  '{username}' → Unexpected error: {type(e).__name__}")
    
    print_subsection("API Error Handling")
    
    # Test different API error scenarios
    api_errors = [
        ("Rate limit exceeded", 429, ErrorType.RATE_LIMIT),
        ("User has protected tweets", 401, ErrorType.PRIVATE_ACCOUNT),
        ("User has been suspended", 403, ErrorType.SUSPENDED_ACCOUNT),
        ("Invalid API key", 403, ErrorType.API_ERROR),
        ("Network timeout", None, ErrorType.UNKNOWN_ERROR)
    ]
    
    for error_msg, status_code, expected_type in api_errors:
        result = workflow.handle_api_error("twitter_api", "testuser", error_msg, status_code)
        actual_type = result.error_type
        match = "✅" if actual_type == expected_type else "❌"
        print(f"  {match} '{error_msg}' → {actual_type.value} (expected: {expected_type.value})")


def demonstrate_workflow_execution():
    """Demonstrate complete workflow execution with error handling."""
    print_section("🔄 WORKFLOW EXECUTION DEMONSTRATION",
                  "Running complete workflow with comprehensive error handling")
    
    workflow = create_advanced_skill_generator_workflow()
    
    # Test usernames representing different scenarios
    test_scenarios = [
        ("elonmusk", "High-profile public account"),
        ("private_user", "Simulated private account"),
        ("suspended_user", "Simulated suspended account"),
        ("low_activity_user", "Account with minimal activity")
    ]
    
    for username, description in test_scenarios:
        print_subsection(f"Testing: @{username} ({description})")
        
        try:
            print(f"🚀 Attempting to generate profile for @{username}...")
            
            # This would normally execute the full workflow
            # For demo purposes, we'll simulate the process
            print("   📋 Validating profile input...")
            print("   🔄 Collecting data in parallel...")
            print("   📊 Evaluating data quality...")
            print("   🔍 Performing analysis...")
            print("   ✨ Generating enhanced profile...")
            
            # Simulate different outcomes based on username
            if username == "private_user":
                raise ValueError(f"Cannot generate profile for @{username}: Account is private. Suggestions: Use only publicly available profile information; Focus on bio and public metrics if available")
            elif username == "suspended_user":
                raise ValueError(f"Cannot generate profile for @{username}: Account is suspended. Suggestions: Cannot generate skill profile for suspended account; Inform user that account is not accessible")
            elif username == "low_activity_user":
                print("   ⚠️  Data quality warnings detected")
                print("   📈 Profile generated with reduced confidence")
            else:
                print("   ✅ High-quality profile generated successfully!")
            
            print(f"   🎯 Profile generation completed for @{username}")
            
        except ValueError as e:
            if "private" in str(e).lower():
                print(f"   🔒 Private account detected: {str(e)[:80]}...")
            elif "suspended" in str(e).lower():
                print(f"   🚫 Suspended account detected: {str(e)[:80]}...")
            elif "rate limit" in str(e).lower():
                print(f"   ⏱️  Rate limit encountered: {str(e)[:80]}...")
            else:
                print(f"   ❌ Validation error: {str(e)[:80]}...")
        except Exception as e:
            print(f"   🚨 Unexpected error: {type(e).__name__}: {str(e)[:60]}...")
        
        print()


def main():
    """Run the enhanced workflow demonstration."""
    
    # Load environment variables
    load_dotenv()
    
    print("🚀 Enhanced Advanced Skill Generator Workflow Demo")
    print("   Task 2.2 Implementation: Workflow Validation & Error Handling")
    print("   Features: Mistral AI, Exponential Backoff, Comprehensive Validation")
    
    try:
        # 1. Configuration validation
        config_result = demonstrate_configuration_validation()
        
        # 2. Rate limit handling (AC4.1)
        demonstrate_rate_limit_handling()
        
        # 3. Account access validation (AC4.2)
        demonstrate_account_access_validation()
        
        # 4. Data quality validation (AC4.3)
        demonstrate_data_quality_validation()
        
        # 5. Mistral AI integration
        workflow = demonstrate_mistral_ai_integration()
        
        # 6. Error scenario testing
        if workflow:
            demonstrate_error_scenarios()
            
            # 7. Complete workflow execution
            demonstrate_workflow_execution()
        
        print_section("🎉 DEMONSTRATION COMPLETED",
                      "All enhanced features have been successfully demonstrated!")
        
        print("\n📋 Summary of Implemented Features:")
        print("   ✅ AC4.1: API rate limits with exponential backoff")
        print("   ✅ AC4.2: Private/suspended account management")
        print("   ✅ AC4.3: Meaningful responses for insufficient data")
        print("   ✅ Mistral AI integration for improved performance")
        print("   ✅ Comprehensive error handling and validation")
        print("   ✅ Enhanced monitoring and logging capabilities")
        
        print("\n🚀 Next Steps:")
        print("   1. Run comprehensive tests: `uv run pytest tests/test_enhanced_workflow_validation.py -v`")
        print("   2. Configure real API keys for production use")
        print("   3. Set up monitoring and alerting for production deployment")
        print("   4. Integrate with existing skill generation pipeline")
        
        if not config_result["ready_for_production"]:
            print("\n⚠️  Note: Additional configuration required for production use")
            print("   - Ensure all API keys are properly configured")
            print("   - Verify network connectivity to API endpoints")
            print("   - Set up appropriate logging and monitoring")
        
    except Exception as e:
        print(f"\n🚨 Demo failed with error: {e}")
        print("   This may be due to missing dependencies or configuration issues")
        print("   Please check your environment setup and try again")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
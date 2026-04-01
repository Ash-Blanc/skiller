"""
Profile validation step for the Advanced Skill Generator Workflow.

This module implements profile input validation, username format checking,
and tool availability verification.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import requests
from urllib.parse import urlparse

from ..utils.circuit_breaker import get_circuit_manager, CircuitBreakerConfig
from ..utils.workflow_metrics import get_workflow_monitor


@dataclass
class ValidationResult:
    """Result of profile validation."""
    is_valid: bool
    username: str
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
    tools_available: Dict[str, bool]


@dataclass
class ToolAvailability:
    """Tool availability status."""
    name: str
    is_available: bool
    response_time_ms: Optional[float]
    error_message: Optional[str]
    last_checked: datetime


class ProfileValidator:
    """Validates profile inputs and checks tool availability."""
    
    def __init__(self):
        self.logger = logging.getLogger("profile_validator")
        self.circuit_manager = get_circuit_manager()
        self.workflow_monitor = get_workflow_monitor()
        
        # Username validation patterns
        self.username_patterns = {
            'twitter': re.compile(r'^[a-zA-Z0-9_]{1,15}$'),
            'x': re.compile(r'^[a-zA-Z0-9_]{1,15}$'),  # Same as Twitter
        }
        
        # Tool endpoints for availability checking
        self.tool_endpoints = {
            'twitter_api_io': 'https://api.twitterapi.io/health',
            'scrapebadger': 'https://api.scrapebadger.com/health',
        }
    
    def validate_profile_input(self, username: str, platform: str = 'twitter', 
                             workflow_id: str = None) -> ValidationResult:
        """
        Validate profile input and check system readiness.
        
        Args:
            username: The username to validate
            platform: The platform (twitter, x)
            workflow_id: Optional workflow ID for logging
            
        Returns:
            ValidationResult with validation status and details
        """
        if workflow_id:
            self.workflow_monitor.start_timer(f"{workflow_id}_validation")
        
        errors = []
        warnings = []
        metadata = {}
        
        # Clean and normalize username
        cleaned_username = self._clean_username(username)
        
        # Validate username format
        format_valid, format_errors = self._validate_username_format(cleaned_username, platform)
        errors.extend(format_errors)
        
        # Check for common issues
        issue_warnings = self._check_common_issues(cleaned_username)
        warnings.extend(issue_warnings)
        
        # Check tool availability
        tools_available = self._check_tool_availability()
        
        # Validate that at least one tool is available
        if not any(tools_available.values()):
            errors.append("No data collection tools are currently available")
        
        # Additional metadata
        metadata.update({
            'original_username': username,
            'cleaned_username': cleaned_username,
            'platform': platform,
            'validation_timestamp': datetime.now().isoformat(),
            'available_tools': list(k for k, v in tools_available.items() if v)
        })
        
        is_valid = len(errors) == 0
        
        # Log validation result
        if workflow_id:
            duration = self.workflow_monitor.end_timer(f"{workflow_id}_validation", workflow_id)
            self.workflow_monitor.log_step_completion(
                workflow_id, 
                "profile_validation", 
                is_valid,
                username=cleaned_username,
                platform=platform,
                errors_count=len(errors),
                warnings_count=len(warnings),
                tools_available_count=sum(tools_available.values())
            )
        
        return ValidationResult(
            is_valid=is_valid,
            username=cleaned_username,
            errors=errors,
            warnings=warnings,
            metadata=metadata,
            tools_available=tools_available
        )
    
    def _clean_username(self, username: str) -> str:
        """Clean and normalize username input."""
        if not username:
            return ""
        
        # Remove common prefixes and whitespace
        cleaned = username.strip()
        
        # Remove @ symbol if present
        if cleaned.startswith('@'):
            cleaned = cleaned[1:]
        
        # Remove URL prefixes if someone pasted a profile URL
        if cleaned.startswith(('http://', 'https://')):
            try:
                parsed = urlparse(cleaned)
                path_parts = parsed.path.strip('/').split('/')
                if path_parts and path_parts[0]:
                    cleaned = path_parts[0]
            except:
                pass
        
        # Remove twitter.com/x.com domain references
        for domain in ['twitter.com/', 'x.com/', 'mobile.twitter.com/', 'm.twitter.com/']:
            if domain in cleaned:
                cleaned = cleaned.split(domain)[-1]
        
        return cleaned.strip()
    
    def _validate_username_format(self, username: str, platform: str) -> Tuple[bool, List[str]]:
        """Validate username format according to platform rules."""
        errors = []
        
        if not username:
            errors.append("Username cannot be empty")
            return False, errors
        
        # Get pattern for platform
        pattern = self.username_patterns.get(platform.lower())
        if not pattern:
            errors.append(f"Unsupported platform: {platform}")
            return False, errors
        
        # Check format
        if not pattern.match(username):
            errors.append(f"Invalid username format for {platform}. Must be 1-15 characters, letters, numbers, and underscores only")
        
        # Check length
        if len(username) > 15:
            errors.append(f"Username too long: {len(username)} characters (max 15)")
        
        # Check for reserved usernames
        reserved_usernames = {
            'admin', 'root', 'api', 'www', 'mail', 'ftp', 'support', 'help',
            'twitter', 'x', 'about', 'home', 'settings', 'privacy', 'terms'
        }
        
        if username.lower() in reserved_usernames:
            errors.append(f"Username '{username}' is reserved and cannot be processed")
        
        return len(errors) == 0, errors
    
    def _check_common_issues(self, username: str) -> List[str]:
        """Check for common issues that might affect data collection."""
        warnings = []
        
        # Check for potentially problematic patterns
        if username.startswith('_') or username.endswith('_'):
            warnings.append("Usernames starting or ending with underscore may have limited data")
        
        if len(username) < 3:
            warnings.append("Very short usernames may be harder to analyze")
        
        if username.isdigit():
            warnings.append("Numeric-only usernames may have limited profile information")
        
        # Check for common bot patterns
        bot_patterns = ['bot', 'api', 'test', 'demo', 'fake', 'spam']
        if any(pattern in username.lower() for pattern in bot_patterns):
            warnings.append("Username suggests automated account - analysis may be limited")
        
        return warnings
    
    def _check_tool_availability(self) -> Dict[str, bool]:
        """Check availability of data collection tools."""
        availability = {}
        
        for tool_name, endpoint in self.tool_endpoints.items():
            try:
                # Use circuit breaker for health checks
                config = CircuitBreakerConfig(
                    failure_threshold=2,
                    recovery_timeout=30,
                    timeout=5.0
                )
                
                is_available = self.circuit_manager.call_with_circuit_breaker(
                    f"{tool_name}_health",
                    self._check_single_tool,
                    config,
                    endpoint
                )
                
                availability[tool_name] = is_available
                
            except Exception as e:
                self.logger.warning(f"Tool {tool_name} availability check failed: {e}")
                availability[tool_name] = False
        
        return availability
    
    def _check_single_tool(self, endpoint: str) -> bool:
        """Check if a single tool is available."""
        try:
            response = requests.get(endpoint, timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            # If health endpoint doesn't exist, try a basic connection
            try:
                base_url = '/'.join(endpoint.split('/')[:3])
                response = requests.head(base_url, timeout=5)
                return response.status_code < 500
            except:
                return False
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation statistics."""
        circuit_stats = self.circuit_manager.get_all_stats()
        
        # Filter for validation-related circuits
        validation_stats = {
            name: stats for name, stats in circuit_stats.items()
            if 'health' in name or 'validation' in name
        }
        
        return {
            'tool_availability': self._check_tool_availability(),
            'circuit_breaker_stats': validation_stats,
            'supported_platforms': list(self.username_patterns.keys()),
            'validation_rules': {
                'max_username_length': 15,
                'allowed_characters': 'letters, numbers, underscores',
                'required_tools': list(self.tool_endpoints.keys())
            }
        }


def validate_profile_input(username: str, platform: str = 'twitter', workflow_id: str = None) -> ValidationResult:
    """
    Convenience function for profile validation.
    
    Args:
        username: Username to validate
        platform: Platform type (twitter, x)
        workflow_id: Optional workflow ID for tracking
        
    Returns:
        ValidationResult with validation status
    """
    validator = ProfileValidator()
    return validator.validate_profile_input(username, platform, workflow_id)


def check_system_readiness() -> Dict[str, Any]:
    """
    Check if the system is ready for profile processing.
    
    Returns:
        Dictionary with system readiness status
    """
    validator = ProfileValidator()
    
    # Check tool availability
    tools_available = validator._check_tool_availability()
    
    # Get circuit breaker health
    circuit_stats = validator.circuit_manager.get_all_stats()
    
    # Determine overall readiness
    tools_ready = any(tools_available.values())
    circuits_healthy = all(
        stats['state'] != 'open' 
        for stats in circuit_stats.values()
    )
    
    readiness_status = "ready" if tools_ready and circuits_healthy else "degraded"
    if not tools_ready:
        readiness_status = "not_ready"
    
    return {
        'status': readiness_status,
        'tools_available': tools_available,
        'available_tool_count': sum(tools_available.values()),
        'total_tool_count': len(tools_available),
        'circuit_breaker_health': {
            name: stats['state'] for name, stats in circuit_stats.items()
        },
        'recommendations': _get_readiness_recommendations(tools_available, circuit_stats)
    }


def _get_readiness_recommendations(tools_available: Dict[str, bool], 
                                 circuit_stats: Dict[str, Any]) -> List[str]:
    """Get recommendations for improving system readiness."""
    recommendations = []
    
    # Tool availability recommendations
    unavailable_tools = [name for name, available in tools_available.items() if not available]
    if unavailable_tools:
        recommendations.append(f"Check connectivity to: {', '.join(unavailable_tools)}")
    
    # Circuit breaker recommendations
    open_circuits = [name for name, stats in circuit_stats.items() if stats['state'] == 'open']
    if open_circuits:
        recommendations.append(f"Reset or wait for recovery of: {', '.join(open_circuits)}")
    
    # General recommendations
    if not any(tools_available.values()):
        recommendations.append("Ensure at least one data collection tool is available")
    
    if len([t for t in tools_available.values() if t]) == 1:
        recommendations.append("Consider having multiple tools available for redundancy")
    
    return recommendations


if __name__ == "__main__":
    # Demo profile validation
    validator = ProfileValidator()
    
    # Test cases
    test_cases = [
        "elonmusk",
        "@elonmusk",
        "https://twitter.com/elonmusk",
        "invalid@username!",
        "",
        "toolongusernamehere123456",
        "bot_account_123",
        "_underscore_user_"
    ]
    
    print("Profile Validation Demo")
    print("=" * 50)
    
    for username in test_cases:
        result = validator.validate_profile_input(username)
        
        print(f"\nUsername: '{username}'")
        print(f"Valid: {result.is_valid}")
        print(f"Cleaned: '{result.username}'")
        
        if result.errors:
            print(f"Errors: {result.errors}")
        
        if result.warnings:
            print(f"Warnings: {result.warnings}")
        
        print(f"Tools Available: {result.tools_available}")
    
    # System readiness check
    print(f"\n" + "=" * 50)
    print("System Readiness Check")
    print("=" * 50)
    
    readiness = check_system_readiness()
    print(f"Status: {readiness['status']}")
    print(f"Available Tools: {readiness['available_tool_count']}/{readiness['total_tool_count']}")
    
    if readiness['recommendations']:
        print("Recommendations:")
        for rec in readiness['recommendations']:
            print(f"  • {rec}")
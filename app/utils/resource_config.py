"""
Resource configuration management for the Advanced Skill Generator Workflow.

This module provides configuration management for resource allocation,
parallel processing settings, and performance optimization parameters.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import json
import yaml
from pathlib import Path

from .resource_monitor import ResourceRequirements, ResourceValidationResult


@dataclass
class ParallelProcessingConfig:
    """Configuration for parallel processing behavior."""
    
    # Core parallel processing settings
    max_concurrent_workflows: int = 10
    max_concurrent_data_collection: int = 2  # TwitterAPI + ScrapeBadger
    max_concurrent_analysis: int = 3  # Expertise, Communication, Insight agents
    
    # Resource limits per workflow
    memory_limit_mb: int = 500
    cpu_cores_per_workflow: int = 1
    timeout_seconds: int = 300  # 5 minutes
    
    # Batch processing settings
    batch_size: int = 5
    batch_timeout_seconds: int = 1800  # 30 minutes
    
    # Performance optimization
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600  # 1 hour
    enable_resource_monitoring: bool = True
    monitoring_interval_seconds: float = 1.0
    
    # Quality vs Speed tradeoffs
    quality_mode: str = "balanced"  # "fast", "balanced", "quality"
    max_retry_attempts: int = 3
    retry_backoff_multiplier: float = 2.0
    
    # Resource thresholds for auto-scaling
    cpu_threshold_percent: float = 80.0
    memory_threshold_percent: float = 85.0
    auto_scale_down_threshold: float = 50.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "max_concurrent_workflows": self.max_concurrent_workflows,
            "max_concurrent_data_collection": self.max_concurrent_data_collection,
            "max_concurrent_analysis": self.max_concurrent_analysis,
            "memory_limit_mb": self.memory_limit_mb,
            "cpu_cores_per_workflow": self.cpu_cores_per_workflow,
            "timeout_seconds": self.timeout_seconds,
            "batch_size": self.batch_size,
            "batch_timeout_seconds": self.batch_timeout_seconds,
            "enable_caching": self.enable_caching,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "enable_resource_monitoring": self.enable_resource_monitoring,
            "monitoring_interval_seconds": self.monitoring_interval_seconds,
            "quality_mode": self.quality_mode,
            "max_retry_attempts": self.max_retry_attempts,
            "retry_backoff_multiplier": self.retry_backoff_multiplier,
            "cpu_threshold_percent": self.cpu_threshold_percent,
            "memory_threshold_percent": self.memory_threshold_percent,
            "auto_scale_down_threshold": self.auto_scale_down_threshold,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParallelProcessingConfig":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class EnvironmentConfig:
    """Environment-specific configuration."""
    
    # Environment type
    environment: str = "development"  # "development", "staging", "production"
    
    # Resource requirements based on environment
    resource_requirements: ResourceRequirements = field(default_factory=ResourceRequirements)
    
    # Parallel processing config
    parallel_config: ParallelProcessingConfig = field(default_factory=ParallelProcessingConfig)
    
    # Logging and monitoring
    log_level: str = "INFO"
    enable_metrics: bool = True
    metrics_export_interval: int = 60
    
    # External service limits
    api_rate_limits: Dict[str, int] = field(default_factory=lambda: {
        "twitter_api_io": 100,  # requests per minute
        "scrapebadger": 60,     # requests per minute
    })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "environment": self.environment,
            "resource_requirements": {
                "min_cpu_cores": self.resource_requirements.min_cpu_cores,
                "min_memory_gb": self.resource_requirements.min_memory_gb,
                "min_disk_free_gb": self.resource_requirements.min_disk_free_gb,
                "max_memory_per_workflow_mb": self.resource_requirements.max_memory_per_workflow_mb,
                "max_concurrent_workflows": self.resource_requirements.max_concurrent_workflows,
                "recommended_cpu_cores": self.resource_requirements.recommended_cpu_cores,
                "recommended_memory_gb": self.resource_requirements.recommended_memory_gb,
            },
            "parallel_config": self.parallel_config.to_dict(),
            "log_level": self.log_level,
            "enable_metrics": self.enable_metrics,
            "metrics_export_interval": self.metrics_export_interval,
            "api_rate_limits": self.api_rate_limits,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvironmentConfig":
        """Create from dictionary."""
        config = cls()
        
        if "environment" in data:
            config.environment = data["environment"]
        
        if "resource_requirements" in data:
            req_data = data["resource_requirements"]
            config.resource_requirements = ResourceRequirements(**req_data)
        
        if "parallel_config" in data:
            config.parallel_config = ParallelProcessingConfig.from_dict(data["parallel_config"])
        
        if "log_level" in data:
            config.log_level = data["log_level"]
        
        if "enable_metrics" in data:
            config.enable_metrics = data["enable_metrics"]
        
        if "metrics_export_interval" in data:
            config.metrics_export_interval = data["metrics_export_interval"]
        
        if "api_rate_limits" in data:
            config.api_rate_limits = data["api_rate_limits"]
        
        return config


class ResourceConfigManager:
    """Manage resource configuration for different environments."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self._current_config: Optional[EnvironmentConfig] = None
    
    def get_default_configs(self) -> Dict[str, EnvironmentConfig]:
        """Get default configurations for different environments."""
        
        # Development configuration - conservative settings
        dev_config = EnvironmentConfig(
            environment="development",
            resource_requirements=ResourceRequirements(
                min_cpu_cores=2,
                min_memory_gb=2.0,
                min_disk_free_gb=1.0,
                max_memory_per_workflow_mb=300,
                max_concurrent_workflows=3,
                recommended_cpu_cores=4,
                recommended_memory_gb=4.0,
            ),
            parallel_config=ParallelProcessingConfig(
                max_concurrent_workflows=3,
                max_concurrent_data_collection=2,
                max_concurrent_analysis=2,
                memory_limit_mb=300,
                batch_size=2,
                quality_mode="balanced",
                enable_resource_monitoring=True,
            ),
            log_level="DEBUG",
        )
        
        # Staging configuration - moderate settings
        staging_config = EnvironmentConfig(
            environment="staging",
            resource_requirements=ResourceRequirements(
                min_cpu_cores=4,
                min_memory_gb=4.0,
                min_disk_free_gb=2.0,
                max_memory_per_workflow_mb=400,
                max_concurrent_workflows=6,
                recommended_cpu_cores=8,
                recommended_memory_gb=8.0,
            ),
            parallel_config=ParallelProcessingConfig(
                max_concurrent_workflows=6,
                max_concurrent_data_collection=2,
                max_concurrent_analysis=3,
                memory_limit_mb=400,
                batch_size=4,
                quality_mode="balanced",
                enable_resource_monitoring=True,
            ),
            log_level="INFO",
        )
        
        # Production configuration - optimized settings
        prod_config = EnvironmentConfig(
            environment="production",
            resource_requirements=ResourceRequirements(
                min_cpu_cores=8,
                min_memory_gb=8.0,
                min_disk_free_gb=5.0,
                max_memory_per_workflow_mb=500,
                max_concurrent_workflows=10,
                recommended_cpu_cores=16,
                recommended_memory_gb=16.0,
            ),
            parallel_config=ParallelProcessingConfig(
                max_concurrent_workflows=10,
                max_concurrent_data_collection=2,
                max_concurrent_analysis=4,
                memory_limit_mb=500,
                batch_size=8,
                quality_mode="quality",
                enable_resource_monitoring=True,
                monitoring_interval_seconds=0.5,
            ),
            log_level="WARNING",
        )
        
        return {
            "development": dev_config,
            "staging": staging_config,
            "production": prod_config,
        }
    
    def save_config(self, config: EnvironmentConfig, filename: Optional[str] = None):
        """Save configuration to file."""
        if filename is None:
            filename = f"{config.environment}_config.yaml"
        
        config_path = self.config_dir / filename
        
        with open(config_path, 'w') as f:
            yaml.dump(config.to_dict(), f, default_flow_style=False, indent=2)
    
    def load_config(self, filename: str) -> EnvironmentConfig:
        """Load configuration from file."""
        config_path = self.config_dir / filename
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        return EnvironmentConfig.from_dict(data)
    
    def get_config_for_environment(self, environment: str = None) -> EnvironmentConfig:
        """Get configuration for the specified environment."""
        if environment is None:
            environment = os.getenv("ENVIRONMENT", "development")
        
        # Try to load from file first
        config_file = f"{environment}_config.yaml"
        config_path = self.config_dir / config_file
        
        if config_path.exists():
            return self.load_config(config_file)
        
        # Fall back to default configuration
        default_configs = self.get_default_configs()
        if environment in default_configs:
            config = default_configs[environment]
            # Save the default config for future use
            self.save_config(config)
            return config
        
        # If environment not recognized, use development config
        config = default_configs["development"]
        config.environment = environment
        return config
    
    def auto_configure_from_system(self, validation_result: ResourceValidationResult) -> EnvironmentConfig:
        """Auto-configure based on system resources."""
        current_resources = validation_result.current_resources
        
        # Determine appropriate environment based on resources
        if (current_resources.memory_available_gb >= 8.0 and 
            validation_result.max_safe_concurrent_workflows >= 8):
            base_env = "production"
        elif (current_resources.memory_available_gb >= 4.0 and 
              validation_result.max_safe_concurrent_workflows >= 4):
            base_env = "staging"
        else:
            base_env = "development"
        
        config = self.get_config_for_environment(base_env)
        
        # Adjust based on actual system capabilities
        config.parallel_config.max_concurrent_workflows = min(
            validation_result.max_safe_concurrent_workflows,
            config.parallel_config.max_concurrent_workflows
        )
        
        # Adjust memory limits based on available memory
        available_memory_mb = current_resources.memory_available_gb * 1024
        safe_memory_per_workflow = int(available_memory_mb * 0.8 / config.parallel_config.max_concurrent_workflows)
        config.parallel_config.memory_limit_mb = min(
            safe_memory_per_workflow,
            config.parallel_config.memory_limit_mb
        )
        
        return config
    
    def initialize_default_configs(self):
        """Initialize default configuration files."""
        default_configs = self.get_default_configs()
        
        for env_name, config in default_configs.items():
            self.save_config(config)
        
        print(f"Default configurations saved to {self.config_dir}/")
        print("Available configurations:")
        for env_name in default_configs.keys():
            print(f"  - {env_name}_config.yaml")


# Global configuration manager
_config_manager = None


def get_config_manager() -> ResourceConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ResourceConfigManager()
    return _config_manager


def get_current_config() -> EnvironmentConfig:
    """Get the current environment configuration."""
    manager = get_config_manager()
    return manager.get_config_for_environment()


def auto_configure_resources() -> EnvironmentConfig:
    """Auto-configure resources based on current system capabilities."""
    from .resource_monitor import validate_parallel_processing_resources
    
    validation_result = validate_parallel_processing_resources()
    manager = get_config_manager()
    
    return manager.auto_configure_from_system(validation_result)


if __name__ == "__main__":
    # Initialize default configurations when run directly
    manager = ResourceConfigManager()
    manager.initialize_default_configs()
    
    # Show auto-configured settings
    print("\nAuto-configured settings for current system:")
    config = auto_configure_resources()
    print(f"Environment: {config.environment}")
    print(f"Max Concurrent Workflows: {config.parallel_config.max_concurrent_workflows}")
    print(f"Memory Limit per Workflow: {config.parallel_config.memory_limit_mb}MB")
    print(f"Batch Size: {config.parallel_config.batch_size}")
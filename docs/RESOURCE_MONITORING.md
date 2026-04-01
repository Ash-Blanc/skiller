# Resource Monitoring and Parallel Processing

This document explains the resource monitoring and parallel processing capabilities implemented for the Advanced Skill Generator Workflow.

## Overview

The resource monitoring system ensures that the Advanced Skill Generator Workflow has sufficient compute resources for parallel processing and automatically optimizes performance based on system capabilities.

## Key Components

### 1. Resource Monitor (`app/utils/resource_monitor.py`)

Monitors system resources in real-time and validates that the system meets requirements for parallel processing.

**Key Features:**
- Real-time CPU, memory, and disk monitoring
- Resource validation against configurable requirements
- Workflow capacity calculation
- Performance estimation
- Continuous monitoring with history tracking

**Usage:**
```python
from app.utils.resource_monitor import get_resource_monitor, validate_parallel_processing_resources

# Get current system metrics
monitor = get_resource_monitor()
metrics = monitor.get_current_metrics()
print(f"CPU: {metrics.cpu_percent}%, Memory: {metrics.memory_percent}%")

# Validate resources for parallel processing
result = validate_parallel_processing_resources()
if result.is_sufficient:
    print(f"System can handle {result.max_safe_concurrent_workflows} concurrent workflows")
```

### 2. Resource Configuration (`app/utils/resource_config.py`)

Manages configuration for different environments and automatically optimizes settings based on system capabilities.

**Key Features:**
- Environment-specific configurations (development, staging, production)
- Auto-configuration based on system resources
- Parallel processing parameter management
- Quality vs. performance trade-offs

**Usage:**
```python
from app.utils.resource_config import get_current_config, auto_configure_resources

# Get current configuration
config = get_current_config()
print(f"Max concurrent workflows: {config.parallel_config.max_concurrent_workflows}")

# Auto-configure based on system
optimized_config = auto_configure_resources()
```

### 3. Workflow Integration (`app/utils/workflow_resource_integration.py`)

Integrates resource monitoring with Agno workflows through decorators and context managers.

**Key Features:**
- Resource-aware workflow execution
- Adaptive resource management
- Workflow capacity management
- Performance optimization

**Usage:**
```python
from app.utils.workflow_resource_integration import with_resource_monitoring, resource_managed_execution

# Using decorator
@with_resource_monitoring("skill_generation")
def generate_skill_profile(username):
    # Workflow implementation
    return profile

# Using context manager
with resource_managed_execution("batch_processing") as workflow_id:
    # Process multiple profiles
    results = process_batch(usernames)
```

## Resource Requirements

### Minimum Requirements
- **CPU Cores:** 2 (4+ recommended)
- **Memory:** 2GB total, 1GB available (4GB+ recommended)
- **Disk Space:** 1GB free
- **Concurrent Workflows:** 1-3 depending on resources

### Recommended Requirements
- **CPU Cores:** 8+ for optimal parallel processing
- **Memory:** 8GB+ for handling 10+ concurrent workflows
- **Disk Space:** 5GB+ for caching and temporary data
- **Concurrent Workflows:** 10+ for maximum throughput

### Performance Estimates
- **Standard Profile:** ~30 seconds processing time
- **Throughput:** 120+ profiles/hour with optimal resources
- **Memory per Workflow:** 300-500MB depending on configuration
- **Parallel Speedup:** 40%+ improvement over sequential processing

## Configuration Files

The system creates configuration files in the `config/` directory:

- `development_config.yaml` - Conservative settings for development
- `staging_config.yaml` - Moderate settings for testing
- `production_config.yaml` - Optimized settings for production
- `auto_configured_*.yaml` - System-optimized configurations

### Example Configuration
```yaml
environment: development
resource_requirements:
  min_cpu_cores: 2
  min_memory_gb: 2.0
  max_concurrent_workflows: 3
  max_memory_per_workflow_mb: 300
parallel_config:
  max_concurrent_workflows: 3
  batch_size: 2
  quality_mode: balanced
  enable_caching: true
  enable_resource_monitoring: true
```

## Command Line Tools

### Resource Validation Script

Use `scripts/validate_resources.py` to check system resources:

```bash
# Basic validation
uv run python scripts/validate_resources.py

# Verbose output with detailed report
uv run python scripts/validate_resources.py --verbose

# Auto-configure for current system
uv run python scripts/validate_resources.py --auto-configure --save-config

# Run performance benchmark
uv run python scripts/validate_resources.py --benchmark

# Initialize default configurations
uv run python scripts/validate_resources.py --init-configs
```

### Example Output
```
🔍 Validating system resources for parallel processing...

📋 Current Environment: development
📋 Resource Requirements:
   • Min CPU Cores: 2 (Recommended: 4)
   • Min Memory: 2.0GB (Recommended: 4.0GB)
   • Max Concurrent Workflows: 3

✅ VALIDATION PASSED
   System has sufficient resources for parallel processing
   Max safe concurrent workflows: 2
   Estimated throughput: 240 profiles/hour

🎉 System is ready for parallel processing!
```

## Integration with Agno Workflows

### Resource-Aware Workflow Execution

```python
from agno import Agent, Workflow
from app.utils.workflow_resource_integration import with_resource_monitoring

class AdvancedSkillGeneratorWorkflow(Workflow):
    
    @with_resource_monitoring("skill_generation")
    def generate_profile(self, username: str):
        # Workflow steps with automatic resource management
        return self.run_workflow_steps(username)
    
    def run_workflow_steps(self, username: str):
        # Get adaptive configuration
        from app.utils.workflow_resource_integration import get_current_resource_limits
        limits = get_current_resource_limits()
        
        # Adjust workflow based on resources
        if limits['quality_mode'] == 'fast':
            return self.run_fast_workflow(username)
        elif limits['quality_mode'] == 'quality':
            return self.run_quality_workflow(username)
        else:
            return self.run_balanced_workflow(username)
```

### Adaptive Batch Processing

```python
from app.utils.workflow_resource_integration import get_adaptive_manager

def process_multiple_profiles(usernames: List[str]):
    adaptive_manager = get_adaptive_manager()
    
    # Get optimal batch size based on current resources
    batch_size = adaptive_manager.get_optimal_batch_size()
    
    # Process in batches
    for i in range(0, len(usernames), batch_size):
        batch = usernames[i:i + batch_size]
        
        # Check if we can start this batch
        with resource_managed_execution(f"batch_{i}"):
            results = process_batch_parallel(batch)
            yield results
```

## Monitoring and Observability

### Resource Health Checks

```python
from app.utils.workflow_resource_integration import check_resource_health

def health_check_endpoint():
    is_healthy, health_info = check_resource_health()
    
    return {
        "status": "healthy" if is_healthy else "degraded",
        "active_workflows": health_info["active_workflows"],
        "max_concurrent": health_info["max_safe_concurrent"],
        "issues": health_info["issues"],
        "recommendations": health_info["recommendations"]
    }
```

### Performance Metrics

The system automatically tracks:
- Workflow execution times
- Resource utilization during processing
- Success/failure rates
- Throughput metrics
- System load patterns

### Logging

Resource monitoring includes structured logging:
```
INFO - Workflow skill_generation_abc123 started. Active workflows: 2
INFO - Resource Status - CPU: 45.2%, Memory: 67.8%, Available: 2.1GB
INFO - Adaptive Config - Batch: 3, Concurrent: 4, Quality: balanced, Caching: true
INFO - Workflow skill_generation_abc123 completed successfully in 28.5s
```

## Troubleshooting

### Common Issues

1. **"Insufficient system resources"**
   - Run `scripts/validate_resources.py --auto-configure` to optimize settings
   - Consider upgrading memory or reducing concurrent workflows

2. **"Maximum concurrent workflows reached"**
   - Wait for existing workflows to complete
   - Reduce batch size or concurrent processing

3. **High memory usage warnings**
   - System automatically reduces batch sizes and disables caching
   - Consider processing profiles sequentially

4. **Performance degradation**
   - System adapts quality mode based on load
   - Monitor resource usage and adjust configuration

### Performance Optimization

1. **Memory Optimization**
   - Enable caching only when memory is abundant
   - Reduce memory limit per workflow if needed
   - Process smaller batches during high load

2. **CPU Optimization**
   - Adjust concurrent workflow limits based on CPU cores
   - Use quality mode 'fast' during high CPU usage
   - Reserve CPU cores for system processes

3. **Quality vs Speed Trade-offs**
   - `fast` mode: Reduced analysis depth, faster processing
   - `balanced` mode: Good balance of quality and speed
   - `quality` mode: Maximum analysis depth, slower processing

## Environment Variables

Configure the system using environment variables:

```bash
# Environment type
export ENVIRONMENT=production

# Resource limits
export MAX_CONCURRENT_WORKFLOWS=10
export MEMORY_LIMIT_MB=500
export ENABLE_RESOURCE_MONITORING=true

# Quality settings
export QUALITY_MODE=balanced
export ENABLE_CACHING=true
```

## Best Practices

1. **Always validate resources** before deploying to new environments
2. **Use auto-configuration** to optimize for specific hardware
3. **Monitor resource usage** during high-load periods
4. **Adjust batch sizes** based on available memory
5. **Enable resource monitoring** in production environments
6. **Set appropriate timeouts** for workflow execution
7. **Use quality modes** to balance performance and accuracy

## Future Enhancements

- **Auto-scaling:** Automatic adjustment of concurrent workflows based on load
- **Resource prediction:** Predict resource needs based on profile complexity
- **Distributed processing:** Support for multi-node parallel processing
- **Advanced caching:** Intelligent caching strategies based on usage patterns
- **Resource alerts:** Proactive alerting for resource constraints
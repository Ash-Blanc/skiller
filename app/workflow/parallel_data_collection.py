"""
Parallel data collection implementation using Agno workflows.

This module implements simultaneous data collection from multiple sources
using Agno's parallel execution capabilities.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from agno.workflow import Workflow, Step
from agno.workflow.parallel import Parallel
from agno.agent import Agent
from agno.models.openai import OpenAIChat

from ..models.collected_data import CollectedData, TwitterAPIData, ScrapeBadgerData
from ..agents.twitter_api_collector import TwitterAPICollector
from ..agents.scrapebadger_collector import ScrapeBadgerCollector
from ..utils.workflow_metrics import get_workflow_monitor
from ..utils.circuit_breaker import get_circuit_manager
from ..utils.workflow_resource_integration import get_current_resource_limits
from ..utils.network_manager import get_network_manager
from .error_handling import GracefulDegradationHandler, PartialSuccessResult


class ParallelDataCollectionWorkflow:
    """Agno workflow for parallel data collection."""
    
    def __init__(self):
        self.logger = logging.getLogger("parallel_data_collection")
        self.workflow_monitor = get_workflow_monitor()
        self.network_manager = get_network_manager()
        
        # Initialize collectors
        self.twitter_collector = TwitterAPICollector()
        self.scrapebadger_collector = ScrapeBadgerCollector()
        
        # Error handling
        self.error_handler = GracefulDegradationHandler()
        
        # Resource management
        self.resource_limits = get_current_resource_limits()
        
        # Create agents for data collection
        self.twitter_agent = Agent(
            name="TwitterAPI Collector",
            instructions="Collect comprehensive Twitter profile data using TwitterAPI.io",
            model=OpenAIChat(id="gpt-4o")
        )
        
        self.scrapebadger_agent = Agent(
            name="ScrapeBadger Collector", 
            instructions="Collect enriched Twitter profile data using ScrapeBadger",
            model=OpenAIChat(id="gpt-4o")
        )
        
        # Create workflow steps
        self.twitter_step = Step(
            name="TwitterAPI Collection",
            agent=self.twitter_agent,
            description="Collect data using TwitterAPI.io"
        )
        
        self.scrapebadger_step = Step(
            name="ScrapeBadger Collection",
            agent=self.scrapebadger_agent, 
            description="Collect enriched data using ScrapeBadger"
        )
        
        # Create parallel workflow
        self.workflow = Workflow(
            name="Parallel Data Collection",
            steps=[
                Parallel(
                    self.twitter_step,
                    self.scrapebadger_step,
                    name="Data Collection Phase",
                    description="Collect data from multiple sources simultaneously"
                )
            ]
        )
    
    def collect_data_parallel(self, username: str, workflow_id: str = None) -> CollectedData:
        """
        Execute parallel data collection from multiple sources.
        
        Args:
            username: Username to collect data for
            workflow_id: Optional workflow ID for tracking
            
        Returns:
            CollectedData with results from all sources
        """
        if workflow_id:
            self.workflow_monitor.start_timer(f"{workflow_id}_parallel_collection")
        
        self.logger.info(f"Starting parallel data collection for {username}")
        
        # Check network health before starting
        network_health = self.network_manager.get_network_health_report()
        self.logger.info(f"Network health status: {network_health['overall_status']}")
        
        # For now, use the direct parallel execution approach
        # In production, this would use the Agno workflow execution
        max_concurrent = self.resource_limits.get('max_concurrent', 2)
        
        # Prepare collection tasks
        collection_tasks = [
            {
                'name': 'twitter_api',
                'collector': self.twitter_collector,
                'method': 'collect_profile_data',
                'args': (username, workflow_id)
            },
            {
                'name': 'scrapebadger',
                'collector': self.scrapebadger_collector,
                'method': 'collect_enriched_data',
                'args': (username, workflow_id)
            }
        ]
        
        # Execute parallel collection
        results = self._execute_parallel_collection(collection_tasks, max_concurrent)
        
        # Combine results
        collected_data = self._combine_collection_results(results, username, workflow_id)
        
        if workflow_id:
            duration = self.workflow_monitor.end_timer(f"{workflow_id}_parallel_collection", workflow_id)
            self.workflow_monitor.log_step_completion(
                workflow_id,
                "parallel_data_collection",
                collected_data.collection_success,
                sources_attempted=len(collection_tasks),
                sources_successful=len([r for r in results.values() if r.get('success', False)]),
                total_items=collected_data.get_total_items(),
                data_quality_score=collected_data.calculate_quality_score()
            )
        
        return collected_data
    
    def _execute_parallel_collection(self, tasks: List[Dict[str, Any]], 
                                   max_concurrent: int) -> Dict[str, Dict[str, Any]]:
        """Execute collection tasks in parallel with resource limits and error handling."""
        results = {}
        
        # Use ThreadPoolExecutor for parallel execution
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            # Submit all tasks
            future_to_task = {}
            for task in tasks:
                future = executor.submit(self._execute_single_collection_with_error_handling, task)
                future_to_task[future] = task['name']
            
            # Collect results as they complete
            for future in as_completed(future_to_task):
                task_name = future_to_task[future]
                try:
                    result = future.result(timeout=30)  # 30 second timeout per task
                    results[task_name] = result
                    
                    if result['success']:
                        self.logger.info(f"Collection completed successfully for {task_name}")
                    else:
                        self.logger.warning(f"Collection failed for {task_name}: {result.get('error')}")
                    
                except Exception as e:
                    results[task_name] = {
                        'success': False,
                        'data': None,
                        'error': str(e),
                        'completion_time': datetime.now(),
                        'error_category': 'timeout' if 'timeout' in str(e).lower() else 'system'
                    }
                    self.logger.error(f"Collection task {task_name} failed with exception: {e}")
        
        return results
    
    def _execute_single_collection_with_error_handling(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single collection task with comprehensive error handling."""
        circuit_breaker = self.circuit_manager.get_breaker(task['name'])
        
        try:
            # Check circuit breaker state
            if not circuit_breaker.can_execute():
                raise Exception(f"Circuit breaker open for {task['name']}")
            
            # Execute the collection with circuit breaker protection
            with circuit_breaker:
                result = self._execute_single_collection(task)
            
            return {
                'success': True,
                'data': result,
                'error': None,
                'completion_time': datetime.now(),
                'error_category': None,
                'circuit_breaker_state': circuit_breaker.state.value
            }
            
        except Exception as e:
            # Classify the error
            error_info = self.error_handler._classify_error(e, task['name'])
            
            # Record failure in circuit breaker
            circuit_breaker.record_failure()
            
            # Determine if we should attempt graceful degradation
            degradation_result = self._attempt_graceful_degradation(task, e, error_info)
            
            return {
                'success': False,
                'data': degradation_result.get('fallback_data'),
                'error': str(e),
                'completion_time': datetime.now(),
                'error_category': error_info.category.value,
                'error_severity': error_info.severity.value,
                'recovery_suggestions': error_info.recovery_suggestions,
                'circuit_breaker_state': circuit_breaker.state.value,
                'degradation_applied': degradation_result.get('degradation_applied', False),
                'degradation_level': degradation_result.get('degradation_level', 'none')
            }
    
    def _attempt_graceful_degradation(self, task: Dict[str, Any], error: Exception, 
                                     error_info) -> Dict[str, Any]:
        """Attempt graceful degradation for failed collection tasks."""
        
        degradation_result = {
            'degradation_applied': False,
            'degradation_level': 'none',
            'fallback_data': None
        }
        
        # Check if degradation is possible based on error type
        if error_info.severity in ['low', 'medium']:
            # For non-critical errors, try to provide minimal fallback data
            task_name = task['name']
            username = task['args'][0] if task['args'] else 'unknown'
            
            if task_name == 'twitter_api':
                # Create minimal TwitterAPI fallback data
                from ..models.collected_data import TwitterAPIData
                fallback_data = TwitterAPIData(
                    profile={
                        "username": username,
                        "display_name": username,
                        "description": f"Profile for {username} (limited data available)",
                        "followers_count": 0,
                        "following_count": 0,
                        "verified": False
                    },
                    tweets=[],
                    followings=[],
                    collection_success=False,
                    error_message=f"TwitterAPI collection failed: {str(error)}",
                    metadata={
                        "fallback_mode": True,
                        "degradation_reason": error_info.category.value,
                        "original_error": str(error)
                    }
                )
                degradation_result.update({
                    'degradation_applied': True,
                    'degradation_level': 'minimal',
                    'fallback_data': fallback_data
                })
                
            elif task_name == 'scrapebadger':
                # Create minimal ScrapeBadger fallback data
                from ..models.collected_data import ScrapeBadgerData
                fallback_data = ScrapeBadgerData(
                    profile={
                        "username": username,
                        "user_id": f"fallback_{username}",
                        "description": f"Profile for {username} (ScrapeBadger unavailable)"
                    },
                    tweets=[],
                    highlights=[],
                    collection_success=False,
                    error_message=f"ScrapeBadger collection failed: {str(error)}",
                    metadata={
                        "fallback_mode": True,
                        "degradation_reason": error_info.category.value,
                        "original_error": str(error)
                    }
                )
                degradation_result.update({
                    'degradation_applied': True,
                    'degradation_level': 'minimal',
                    'fallback_data': fallback_data
                })
        
        return degradation_result
    
    def _execute_single_collection(self, task: Dict[str, Any]) -> Any:
        """Execute a single collection task."""
        collector = task['collector']
        method_name = task['method']
        args = task['args']
        
        # Get the method from the collector
        method = getattr(collector, method_name)
        
        # Execute the collection
        return method(*args)
    
    def _combine_collection_results(self, results: Dict[str, Dict[str, Any]], 
                                  username: str, workflow_id: str = None) -> CollectedData:
        """Combine results from multiple collection sources with partial success handling."""
        
        # Extract successful results and handle partial success
        twitter_data = None
        scrapebadger_data = None
        errors = {}
        degradation_info = {}
        
        # Process TwitterAPI result
        twitter_result = results.get('twitter_api', {})
        if twitter_result.get('success'):
            twitter_data = twitter_result['data']
        elif twitter_result.get('degradation_applied'):
            # Use fallback data from graceful degradation
            twitter_data = twitter_result['data']
            degradation_info['twitter_api'] = {
                'level': twitter_result.get('degradation_level', 'minimal'),
                'reason': twitter_result.get('error_category', 'unknown')
            }
        else:
            errors['twitter_api'] = twitter_result.get('error', 'Unknown error')
        
        # Process ScrapeBadger result
        scrapebadger_result = results.get('scrapebadger', {})
        if scrapebadger_result.get('success'):
            scrapebadger_data = scrapebadger_result['data']
        elif scrapebadger_result.get('degradation_applied'):
            # Use fallback data from graceful degradation
            scrapebadger_data = scrapebadger_result['data']
            degradation_info['scrapebadger'] = {
                'level': scrapebadger_result.get('degradation_level', 'minimal'),
                'reason': scrapebadger_result.get('error_category', 'unknown')
            }
        else:
            errors['scrapebadger'] = scrapebadger_result.get('error', 'Unknown error')
        
        # Handle complete failure scenario
        if twitter_data is None and scrapebadger_data is None:
            # Create emergency fallback data
            twitter_data = self._create_emergency_fallback_data(username, errors)
        
        # Create combined data structure
        collected_data = CollectedData(
            username=username,
            twitter_api_data=twitter_data,
            scrapebadger_data=scrapebadger_data,
            collection_timestamp=datetime.now()
        )
        
        # Calculate success metrics
        successful_sources = len([r for r in results.values() if r.get('success')])
        degraded_sources = len([r for r in results.values() if r.get('degradation_applied')])
        total_sources = len(results)
        
        # Add comprehensive metadata
        metadata = {
            'workflow_id': workflow_id,
            'collection_method': 'parallel',
            'sources_attempted': list(results.keys()),
            'sources_successful': [name for name, result in results.items() if result.get('success')],
            'sources_degraded': [name for name, result in results.items() if result.get('degradation_applied')],
            'sources_failed': [name for name, result in results.items() 
                             if not result.get('success') and not result.get('degradation_applied')],
            'errors': errors,
            'degradation_info': degradation_info,
            'resource_limits': self.resource_limits,
            'partial_success': successful_sources > 0 or degraded_sources > 0,
            'success_rate': (successful_sources + degraded_sources * 0.5) / total_sources,
            'circuit_breaker_states': {
                name: result.get('circuit_breaker_state', 'unknown') 
                for name, result in results.items()
            },
            'network_health_report': self.network_manager.get_network_health_report()
        }
        
        # Add metadata to individual data objects if they exist
        if twitter_data and hasattr(twitter_data, 'metadata'):
            if not twitter_data.metadata:
                twitter_data.metadata = {}
            twitter_data.metadata.update(metadata)
        
        if scrapebadger_data and hasattr(scrapebadger_data, 'metadata'):
            if not scrapebadger_data.metadata:
                scrapebadger_data.metadata = {}
            scrapebadger_data.metadata.update(metadata)
        
        # Calculate data quality score with degradation consideration
        base_quality = collected_data.calculate_quality_score()
        degradation_penalty = len(degradation_info) * 0.1  # 10% penalty per degraded source
        collected_data.data_quality_score = max(base_quality - degradation_penalty, 0.0)
        
        # Log comprehensive results
        self.logger.info(
            f"Combined collection results for {username}: "
            f"{successful_sources} successful, {degraded_sources} degraded, "
            f"{total_sources - successful_sources - degraded_sources} failed. "
            f"Quality score: {collected_data.data_quality_score:.2f}"
        )
        
        if degradation_info:
            self.logger.warning(f"Graceful degradation applied: {degradation_info}")
        
        return collected_data
    
    def _create_emergency_fallback_data(self, username: str, errors: Dict[str, str]):
        """Create emergency fallback data when all sources fail."""
        from ..models.collected_data import TwitterAPIData
        
        return TwitterAPIData(
            profile={
                "username": username,
                "display_name": username,
                "description": f"Emergency fallback profile for {username}",
                "followers_count": 0,
                "following_count": 0,
                "verified": False,
                "emergency_fallback": True
            },
            tweets=[],
            followings=[],
            collection_success=False,
            error_message="All data collection sources failed",
            metadata={
                "emergency_fallback": True,
                "all_sources_failed": True,
                "source_errors": errors,
                "fallback_timestamp": datetime.now().isoformat()
            }
        )


class AdaptiveParallelCollector:
    """Adaptive parallel collector that adjusts based on system resources and performance."""
    
    def __init__(self):
        self.logger = logging.getLogger("adaptive_parallel_collector")
        self.workflow_monitor = get_workflow_monitor()
        self.circuit_manager = get_circuit_manager()
        self.error_handler = GracefulDegradationHandler()
        self.network_manager = get_network_manager()
        
        # Performance tracking
        self.performance_history = []
        self.max_history = 100
    
    def collect_with_adaptation(self, username: str, workflow_id: str = None) -> CollectedData:
        """
        Collect data with adaptive parallel execution based on system state.
        
        Args:
            username: Username to collect data for
            workflow_id: Optional workflow ID for tracking
            
        Returns:
            CollectedData with adaptive collection results
        """
        start_time = time.time()
        
        # Get current resource limits and system state
        resource_limits = get_current_resource_limits()
        circuit_stats = self.circuit_manager.get_all_stats()
        network_health = self.network_manager.get_network_health_report()
        
        # Determine optimal collection strategy
        strategy = self._determine_collection_strategy(resource_limits, circuit_stats, network_health)
        
        self.logger.info(f"Using collection strategy: {strategy['name']} for {username}")
        
        # Execute collection based on strategy
        if strategy['type'] == 'parallel':
            workflow = ParallelDataCollectionWorkflow()
            result = workflow.collect_data_parallel(username, workflow_id)
        elif strategy['type'] == 'sequential':
            result = self._collect_sequential(username, workflow_id, strategy)
        else:  # fallback
            result = self._collect_fallback(username, workflow_id, strategy)
        
        # Record performance metrics
        end_time = time.time()
        duration = end_time - start_time
        
        self._record_performance(strategy, duration, result.collection_success, result.data_quality_score)
        
        return result
    
    def _determine_collection_strategy(self, resource_limits: Dict[str, Any], 
                                     circuit_stats: Dict[str, Any],
                                     network_health: Dict[str, Any]) -> Dict[str, Any]:
        """Determine the optimal collection strategy based on current conditions."""
        
        # Check circuit breaker states
        twitter_healthy = circuit_stats.get('twitter_api_collector', {}).get('state') != 'open'
        scrapebadger_healthy = circuit_stats.get('scrapebadger_collector', {}).get('state') != 'open'
        
        # Check network health
        twitter_network_healthy = network_health.get('services', {}).get('twitter_api', {}).get('health', {}).get('status') != 'unhealthy'
        scrapebadger_network_healthy = network_health.get('services', {}).get('scrapebadger', {}).get('health', {}).get('status') != 'unhealthy'
        
        # Combine health checks
        twitter_overall_healthy = twitter_healthy and twitter_network_healthy
        scrapebadger_overall_healthy = scrapebadger_healthy and scrapebadger_network_healthy
        
        # Check resource availability
        max_concurrent = resource_limits.get('max_concurrent', 2)
        quality_mode = resource_limits.get('quality_mode', 'balanced')
        
        # Determine strategy
        if twitter_overall_healthy and scrapebadger_overall_healthy and max_concurrent >= 2:
            return {
                'name': 'full_parallel',
                'type': 'parallel',
                'sources': ['twitter_api', 'scrapebadger'],
                'concurrent_limit': min(max_concurrent, 2),
                'timeout': 30 if quality_mode == 'fast' else 60
            }
        elif twitter_overall_healthy or scrapebadger_overall_healthy:
            available_source = 'twitter_api' if twitter_overall_healthy else 'scrapebadger'
            return {
                'name': 'single_source',
                'type': 'sequential',
                'sources': [available_source],
                'timeout': 45
            }
        else:
            return {
                'name': 'fallback_mode',
                'type': 'fallback',
                'sources': [],
                'timeout': 15
            }
    
    def _collect_sequential(self, username: str, workflow_id: str, 
                          strategy: Dict[str, Any]) -> CollectedData:
        """Collect data sequentially when parallel execution is not optimal."""
        
        self.logger.info(f"Executing sequential collection for {username}")
        
        twitter_data = None
        scrapebadger_data = None
        errors = {}
        
        # Collect from available sources sequentially
        if 'twitter_api' in strategy['sources']:
            try:
                collector = TwitterAPICollector()
                twitter_data = collector.collect_profile_data(username, workflow_id)
            except Exception as e:
                errors['twitter_api'] = str(e)
                self.logger.error(f"Sequential Twitter collection failed: {e}")
        
        if 'scrapebadger' in strategy['sources']:
            try:
                collector = ScrapeBadgerCollector()
                scrapebadger_data = collector.collect_enriched_data(username, workflow_id)
            except Exception as e:
                errors['scrapebadger'] = str(e)
                self.logger.error(f"Sequential ScrapeBadger collection failed: {e}")
        
        # Create combined result
        collected_data = CollectedData(
            username=username,
            twitter_api_data=twitter_data,
            scrapebadger_data=scrapebadger_data,
            collection_timestamp=datetime.now()
        )
        
        # Add metadata
        metadata = {
            'workflow_id': workflow_id,
            'collection_method': 'sequential',
            'strategy': strategy,
            'errors': errors
        }
        
        if twitter_data and hasattr(twitter_data, 'metadata'):
            if not twitter_data.metadata:
                twitter_data.metadata = {}
            twitter_data.metadata.update(metadata)
        
        if scrapebadger_data and hasattr(scrapebadger_data, 'metadata'):
            if not scrapebadger_data.metadata:
                scrapebadger_data.metadata = {}
            scrapebadger_data.metadata.update(metadata)
        
        collected_data.data_quality_score = collected_data.calculate_quality_score()
        
        return collected_data
    
    def _collect_fallback(self, username: str, workflow_id: str, 
                         strategy: Dict[str, Any]) -> CollectedData:
        """Fallback collection when all primary sources are unavailable."""
        
        self.logger.warning(f"Using fallback collection for {username}")
        
        # Create minimal data structure with basic information
        fallback_profile = {
            "username": username,
            "display_name": username,
            "description": f"Profile for {username} (limited data available)",
            "collection_method": "fallback"
        }
        
        # Create fallback TwitterAPI data
        twitter_data = TwitterAPIData(
            profile=fallback_profile,
            tweets=[],
            followings=[],
            collection_success=False,
            error_message="Primary collection sources unavailable",
            collection_timestamp=datetime.now()
        )
        
        collected_data = CollectedData(
            username=username,
            twitter_api_data=twitter_data,
            scrapebadger_data=None,
            collection_timestamp=datetime.now()
        )
        
        # Add metadata
        metadata = {
            'workflow_id': workflow_id,
            'collection_method': 'fallback',
            'strategy': strategy,
            'warning': 'Limited data available due to service unavailability'
        }
        
        if twitter_data and hasattr(twitter_data, 'metadata'):
            if not twitter_data.metadata:
                twitter_data.metadata = {}
            twitter_data.metadata.update(metadata)
        
        collected_data.data_quality_score = 0.1  # Very low quality score
        
        return collected_data
    
    def _record_performance(self, strategy: Dict[str, Any], duration: float, 
                          success: bool, quality_score: float):
        """Record performance metrics for strategy optimization."""
        
        performance_record = {
            'timestamp': datetime.now(),
            'strategy': strategy['name'],
            'duration': duration,
            'success': success,
            'quality_score': quality_score,
            'sources_count': len(strategy.get('sources', []))
        }
        
        self.performance_history.append(performance_record)
        
        # Keep history manageable
        if len(self.performance_history) > self.max_history:
            self.performance_history = self.performance_history[-self.max_history:]
        
        # Log performance
        self.logger.info(
            f"Performance recorded: {strategy['name']} - "
            f"Duration: {duration:.2f}s, Success: {success}, Quality: {quality_score:.2f}"
        )
    
    def get_performance_analytics(self) -> Dict[str, Any]:
        """Get performance analytics for optimization."""
        
        if not self.performance_history:
            return {"message": "No performance data available"}
        
        # Calculate statistics by strategy
        strategy_stats = {}
        for record in self.performance_history:
            strategy_name = record['strategy']
            if strategy_name not in strategy_stats:
                strategy_stats[strategy_name] = {
                    'count': 0,
                    'total_duration': 0,
                    'successes': 0,
                    'total_quality': 0
                }
            
            stats = strategy_stats[strategy_name]
            stats['count'] += 1
            stats['total_duration'] += record['duration']
            stats['successes'] += 1 if record['success'] else 0
            stats['total_quality'] += record['quality_score']
        
        # Calculate averages
        for strategy_name, stats in strategy_stats.items():
            stats['avg_duration'] = stats['total_duration'] / stats['count']
            stats['success_rate'] = stats['successes'] / stats['count']
            stats['avg_quality'] = stats['total_quality'] / stats['count']
        
        return {
            'total_collections': len(self.performance_history),
            'strategy_performance': strategy_stats,
            'recent_performance': self.performance_history[-10:] if len(self.performance_history) >= 10 else self.performance_history
        }


# Factory functions
def create_parallel_workflow() -> ParallelDataCollectionWorkflow:
    """Create a parallel data collection workflow."""
    return ParallelDataCollectionWorkflow()


def create_adaptive_collector() -> AdaptiveParallelCollector:
    """Create an adaptive parallel collector."""
    return AdaptiveParallelCollector()


if __name__ == "__main__":
    # Demo parallel data collection
    import asyncio
    
    async def demo_parallel_collection():
        print("Testing Parallel Data Collection")
        print("=" * 40)
        
        # Test with adaptive collector
        collector = AdaptiveParallelCollector()
        
        test_username = "elonmusk"
        workflow_id = "demo_parallel_123"
        
        print(f"Collecting data for: {test_username}")
        
        start_time = time.time()
        result = collector.collect_with_adaptation(test_username, workflow_id)
        end_time = time.time()
        
        print(f"\nCollection Results:")
        print(f"  Success: {result.collection_success}")
        print(f"  Duration: {end_time - start_time:.2f}s")
        print(f"  Quality Score: {result.data_quality_score:.2f}")
        print(f"  Total Items: {result.get_total_items()}")
        
        if result.twitter_api_data:
            print(f"  Twitter Data: {len(result.twitter_api_data.tweets)} tweets")
        
        if result.scrapebadger_data:
            print(f"  ScrapeBadger Data: {len(result.scrapebadger_data.highlights)} highlights")
        
        # Show performance analytics
        analytics = collector.get_performance_analytics()
        print(f"\nPerformance Analytics:")
        print(f"  Total Collections: {analytics.get('total_collections', 0)}")
        
        if 'strategy_performance' in analytics:
            for strategy, stats in analytics['strategy_performance'].items():
                print(f"  {strategy}: {stats['avg_duration']:.2f}s avg, {stats['success_rate']:.1%} success")
    
    # Run the demo
    asyncio.run(demo_parallel_collection())
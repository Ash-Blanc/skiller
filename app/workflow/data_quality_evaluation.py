"""
Data quality evaluation and scoring algorithms.

This module implements comprehensive data quality assessment for collected profile data,
providing scoring algorithms and quality thresholds for the Advanced Skill Generator Workflow.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from agno.workflow import Workflow, Step, Loop, Condition
from agno.agent import Agent
from app.utils.llm import get_llm_model

from ..models.collected_data import CollectedData, TwitterAPIData, ScrapeBadgerData
from ..utils.workflow_metrics import get_workflow_monitor


class QualityDimension(Enum):
    """Different dimensions of data quality."""
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    RELEVANCE = "relevance"
    UNIQUENESS = "uniqueness"


@dataclass
class QualityMetric:
    """Individual quality metric assessment."""
    dimension: QualityDimension
    score: float  # 0.0 to 1.0
    weight: float  # Importance weight
    details: Dict[str, Any] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class QualityAssessment:
    """Comprehensive quality assessment result."""
    overall_score: float
    weighted_score: float
    metrics: List[QualityMetric]
    data_completeness: float
    source_diversity: float
    content_richness: float
    meets_threshold: bool
    quality_level: str  # "excellent", "good", "acceptable", "poor"
    improvement_suggestions: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class QualityThresholds:
    """Quality thresholds for different use cases."""
    minimum_acceptable: float = 0.4
    good_quality: float = 0.6
    excellent_quality: float = 0.8
    
    # Component-specific thresholds
    min_profile_completeness: float = 0.5
    min_content_volume: float = 0.3
    min_source_diversity: float = 0.2
    min_timeliness: float = 0.4


class DataQualityEvaluator:
    """Evaluates data quality across multiple dimensions."""
    
    def __init__(self, thresholds: Optional[QualityThresholds] = None):
        self.logger = logging.getLogger("data_quality_evaluator")
        self.workflow_monitor = get_workflow_monitor()
        self.thresholds = thresholds or QualityThresholds()
        
        # Quality dimension weights (should sum to 1.0)
        self.dimension_weights = {
            QualityDimension.COMPLETENESS: 0.25,
            QualityDimension.ACCURACY: 0.20,
            QualityDimension.CONSISTENCY: 0.15,
            QualityDimension.TIMELINESS: 0.15,
            QualityDimension.RELEVANCE: 0.15,
            QualityDimension.UNIQUENESS: 0.10
        }
    
    def evaluate_data_quality(self, collected_data: CollectedData, 
                            workflow_id: str = None) -> QualityAssessment:
        """
        Evaluate comprehensive data quality for collected profile data.
        
        Args:
            collected_data: The collected data to evaluate
            workflow_id: Optional workflow ID for tracking
            
        Returns:
            QualityAssessment with detailed quality metrics
        """
        if workflow_id:
            self.workflow_monitor.start_timer(f"{workflow_id}_quality_evaluation")
        
        self.logger.info(f"Evaluating data quality for {collected_data.username}")
        
        # Evaluate each quality dimension
        metrics = []
        
        # Completeness
        completeness_metric = self._evaluate_completeness(collected_data)
        metrics.append(completeness_metric)
        
        # Accuracy
        accuracy_metric = self._evaluate_accuracy(collected_data)
        metrics.append(accuracy_metric)
        
        # Consistency
        consistency_metric = self._evaluate_consistency(collected_data)
        metrics.append(consistency_metric)
        
        # Timeliness
        timeliness_metric = self._evaluate_timeliness(collected_data)
        metrics.append(timeliness_metric)
        
        # Relevance
        relevance_metric = self._evaluate_relevance(collected_data)
        metrics.append(relevance_metric)
        
        # Uniqueness
        uniqueness_metric = self._evaluate_uniqueness(collected_data)
        metrics.append(uniqueness_metric)
        
        # Calculate overall scores
        overall_score = sum(m.score for m in metrics) / len(metrics)
        weighted_score = sum(m.score * self.dimension_weights[m.dimension] for m in metrics)
        
        # Calculate component scores
        data_completeness = completeness_metric.score
        source_diversity = self._calculate_source_diversity(collected_data)
        content_richness = self._calculate_content_richness(collected_data)
        
        # Determine quality level and threshold compliance
        quality_level = self._determine_quality_level(weighted_score)
        meets_threshold = weighted_score >= self.thresholds.minimum_acceptable
        
        # Generate improvement suggestions
        improvement_suggestions = self._generate_improvement_suggestions(metrics, collected_data)
        
        assessment = QualityAssessment(
            overall_score=overall_score,
            weighted_score=weighted_score,
            metrics=metrics,
            data_completeness=data_completeness,
            source_diversity=source_diversity,
            content_richness=content_richness,
            meets_threshold=meets_threshold,
            quality_level=quality_level,
            improvement_suggestions=improvement_suggestions
        )
        
        # Log quality evaluation
        if workflow_id:
            duration = self.workflow_monitor.end_timer(f"{workflow_id}_quality_evaluation", workflow_id)
            self.workflow_monitor.log_step_completion(
                workflow_id,
                "data_quality_evaluation",
                meets_threshold,
                overall_score=overall_score,
                weighted_score=weighted_score,
                quality_level=quality_level,
                data_completeness=data_completeness,
                source_diversity=source_diversity
            )
        
        return assessment
    
    def _evaluate_completeness(self, data: CollectedData) -> QualityMetric:
        """Evaluate data completeness across all sources."""
        score = 0.0
        details = {}
        issues = []
        recommendations = []
        
        # Profile completeness
        profile_score = 0.0
        if data.has_profile_data:
            profile = data.get_consolidated_profile()
            required_fields = ['username', 'description', 'followers_count', 'verified']
            present_fields = sum(1 for field in required_fields if profile.get(field) is not None)
            profile_score = present_fields / len(required_fields)
        else:
            issues.append("No profile data available")
            recommendations.append("Ensure at least one data source provides profile information")
        
        details['profile_completeness'] = profile_score
        
        # Content completeness
        content_score = 0.0
        total_tweets = data.total_tweets
        if total_tweets > 0:
            content_score = min(total_tweets / 20, 1.0)  # 20 tweets = full score
        else:
            issues.append("No tweet content available")
            recommendations.append("Collect recent tweets for content analysis")
        
        details['content_completeness'] = content_score
        
        # Network completeness (followings)
        network_score = 0.0
        total_followings = data.total_followings
        if total_followings > 0:
            network_score = min(total_followings / 50, 1.0)  # 50 followings = full score
        else:
            issues.append("No following data available")
            recommendations.append("Collect following information for network analysis")
        
        details['network_completeness'] = network_score
        
        # Highlights completeness (ScrapeBadger specific)
        highlights_score = 0.0
        if data.has_highlights:
            highlights_count = len(data.get_highlights())
            highlights_score = min(highlights_count / 3, 1.0)  # 3 highlights = full score
        else:
            issues.append("No highlighted content available")
            recommendations.append("Use ScrapeBadger to collect highlighted/pinned content")
        
        details['highlights_completeness'] = highlights_score
        
        # Overall completeness score
        score = (profile_score * 0.3 + content_score * 0.4 + 
                network_score * 0.2 + highlights_score * 0.1)
        
        return QualityMetric(
            dimension=QualityDimension.COMPLETENESS,
            score=score,
            weight=self.dimension_weights[QualityDimension.COMPLETENESS],
            details=details,
            issues=issues,
            recommendations=recommendations
        )
    
    def _evaluate_accuracy(self, data: CollectedData) -> QualityMetric:
        """Evaluate data accuracy and consistency across sources."""
        score = 0.8  # Default high score, reduced for detected issues
        details = {}
        issues = []
        recommendations = []
        
        # Cross-source consistency check
        if data.has_both_sources:
            twitter_profile = data.twitter_api_data.profile if data.twitter_api_data else {}
            scrapebadger_profile = data.scrapebadger_data.profile if data.scrapebadger_data else {}
            
            # Check username consistency
            twitter_username = twitter_profile.get('username', '').lower()
            scrapebadger_username = scrapebadger_profile.get('username', '').lower()
            
            if twitter_username and scrapebadger_username and twitter_username != scrapebadger_username:
                score -= 0.2
                issues.append("Username mismatch between sources")
                recommendations.append("Verify username consistency across data sources")
            
            # Check follower count consistency (allow 10% variance)
            twitter_followers = twitter_profile.get('followers_count', 0)
            scrapebadger_followers = scrapebadger_profile.get('followers_count', 0)
            
            if twitter_followers > 0 and scrapebadger_followers > 0:
                variance = abs(twitter_followers - scrapebadger_followers) / max(twitter_followers, scrapebadger_followers)
                if variance > 0.1:  # More than 10% difference
                    score -= 0.1
                    issues.append(f"Follower count variance: {variance:.1%}")
                    recommendations.append("Check for data collection timing differences")
            
            details['cross_source_consistency'] = 1.0 - len(issues) * 0.1
        
        # Data format validation
        format_score = 1.0
        
        # Check tweet data format
        all_tweets = data.get_all_tweets(deduplicate=False)
        for tweet in all_tweets[:5]:  # Check first 5 tweets
            required_fields = ['id', 'text', 'created_at']
            missing_fields = [f for f in required_fields if not tweet.get(f)]
            if missing_fields:
                format_score -= 0.1
                issues.append(f"Tweet missing fields: {missing_fields}")
        
        details['format_accuracy'] = format_score
        score = min(score, score * format_score)
        
        return QualityMetric(
            dimension=QualityDimension.ACCURACY,
            score=max(score, 0.0),
            weight=self.dimension_weights[QualityDimension.ACCURACY],
            details=details,
            issues=issues,
            recommendations=recommendations
        )
    
    def _evaluate_consistency(self, data: CollectedData) -> QualityMetric:
        """Evaluate internal data consistency."""
        score = 1.0
        details = {}
        issues = []
        recommendations = []
        
        # Check for duplicate content
        all_tweets = data.get_all_tweets(deduplicate=False)
        unique_tweets = data.get_all_tweets(deduplicate=True)
        
        if len(all_tweets) > len(unique_tweets):
            duplicate_ratio = (len(all_tweets) - len(unique_tweets)) / len(all_tweets)
            score -= duplicate_ratio * 0.3  # Penalize duplicates
            issues.append(f"Duplicate content detected: {duplicate_ratio:.1%}")
            recommendations.append("Improve deduplication logic")
        
        details['content_uniqueness'] = len(unique_tweets) / len(all_tweets) if all_tweets else 1.0
        
        # Check timestamp consistency
        timestamps = []
        for tweet in all_tweets:
            created_at = tweet.get('created_at')
            if created_at:
                try:
                    # Basic timestamp validation
                    if isinstance(created_at, str) and len(created_at) > 10:
                        timestamps.append(created_at)
                except:
                    score -= 0.05
                    issues.append("Invalid timestamp format detected")
        
        details['timestamp_consistency'] = len(timestamps) / len(all_tweets) if all_tweets else 1.0
        
        return QualityMetric(
            dimension=QualityDimension.CONSISTENCY,
            score=max(score, 0.0),
            weight=self.dimension_weights[QualityDimension.CONSISTENCY],
            details=details,
            issues=issues,
            recommendations=recommendations
        )
    
    def _evaluate_timeliness(self, data: CollectedData) -> QualityMetric:
        """Evaluate data timeliness and recency."""
        score = 0.0
        details = {}
        issues = []
        recommendations = []
        
        # Check collection recency
        collection_age = datetime.now() - data.collection_timestamp
        if collection_age.total_seconds() < 3600:  # Less than 1 hour
            recency_score = 1.0
        elif collection_age.total_seconds() < 86400:  # Less than 1 day
            recency_score = 0.8
        elif collection_age.total_seconds() < 604800:  # Less than 1 week
            recency_score = 0.6
        else:
            recency_score = 0.3
            issues.append("Data collection is more than 1 week old")
            recommendations.append("Refresh data collection for current information")
        
        details['collection_recency'] = recency_score
        
        # Check content recency
        all_tweets = data.get_all_tweets()
        recent_tweets = 0
        
        for tweet in all_tweets:
            created_at = tweet.get('created_at')
            if created_at:
                try:
                    # Simple recency check (would need proper date parsing in production)
                    if '2024' in str(created_at):  # Recent year
                        recent_tweets += 1
                except:
                    pass
        
        content_recency = recent_tweets / len(all_tweets) if all_tweets else 0.0
        details['content_recency'] = content_recency
        
        if content_recency < 0.5:
            issues.append("Most content is not recent")
            recommendations.append("Focus on collecting recent tweets and activity")
        
        # Overall timeliness score
        score = (recency_score * 0.6 + content_recency * 0.4)
        
        return QualityMetric(
            dimension=QualityDimension.TIMELINESS,
            score=score,
            weight=self.dimension_weights[QualityDimension.TIMELINESS],
            details=details,
            issues=issues,
            recommendations=recommendations
        )
    
    def _evaluate_relevance(self, data: CollectedData) -> QualityMetric:
        """Evaluate content relevance for skill analysis."""
        score = 0.5  # Default moderate score
        details = {}
        issues = []
        recommendations = []
        
        # Check for professional content indicators
        all_tweets = data.get_all_tweets()
        professional_indicators = [
            'work', 'project', 'team', 'build', 'develop', 'create', 'launch',
            'experience', 'skill', 'expertise', 'professional', 'career'
        ]
        
        relevant_tweets = 0
        for tweet in all_tweets:
            text = tweet.get('text', '').lower()
            if any(indicator in text for indicator in professional_indicators):
                relevant_tweets += 1
        
        relevance_ratio = relevant_tweets / len(all_tweets) if all_tweets else 0.0
        details['professional_content_ratio'] = relevance_ratio
        
        if relevance_ratio > 0.3:
            score = 0.8
        elif relevance_ratio > 0.1:
            score = 0.6
        else:
            score = 0.3
            issues.append("Limited professional/skill-related content")
            recommendations.append("Focus on collecting professional and expertise-related content")
        
        # Check for engagement quality
        high_engagement_tweets = 0
        for tweet in all_tweets:
            engagement = (tweet.get('like_count', 0) + 
                         tweet.get('retweet_count', 0) + 
                         tweet.get('reply_count', 0))
            if engagement > 10:  # Arbitrary threshold
                high_engagement_tweets += 1
        
        engagement_ratio = high_engagement_tweets / len(all_tweets) if all_tweets else 0.0
        details['high_engagement_ratio'] = engagement_ratio
        
        # Adjust score based on engagement
        score = score * (0.7 + engagement_ratio * 0.3)
        
        return QualityMetric(
            dimension=QualityDimension.RELEVANCE,
            score=score,
            weight=self.dimension_weights[QualityDimension.RELEVANCE],
            details=details,
            issues=issues,
            recommendations=recommendations
        )
    
    def _evaluate_uniqueness(self, data: CollectedData) -> QualityMetric:
        """Evaluate content uniqueness and diversity."""
        score = 0.8  # Default high score
        details = {}
        issues = []
        recommendations = []
        
        # Check content diversity
        all_tweets = data.get_all_tweets()
        
        if len(all_tweets) > 1:
            # Simple diversity check based on text length variation
            text_lengths = [len(tweet.get('text', '')) for tweet in all_tweets]
            if text_lengths:
                avg_length = sum(text_lengths) / len(text_lengths)
                length_variance = sum((l - avg_length) ** 2 for l in text_lengths) / len(text_lengths)
                diversity_score = min(length_variance / 1000, 1.0)  # Normalize
                details['content_diversity'] = diversity_score
                
                if diversity_score < 0.3:
                    issues.append("Low content diversity detected")
                    recommendations.append("Collect more varied content types")
        
        # Check for source diversity
        sources = data.available_sources
        source_diversity = len(sources) / 2.0  # Max 2 sources
        details['source_diversity'] = source_diversity
        
        if source_diversity < 0.5:
            score -= 0.2
            issues.append("Limited source diversity")
            recommendations.append("Use multiple data collection sources")
        
        return QualityMetric(
            dimension=QualityDimension.UNIQUENESS,
            score=max(score, 0.0),
            weight=self.dimension_weights[QualityDimension.UNIQUENESS],
            details=details,
            issues=issues,
            recommendations=recommendations
        )
    
    def _calculate_source_diversity(self, data: CollectedData) -> float:
        """Calculate source diversity score."""
        return len(data.available_sources) / 2.0  # Max 2 sources currently
    
    def _calculate_content_richness(self, data: CollectedData) -> float:
        """Calculate content richness score."""
        score = 0.0
        
        # Tweet content
        if data.total_tweets > 0:
            score += min(data.total_tweets / 30, 0.4)  # Max 0.4 for tweets
        
        # Following data
        if data.total_followings > 0:
            score += min(data.total_followings / 100, 0.3)  # Max 0.3 for followings
        
        # Highlights
        if data.has_highlights:
            highlights_count = len(data.get_highlights())
            score += min(highlights_count / 5, 0.3)  # Max 0.3 for highlights
        
        return min(score, 1.0)
    
    def _determine_quality_level(self, score: float) -> str:
        """Determine quality level based on score."""
        if score >= self.thresholds.excellent_quality:
            return "excellent"
        elif score >= self.thresholds.good_quality:
            return "good"
        elif score >= self.thresholds.minimum_acceptable:
            return "acceptable"
        else:
            return "poor"
    
    def _generate_improvement_suggestions(self, metrics: List[QualityMetric], 
                                        data: CollectedData) -> List[str]:
        """Generate prioritized improvement suggestions."""
        suggestions = []
        
        # Collect all recommendations from metrics
        all_recommendations = []
        for metric in metrics:
            for rec in metric.recommendations:
                if rec not in all_recommendations:
                    all_recommendations.append(rec)
        
        # Prioritize based on metric weights and scores
        low_scoring_metrics = [m for m in metrics if m.score < 0.5]
        
        if low_scoring_metrics:
            # Sort by impact (weight * (1 - score))
            low_scoring_metrics.sort(key=lambda m: m.weight * (1 - m.score), reverse=True)
            
            for metric in low_scoring_metrics[:3]:  # Top 3 issues
                suggestions.extend(metric.recommendations[:2])  # Top 2 recommendations per metric
        
        # Add general suggestions based on data state
        if not data.has_both_sources:
            suggestions.append("Enable both TwitterAPI.io and ScrapeBadger for comprehensive data collection")
        
        if data.total_tweets < 10:
            suggestions.append("Collect more recent tweets for better analysis")
        
        if not data.has_highlights:
            suggestions.append("Use ScrapeBadger to collect highlighted/pinned content")
        
        # Remove duplicates while preserving order
        unique_suggestions = []
        for suggestion in suggestions:
            if suggestion not in unique_suggestions:
                unique_suggestions.append(suggestion)
        
        return unique_suggestions[:5]  # Return top 5 suggestions


def evaluate_data_quality(collected_data: CollectedData, 
                         thresholds: Optional[QualityThresholds] = None,
                         workflow_id: str = None) -> QualityAssessment:
    """
    Convenience function for data quality evaluation.
    
    Args:
        collected_data: The collected data to evaluate
        thresholds: Optional custom quality thresholds
        workflow_id: Optional workflow ID for tracking
        
    Returns:
        QualityAssessment with detailed quality metrics
    """
    evaluator = DataQualityEvaluator(thresholds)
    return evaluator.evaluate_data_quality(collected_data, workflow_id)


class QualityEvaluationLoop:
    """Agno Loop implementation for iterative quality evaluation and improvement."""
    
    def __init__(self, max_iterations: int = 3, target_quality: float = 0.6):
        self.logger = logging.getLogger("quality_evaluation_loop")
        self.workflow_monitor = get_workflow_monitor()
        self.max_iterations = max_iterations
        self.target_quality = target_quality
        
        # Create quality evaluation agent
        self.quality_agent = Agent(
            name="Quality Evaluator",
            instructions="""
            You are a data quality evaluator. Analyze the collected profile data and determine:
            1. Overall data quality score (0.0 to 1.0)
            2. Specific areas that need improvement
            3. Whether additional data collection is needed
            4. Recommendations for quality enhancement
            
            Focus on completeness, accuracy, relevance, and timeliness of the data.
            """,
            model=get_llm_model("gpt-4o")
        )
        
        # Create improvement agent
        self.improvement_agent = Agent(
            name="Data Improvement Strategist",
            instructions="""
            You are a data improvement strategist. Based on quality assessment results:
            1. Identify specific data gaps and issues
            2. Recommend targeted collection strategies
            3. Suggest alternative data sources if needed
            4. Prioritize improvement actions by impact
            
            Provide actionable recommendations for enhancing data quality.
            """,
            model=get_llm_model("gpt-4o")
        )
    
    def create_quality_evaluation_workflow(self, username: str) -> Workflow:
        """Create an Agno workflow with quality evaluation loop."""
        
        # Define the quality check condition
        def quality_meets_threshold(context: Dict[str, Any]) -> bool:
            """Check if data quality meets the target threshold."""
            assessment = context.get('quality_assessment')
            if not assessment:
                return False
            
            return (assessment.weighted_score >= self.target_quality and 
                   assessment.meets_threshold)
        
        # Define the iteration limit condition
        def within_iteration_limit(context: Dict[str, Any]) -> bool:
            """Check if we're within the iteration limit."""
            iteration = context.get('iteration', 0)
            return iteration < self.max_iterations
        
        # Create workflow steps
        quality_evaluation_step = Step(
            name="Quality Evaluation",
            agent=self.quality_agent,
            description="Evaluate data quality and identify improvement areas"
        )
        
        improvement_strategy_step = Step(
            name="Improvement Strategy",
            agent=self.improvement_agent,
            description="Develop strategy for data quality improvement"
        )
        
        # Create the loop condition
        continue_condition = Condition(
            name="Continue Quality Loop",
            condition=lambda ctx: (not quality_meets_threshold(ctx) and 
                                 within_iteration_limit(ctx)),
            description="Continue if quality is below threshold and within iteration limit"
        )
        
        # Create the workflow with loop
        workflow = Workflow(
            name=f"Quality Evaluation Loop - {username}",
            steps=[
                Loop(
                    steps=[
                        quality_evaluation_step,
                        improvement_strategy_step
                    ],
                    condition=continue_condition,
                    max_iterations=self.max_iterations,
                    name="Quality Improvement Loop",
                    description="Iteratively evaluate and improve data quality"
                )
            ]
        )
        
        return workflow
    
    def execute_quality_loop(self, collected_data: CollectedData, 
                           workflow_id: str = None) -> Dict[str, Any]:
        """
        Execute the quality evaluation loop with iterative improvement.
        
        Args:
            collected_data: The collected data to evaluate and improve
            workflow_id: Optional workflow ID for tracking
            
        Returns:
            Dictionary with final assessment and improvement history
        """
        if workflow_id:
            self.workflow_monitor.start_timer(f"{workflow_id}_quality_loop")
        
        self.logger.info(f"Starting quality evaluation loop for {collected_data.username}")
        
        # Initialize loop context
        context = {
            'username': collected_data.username,
            'collected_data': collected_data,
            'iteration': 0,
            'assessments': [],
            'improvements': [],
            'workflow_id': workflow_id
        }
        
        # Execute iterative quality evaluation
        final_assessment = None
        
        for iteration in range(self.max_iterations):
            context['iteration'] = iteration
            
            self.logger.info(f"Quality evaluation iteration {iteration + 1}/{self.max_iterations}")
            
            # Evaluate current data quality
            evaluator = DataQualityEvaluator()
            assessment = evaluator.evaluate_data_quality(collected_data, workflow_id)
            context['assessments'].append(assessment)
            context['quality_assessment'] = assessment
            
            self.logger.info(
                f"Iteration {iteration + 1} quality score: {assessment.weighted_score:.2f} "
                f"(target: {self.target_quality:.2f})"
            )
            
            # Check if quality meets threshold
            if assessment.weighted_score >= self.target_quality and assessment.meets_threshold:
                self.logger.info("Quality threshold met, stopping loop")
                final_assessment = assessment
                break
            
            # Generate improvement recommendations
            improvement_suggestions = self._generate_improvement_plan(assessment, context)
            context['improvements'].append(improvement_suggestions)
            
            # Apply improvements if possible (in a real implementation, this would
            # trigger additional data collection or processing)
            improved_data = self._apply_improvements(collected_data, improvement_suggestions)
            if improved_data != collected_data:
                collected_data = improved_data
                context['collected_data'] = collected_data
            
            final_assessment = assessment
        
        # Log final results
        if workflow_id:
            duration = self.workflow_monitor.end_timer(f"{workflow_id}_quality_loop", workflow_id)
            self.workflow_monitor.log_step_completion(
                workflow_id,
                "quality_evaluation_loop",
                final_assessment.meets_threshold if final_assessment else False,
                iterations_completed=context['iteration'] + 1,
                final_quality_score=final_assessment.weighted_score if final_assessment else 0.0,
                quality_improved=len(context['assessments']) > 1 and 
                               context['assessments'][-1].weighted_score > context['assessments'][0].weighted_score
            )
        
        return {
            'final_assessment': final_assessment,
            'iterations_completed': context['iteration'] + 1,
            'quality_history': context['assessments'],
            'improvement_history': context['improvements'],
            'quality_improved': (len(context['assessments']) > 1 and 
                               context['assessments'][-1].weighted_score > context['assessments'][0].weighted_score),
            'target_reached': (final_assessment.weighted_score >= self.target_quality 
                             if final_assessment else False)
        }
    
    def _generate_improvement_plan(self, assessment: QualityAssessment, 
                                 context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate specific improvement plan based on quality assessment."""
        
        improvement_plan = {
            'timestamp': datetime.now(),
            'iteration': context['iteration'],
            'current_score': assessment.weighted_score,
            'target_score': self.target_quality,
            'priority_areas': [],
            'specific_actions': [],
            'estimated_impact': {}
        }
        
        # Identify priority improvement areas
        low_scoring_metrics = [m for m in assessment.metrics if m.score < 0.5]
        low_scoring_metrics.sort(key=lambda m: m.weight * (1 - m.score), reverse=True)
        
        for metric in low_scoring_metrics[:3]:  # Top 3 priority areas
            improvement_plan['priority_areas'].append({
                'dimension': metric.dimension.value,
                'current_score': metric.score,
                'weight': metric.weight,
                'impact_potential': metric.weight * (1 - metric.score),
                'issues': metric.issues,
                'recommendations': metric.recommendations
            })
        
        # Generate specific actions
        if assessment.data_completeness < 0.5:
            improvement_plan['specific_actions'].append({
                'action': 'enhance_data_collection',
                'description': 'Collect additional profile and content data',
                'priority': 'high',
                'estimated_impact': 0.2
            })
        
        if assessment.source_diversity < 0.5:
            improvement_plan['specific_actions'].append({
                'action': 'diversify_sources',
                'description': 'Enable additional data collection sources',
                'priority': 'medium',
                'estimated_impact': 0.15
            })
        
        if assessment.content_richness < 0.4:
            improvement_plan['specific_actions'].append({
                'action': 'collect_rich_content',
                'description': 'Focus on collecting high-quality, relevant content',
                'priority': 'high',
                'estimated_impact': 0.25
            })
        
        return improvement_plan
    
    def _apply_improvements(self, collected_data: CollectedData, 
                          improvement_plan: Dict[str, Any]) -> CollectedData:
        """Apply improvements to collected data (simulation for now)."""
        
        # In a real implementation, this would trigger additional data collection
        # or processing based on the improvement plan. For now, we simulate
        # minor improvements to demonstrate the loop functionality.
        
        improved_data = collected_data
        
        for action in improvement_plan.get('specific_actions', []):
            if action['action'] == 'enhance_data_collection':
                # Simulate adding some basic profile information if missing
                if improved_data.twitter_api_data and improved_data.twitter_api_data.profile:
                    profile = improved_data.twitter_api_data.profile
                    if not profile.get('description'):
                        profile['description'] = f"Enhanced profile for {improved_data.username}"
                    if not profile.get('location'):
                        profile['location'] = "Location enhanced via quality loop"
        
        return improved_data


def create_quality_evaluation_loop(max_iterations: int = 3, 
                                 target_quality: float = 0.6) -> QualityEvaluationLoop:
    """Factory function to create a quality evaluation loop."""
    return QualityEvaluationLoop(max_iterations, target_quality)


if __name__ == "__main__":
    # Demo data quality evaluation with loop
    from ..models.collected_data import create_collected_data, TwitterAPIData, ScrapeBadgerData
    
    # Create sample data for testing
    twitter_data = TwitterAPIData(
        profile={
            "username": "testuser",
            "description": "Test user for quality evaluation",
            "followers_count": 1000,
            "verified": False
        },
        tweets=[
            {"id": "1", "text": "Working on a new project", "like_count": 10, "created_at": "2024-01-15"},
            {"id": "2", "text": "Building something amazing", "like_count": 5, "created_at": "2024-01-14"}
        ],
        followings=[
            {"username": "expert1", "verified": True},
            {"username": "expert2", "verified": False}
        ],
        collection_success=True
    )
    
    scrapebadger_data = ScrapeBadgerData(
        profile={
            "username": "testuser",
            "user_id": "123456",
            "description": "Test user for quality evaluation",
            "followers_count": 1050  # Slight difference for consistency test
        },
        tweets=[
            {"id": "3", "text": "Sharing my expertise in tech", "like_count": 15, "created_at": "2024-01-16"}
        ],
        highlights=[
            {"type": "pinned", "text": "This is what I want to be known for", "id": "pin1"}
        ],
        collection_success=True
    )
    
    collected_data = create_collected_data("testuser", twitter_data, scrapebadger_data)
    
    print("Data Quality Evaluation Demo")
    print("=" * 50)
    
    # Basic evaluation
    evaluator = DataQualityEvaluator()
    assessment = evaluator.evaluate_data_quality(collected_data)
    
    print(f"Initial Quality Assessment:")
    print(f"Overall Score: {assessment.overall_score:.2f}")
    print(f"Weighted Score: {assessment.weighted_score:.2f}")
    print(f"Quality Level: {assessment.quality_level}")
    print(f"Meets Threshold: {assessment.meets_threshold}")
    print(f"Data Completeness: {assessment.data_completeness:.2f}")
    print(f"Source Diversity: {assessment.source_diversity:.2f}")
    print(f"Content Richness: {assessment.content_richness:.2f}")
    
    print(f"\nQuality Metrics:")
    for metric in assessment.metrics:
        print(f"  {metric.dimension.value}: {metric.score:.2f} (weight: {metric.weight:.2f})")
        if metric.issues:
            print(f"    Issues: {', '.join(metric.issues)}")
    
    print(f"\nImprovement Suggestions:")
    for i, suggestion in enumerate(assessment.improvement_suggestions, 1):
        print(f"  {i}. {suggestion}")
    
    # Quality evaluation loop demo
    print(f"\n" + "=" * 50)
    print("Quality Evaluation Loop Demo")
    print("=" * 50)
    
    quality_loop = QualityEvaluationLoop(max_iterations=3, target_quality=0.7)
    loop_result = quality_loop.execute_quality_loop(collected_data, "demo_workflow_123")
    
    print(f"Loop Results:")
    print(f"Iterations Completed: {loop_result['iterations_completed']}")
    print(f"Target Reached: {loop_result['target_reached']}")
    print(f"Quality Improved: {loop_result['quality_improved']}")
    
    if loop_result['final_assessment']:
        final = loop_result['final_assessment']
        print(f"Final Quality Score: {final.weighted_score:.2f}")
        print(f"Final Quality Level: {final.quality_level}")
    
    print(f"\nQuality History:")
    for i, hist_assessment in enumerate(loop_result['quality_history']):
        print(f"  Iteration {i+1}: {hist_assessment.weighted_score:.2f} ({hist_assessment.quality_level})")
    
    if loop_result['improvement_history']:
        print(f"\nImprovement Actions Applied:")
        for i, improvement in enumerate(loop_result['improvement_history']):
            print(f"  Iteration {i+1}: {len(improvement.get('specific_actions', []))} actions")
            for action in improvement.get('specific_actions', [])[:2]:  # Show first 2 actions
                print(f"    - {action['description']} (impact: {action['estimated_impact']:.2f})")
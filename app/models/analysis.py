"""
Analysis result dataclasses for the Advanced Skill Generator Workflow.

This module defines dataclasses for the results of different analysis phases
in the advanced skill generation pipeline, providing structured storage for
expertise extraction, communication style analysis, and insight generation.

Validates Requirements:
- AC3.2: Performs content quality assessment and filtering
- AC3.3: Extracts expertise using advanced prompting techniques
- AC3.4: Analyzes communication style based on writing patterns
- AC3.5: Identifies unique insights from high-engagement content
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field
from enum import Enum


class ConfidenceLevel(Enum):
    """Confidence level categories for analysis results."""
    LOW = "low"          # 0.0 - 0.4
    MEDIUM = "medium"    # 0.4 - 0.7
    HIGH = "high"        # 0.7 - 1.0


class ExpertiseType(Enum):
    """Types of expertise that can be identified."""
    TECHNICAL = "technical"
    DOMAIN_KNOWLEDGE = "domain_knowledge"
    SOFT_SKILLS = "soft_skills"
    INDUSTRY_EXPERIENCE = "industry_experience"
    THOUGHT_LEADERSHIP = "thought_leadership"


class CommunicationTone(Enum):
    """Communication tone categories."""
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    WITTY = "witty"
    TECHNICAL = "technical"
    INSPIRATIONAL = "inspirational"
    EDUCATIONAL = "educational"
    CONVERSATIONAL = "conversational"


class InsightType(Enum):
    """Types of insights that can be generated."""
    UNIQUE_PERSPECTIVE = "unique_perspective"
    NOVEL_FRAMEWORK = "novel_framework"
    CONTRARIAN_VIEW = "contrarian_view"
    SYNTHESIS = "synthesis"
    PREDICTION = "prediction"
    BEST_PRACTICE = "best_practice"


@dataclass
class ExpertiseItem:
    """Individual expertise item with metadata."""
    name: str
    expertise_type: ExpertiseType
    confidence_score: float
    evidence_sources: List[str] = field(default_factory=list)
    supporting_content: List[str] = field(default_factory=list)
    authority_signals: List[str] = field(default_factory=list)
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get confidence level category."""
        if self.confidence_score < 0.4:
            return ConfidenceLevel.LOW
        elif self.confidence_score < 0.7:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.HIGH
    
    def validate(self) -> Dict[str, bool]:
        """Validate expertise item quality."""
        return {
            'has_name': bool(self.name and self.name.strip()),
            'valid_confidence': 0.0 <= self.confidence_score <= 1.0,
            'has_evidence': len(self.evidence_sources) > 0,
            'has_supporting_content': len(self.supporting_content) > 0,
            'sufficient_confidence': self.confidence_score >= 0.5,
        }


@dataclass
class CommunicationPattern:
    """Individual communication pattern with analysis."""
    pattern_name: str
    description: str
    frequency: float  # 0.0 to 1.0
    examples: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get confidence level category."""
        if self.confidence_score < 0.4:
            return ConfidenceLevel.LOW
        elif self.confidence_score < 0.7:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.HIGH
    
    def validate(self) -> Dict[str, bool]:
        """Validate communication pattern quality."""
        return {
            'has_name': bool(self.pattern_name and self.pattern_name.strip()),
            'has_description': bool(self.description and self.description.strip()),
            'valid_frequency': 0.0 <= self.frequency <= 1.0,
            'valid_confidence': 0.0 <= self.confidence_score <= 1.0,
            'has_examples': len(self.examples) > 0,
            'sufficient_confidence': self.confidence_score >= 0.5,
        }


@dataclass
class InsightItem:
    """Individual insight with metadata and validation."""
    content: str
    insight_type: InsightType
    confidence_score: float
    novelty_score: float  # How unique/novel this insight is (0.0 to 1.0)
    evidence_sources: List[str] = field(default_factory=list)
    supporting_content: List[str] = field(default_factory=list)
    engagement_metrics: Dict[str, int] = field(default_factory=dict)
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Get confidence level category."""
        if self.confidence_score < 0.4:
            return ConfidenceLevel.LOW
        elif self.confidence_score < 0.7:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.HIGH
    
    @property
    def is_high_novelty(self) -> bool:
        """Check if this insight has high novelty."""
        return self.novelty_score >= 0.7
    
    def validate(self) -> Dict[str, bool]:
        """Validate insight quality."""
        return {
            'has_content': bool(self.content and self.content.strip()),
            'valid_confidence': 0.0 <= self.confidence_score <= 1.0,
            'valid_novelty': 0.0 <= self.novelty_score <= 1.0,
            'has_evidence': len(self.evidence_sources) > 0,
            'has_supporting_content': len(self.supporting_content) > 0,
            'sufficient_confidence': self.confidence_score >= 0.5,
            'sufficient_novelty': self.novelty_score >= 0.4,
        }


@dataclass
class ExpertiseAnalysis:
    """
    Results of expertise extraction analysis.
    
    This dataclass stores the results of advanced prompting techniques used to
    extract core expertise, skills, and domain knowledge from profile data.
    
    Validates Requirements:
    - AC3.3: Extracts expertise using advanced prompting techniques
    """
    
    # Core analysis results
    core_expertise: List[ExpertiseItem] = field(default_factory=list)
    domain_knowledge: List[str] = field(default_factory=list)
    technical_skills: List[str] = field(default_factory=list)
    soft_skills: List[str] = field(default_factory=list)
    authority_signals: List[str] = field(default_factory=list)
    
    # Confidence and quality metrics
    overall_confidence: float = 0.0
    expertise_confidence: Dict[str, float] = field(default_factory=dict)
    quality_score: float = 0.0
    
    # Source attribution and metadata
    source_attribution: Dict[str, List[str]] = field(default_factory=dict)
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    content_analyzed: Dict[str, int] = field(default_factory=dict)  # Content type -> count
    
    # Analysis metadata
    extraction_method: str = "advanced_prompting"
    prompt_version: Optional[str] = None
    model_used: Optional[str] = None
    
    def __post_init__(self):
        """Calculate derived metrics after initialization."""
        self.overall_confidence = self.calculate_overall_confidence()
        self.quality_score = self.calculate_quality_score()
    
    @property
    def total_expertise_items(self) -> int:
        """Get total number of expertise items identified."""
        return len(self.core_expertise)
    
    @property
    def high_confidence_expertise(self) -> List[ExpertiseItem]:
        """Get expertise items with high confidence (>= 0.7)."""
        return [item for item in self.core_expertise if item.confidence_score >= 0.7]
    
    @property
    def expertise_by_type(self) -> Dict[ExpertiseType, List[ExpertiseItem]]:
        """Group expertise items by type."""
        grouped = {}
        for item in self.core_expertise:
            if item.expertise_type not in grouped:
                grouped[item.expertise_type] = []
            grouped[item.expertise_type].append(item)
        return grouped
    
    def calculate_overall_confidence(self) -> float:
        """
        Calculate overall confidence score for expertise analysis.
        
        Factors:
        - Average confidence of core expertise items (60%)
        - Number of authority signals (20%)
        - Content analysis completeness (20%)
        
        Returns:
            Overall confidence score between 0.0 and 1.0
        """
        if not self.core_expertise:
            return 0.0
        
        # Core expertise confidence (60%)
        avg_expertise_confidence = sum(item.confidence_score for item in self.core_expertise) / len(self.core_expertise)
        expertise_component = avg_expertise_confidence * 0.6
        
        # Authority signals component (20%)
        authority_component = min(len(self.authority_signals) / 5 * 0.2, 0.2)
        
        # Content analysis completeness (20%)
        total_content = sum(self.content_analyzed.values())
        content_component = min(total_content / 20 * 0.2, 0.2)
        
        return min(expertise_component + authority_component + content_component, 1.0)
    
    def calculate_quality_score(self) -> float:
        """
        Calculate quality score based on analysis completeness and validation.
        
        Returns:
            Quality score between 0.0 and 1.0
        """
        if not self.core_expertise:
            return 0.0
        
        # Validation scores for all expertise items
        validation_scores = []
        for item in self.core_expertise:
            validation = item.validate()
            score = sum(1 for result in validation.values() if result) / len(validation)
            validation_scores.append(score)
        
        # Average validation score
        avg_validation = sum(validation_scores) / len(validation_scores)
        
        # Diversity bonus (having different types of expertise)
        unique_types = len(set(item.expertise_type for item in self.core_expertise))
        diversity_bonus = min(unique_types / len(ExpertiseType) * 0.2, 0.2)
        
        return min(avg_validation * 0.8 + diversity_bonus, 1.0)
    
    def add_expertise_item(self, 
                          name: str, 
                          expertise_type: ExpertiseType, 
                          confidence_score: float,
                          evidence_sources: List[str] = None,
                          supporting_content: List[str] = None,
                          authority_signals: List[str] = None) -> ExpertiseItem:
        """
        Add a new expertise item to the analysis.
        
        Args:
            name: Name/description of the expertise
            expertise_type: Type of expertise
            confidence_score: Confidence score (0.0 to 1.0)
            evidence_sources: Sources that support this expertise
            supporting_content: Content that demonstrates this expertise
            authority_signals: Signals that indicate authority in this area
            
        Returns:
            The created ExpertiseItem
        """
        item = ExpertiseItem(
            name=name,
            expertise_type=expertise_type,
            confidence_score=confidence_score,
            evidence_sources=evidence_sources or [],
            supporting_content=supporting_content or [],
            authority_signals=authority_signals or []
        )
        
        self.core_expertise.append(item)
        self.expertise_confidence[name] = confidence_score
        
        # Update derived metrics
        self.overall_confidence = self.calculate_overall_confidence()
        self.quality_score = self.calculate_quality_score()
        
        return item
    
    def get_expertise_summary(self) -> Dict[str, Any]:
        """
        Get a summary of expertise analysis results.
        
        Returns:
            Dictionary with expertise statistics and insights
        """
        return {
            'total_expertise_items': self.total_expertise_items,
            'high_confidence_count': len(self.high_confidence_expertise),
            'expertise_by_type': {
                expertise_type.value: len(items) 
                for expertise_type, items in self.expertise_by_type.items()
            },
            'overall_confidence': self.overall_confidence,
            'quality_score': self.quality_score,
            'authority_signals_count': len(self.authority_signals),
            'content_analyzed': self.content_analyzed,
            'top_expertise': [
                {
                    'name': item.name,
                    'type': item.expertise_type.value,
                    'confidence': item.confidence_score,
                    'confidence_level': item.confidence_level.value
                }
                for item in sorted(self.core_expertise, key=lambda x: x.confidence_score, reverse=True)[:5]
            ]
        }
    
    def validate_analysis(self) -> Dict[str, bool]:
        """
        Validate the expertise analysis quality and completeness.
        
        Returns:
            Dictionary with validation results
        """
        validations = {
            'has_expertise_items': len(self.core_expertise) > 0,
            'sufficient_expertise': len(self.core_expertise) >= 3,
            'has_high_confidence_items': len(self.high_confidence_expertise) > 0,
            'has_authority_signals': len(self.authority_signals) > 0,
            'confidence_above_threshold': self.overall_confidence >= 0.6,
            'quality_above_threshold': self.quality_score >= 0.6,
            'has_diverse_expertise': len(self.expertise_by_type) >= 2,
            'has_source_attribution': len(self.source_attribution) > 0,
            'content_analyzed': sum(self.content_analyzed.values()) > 0,
        }
        
        # Validate individual expertise items
        item_validations = []
        for item in self.core_expertise:
            item_validation = item.validate()
            item_validations.append(all(item_validation.values()))
        
        validations['all_items_valid'] = all(item_validations) if item_validations else False
        validations['majority_items_valid'] = (
            sum(item_validations) / len(item_validations) >= 0.8 
            if item_validations else False
        )
        
        return validations


@dataclass
class CommunicationAnalysis:
    """
    Results of communication style analysis.
    
    This dataclass stores the results of analyzing writing patterns, tone,
    and engagement style from the user's content.
    
    Validates Requirements:
    - AC3.4: Analyzes communication style based on writing patterns
    """
    
    # Core analysis results
    primary_tone: CommunicationTone = CommunicationTone.PROFESSIONAL
    secondary_tones: List[CommunicationTone] = field(default_factory=list)
    writing_patterns: List[CommunicationPattern] = field(default_factory=list)
    engagement_style: str = ""
    communication_strengths: List[str] = field(default_factory=list)
    
    # Style metrics
    average_post_length: float = 0.0
    vocabulary_complexity: float = 0.0  # 0.0 to 1.0
    emotional_range: float = 0.0  # 0.0 to 1.0
    interaction_frequency: float = 0.0  # 0.0 to 1.0
    
    # Confidence and quality metrics
    overall_confidence: float = 0.0
    pattern_confidence: Dict[str, float] = field(default_factory=dict)
    quality_score: float = 0.0
    
    # Source attribution and metadata
    source_attribution: Dict[str, List[str]] = field(default_factory=dict)
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    content_analyzed: Dict[str, int] = field(default_factory=dict)
    
    # Analysis metadata
    analysis_method: str = "pattern_analysis"
    sample_size: int = 0
    
    def __post_init__(self):
        """Calculate derived metrics after initialization."""
        self.overall_confidence = self.calculate_overall_confidence()
        self.quality_score = self.calculate_quality_score()
    
    @property
    def total_patterns(self) -> int:
        """Get total number of communication patterns identified."""
        return len(self.writing_patterns)
    
    @property
    def high_confidence_patterns(self) -> List[CommunicationPattern]:
        """Get patterns with high confidence (>= 0.7)."""
        return [pattern for pattern in self.writing_patterns if pattern.confidence_score >= 0.7]
    
    @property
    def dominant_patterns(self) -> List[CommunicationPattern]:
        """Get patterns with high frequency (>= 0.6)."""
        return [pattern for pattern in self.writing_patterns if pattern.frequency >= 0.6]
    
    def calculate_overall_confidence(self) -> float:
        """
        Calculate overall confidence score for communication analysis.
        
        Factors:
        - Average confidence of writing patterns (50%)
        - Sample size adequacy (25%)
        - Analysis completeness (25%)
        
        Returns:
            Overall confidence score between 0.0 and 1.0
        """
        if not self.writing_patterns:
            return 0.0
        
        # Pattern confidence component (50%)
        avg_pattern_confidence = sum(p.confidence_score for p in self.writing_patterns) / len(self.writing_patterns)
        pattern_component = avg_pattern_confidence * 0.5
        
        # Sample size component (25%)
        sample_component = min(self.sample_size / 20 * 0.25, 0.25)
        
        # Analysis completeness component (25%)
        completeness_factors = [
            bool(self.engagement_style),
            len(self.communication_strengths) > 0,
            self.average_post_length > 0,
            self.vocabulary_complexity > 0
        ]
        completeness_score = sum(completeness_factors) / len(completeness_factors)
        completeness_component = completeness_score * 0.25
        
        return min(pattern_component + sample_component + completeness_component, 1.0)
    
    def calculate_quality_score(self) -> float:
        """
        Calculate quality score based on analysis depth and validation.
        
        Returns:
            Quality score between 0.0 and 1.0
        """
        if not self.writing_patterns:
            return 0.0
        
        # Pattern validation scores
        validation_scores = []
        for pattern in self.writing_patterns:
            validation = pattern.validate()
            score = sum(1 for result in validation.values() if result) / len(validation)
            validation_scores.append(score)
        
        avg_validation = sum(validation_scores) / len(validation_scores)
        
        # Depth bonus (having detailed analysis)
        depth_factors = [
            len(self.secondary_tones) > 0,
            len(self.communication_strengths) >= 3,
            self.vocabulary_complexity > 0,
            self.emotional_range > 0,
            self.interaction_frequency > 0
        ]
        depth_bonus = sum(depth_factors) / len(depth_factors) * 0.2
        
        return min(avg_validation * 0.8 + depth_bonus, 1.0)
    
    def add_writing_pattern(self,
                           pattern_name: str,
                           description: str,
                           frequency: float,
                           examples: List[str] = None,
                           confidence_score: float = 0.0) -> CommunicationPattern:
        """
        Add a new writing pattern to the analysis.
        
        Args:
            pattern_name: Name of the communication pattern
            description: Description of the pattern
            frequency: How frequently this pattern appears (0.0 to 1.0)
            examples: Example content showing this pattern
            confidence_score: Confidence in this pattern identification
            
        Returns:
            The created CommunicationPattern
        """
        pattern = CommunicationPattern(
            pattern_name=pattern_name,
            description=description,
            frequency=frequency,
            examples=examples or [],
            confidence_score=confidence_score
        )
        
        self.writing_patterns.append(pattern)
        self.pattern_confidence[pattern_name] = confidence_score
        
        # Update derived metrics
        self.overall_confidence = self.calculate_overall_confidence()
        self.quality_score = self.calculate_quality_score()
        
        return pattern
    
    def get_communication_summary(self) -> Dict[str, Any]:
        """
        Get a summary of communication analysis results.
        
        Returns:
            Dictionary with communication style insights
        """
        return {
            'primary_tone': self.primary_tone.value,
            'secondary_tones': [tone.value for tone in self.secondary_tones],
            'total_patterns': self.total_patterns,
            'high_confidence_patterns': len(self.high_confidence_patterns),
            'dominant_patterns': len(self.dominant_patterns),
            'engagement_style': self.engagement_style,
            'communication_strengths': self.communication_strengths,
            'style_metrics': {
                'average_post_length': self.average_post_length,
                'vocabulary_complexity': self.vocabulary_complexity,
                'emotional_range': self.emotional_range,
                'interaction_frequency': self.interaction_frequency
            },
            'overall_confidence': self.overall_confidence,
            'quality_score': self.quality_score,
            'sample_size': self.sample_size,
            'top_patterns': [
                {
                    'name': pattern.pattern_name,
                    'frequency': pattern.frequency,
                    'confidence': pattern.confidence_score,
                    'confidence_level': pattern.confidence_level.value
                }
                for pattern in sorted(self.writing_patterns, key=lambda x: x.frequency, reverse=True)[:5]
            ]
        }
    
    def validate_analysis(self) -> Dict[str, bool]:
        """
        Validate the communication analysis quality and completeness.
        
        Returns:
            Dictionary with validation results
        """
        validations = {
            'has_writing_patterns': len(self.writing_patterns) > 0,
            'sufficient_patterns': len(self.writing_patterns) >= 3,
            'has_high_confidence_patterns': len(self.high_confidence_patterns) > 0,
            'has_engagement_style': bool(self.engagement_style),
            'has_communication_strengths': len(self.communication_strengths) > 0,
            'confidence_above_threshold': self.overall_confidence >= 0.6,
            'quality_above_threshold': self.quality_score >= 0.6,
            'sufficient_sample_size': self.sample_size >= 10,
            'has_style_metrics': all([
                self.average_post_length > 0,
                self.vocabulary_complexity > 0,
                self.emotional_range > 0
            ]),
            'has_source_attribution': len(self.source_attribution) > 0,
        }
        
        # Validate individual patterns
        pattern_validations = []
        for pattern in self.writing_patterns:
            pattern_validation = pattern.validate()
            pattern_validations.append(all(pattern_validation.values()))
        
        validations['all_patterns_valid'] = all(pattern_validations) if pattern_validations else False
        validations['majority_patterns_valid'] = (
            sum(pattern_validations) / len(pattern_validations) >= 0.8 
            if pattern_validations else False
        )
        
        return validations


@dataclass
class InsightAnalysis:
    """
    Results of insight generation analysis.
    
    This dataclass stores unique insights and value propositions identified
    from high-engagement content and comprehensive profile analysis.
    
    Validates Requirements:
    - AC3.5: Identifies unique insights from high-engagement content
    """
    
    # Core analysis results
    unique_insights: List[InsightItem] = field(default_factory=list)
    value_propositions: List[str] = field(default_factory=list)
    key_differentiators: List[str] = field(default_factory=list)
    thought_leadership_areas: List[str] = field(default_factory=list)
    
    # Insight metrics
    average_novelty_score: float = 0.0
    total_engagement_analyzed: int = 0
    high_engagement_threshold: int = 10
    
    # Confidence and quality metrics
    overall_confidence: float = 0.0
    insight_confidence: Dict[str, float] = field(default_factory=dict)
    quality_score: float = 0.0
    
    # Source attribution and metadata
    source_attribution: Dict[str, List[str]] = field(default_factory=dict)
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    content_analyzed: Dict[str, int] = field(default_factory=dict)
    
    # Analysis metadata
    generation_method: str = "high_engagement_analysis"
    engagement_sources: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate derived metrics after initialization."""
        self.average_novelty_score = self.calculate_average_novelty()
        self.overall_confidence = self.calculate_overall_confidence()
        self.quality_score = self.calculate_quality_score()
    
    @property
    def total_insights(self) -> int:
        """Get total number of insights identified."""
        return len(self.unique_insights)
    
    @property
    def high_confidence_insights(self) -> List[InsightItem]:
        """Get insights with high confidence (>= 0.7)."""
        return [insight for insight in self.unique_insights if insight.confidence_score >= 0.7]
    
    @property
    def high_novelty_insights(self) -> List[InsightItem]:
        """Get insights with high novelty (>= 0.7)."""
        return [insight for insight in self.unique_insights if insight.is_high_novelty]
    
    @property
    def insights_by_type(self) -> Dict[InsightType, List[InsightItem]]:
        """Group insights by type."""
        grouped = {}
        for insight in self.unique_insights:
            if insight.insight_type not in grouped:
                grouped[insight.insight_type] = []
            grouped[insight.insight_type].append(insight)
        return grouped
    
    def calculate_average_novelty(self) -> float:
        """Calculate average novelty score across all insights."""
        if not self.unique_insights:
            return 0.0
        return sum(insight.novelty_score for insight in self.unique_insights) / len(self.unique_insights)
    
    def calculate_overall_confidence(self) -> float:
        """
        Calculate overall confidence score for insight analysis.
        
        Factors:
        - Average confidence of insights (50%)
        - Engagement data quality (25%)
        - Analysis completeness (25%)
        
        Returns:
            Overall confidence score between 0.0 and 1.0
        """
        if not self.unique_insights:
            return 0.0
        
        # Insight confidence component (50%)
        avg_insight_confidence = sum(insight.confidence_score for insight in self.unique_insights) / len(self.unique_insights)
        insight_component = avg_insight_confidence * 0.5
        
        # Engagement data quality component (25%)
        engagement_component = min(self.total_engagement_analyzed / 100 * 0.25, 0.25)
        
        # Analysis completeness component (25%)
        completeness_factors = [
            len(self.value_propositions) > 0,
            len(self.key_differentiators) > 0,
            len(self.thought_leadership_areas) > 0,
            self.average_novelty_score > 0.5
        ]
        completeness_score = sum(completeness_factors) / len(completeness_factors)
        completeness_component = completeness_score * 0.25
        
        return min(insight_component + engagement_component + completeness_component, 1.0)
    
    def calculate_quality_score(self) -> float:
        """
        Calculate quality score based on insight validation and novelty.
        
        Returns:
            Quality score between 0.0 and 1.0
        """
        if not self.unique_insights:
            return 0.0
        
        # Insight validation scores
        validation_scores = []
        for insight in self.unique_insights:
            validation = insight.validate()
            score = sum(1 for result in validation.values() if result) / len(validation)
            validation_scores.append(score)
        
        avg_validation = sum(validation_scores) / len(validation_scores)
        
        # Novelty bonus
        novelty_bonus = min(self.average_novelty_score * 0.3, 0.3)
        
        # Diversity bonus (having different types of insights)
        unique_types = len(set(insight.insight_type for insight in self.unique_insights))
        diversity_bonus = min(unique_types / len(InsightType) * 0.2, 0.2)
        
        return min(avg_validation * 0.5 + novelty_bonus + diversity_bonus, 1.0)
    
    def add_insight(self,
                   content: str,
                   insight_type: InsightType,
                   confidence_score: float,
                   novelty_score: float,
                   evidence_sources: List[str] = None,
                   supporting_content: List[str] = None,
                   engagement_metrics: Dict[str, int] = None) -> InsightItem:
        """
        Add a new insight to the analysis.
        
        Args:
            content: The insight content/description
            insight_type: Type of insight
            confidence_score: Confidence in this insight (0.0 to 1.0)
            novelty_score: How novel/unique this insight is (0.0 to 1.0)
            evidence_sources: Sources that support this insight
            supporting_content: Content that demonstrates this insight
            engagement_metrics: Engagement metrics for supporting content
            
        Returns:
            The created InsightItem
        """
        insight = InsightItem(
            content=content,
            insight_type=insight_type,
            confidence_score=confidence_score,
            novelty_score=novelty_score,
            evidence_sources=evidence_sources or [],
            supporting_content=supporting_content or [],
            engagement_metrics=engagement_metrics or {}
        )
        
        self.unique_insights.append(insight)
        self.insight_confidence[content[:50]] = confidence_score  # Use first 50 chars as key
        
        # Update derived metrics
        self.average_novelty_score = self.calculate_average_novelty()
        self.overall_confidence = self.calculate_overall_confidence()
        self.quality_score = self.calculate_quality_score()
        
        return insight
    
    def get_insight_summary(self) -> Dict[str, Any]:
        """
        Get a summary of insight analysis results.
        
        Returns:
            Dictionary with insight statistics and key findings
        """
        return {
            'total_insights': self.total_insights,
            'high_confidence_count': len(self.high_confidence_insights),
            'high_novelty_count': len(self.high_novelty_insights),
            'insights_by_type': {
                insight_type.value: len(insights) 
                for insight_type, insights in self.insights_by_type.items()
            },
            'value_propositions_count': len(self.value_propositions),
            'key_differentiators_count': len(self.key_differentiators),
            'thought_leadership_areas': self.thought_leadership_areas,
            'average_novelty_score': self.average_novelty_score,
            'overall_confidence': self.overall_confidence,
            'quality_score': self.quality_score,
            'total_engagement_analyzed': self.total_engagement_analyzed,
            'top_insights': [
                {
                    'content': insight.content[:100] + "..." if len(insight.content) > 100 else insight.content,
                    'type': insight.insight_type.value,
                    'confidence': insight.confidence_score,
                    'novelty': insight.novelty_score,
                    'confidence_level': insight.confidence_level.value
                }
                for insight in sorted(self.unique_insights, key=lambda x: x.confidence_score * x.novelty_score, reverse=True)[:5]
            ]
        }
    
    def validate_analysis(self) -> Dict[str, bool]:
        """
        Validate the insight analysis quality and completeness.
        
        Returns:
            Dictionary with validation results
        """
        validations = {
            'has_insights': len(self.unique_insights) > 0,
            'sufficient_insights': len(self.unique_insights) >= 2,
            'has_high_confidence_insights': len(self.high_confidence_insights) > 0,
            'has_high_novelty_insights': len(self.high_novelty_insights) > 0,
            'has_value_propositions': len(self.value_propositions) > 0,
            'has_key_differentiators': len(self.key_differentiators) > 0,
            'confidence_above_threshold': self.overall_confidence >= 0.6,
            'quality_above_threshold': self.quality_score >= 0.6,
            'novelty_above_threshold': self.average_novelty_score >= 0.5,
            'sufficient_engagement_data': self.total_engagement_analyzed >= 50,
            'has_diverse_insights': len(self.insights_by_type) >= 2,
            'has_source_attribution': len(self.source_attribution) > 0,
        }
        
        # Validate individual insights
        insight_validations = []
        for insight in self.unique_insights:
            insight_validation = insight.validate()
            insight_validations.append(all(insight_validation.values()))
        
        validations['all_insights_valid'] = all(insight_validations) if insight_validations else False
        validations['majority_insights_valid'] = (
            sum(insight_validations) / len(insight_validations) >= 0.8 
            if insight_validations else False
        )
        
        return validations


# Pydantic models for API compatibility
class ExpertiseAnalysisModel(BaseModel):
    """Pydantic model version of ExpertiseAnalysis for API serialization."""
    
    core_expertise: List[Dict[str, Any]] = Field(default_factory=list)
    domain_knowledge: List[str] = Field(default_factory=list)
    technical_skills: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    authority_signals: List[str] = Field(default_factory=list)
    overall_confidence: float = Field(0.0, ge=0.0, le=1.0)
    expertise_confidence: Dict[str, float] = Field(default_factory=dict)
    quality_score: float = Field(0.0, ge=0.0, le=1.0)
    source_attribution: Dict[str, List[str]] = Field(default_factory=dict)
    analysis_timestamp: datetime = Field(default_factory=datetime.now)
    
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }


class CommunicationAnalysisModel(BaseModel):
    """Pydantic model version of CommunicationAnalysis for API serialization."""
    
    primary_tone: str = Field("professional")
    secondary_tones: List[str] = Field(default_factory=list)
    writing_patterns: List[Dict[str, Any]] = Field(default_factory=list)
    engagement_style: str = Field("")
    communication_strengths: List[str] = Field(default_factory=list)
    overall_confidence: float = Field(0.0, ge=0.0, le=1.0)
    quality_score: float = Field(0.0, ge=0.0, le=1.0)
    source_attribution: Dict[str, List[str]] = Field(default_factory=dict)
    analysis_timestamp: datetime = Field(default_factory=datetime.now)
    
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }


class InsightAnalysisModel(BaseModel):
    """Pydantic model version of InsightAnalysis for API serialization."""
    
    unique_insights: List[Dict[str, Any]] = Field(default_factory=list)
    value_propositions: List[str] = Field(default_factory=list)
    key_differentiators: List[str] = Field(default_factory=list)
    thought_leadership_areas: List[str] = Field(default_factory=list)
    average_novelty_score: float = Field(0.0, ge=0.0, le=1.0)
    overall_confidence: float = Field(0.0, ge=0.0, le=1.0)
    quality_score: float = Field(0.0, ge=0.0, le=1.0)
    source_attribution: Dict[str, List[str]] = Field(default_factory=dict)
    analysis_timestamp: datetime = Field(default_factory=datetime.now)
    
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }


# Factory functions for creating analysis instances
def create_expertise_analysis(
    extraction_method: str = "advanced_prompting",
    prompt_version: Optional[str] = None,
    model_used: Optional[str] = None
) -> ExpertiseAnalysis:
    """
    Factory function to create an ExpertiseAnalysis instance.
    
    Args:
        extraction_method: Method used for expertise extraction
        prompt_version: Version of the prompt used
        model_used: AI model used for analysis
        
    Returns:
        ExpertiseAnalysis instance ready for population
    """
    return ExpertiseAnalysis(
        extraction_method=extraction_method,
        prompt_version=prompt_version,
        model_used=model_used
    )


def create_communication_analysis(
    analysis_method: str = "pattern_analysis"
) -> CommunicationAnalysis:
    """
    Factory function to create a CommunicationAnalysis instance.
    
    Args:
        analysis_method: Method used for communication analysis
        
    Returns:
        CommunicationAnalysis instance ready for population
    """
    return CommunicationAnalysis(
        analysis_method=analysis_method
    )


def create_insight_analysis(
    generation_method: str = "high_engagement_analysis",
    high_engagement_threshold: int = 10
) -> InsightAnalysis:
    """
    Factory function to create an InsightAnalysis instance.
    
    Args:
        generation_method: Method used for insight generation
        high_engagement_threshold: Minimum engagement for content analysis
        
    Returns:
        InsightAnalysis instance ready for population
    """
    return InsightAnalysis(
        generation_method=generation_method,
        high_engagement_threshold=high_engagement_threshold
    )
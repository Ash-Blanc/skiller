from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class SkillProfile(BaseModel):
    person_name: str = Field(..., description="The name of the person this skill is based on.")
    x_handle: str = Field(..., description="The X (Twitter) handle of the person.")
    core_expertise: List[str] = Field(..., description="List of core topics or fields they are experts in.")
    unique_insights: List[str] = Field(..., description="Novel takes, frameworks, or unique perspectives found in their posts.")
    communication_style: str = Field(..., description="Description of how they communicate (e.g., witty, technical, concise).")
    agent_instructions: str = Field(..., description="A set of system instructions to allow an AI to act as this person or use their expertise.")
    sample_posts: List[str] = Field(default_factory=list, description="A few high-quality posts that represent their style and knowledge.")


class EnhancedSkillProfile(SkillProfile):
    """
    Enhanced version of SkillProfile with confidence scoring and source attribution.
    
    This extended model provides additional metadata about the quality and sources
    of the generated skill profile, enabling better validation and trust in the
    generated insights.
    
    Validates Requirements:
    - AC3.6: Generates confidence scores for extracted skills
    - AC6.2: Provides confidence scoring for generated profiles  
    - AC6.3: Includes source attribution for key insights
    """
    
    # Confidence scoring (AC3.6, AC6.2)
    confidence_score: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Overall confidence score for the profile (0.0 to 1.0)"
    )
    
    expertise_confidence: Dict[str, float] = Field(
        default_factory=dict,
        description="Confidence scores for each expertise area (0.0 to 1.0)"
    )
    
    insight_confidence: Dict[str, float] = Field(
        default_factory=dict,
        description="Confidence scores for each unique insight (0.0 to 1.0)"
    )
    
    # Source attribution (AC6.3)
    data_sources: List[str] = Field(
        default_factory=list,
        description="List of data sources used (e.g., 'TwitterAPI.io', 'ScrapeBadger')"
    )
    
    source_attribution: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Maps profile elements to their contributing sources"
    )
    
    # Quality metrics and metadata
    quality_metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Various quality metrics for the profile generation"
    )
    
    collection_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about the data collection process"
    )
    
    generation_timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When this enhanced profile was generated"
    )
    
    # Validation and quality indicators
    validation_results: Dict[str, bool] = Field(
        default_factory=dict,
        description="Results of various validation checks"
    )
    
    def calculate_overall_confidence(self) -> float:
        """
        Calculate overall confidence score based on individual component scores.
        
        The overall confidence is a weighted average of:
        - Data quality (40%): Based on source diversity and completeness
        - Expertise confidence (30%): Average confidence of extracted expertise
        - Insight confidence (20%): Average confidence of unique insights  
        - Validation results (10%): Percentage of passed validation checks
        
        Returns:
            Overall confidence score between 0.0 and 1.0
        """
        # Data quality component (40%)
        data_quality = self.quality_metrics.get('data_quality_score', 0.0)
        data_component = data_quality * 0.4
        
        # Expertise confidence component (30%)
        if self.expertise_confidence:
            avg_expertise_confidence = sum(self.expertise_confidence.values()) / len(self.expertise_confidence)
        else:
            avg_expertise_confidence = 0.0
        expertise_component = avg_expertise_confidence * 0.3
        
        # Insight confidence component (20%)
        if self.insight_confidence:
            avg_insight_confidence = sum(self.insight_confidence.values()) / len(self.insight_confidence)
        else:
            avg_insight_confidence = 0.0
        insight_component = avg_insight_confidence * 0.2
        
        # Validation component (10%)
        if self.validation_results:
            validation_score = sum(1 for result in self.validation_results.values() if result) / len(self.validation_results)
        else:
            validation_score = 0.0
        validation_component = validation_score * 0.1
        
        return min(data_component + expertise_component + insight_component + validation_component, 1.0)
    
    def get_source_summary(self) -> Dict[str, Any]:
        """
        Get a summary of data sources and their contributions.
        
        Returns:
            Dictionary with source statistics and attribution summary
        """
        source_stats = {}
        
        # Count contributions per source
        for element, sources in self.source_attribution.items():
            for source in sources:
                if source not in source_stats:
                    source_stats[source] = {'elements': [], 'count': 0}
                source_stats[source]['elements'].append(element)
                source_stats[source]['count'] += 1
        
        return {
            'total_sources': len(self.data_sources),
            'sources_used': self.data_sources,
            'source_contributions': source_stats,
            'attribution_coverage': len(self.source_attribution),
            'has_multi_source_validation': len(self.data_sources) > 1
        }
    
    def get_confidence_summary(self) -> Dict[str, Any]:
        """
        Get a summary of confidence scores across all components.
        
        Returns:
            Dictionary with confidence statistics and analysis
        """
        return {
            'overall_confidence': self.confidence_score,
            'expertise_confidence': {
                'average': (
                    sum(self.expertise_confidence.values()) / len(self.expertise_confidence)
                    if self.expertise_confidence else 0.0
                ),
                'min': min(self.expertise_confidence.values()) if self.expertise_confidence else 0.0,
                'max': max(self.expertise_confidence.values()) if self.expertise_confidence else 0.0,
                'count': len(self.expertise_confidence)
            },
            'insight_confidence': {
                'average': (
                    sum(self.insight_confidence.values()) / len(self.insight_confidence)
                    if self.insight_confidence else 0.0
                ),
                'min': min(self.insight_confidence.values()) if self.insight_confidence else 0.0,
                'max': max(self.insight_confidence.values()) if self.insight_confidence else 0.0,
                'count': len(self.insight_confidence)
            },
            'quality_indicators': {
                'high_confidence_expertise': sum(
                    1 for conf in self.expertise_confidence.values() if conf >= 0.8
                ),
                'high_confidence_insights': sum(
                    1 for conf in self.insight_confidence.values() if conf >= 0.8
                ),
                'low_confidence_items': sum(
                    1 for conf in list(self.expertise_confidence.values()) + list(self.insight_confidence.values()) 
                    if conf < 0.5
                )
            }
        }
    
    def validate_profile_quality(self) -> Dict[str, bool]:
        """
        Perform comprehensive validation of the enhanced profile quality.
        
        Returns:
            Dictionary with validation results for different quality aspects
        """
        validations = {}
        
        # Basic completeness validations
        validations['has_person_name'] = bool(self.person_name and self.person_name.strip())
        validations['has_x_handle'] = bool(self.x_handle and self.x_handle.strip())
        validations['has_core_expertise'] = len(self.core_expertise) > 0
        validations['has_unique_insights'] = len(self.unique_insights) > 0
        validations['has_communication_style'] = bool(self.communication_style and self.communication_style.strip())
        validations['has_agent_instructions'] = bool(self.agent_instructions and self.agent_instructions.strip())
        
        # Enhanced profile validations
        validations['has_confidence_score'] = 0.0 <= self.confidence_score <= 1.0
        validations['has_data_sources'] = len(self.data_sources) > 0
        validations['has_source_attribution'] = len(self.source_attribution) > 0
        validations['has_quality_metrics'] = len(self.quality_metrics) > 0
        
        # Quality threshold validations
        validations['confidence_above_threshold'] = self.confidence_score >= 0.6
        validations['sufficient_expertise'] = len(self.core_expertise) >= 3
        validations['sufficient_insights'] = len(self.unique_insights) >= 2
        validations['multi_source_validation'] = len(self.data_sources) > 1
        
        # Expertise confidence validations
        if self.expertise_confidence:
            avg_expertise_conf = sum(self.expertise_confidence.values()) / len(self.expertise_confidence)
            validations['expertise_confidence_adequate'] = avg_expertise_conf >= 0.5
            validations['has_high_confidence_expertise'] = any(conf >= 0.8 for conf in self.expertise_confidence.values())
        else:
            validations['expertise_confidence_adequate'] = False
            validations['has_high_confidence_expertise'] = False
        
        # Insight confidence validations
        if self.insight_confidence:
            avg_insight_conf = sum(self.insight_confidence.values()) / len(self.insight_confidence)
            validations['insight_confidence_adequate'] = avg_insight_conf >= 0.5
            validations['has_high_confidence_insights'] = any(conf >= 0.8 for conf in self.insight_confidence.values())
        else:
            validations['insight_confidence_adequate'] = False
            validations['has_high_confidence_insights'] = False
        
        # Update internal validation results
        self.validation_results = validations
        
        return validations
    
    def get_quality_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive quality report for the enhanced profile.
        
        Returns:
            Dictionary with detailed quality analysis and recommendations
        """
        # Run validation if not already done
        if not self.validation_results:
            self.validate_profile_quality()
        
        # Calculate quality indicators
        passed_validations = sum(1 for result in self.validation_results.values() if result)
        total_validations = len(self.validation_results)
        validation_score = passed_validations / total_validations if total_validations > 0 else 0.0
        
        # Identify strengths and weaknesses
        strengths = [key for key, value in self.validation_results.items() if value]
        weaknesses = [key for key, value in self.validation_results.items() if not value]
        
        # Generate recommendations
        recommendations = []
        if not self.validation_results.get('multi_source_validation', False):
            recommendations.append("Consider collecting data from multiple sources for better validation")
        if not self.validation_results.get('confidence_above_threshold', False):
            recommendations.append("Profile confidence is below recommended threshold (0.6)")
        if not self.validation_results.get('expertise_confidence_adequate', False):
            recommendations.append("Expertise confidence scores could be improved with more data")
        if not self.validation_results.get('insight_confidence_adequate', False):
            recommendations.append("Insight confidence scores indicate need for higher quality content analysis")
        
        return {
            'overall_quality_score': validation_score,
            'confidence_summary': self.get_confidence_summary(),
            'source_summary': self.get_source_summary(),
            'validation_results': {
                'passed': passed_validations,
                'total': total_validations,
                'score': validation_score,
                'strengths': strengths,
                'weaknesses': weaknesses
            },
            'recommendations': recommendations,
            'generation_metadata': {
                'timestamp': self.generation_timestamp.isoformat(),
                'data_sources': self.data_sources,
                'collection_metadata': self.collection_metadata
            }
        }
    
    def update_confidence_score(self):
        """Update the overall confidence score based on current component scores."""
        self.confidence_score = self.calculate_overall_confidence()
    
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }

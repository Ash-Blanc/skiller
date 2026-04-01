"""
Tests for EnhancedSkillProfile model with confidence scoring and source attribution.

This test suite validates the enhanced skill profile functionality including:
- Confidence scoring calculations
- Source attribution tracking
- Quality validation and reporting
- Backward compatibility with SkillProfile

Validates Requirements:
- AC3.6: Generates confidence scores for extracted skills
- AC6.2: Provides confidence scoring for generated profiles
- AC6.3: Includes source attribution for key insights
"""

import pytest
from datetime import datetime
from typing import Dict, List, Any

from app.models.skill import SkillProfile, EnhancedSkillProfile


@pytest.fixture
def basic_skill_data() -> Dict[str, Any]:
    """Basic skill profile data for testing."""
    return {
        "person_name": "John Doe",
        "x_handle": "@johndoe",
        "core_expertise": ["Machine Learning", "Python", "Data Science"],
        "unique_insights": [
            "ML models need continuous monitoring in production",
            "Feature engineering is more important than algorithm choice"
        ],
        "communication_style": "Technical but accessible, uses practical examples",
        "agent_instructions": "Act as a senior ML engineer with practical experience",
        "sample_posts": [
            "Just deployed a model that improved accuracy by 15%",
            "Remember: garbage in, garbage out - data quality matters most"
        ]
    }


@pytest.fixture
def enhanced_skill_data(basic_skill_data) -> Dict[str, Any]:
    """Enhanced skill profile data with confidence and attribution."""
    enhanced_data = basic_skill_data.copy()
    enhanced_data.update({
        "confidence_score": 0.85,
        "expertise_confidence": {
            "Machine Learning": 0.9,
            "Python": 0.8,
            "Data Science": 0.85
        },
        "insight_confidence": {
            "ML models need continuous monitoring in production": 0.9,
            "Feature engineering is more important than algorithm choice": 0.8
        },
        "data_sources": ["TwitterAPI.io", "ScrapeBadger"],
        "source_attribution": {
            "core_expertise": ["TwitterAPI.io", "ScrapeBadger"],
            "unique_insights": ["ScrapeBadger"],
            "communication_style": ["TwitterAPI.io"],
            "sample_posts": ["TwitterAPI.io", "ScrapeBadger"]
        },
        "quality_metrics": {
            "data_quality_score": 0.8,
            "content_volume_score": 0.7,
            "source_diversity_score": 1.0
        },
        "collection_metadata": {
            "total_tweets": 45,
            "total_sources": 2,
            "collection_duration": 12.5
        }
    })
    return enhanced_data


class TestEnhancedSkillProfile:
    """Test suite for EnhancedSkillProfile functionality."""
    
    def test_enhanced_skill_profile_creation(self, enhanced_skill_data):
        """Test creating an EnhancedSkillProfile with all fields."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        
        # Test basic SkillProfile fields
        assert profile.person_name == "John Doe"
        assert profile.x_handle == "@johndoe"
        assert len(profile.core_expertise) == 3
        assert len(profile.unique_insights) == 2
        
        # Test enhanced fields
        assert profile.confidence_score == 0.85
        assert len(profile.expertise_confidence) == 3
        assert len(profile.insight_confidence) == 2
        assert len(profile.data_sources) == 2
        assert len(profile.source_attribution) == 4
        assert len(profile.quality_metrics) == 3
        assert isinstance(profile.generation_timestamp, datetime)
    
    def test_backward_compatibility_with_skill_profile(self, basic_skill_data):
        """Test that EnhancedSkillProfile is backward compatible with SkillProfile."""
        # Should be able to create EnhancedSkillProfile with just basic data
        profile = EnhancedSkillProfile(**basic_skill_data, confidence_score=0.7)
        
        assert profile.person_name == "John Doe"
        assert profile.confidence_score == 0.7
        assert profile.data_sources == []  # Default empty list
        assert profile.source_attribution == {}  # Default empty dict
        assert profile.quality_metrics == {}  # Default empty dict
    
    def test_confidence_score_validation(self, basic_skill_data):
        """Test confidence score validation (must be between 0.0 and 1.0)."""
        # Valid confidence scores
        profile = EnhancedSkillProfile(**basic_skill_data, confidence_score=0.0)
        assert profile.confidence_score == 0.0
        
        profile = EnhancedSkillProfile(**basic_skill_data, confidence_score=1.0)
        assert profile.confidence_score == 1.0
        
        profile = EnhancedSkillProfile(**basic_skill_data, confidence_score=0.75)
        assert profile.confidence_score == 0.75
        
        # Invalid confidence scores should raise validation error
        with pytest.raises(ValueError):
            EnhancedSkillProfile(**basic_skill_data, confidence_score=-0.1)
        
        with pytest.raises(ValueError):
            EnhancedSkillProfile(**basic_skill_data, confidence_score=1.1)
    
    def test_calculate_overall_confidence(self, enhanced_skill_data):
        """Test overall confidence calculation based on components."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        
        # Calculate expected confidence
        # Data quality (40%): 0.8 * 0.4 = 0.32
        # Expertise confidence (30%): 0.85 * 0.3 = 0.255
        # Insight confidence (20%): 0.85 * 0.2 = 0.17
        # Validation (10%): depends on validation results
        
        calculated_confidence = profile.calculate_overall_confidence()
        
        # Should be a reasonable confidence score
        assert 0.0 <= calculated_confidence <= 1.0
        assert calculated_confidence > 0.5  # Should be reasonably high with good data
    
    def test_update_confidence_score(self, enhanced_skill_data):
        """Test updating confidence score based on components."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        original_confidence = profile.confidence_score
        
        # Update component scores
        profile.expertise_confidence["Machine Learning"] = 0.95
        profile.quality_metrics["data_quality_score"] = 0.9
        
        # Update overall confidence
        profile.update_confidence_score()
        
        # Confidence should have changed
        assert profile.confidence_score != original_confidence
    
    def test_get_source_summary(self, enhanced_skill_data):
        """Test source summary generation."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        summary = profile.get_source_summary()
        
        assert summary["total_sources"] == 2
        assert "TwitterAPI.io" in summary["sources_used"]
        assert "ScrapeBadger" in summary["sources_used"]
        assert summary["attribution_coverage"] == 4
        assert summary["has_multi_source_validation"] is True
        
        # Check source contributions
        assert "TwitterAPI.io" in summary["source_contributions"]
        assert "ScrapeBadger" in summary["source_contributions"]
    
    def test_get_confidence_summary(self, enhanced_skill_data):
        """Test confidence summary generation."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        summary = profile.get_confidence_summary()
        
        assert summary["overall_confidence"] == 0.85
        
        # Check expertise confidence stats
        expertise_stats = summary["expertise_confidence"]
        assert expertise_stats["count"] == 3
        assert abs(expertise_stats["average"] - 0.85) < 0.001  # (0.9 + 0.8 + 0.85) / 3
        assert expertise_stats["min"] == 0.8
        assert expertise_stats["max"] == 0.9
        
        # Check insight confidence stats
        insight_stats = summary["insight_confidence"]
        assert insight_stats["count"] == 2
        assert abs(insight_stats["average"] - 0.85) < 0.001  # (0.9 + 0.8) / 2
        
        # Check quality indicators
        quality_indicators = summary["quality_indicators"]
        assert quality_indicators["high_confidence_expertise"] == 3  # All three >= 0.8 (0.9, 0.8, 0.85)
        assert quality_indicators["high_confidence_insights"] == 2   # Both insights >= 0.8 (0.9, 0.8)
    
    def test_validate_profile_quality(self, enhanced_skill_data):
        """Test comprehensive profile quality validation."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        validations = profile.validate_profile_quality()
        
        # Basic completeness validations should pass
        assert validations["has_person_name"] is True
        assert validations["has_x_handle"] is True
        assert validations["has_core_expertise"] is True
        assert validations["has_unique_insights"] is True
        assert validations["has_communication_style"] is True
        assert validations["has_agent_instructions"] is True
        
        # Enhanced profile validations should pass
        assert validations["has_confidence_score"] is True
        assert validations["has_data_sources"] is True
        assert validations["has_source_attribution"] is True
        assert validations["has_quality_metrics"] is True
        
        # Quality threshold validations
        assert validations["confidence_above_threshold"] is True  # 0.85 >= 0.6
        assert validations["sufficient_expertise"] is True  # 3 >= 3
        assert validations["sufficient_insights"] is True  # 2 >= 2
        assert validations["multi_source_validation"] is True  # 2 > 1
        
        # Confidence validations
        assert validations["expertise_confidence_adequate"] is True  # 0.85 >= 0.5
        assert validations["insight_confidence_adequate"] is True  # 0.85 >= 0.5
        assert validations["has_high_confidence_expertise"] is True  # ML: 0.9 >= 0.8
        assert validations["has_high_confidence_insights"] is True  # First insight: 0.9 >= 0.8
    
    def test_validate_profile_quality_with_poor_data(self, basic_skill_data):
        """Test validation with poor quality data."""
        # Create profile with minimal data and low confidence
        poor_data = basic_skill_data.copy()
        poor_data.update({
            "core_expertise": ["Python"],  # Only 1 expertise (< 3)
            "unique_insights": ["Some insight"],  # Only 1 insight (< 2)
            "confidence_score": 0.4,  # Below threshold (< 0.6)
            "data_sources": ["TwitterAPI.io"],  # Only 1 source
            "expertise_confidence": {"Python": 0.3},  # Low confidence
            "insight_confidence": {"Some insight": 0.4}  # Low confidence
        })
        
        profile = EnhancedSkillProfile(**poor_data)
        validations = profile.validate_profile_quality()
        
        # These should fail
        assert validations["confidence_above_threshold"] is False
        assert validations["sufficient_expertise"] is False
        assert validations["sufficient_insights"] is False
        assert validations["multi_source_validation"] is False
        assert validations["expertise_confidence_adequate"] is False
        assert validations["insight_confidence_adequate"] is False
        assert validations["has_high_confidence_expertise"] is False
        assert validations["has_high_confidence_insights"] is False
    
    def test_get_quality_report(self, enhanced_skill_data):
        """Test comprehensive quality report generation."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        report = profile.get_quality_report()
        
        # Check report structure
        assert "overall_quality_score" in report
        assert "confidence_summary" in report
        assert "source_summary" in report
        assert "validation_results" in report
        assert "recommendations" in report
        assert "generation_metadata" in report
        
        # Check validation results
        validation_results = report["validation_results"]
        assert validation_results["passed"] > 0
        assert validation_results["total"] > 0
        assert 0.0 <= validation_results["score"] <= 1.0
        assert isinstance(validation_results["strengths"], list)
        assert isinstance(validation_results["weaknesses"], list)
        
        # Check recommendations
        assert isinstance(report["recommendations"], list)
        
        # Check metadata
        metadata = report["generation_metadata"]
        assert "timestamp" in metadata
        assert "data_sources" in metadata
        assert "collection_metadata" in metadata
    
    def test_empty_confidence_dictionaries(self, basic_skill_data):
        """Test behavior with empty confidence dictionaries."""
        profile = EnhancedSkillProfile(**basic_skill_data, confidence_score=0.5)
        
        # Should handle empty confidence dictionaries gracefully
        summary = profile.get_confidence_summary()
        
        assert summary["expertise_confidence"]["average"] == 0.0
        assert summary["expertise_confidence"]["count"] == 0
        assert summary["insight_confidence"]["average"] == 0.0
        assert summary["insight_confidence"]["count"] == 0
        
        # Quality indicators should be 0 for empty dictionaries
        quality_indicators = summary["quality_indicators"]
        assert quality_indicators["high_confidence_expertise"] == 0
        assert quality_indicators["high_confidence_insights"] == 0
        assert quality_indicators["low_confidence_items"] == 0
    
    def test_json_serialization(self, enhanced_skill_data):
        """Test that EnhancedSkillProfile can be serialized to JSON."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        
        # Should be able to convert to dict and back
        profile_dict = profile.model_dump()
        assert isinstance(profile_dict, dict)
        assert "confidence_score" in profile_dict
        assert "data_sources" in profile_dict
        assert "source_attribution" in profile_dict
        
        # Should be able to recreate from dict
        recreated_profile = EnhancedSkillProfile(**profile_dict)
        assert recreated_profile.confidence_score == profile.confidence_score
        assert recreated_profile.data_sources == profile.data_sources
    
    def test_datetime_handling(self, basic_skill_data):
        """Test datetime field handling and serialization."""
        profile = EnhancedSkillProfile(**basic_skill_data, confidence_score=0.7)
        
        # Should have generation timestamp
        assert isinstance(profile.generation_timestamp, datetime)
        
        # Should be able to serialize with datetime
        profile_dict = profile.model_dump()
        assert "generation_timestamp" in profile_dict
        
        # Timestamp should be serializable
        json_str = profile.model_dump_json()
        assert isinstance(json_str, str)
        assert "generation_timestamp" in json_str


class TestEnhancedSkillProfileIntegration:
    """Integration tests for EnhancedSkillProfile with other components."""
    
    def test_inheritance_from_skill_profile(self):
        """Test that EnhancedSkillProfile properly inherits from SkillProfile."""
        # Should be able to use EnhancedSkillProfile wherever SkillProfile is expected
        assert issubclass(EnhancedSkillProfile, SkillProfile)
        
        # Should have all SkillProfile fields
        skill_fields = set(SkillProfile.model_fields.keys())
        enhanced_fields = set(EnhancedSkillProfile.model_fields.keys())
        
        assert skill_fields.issubset(enhanced_fields)
    
    def test_polymorphic_usage(self, basic_skill_data):
        """Test polymorphic usage of EnhancedSkillProfile as SkillProfile."""
        def process_skill_profile(profile: SkillProfile) -> str:
            """Function that expects a SkillProfile."""
            return f"{profile.person_name} - {len(profile.core_expertise)} expertise areas"
        
        # Should work with EnhancedSkillProfile
        enhanced_profile = EnhancedSkillProfile(**basic_skill_data, confidence_score=0.8)
        result = process_skill_profile(enhanced_profile)
        
        assert "John Doe" in result
        assert "3 expertise areas" in result
    
    def test_field_validation_inheritance(self, basic_skill_data):
        """Test that field validation from SkillProfile is inherited."""
        # Required fields should still be required
        with pytest.raises(ValueError):
            EnhancedSkillProfile(confidence_score=0.8)  # Missing required fields
        
        # Field types should be validated
        invalid_data = basic_skill_data.copy()
        invalid_data["core_expertise"] = "not a list"  # Should be List[str]
        
        with pytest.raises(ValueError):
            EnhancedSkillProfile(**invalid_data, confidence_score=0.8)


class TestEnhancedSkillProfileRequirements:
    """Test that EnhancedSkillProfile meets specific requirements."""
    
    def test_ac3_6_confidence_scores_for_skills(self, enhanced_skill_data):
        """Test AC3.6: Generates confidence scores for extracted skills."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        
        # Should have confidence scores for each expertise area
        assert len(profile.expertise_confidence) > 0
        for expertise in profile.core_expertise:
            assert expertise in profile.expertise_confidence
            assert 0.0 <= profile.expertise_confidence[expertise] <= 1.0
        
        # Should have confidence scores for insights
        assert len(profile.insight_confidence) > 0
        for insight in profile.unique_insights:
            assert insight in profile.insight_confidence
            assert 0.0 <= profile.insight_confidence[insight] <= 1.0
    
    def test_ac6_2_confidence_scoring_for_profiles(self, enhanced_skill_data):
        """Test AC6.2: Provides confidence scoring for generated profiles."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        
        # Should have overall confidence score
        assert hasattr(profile, 'confidence_score')
        assert 0.0 <= profile.confidence_score <= 1.0
        
        # Should be able to calculate confidence based on components
        calculated_confidence = profile.calculate_overall_confidence()
        assert 0.0 <= calculated_confidence <= 1.0
        
        # Should provide confidence summary
        summary = profile.get_confidence_summary()
        assert "overall_confidence" in summary
        assert "expertise_confidence" in summary
        assert "insight_confidence" in summary
    
    def test_ac6_3_source_attribution_for_insights(self, enhanced_skill_data):
        """Test AC6.3: Includes source attribution for key insights."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        
        # Should track data sources
        assert len(profile.data_sources) > 0
        assert all(isinstance(source, str) for source in profile.data_sources)
        
        # Should have source attribution mapping
        assert len(profile.source_attribution) > 0
        for element, sources in profile.source_attribution.items():
            assert isinstance(element, str)
            assert isinstance(sources, list)
            assert all(isinstance(source, str) for source in sources)
            # Sources should be from the available data sources
            assert all(source in profile.data_sources for source in sources)
        
        # Should provide source summary
        source_summary = profile.get_source_summary()
        assert "total_sources" in source_summary
        assert "sources_used" in source_summary
        assert "source_contributions" in source_summary
        assert "attribution_coverage" in source_summary


if __name__ == "__main__":
    pytest.main([__file__])
    
    def test_enhanced_skill_profile_creation(self, enhanced_skill_data):
        """Test creating an EnhancedSkillProfile with all fields."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        
        # Test basic SkillProfile fields
        assert profile.person_name == "John Doe"
        assert profile.x_handle == "@johndoe"
        assert len(profile.core_expertise) == 3
        assert len(profile.unique_insights) == 2
        
        # Test enhanced fields
        assert profile.confidence_score == 0.85
        assert len(profile.expertise_confidence) == 3
        assert len(profile.insight_confidence) == 2
        assert len(profile.data_sources) == 2
        assert len(profile.source_attribution) == 4
        assert len(profile.quality_metrics) == 3
        assert isinstance(profile.generation_timestamp, datetime)
    
    def test_backward_compatibility_with_skill_profile(self, basic_skill_data):
        """Test that EnhancedSkillProfile is backward compatible with SkillProfile."""
        # Should be able to create EnhancedSkillProfile with just basic data
        profile = EnhancedSkillProfile(**basic_skill_data, confidence_score=0.7)
        
        assert profile.person_name == "John Doe"
        assert profile.confidence_score == 0.7
        assert profile.data_sources == []  # Default empty list
        assert profile.source_attribution == {}  # Default empty dict
        assert profile.quality_metrics == {}  # Default empty dict
    
    def test_confidence_score_validation(self, basic_skill_data):
        """Test confidence score validation (must be between 0.0 and 1.0)."""
        # Valid confidence scores
        profile = EnhancedSkillProfile(**basic_skill_data, confidence_score=0.0)
        assert profile.confidence_score == 0.0
        
        profile = EnhancedSkillProfile(**basic_skill_data, confidence_score=1.0)
        assert profile.confidence_score == 1.0
        
        profile = EnhancedSkillProfile(**basic_skill_data, confidence_score=0.75)
        assert profile.confidence_score == 0.75
        
        # Invalid confidence scores should raise validation error
        with pytest.raises(ValueError):
            EnhancedSkillProfile(**basic_skill_data, confidence_score=-0.1)
        
        with pytest.raises(ValueError):
            EnhancedSkillProfile(**basic_skill_data, confidence_score=1.1)
    
    def test_calculate_overall_confidence(self, enhanced_skill_data):
        """Test overall confidence calculation based on components."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        
        # Calculate expected confidence
        # Data quality (40%): 0.8 * 0.4 = 0.32
        # Expertise confidence (30%): 0.85 * 0.3 = 0.255
        # Insight confidence (20%): 0.85 * 0.2 = 0.17
        # Validation (10%): depends on validation results
        
        calculated_confidence = profile.calculate_overall_confidence()
        
        # Should be a reasonable confidence score
        assert 0.0 <= calculated_confidence <= 1.0
        assert calculated_confidence > 0.5  # Should be reasonably high with good data
    
    def test_update_confidence_score(self, enhanced_skill_data):
        """Test updating confidence score based on components."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        original_confidence = profile.confidence_score
        
        # Update component scores
        profile.expertise_confidence["Machine Learning"] = 0.95
        profile.quality_metrics["data_quality_score"] = 0.9
        
        # Update overall confidence
        profile.update_confidence_score()
        
        # Confidence should have changed
        assert profile.confidence_score != original_confidence
    
    def test_get_source_summary(self, enhanced_skill_data):
        """Test source summary generation."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        summary = profile.get_source_summary()
        
        assert summary["total_sources"] == 2
        assert "TwitterAPI.io" in summary["sources_used"]
        assert "ScrapeBadger" in summary["sources_used"]
        assert summary["attribution_coverage"] == 4
        assert summary["has_multi_source_validation"] is True
        
        # Check source contributions
        assert "TwitterAPI.io" in summary["source_contributions"]
        assert "ScrapeBadger" in summary["source_contributions"]
    
    def test_get_confidence_summary(self, enhanced_skill_data):
        """Test confidence summary generation."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        summary = profile.get_confidence_summary()
        
        assert summary["overall_confidence"] == 0.85
        
        # Check expertise confidence stats
        expertise_stats = summary["expertise_confidence"]
        assert expertise_stats["count"] == 3
        assert expertise_stats["average"] == 0.85  # (0.9 + 0.8 + 0.85) / 3
        assert expertise_stats["min"] == 0.8
        assert expertise_stats["max"] == 0.9
        
        # Check insight confidence stats
        insight_stats = summary["insight_confidence"]
        assert insight_stats["count"] == 2
        assert insight_stats["average"] == 0.85  # (0.9 + 0.8) / 2
        
        # Check quality indicators
        quality_indicators = summary["quality_indicators"]
        assert quality_indicators["high_confidence_expertise"] == 1  # Only ML >= 0.8
        assert quality_indicators["high_confidence_insights"] == 1   # Only first insight >= 0.8
    
    def test_validate_profile_quality(self, enhanced_skill_data):
        """Test comprehensive profile quality validation."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        validations = profile.validate_profile_quality()
        
        # Basic completeness validations should pass
        assert validations["has_person_name"] is True
        assert validations["has_x_handle"] is True
        assert validations["has_core_expertise"] is True
        assert validations["has_unique_insights"] is True
        assert validations["has_communication_style"] is True
        assert validations["has_agent_instructions"] is True
        
        # Enhanced profile validations should pass
        assert validations["has_confidence_score"] is True
        assert validations["has_data_sources"] is True
        assert validations["has_source_attribution"] is True
        assert validations["has_quality_metrics"] is True
        
        # Quality threshold validations
        assert validations["confidence_above_threshold"] is True  # 0.85 >= 0.6
        assert validations["sufficient_expertise"] is True  # 3 >= 3
        assert validations["sufficient_insights"] is True  # 2 >= 2
        assert validations["multi_source_validation"] is True  # 2 > 1
        
        # Confidence validations
        assert validations["expertise_confidence_adequate"] is True  # 0.85 >= 0.5
        assert validations["insight_confidence_adequate"] is True  # 0.85 >= 0.5
        assert validations["has_high_confidence_expertise"] is True  # ML: 0.9 >= 0.8
        assert validations["has_high_confidence_insights"] is True  # First insight: 0.9 >= 0.8
    
    def test_validate_profile_quality_with_poor_data(self, basic_skill_data):
        """Test validation with poor quality data."""
        # Create profile with minimal data and low confidence
        poor_data = basic_skill_data.copy()
        poor_data.update({
            "core_expertise": ["Python"],  # Only 1 expertise (< 3)
            "unique_insights": ["Some insight"],  # Only 1 insight (< 2)
            "confidence_score": 0.4,  # Below threshold (< 0.6)
            "data_sources": ["TwitterAPI.io"],  # Only 1 source
            "expertise_confidence": {"Python": 0.3},  # Low confidence
            "insight_confidence": {"Some insight": 0.4}  # Low confidence
        })
        
        profile = EnhancedSkillProfile(**poor_data)
        validations = profile.validate_profile_quality()
        
        # These should fail
        assert validations["confidence_above_threshold"] is False
        assert validations["sufficient_expertise"] is False
        assert validations["sufficient_insights"] is False
        assert validations["multi_source_validation"] is False
        assert validations["expertise_confidence_adequate"] is False
        assert validations["insight_confidence_adequate"] is False
        assert validations["has_high_confidence_expertise"] is False
        assert validations["has_high_confidence_insights"] is False
    
    def test_get_quality_report(self, enhanced_skill_data):
        """Test comprehensive quality report generation."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        report = profile.get_quality_report()
        
        # Check report structure
        assert "overall_quality_score" in report
        assert "confidence_summary" in report
        assert "source_summary" in report
        assert "validation_results" in report
        assert "recommendations" in report
        assert "generation_metadata" in report
        
        # Check validation results
        validation_results = report["validation_results"]
        assert validation_results["passed"] > 0
        assert validation_results["total"] > 0
        assert 0.0 <= validation_results["score"] <= 1.0
        assert isinstance(validation_results["strengths"], list)
        assert isinstance(validation_results["weaknesses"], list)
        
        # Check recommendations
        assert isinstance(report["recommendations"], list)
        
        # Check metadata
        metadata = report["generation_metadata"]
        assert "timestamp" in metadata
        assert "data_sources" in metadata
        assert "collection_metadata" in metadata
    
    def test_empty_confidence_dictionaries(self, basic_skill_data):
        """Test behavior with empty confidence dictionaries."""
        profile = EnhancedSkillProfile(**basic_skill_data, confidence_score=0.5)
        
        # Should handle empty confidence dictionaries gracefully
        summary = profile.get_confidence_summary()
        
        assert summary["expertise_confidence"]["average"] == 0.0
        assert summary["expertise_confidence"]["count"] == 0
        assert summary["insight_confidence"]["average"] == 0.0
        assert summary["insight_confidence"]["count"] == 0
        
        # Quality indicators should be 0 for empty dictionaries
        quality_indicators = summary["quality_indicators"]
        assert quality_indicators["high_confidence_expertise"] == 0
        assert quality_indicators["high_confidence_insights"] == 0
        assert quality_indicators["low_confidence_items"] == 0
    
    def test_json_serialization(self, enhanced_skill_data):
        """Test that EnhancedSkillProfile can be serialized to JSON."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        
        # Should be able to convert to dict and back
        profile_dict = profile.model_dump()
        assert isinstance(profile_dict, dict)
        assert "confidence_score" in profile_dict
        assert "data_sources" in profile_dict
        assert "source_attribution" in profile_dict
        
        # Should be able to recreate from dict
        recreated_profile = EnhancedSkillProfile(**profile_dict)
        assert recreated_profile.confidence_score == profile.confidence_score
        assert recreated_profile.data_sources == profile.data_sources
    
    def test_datetime_handling(self, basic_skill_data):
        """Test datetime field handling and serialization."""
        profile = EnhancedSkillProfile(**basic_skill_data, confidence_score=0.7)
        
        # Should have generation timestamp
        assert isinstance(profile.generation_timestamp, datetime)
        
        # Should be able to serialize with datetime
        profile_dict = profile.model_dump()
        assert "generation_timestamp" in profile_dict
        
        # Timestamp should be serializable
        json_str = profile.model_dump_json()
        assert isinstance(json_str, str)
        assert "generation_timestamp" in json_str


class TestEnhancedSkillProfileIntegration:
    """Integration tests for EnhancedSkillProfile with other components."""
    
    def test_inheritance_from_skill_profile(self):
        """Test that EnhancedSkillProfile properly inherits from SkillProfile."""
        # Should be able to use EnhancedSkillProfile wherever SkillProfile is expected
        assert issubclass(EnhancedSkillProfile, SkillProfile)
        
        # Should have all SkillProfile fields
        skill_fields = set(SkillProfile.model_fields.keys())
        enhanced_fields = set(EnhancedSkillProfile.model_fields.keys())
        
        assert skill_fields.issubset(enhanced_fields)
    
    def test_polymorphic_usage(self, basic_skill_data):
        """Test polymorphic usage of EnhancedSkillProfile as SkillProfile."""
        def process_skill_profile(profile: SkillProfile) -> str:
            """Function that expects a SkillProfile."""
            return f"{profile.person_name} - {len(profile.core_expertise)} expertise areas"
        
        # Should work with EnhancedSkillProfile
        enhanced_profile = EnhancedSkillProfile(**basic_skill_data, confidence_score=0.8)
        result = process_skill_profile(enhanced_profile)
        
        assert "John Doe" in result
        assert "3 expertise areas" in result
    
    def test_field_validation_inheritance(self, basic_skill_data):
        """Test that field validation from SkillProfile is inherited."""
        # Required fields should still be required
        with pytest.raises(ValueError):
            EnhancedSkillProfile(confidence_score=0.8)  # Missing required fields
        
        # Field types should be validated
        invalid_data = basic_skill_data.copy()
        invalid_data["core_expertise"] = "not a list"  # Should be List[str]
        
        with pytest.raises(ValueError):
            EnhancedSkillProfile(**invalid_data, confidence_score=0.8)


class TestEnhancedSkillProfileRequirements:
    """Test that EnhancedSkillProfile meets specific requirements."""
    
    def test_ac3_6_confidence_scores_for_skills(self, enhanced_skill_data):
        """Test AC3.6: Generates confidence scores for extracted skills."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        
        # Should have confidence scores for each expertise area
        assert len(profile.expertise_confidence) > 0
        for expertise in profile.core_expertise:
            assert expertise in profile.expertise_confidence
            assert 0.0 <= profile.expertise_confidence[expertise] <= 1.0
        
        # Should have confidence scores for insights
        assert len(profile.insight_confidence) > 0
        for insight in profile.unique_insights:
            assert insight in profile.insight_confidence
            assert 0.0 <= profile.insight_confidence[insight] <= 1.0
    
    def test_ac6_2_confidence_scoring_for_profiles(self, enhanced_skill_data):
        """Test AC6.2: Provides confidence scoring for generated profiles."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        
        # Should have overall confidence score
        assert hasattr(profile, 'confidence_score')
        assert 0.0 <= profile.confidence_score <= 1.0
        
        # Should be able to calculate confidence based on components
        calculated_confidence = profile.calculate_overall_confidence()
        assert 0.0 <= calculated_confidence <= 1.0
        
        # Should provide confidence summary
        summary = profile.get_confidence_summary()
        assert "overall_confidence" in summary
        assert "expertise_confidence" in summary
        assert "insight_confidence" in summary
    
    def test_ac6_3_source_attribution_for_insights(self, enhanced_skill_data):
        """Test AC6.3: Includes source attribution for key insights."""
        profile = EnhancedSkillProfile(**enhanced_skill_data)
        
        # Should track data sources
        assert len(profile.data_sources) > 0
        assert all(isinstance(source, str) for source in profile.data_sources)
        
        # Should have source attribution mapping
        assert len(profile.source_attribution) > 0
        for element, sources in profile.source_attribution.items():
            assert isinstance(element, str)
            assert isinstance(sources, list)
            assert all(isinstance(source, str) for source in sources)
            # Sources should be from the available data sources
            assert all(source in profile.data_sources for source in sources)
        
        # Should provide source summary
        source_summary = profile.get_source_summary()
        assert "total_sources" in source_summary
        assert "sources_used" in source_summary
        assert "source_contributions" in source_summary
        assert "attribution_coverage" in source_summary


if __name__ == "__main__":
    pytest.main([__file__])
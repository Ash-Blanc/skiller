"""
Tests for AdvancedSkillGeneratorWorkflow with Agno workflow patterns.

This test suite validates the advanced skill generator workflow functionality including:
- Workflow initialization and configuration
- Parallel data collection execution
- Conditional logic for profile enhancement
- Quality evaluation loops
- Error handling and fallback mechanisms
- Integration with existing components

Validates Requirements:
- AC2.1: Implements parallel execution for simultaneous data collection
- AC2.2: Uses conditional logic for different profile types (verified vs unverified)
- AC2.3: Includes quality evaluation loops to ensure sufficient data
- AC2.4: Provides intelligent routing based on data availability
- AC2.5: Supports iterative improvement with max iteration limits
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any

from app.agents.advanced_skill_generator_workflow import (
    AdvancedSkillGeneratorWorkflow,
    WorkflowContext,
    create_advanced_skill_generator_workflow
)
from app.models.skill import EnhancedSkillProfile
from app.models.collected_data import CollectedData, TwitterAPIData, ScrapeBadgerData
from agno.workflow.types import StepInput, StepOutput


@pytest.fixture
def mock_tools():
    """Mock the external tools to avoid API calls during testing."""
    with patch('app.agents.advanced_skill_generator_workflow.TwitterAPIIOToolkit') as mock_twitter, \
         patch('app.agents.advanced_skill_generator_workflow.ScrapeBadgerToolkit') as mock_scraper, \
         patch('app.agents.advanced_skill_generator_workflow.get_shared_skill_knowledge') as mock_kb:
        
        # Configure mock tools
        mock_twitter_instance = Mock()
        mock_twitter_instance.is_available.return_value = True
        mock_twitter.return_value = mock_twitter_instance
        
        mock_scraper_instance = Mock()
        mock_scraper_instance.is_available.return_value = True
        mock_scraper.return_value = mock_scraper_instance
        
        mock_kb_instance = Mock()
        mock_kb.return_value = mock_kb_instance
        
        yield {
            'twitter_api': mock_twitter_instance,
            'scrapebadger': mock_scraper_instance,
            'knowledge_base': mock_kb_instance
        }


@pytest.fixture
def workflow_context():
    """Sample workflow context for testing."""
    return WorkflowContext(
        username="testuser",
        tools_available={"twitter_api": True, "scrapebadger": True},
        quality_score=0.75,
        iteration_count=1
    )


@pytest.fixture
def sample_collected_data():
    """Sample collected data for testing."""
    twitter_data = TwitterAPIData(
        profile={"username": "testuser", "description": "Test user bio", "verified": True, "followers_count": 5000},
        tweets=[
            {"id": "1", "text": "Great insights on AI", "like_count": 50, "retweet_count": 10},
            {"id": "2", "text": "Machine learning best practices", "like_count": 30, "retweet_count": 5}
        ],
        followings=[{"username": "expert1", "verified": True}],
        collection_success=True
    )
    
    scrapebadger_data = ScrapeBadgerData(
        profile={"username": "testuser", "user_id": "12345", "description": "Enhanced bio"},
        tweets=[
            {"id": "1", "text": "Great insights on AI", "like_count": 50},
            {"id": "3", "text": "New framework for ML", "like_count": 75}
        ],
        highlights=[
            {"text": "My approach to AI development", "type": "pinned", "like_count": 100}
        ],
        collection_success=True
    )
    
    return CollectedData(
        username="testuser",
        twitter_api_data=twitter_data,
        scrapebadger_data=scrapebadger_data
    )


class TestWorkflowContext:
    """Test the WorkflowContext dataclass."""
    
    def test_workflow_context_creation(self):
        """Test creating a WorkflowContext with required fields."""
        context = WorkflowContext(
            username="testuser",
            tools_available={"twitter_api": True, "scrapebadger": False}
        )
        
        assert context.username == "testuser"
        assert context.tools_available["twitter_api"] is True
        assert context.tools_available["scrapebadger"] is False
        assert context.collected_data is None
        assert context.quality_score == 0.0
        assert context.iteration_count == 0
        assert context.enhanced_profile is None
        assert context.errors == []
    
    def test_workflow_context_with_optional_fields(self, sample_collected_data):
        """Test WorkflowContext with all optional fields."""
        profile = EnhancedSkillProfile(
            person_name="Test User",
            x_handle="@testuser",
            core_expertise=["AI", "ML"],
            unique_insights=["Insight 1"],
            communication_style="Technical",
            agent_instructions="Act as AI expert",
            confidence_score=0.8
        )
        
        context = WorkflowContext(
            username="testuser",
            tools_available={"twitter_api": True, "scrapebadger": True},
            collected_data=sample_collected_data,
            quality_score=0.85,
            iteration_count=2,
            enhanced_profile=profile,
            errors=["Minor error"]
        )
        
        assert context.collected_data == sample_collected_data
        assert context.quality_score == 0.85
        assert context.iteration_count == 2
        assert context.enhanced_profile == profile
        assert context.errors == ["Minor error"]


class TestAdvancedSkillGeneratorWorkflow:
    """Test suite for AdvancedSkillGeneratorWorkflow functionality."""
    
    def test_workflow_initialization(self, mock_tools):
        """Test workflow initialization with proper agent setup."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # Test basic initialization
        assert workflow.model_id == "mistral-large-latest"
        assert workflow.twitter_api_toolkit is not None
        assert workflow.scrapebadger_toolkit is not None
        assert workflow.knowledge is not None
        
        # Test agent initialization
        assert workflow.twitter_api_agent is not None
        assert workflow.scrapebadger_agent is not None
        assert workflow.expertise_agent is not None
        assert workflow.communication_agent is not None
        assert workflow.insight_agent is not None
        assert workflow.profile_generator_agent is not None
        
        # Test workflow structure
        assert workflow.workflow is not None
        assert workflow.workflow.name == "Advanced Skill Generator Workflow"
        assert len(workflow.workflow.steps) > 0
    
    def test_workflow_initialization_custom_model(self, mock_tools):
        """Test workflow initialization with custom model."""
        workflow = AdvancedSkillGeneratorWorkflow(model_id="gpt-3.5-turbo")
        
        assert workflow.model_id == "gpt-3.5-turbo"
    
    def test_validate_profile_input_valid_username(self, mock_tools):
        """Test profile input validation with valid username."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        step_input = StepInput(input="testuser")
        result = workflow._validate_profile_input(step_input)
        
        assert result.success is True
        assert "testuser" in result.content
        
        # Parse the result content
        content_data = json.loads(result.content)
        assert content_data["username"] == "testuser"
        assert "tools_available" in content_data
    
    def test_validate_profile_input_with_at_symbol(self, mock_tools):
        """Test profile input validation with @ symbol."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        step_input = StepInput(input="@testuser")
        result = workflow._validate_profile_input(step_input)
        
        assert result.success is True
        content_data = json.loads(result.content)
        assert content_data["username"] == "testuser"  # @ should be removed
    
    def test_validate_profile_input_invalid_username(self, mock_tools):
        """Test profile input validation with invalid username."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # Test invalid characters
        step_input = StepInput(input="test@user!")
        result = workflow._validate_profile_input(step_input)
        
        assert result.success is False
        assert "Invalid username format" in result.content
        assert result.error is not None
    
    def test_validate_profile_input_no_tools_available(self, mock_tools):
        """Test profile input validation when no tools are available."""
        # Mock tools as unavailable
        mock_tools['twitter_api'].is_available.return_value = False
        mock_tools['scrapebadger'].is_available.return_value = False
        
        workflow = AdvancedSkillGeneratorWorkflow()
        
        step_input = StepInput(input="testuser")
        result = workflow._validate_profile_input(step_input)
        
        assert result.success is False
        assert "No data collection tools available" in result.content
        assert "Both TwitterAPI.io and ScrapeBadger are unavailable" in result.error
    
    def test_consolidate_data_success(self, mock_tools):
        """Test successful data consolidation."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        step_input = StepInput(
            input="testuser",
            previous_step_content='{"username": "testuser"}'
        )
        result = workflow._consolidate_data(step_input)
        
        assert result.success is True
        
        # Parse result content
        content_data = json.loads(result.content)
        assert content_data["username"] == "testuser"
        assert "collected_data" in content_data
        
        collected_data = content_data["collected_data"]
        assert "quality_score" in collected_data
        assert "sources" in collected_data
        assert "total_tweets" in collected_data
        assert "has_highlights" in collected_data
        assert "has_profile_data" in collected_data
    
    def test_consolidate_data_error_handling(self, mock_tools):
        """Test data consolidation error handling."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # Create a step input that will cause an error
        step_input = StepInput(input=None)  # Invalid input
        result = workflow._consolidate_data(step_input)
        
        # Should handle error gracefully
        assert result.success is False
        assert "Data consolidation failed" in result.content
        assert result.error is not None
    
    def test_evaluate_data_quality_high_quality(self, mock_tools):
        """Test data quality evaluation with high-quality data."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # High-quality data
        high_quality_data = {
            "collected_data": {
                "quality_score": 0.8,
                "has_profile_data": True,
                "total_tweets": 25,
                "has_highlights": True
            }
        }
        
        step_input = StepInput(
            input="testuser",
            previous_step_content=json.dumps(high_quality_data)
        )
        
        result = workflow._evaluate_data_quality(step_input)
        assert result is True  # Should pass quality check
    
    def test_evaluate_data_quality_low_quality(self, mock_tools):
        """Test data quality evaluation with low-quality data."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # Low-quality data
        low_quality_data = {
            "collected_data": {
                "quality_score": 0.3,
                "has_profile_data": False,
                "total_tweets": 5,
                "has_highlights": False
            }
        }
        
        step_input = StepInput(
            input="testuser",
            previous_step_content=json.dumps(low_quality_data)
        )
        
        result = workflow._evaluate_data_quality(step_input)
        assert result is False  # Should fail quality check
    
    def test_evaluate_data_quality_error_handling(self, mock_tools):
        """Test data quality evaluation error handling."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # Invalid input that will cause parsing error
        step_input = StepInput(
            input="testuser",
            previous_step_content="invalid json"
        )
        
        result = workflow._evaluate_data_quality(step_input)
        assert result is False  # Should default to False on error
    
    def test_should_enhance_collection_needs_enhancement(self, mock_tools):
        """Test enhancement decision for profiles that need enhancement."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # Data that needs enhancement
        needs_enhancement_data = {
            "collected_data": {
                "quality_score": 0.5,  # Below 0.8
                "total_tweets": 15,    # Below 20
                "has_highlights": False  # Missing highlights
            }
        }
        
        step_input = StepInput(
            input="testuser",
            previous_step_content=json.dumps(needs_enhancement_data)
        )
        
        result = workflow._should_enhance_collection(step_input)
        assert result is True  # Should need enhancement
    
    def test_should_enhance_collection_no_enhancement_needed(self, mock_tools):
        """Test enhancement decision for high-quality profiles."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # High-quality data that doesn't need enhancement
        high_quality_data = {
            "collected_data": {
                "quality_score": 0.9,  # Above 0.8
                "total_tweets": 30,    # Above 20
                "has_highlights": True  # Has highlights
            }
        }
        
        step_input = StepInput(
            input="testuser",
            previous_step_content=json.dumps(high_quality_data)
        )
        
        result = workflow._should_enhance_collection(step_input)
        assert result is False  # Should not need enhancement
    
    def test_perform_enhanced_collection_success(self, mock_tools):
        """Test successful enhanced data collection."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        step_input = StepInput(
            input="testuser",
            previous_step_content='{"username": "testuser"}'
        )
        
        result = workflow._perform_enhanced_collection(step_input)
        
        assert result.success is True
        
        # Parse result content
        content_data = json.loads(result.content)
        assert content_data["username"] == "testuser"
        assert content_data["enhancement_performed"] is True
        assert "enhanced_data" in content_data
    
    def test_perform_enhanced_collection_error_handling(self, mock_tools):
        """Test enhanced collection error handling."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # Create invalid input to trigger error
        step_input = StepInput(input=None)
        result = workflow._perform_enhanced_collection(step_input)
        
        assert result.success is False
        assert "Enhanced collection failed" in result.content
        assert result.error is not None
    
    def test_finalize_profile_success(self, mock_tools):
        """Test successful profile finalization."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        step_input = StepInput(input="testuser")
        result = workflow._finalize_profile(step_input)
        
        assert result.success is True
        assert isinstance(result.content, EnhancedSkillProfile)
        
        # Validate the enhanced profile
        profile = result.content
        assert profile.person_name == "Sample User"
        assert profile.x_handle == "@sampleuser"
        assert len(profile.core_expertise) > 0
        assert len(profile.unique_insights) > 0
        assert profile.confidence_score > 0
        assert len(profile.data_sources) > 0
    
    def test_get_workflow_metrics(self, mock_tools):
        """Test workflow metrics retrieval."""
        workflow = AdvancedSkillGeneratorWorkflow()
        metrics = workflow.get_workflow_metrics()
        
        assert isinstance(metrics, dict)
        assert metrics["workflow_name"] == "Advanced Skill Generator Workflow"
        assert metrics["total_steps"] > 0
        assert metrics["parallel_steps"] == 2
        assert metrics["conditional_steps"] == 1
        assert metrics["loop_steps"] == 1
        assert metrics["agents_used"] == 6
        assert metrics["tools_integrated"] == 2
        assert metrics["quality_assurance"] is True
        assert metrics["source_attribution"] is True
        assert metrics["confidence_scoring"] is True


class TestWorkflowIntegration:
    """Integration tests for the complete workflow."""
    
    @patch('app.agents.advanced_skill_generator_workflow.Agent')
    def test_generate_skill_profile_integration(self, mock_agent_class, mock_tools):
        """Test the complete skill profile generation workflow."""
        # Mock the workflow run method
        mock_workflow = Mock()
        mock_enhanced_profile = EnhancedSkillProfile(
            person_name="Integration Test User",
            x_handle="@integrationtest",
            core_expertise=["Integration Testing", "Python"],
            unique_insights=["Testing is crucial for reliability"],
            communication_style="Clear and methodical",
            agent_instructions="Act as a testing expert",
            confidence_score=0.9
        )
        
        mock_response = Mock()
        mock_response.content = mock_enhanced_profile
        mock_workflow.run.return_value = mock_response
        
        workflow = AdvancedSkillGeneratorWorkflow()
        workflow.workflow = mock_workflow
        
        # Test successful generation
        result = workflow.generate_skill_profile("integrationtest")
        
        assert isinstance(result, EnhancedSkillProfile)
        assert result.person_name == "Integration Test User"
        assert result.confidence_score == 0.9
    
    @patch('app.agents.advanced_skill_generator_workflow.Agent')
    def test_generate_skill_profile_invalid_username(self, mock_agent_class, mock_tools):
        """Test skill profile generation with invalid username."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # Test empty username
        with pytest.raises(ValueError, match="Username cannot be empty"):
            workflow.generate_skill_profile("")
        
        with pytest.raises(ValueError, match="Username cannot be empty"):
            workflow.generate_skill_profile("   ")
    
    @patch('app.agents.advanced_skill_generator_workflow.Agent')
    def test_generate_skill_profile_workflow_failure(self, mock_agent_class, mock_tools):
        """Test skill profile generation when workflow fails."""
        # Mock workflow failure
        mock_workflow = Mock()
        mock_workflow.run.side_effect = Exception("Workflow execution failed")
        
        workflow = AdvancedSkillGeneratorWorkflow()
        workflow.workflow = mock_workflow
        
        with pytest.raises(ValueError, match="Workflow execution failed"):
            workflow.generate_skill_profile("testuser")
    
    def test_save_skill_profile_integration(self, mock_tools):
        """Test saving skill profile integration."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        profile = EnhancedSkillProfile(
            person_name="Save Test User",
            x_handle="@savetest",
            core_expertise=["Saving", "Testing"],
            unique_insights=["Persistence is key"],
            communication_style="Persistent and reliable",
            agent_instructions="Act as a persistence expert",
            confidence_score=0.85
        )
        
        # Mock the skill generator save method - patch where it's imported
        with patch('app.agents.skill_generator.SkillGenerator') as mock_generator_class:
            mock_generator = Mock()
            mock_generator.save_skill.return_value = "skills/savetest"
            mock_generator_class.return_value = mock_generator
            
            result_path = workflow.save_skill_profile(profile)
            
            assert result_path == "skills/savetest"
            mock_generator.save_skill.assert_called_once_with(profile, "skills")


class TestFactoryFunction:
    """Test the factory function for creating workflow instances."""
    
    def test_create_advanced_skill_generator_workflow_default(self, mock_tools):
        """Test factory function with default parameters."""
        workflow = create_advanced_skill_generator_workflow()
        
        assert isinstance(workflow, AdvancedSkillGeneratorWorkflow)
        assert workflow.model_id == "mistral-large-latest"
    
    def test_create_advanced_skill_generator_workflow_custom_model(self, mock_tools):
        """Test factory function with custom model."""
        workflow = create_advanced_skill_generator_workflow(model_id="gpt-3.5-turbo")
        
        assert isinstance(workflow, AdvancedSkillGeneratorWorkflow)
        assert workflow.model_id == "gpt-3.5-turbo"


class TestWorkflowRequirements:
    """Test that the workflow meets specific requirements."""
    
    def test_ac2_1_parallel_execution(self, mock_tools):
        """Test AC2.1: Implements parallel execution for simultaneous data collection."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # Check that workflow contains parallel steps
        workflow_steps = workflow.workflow.steps
        
        # Find parallel steps in the workflow
        parallel_steps = []
        for step in workflow_steps:
            if hasattr(step, 'name') and 'parallel' in step.name.lower():
                parallel_steps.append(step)
        
        # Should have at least one parallel step for data collection
        assert len(parallel_steps) > 0
        
        # Verify metrics show parallel execution
        metrics = workflow.get_workflow_metrics()
        assert metrics["parallel_steps"] >= 2  # Data collection and analysis
    
    def test_ac2_2_conditional_logic(self, mock_tools):
        """Test AC2.2: Uses conditional logic for different profile types."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # Test conditional enhancement logic
        # High-quality profile (verified, high followers) - should not need enhancement
        high_quality_data = {
            "collected_data": {
                "quality_score": 0.9,
                "total_tweets": 30,
                "has_highlights": True
            }
        }
        
        step_input = StepInput(
            input="verifieduser",
            previous_step_content=json.dumps(high_quality_data)
        )
        
        needs_enhancement = workflow._should_enhance_collection(step_input)
        assert needs_enhancement is False  # High-quality profile doesn't need enhancement
        
        # Low-quality profile - should need enhancement
        low_quality_data = {
            "collected_data": {
                "quality_score": 0.4,
                "total_tweets": 8,
                "has_highlights": False
            }
        }
        
        step_input = StepInput(
            input="unverifieduser",
            previous_step_content=json.dumps(low_quality_data)
        )
        
        needs_enhancement = workflow._should_enhance_collection(step_input)
        assert needs_enhancement is True  # Low-quality profile needs enhancement
    
    def test_ac2_3_quality_evaluation_loops(self, mock_tools):
        """Test AC2.3: Includes quality evaluation loops to ensure sufficient data."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # Test quality evaluation function
        sufficient_quality_data = {
            "collected_data": {
                "quality_score": 0.8,
                "has_profile_data": True,
                "total_tweets": 20,
                "has_highlights": True
            }
        }
        
        step_input = StepInput(
            input="testuser",
            previous_step_content=json.dumps(sufficient_quality_data)
        )
        
        quality_passed = workflow._evaluate_data_quality(step_input)
        assert quality_passed is True
        
        # Test insufficient quality
        insufficient_quality_data = {
            "collected_data": {
                "quality_score": 0.3,
                "has_profile_data": False,
                "total_tweets": 3,
                "has_highlights": False
            }
        }
        
        step_input = StepInput(
            input="testuser",
            previous_step_content=json.dumps(insufficient_quality_data)
        )
        
        quality_passed = workflow._evaluate_data_quality(step_input)
        assert quality_passed is False
    
    def test_ac2_4_intelligent_routing(self, mock_tools):
        """Test AC2.4: Provides intelligent routing based on data availability."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # Test routing when both tools are available
        step_input = StepInput(input="testuser")
        result = workflow._validate_profile_input(step_input)
        
        assert result.success is True
        content_data = json.loads(result.content)
        tools_available = content_data["tools_available"]
        assert tools_available["twitter_api"] is True
        assert tools_available["scrapebadger"] is True
        
        # Test routing when only one tool is available
        mock_tools['scrapebadger'].is_available.return_value = False
        
        workflow_partial = AdvancedSkillGeneratorWorkflow()
        result = workflow_partial._validate_profile_input(step_input)
        
        assert result.success is True  # Should still work with one tool
    
    def test_ac2_5_iterative_improvement(self, mock_tools):
        """Test AC2.5: Supports iterative improvement with max iteration limits."""
        workflow = AdvancedSkillGeneratorWorkflow()
        
        # Check that workflow has loop steps with max iterations
        workflow_steps = workflow.workflow.steps
        
        # Find loop steps
        loop_steps = []
        for step in workflow_steps:
            if hasattr(step, 'max_iterations'):
                loop_steps.append(step)
        
        # Should have at least one loop step
        assert len(loop_steps) > 0
        
        # Verify max iterations are set
        for loop_step in loop_steps:
            assert hasattr(loop_step, 'max_iterations')
            assert loop_step.max_iterations > 0


if __name__ == "__main__":
    pytest.main([__file__])

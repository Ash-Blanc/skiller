"""
Example demonstrating the usage of analysis result dataclasses.

This example shows how to create and use the ExpertiseAnalysis,
CommunicationAnalysis, and InsightAnalysis dataclasses for the
advanced skill generator workflow.
"""

from app.models.analysis import (
    create_expertise_analysis, create_communication_analysis, create_insight_analysis,
    ExpertiseType, CommunicationTone, InsightType
)


def demonstrate_analysis_dataclasses():
    """Demonstrate the usage of all three analysis dataclasses."""
    
    print("=== Analysis Result Dataclasses Demo ===\n")
    
    # 1. Expertise Analysis Example
    print("1. Expertise Analysis:")
    print("-" * 30)
    
    expertise = create_expertise_analysis(
        extraction_method="advanced_prompting",
        prompt_version="v1.2",
        model_used="gpt-4o"
    )
    
    # Add expertise items
    expertise.add_expertise_item(
        name="Machine Learning Engineering",
        expertise_type=ExpertiseType.TECHNICAL,
        confidence_score=0.9,
        evidence_sources=["tweet_123", "github_profile"],
        supporting_content=["Built production ML pipelines", "Published ML research"],
        authority_signals=["10k+ GitHub stars", "ML conference speaker"]
    )
    
    expertise.add_expertise_item(
        name="Team Leadership",
        expertise_type=ExpertiseType.SOFT_SKILLS,
        confidence_score=0.8,
        evidence_sources=["linkedin_profile", "tweet_456"],
        supporting_content=["Led 15-person engineering team", "Mentored junior developers"],
        authority_signals=["Engineering manager at FAANG", "Leadership blog posts"]
    )
    
    # Add additional context
    expertise.authority_signals = ["Industry recognition", "Published articles", "Conference keynotes"]
    expertise.content_analyzed = {"tweets": 25, "bio": 1, "highlights": 3}
    
    # Display results
    summary = expertise.get_expertise_summary()
    print(f"Total expertise items: {summary['total_expertise_items']}")
    print(f"High confidence items: {summary['high_confidence_count']}")
    print(f"Overall confidence: {summary['overall_confidence']:.2f}")
    print(f"Quality score: {summary['quality_score']:.2f}")
    
    validation = expertise.validate_analysis()
    print(f"Validation passed: {sum(validation.values())}/{len(validation)} checks")
    print()
    
    # 2. Communication Analysis Example
    print("2. Communication Analysis:")
    print("-" * 30)
    
    communication = create_communication_analysis("pattern_analysis")
    
    # Set primary communication style
    communication.primary_tone = CommunicationTone.TECHNICAL
    communication.secondary_tones = [CommunicationTone.EDUCATIONAL, CommunicationTone.PROFESSIONAL]
    
    # Add writing patterns
    communication.add_writing_pattern(
        pattern_name="Technical Deep Dives",
        description="Provides detailed technical explanations with code examples",
        frequency=0.8,
        examples=[
            "Here's how to implement a distributed cache...",
            "The key insight is understanding async/await patterns..."
        ],
        confidence_score=0.9
    )
    
    communication.add_writing_pattern(
        pattern_name="Storytelling Approach",
        description="Uses narrative structure to explain complex concepts",
        frequency=0.6,
        examples=[
            "I once faced a similar problem when...",
            "This reminds me of a project where..."
        ],
        confidence_score=0.7
    )
    
    # Set additional metrics
    communication.engagement_style = "Educational and interactive"
    communication.communication_strengths = ["Clear explanations", "Practical examples", "Engaging tone"]
    communication.sample_size = 30
    communication.average_post_length = 180.0
    communication.vocabulary_complexity = 0.7
    communication.emotional_range = 0.6
    communication.interaction_frequency = 0.8
    
    # Display results
    summary = communication.get_communication_summary()
    print(f"Primary tone: {summary['primary_tone']}")
    print(f"Total patterns: {summary['total_patterns']}")
    print(f"High confidence patterns: {summary['high_confidence_patterns']}")
    print(f"Overall confidence: {summary['overall_confidence']:.2f}")
    print(f"Sample size: {summary['sample_size']} posts")
    
    validation = communication.validate_analysis()
    print(f"Validation passed: {sum(validation.values())}/{len(validation)} checks")
    print()
    
    # 3. Insight Analysis Example
    print("3. Insight Analysis:")
    print("-" * 30)
    
    insights = create_insight_analysis(
        generation_method="high_engagement_analysis",
        high_engagement_threshold=15
    )
    
    # Add unique insights
    insights.add_insight(
        content="The future of software development will be AI-augmented, not AI-replaced",
        insight_type=InsightType.PREDICTION,
        confidence_score=0.9,
        novelty_score=0.8,
        evidence_sources=["viral_tweet_789"],
        supporting_content=["Analysis of AI coding tools adoption"],
        engagement_metrics={"likes": 250, "retweets": 80, "replies": 45}
    )
    
    insights.add_insight(
        content="Technical debt is actually 'learning debt' - it represents the gap between what we knew then and what we know now",
        insight_type=InsightType.NOVEL_FRAMEWORK,
        confidence_score=0.8,
        novelty_score=0.9,
        evidence_sources=["blog_post", "conference_talk"],
        supporting_content=["Reframing technical debt discussion"],
        engagement_metrics={"likes": 180, "retweets": 60, "replies": 30}
    )
    
    # Set additional context
    insights.value_propositions = [
        "Practical AI implementation expertise",
        "Unique perspective on technical leadership"
    ]
    insights.key_differentiators = [
        "Combines deep technical knowledge with business acumen",
        "Proven track record of scaling engineering teams"
    ]
    insights.thought_leadership_areas = ["AI/ML Engineering", "Technical Leadership", "Software Architecture"]
    insights.total_engagement_analyzed = 200
    
    # Display results
    summary = insights.get_insight_summary()
    print(f"Total insights: {summary['total_insights']}")
    print(f"High confidence insights: {summary['high_confidence_count']}")
    print(f"High novelty insights: {summary['high_novelty_count']}")
    print(f"Average novelty score: {summary['average_novelty_score']:.2f}")
    print(f"Overall confidence: {summary['overall_confidence']:.2f}")
    print(f"Total engagement analyzed: {summary['total_engagement_analyzed']}")
    
    validation = insights.validate_analysis()
    print(f"Validation passed: {sum(validation.values())}/{len(validation)} checks")
    print()
    
    # 4. Integration Example
    print("4. Integration Summary:")
    print("-" * 30)
    
    print("Analysis Results Summary:")
    print(f"• Expertise: {expertise.total_expertise_items} items (confidence: {expertise.overall_confidence:.2f})")
    print(f"• Communication: {communication.total_patterns} patterns (confidence: {communication.overall_confidence:.2f})")
    print(f"• Insights: {insights.total_insights} insights (confidence: {insights.overall_confidence:.2f})")
    print()
    
    # Show how these would be used together
    print("Combined Profile Attributes:")
    print(f"• Core Expertise: {[item.name for item in expertise.high_confidence_expertise]}")
    print(f"• Communication Style: {communication.primary_tone.value} with {len(communication.secondary_tones)} secondary tones")
    print(f"• Key Insights: {len(insights.high_novelty_insights)} high-novelty insights")
    print(f"• Value Propositions: {insights.value_propositions}")
    
    return expertise, communication, insights


if __name__ == "__main__":
    demonstrate_analysis_dataclasses()
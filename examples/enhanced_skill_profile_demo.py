#!/usr/bin/env python3
"""
Demonstration of EnhancedSkillProfile functionality.

This script shows how to create and use EnhancedSkillProfile with confidence
scoring and source attribution capabilities.

Run with: uv run python examples/enhanced_skill_profile_demo.py
"""

import json
from datetime import datetime
from app.models.skill import SkillProfile, EnhancedSkillProfile


def create_sample_enhanced_profile() -> EnhancedSkillProfile:
    """Create a sample EnhancedSkillProfile for demonstration."""
    
    # Basic skill profile data
    basic_data = {
        "person_name": "Sarah Chen",
        "x_handle": "@sarahchen_ai",
        "core_expertise": [
            "Machine Learning Engineering",
            "MLOps",
            "Python",
            "Distributed Systems",
            "Data Pipeline Architecture"
        ],
        "unique_insights": [
            "ML model performance degrades predictably - monitor data drift, not just accuracy",
            "Feature stores are infrastructure, not products - build for reliability first",
            "The best ML architecture is the one your team can actually maintain",
            "Real-time inference is 90% engineering, 10% ML - plan accordingly"
        ],
        "communication_style": "Direct and practical, focuses on production challenges, uses real-world examples from scaling ML systems",
        "agent_instructions": "Act as a senior ML engineer with 8+ years experience scaling ML systems at tech companies. Focus on practical, production-ready solutions rather than theoretical approaches. Always consider operational complexity and team capabilities when making recommendations.",
        "sample_posts": [
            "Spent 3 months debugging a model that worked perfectly in staging. The issue? Training data had timestamps, production didn't. Always validate your feature pipeline end-to-end.",
            "Hot take: Your ML model doesn't need 99.9% accuracy if your data pipeline has 95% reliability. Fix the foundation first.",
            "Just migrated our inference from batch to real-time. Latency went from 4 hours to 200ms, but complexity increased 10x. Worth it? Depends on your business case.",
            "Feature engineering is still the highest ROI activity in ML. Spent 2 days creating one new feature, improved model performance by 15%. Sometimes simple wins."
        ]
    }
    
    # Enhanced data with confidence scoring and source attribution
    enhanced_data = basic_data.copy()
    enhanced_data.update({
        "confidence_score": 0.92,
        "expertise_confidence": {
            "Machine Learning Engineering": 0.95,
            "MLOps": 0.90,
            "Python": 0.85,
            "Distributed Systems": 0.88,
            "Data Pipeline Architecture": 0.92
        },
        "insight_confidence": {
            "ML model performance degrades predictably - monitor data drift, not just accuracy": 0.95,
            "Feature stores are infrastructure, not products - build for reliability first": 0.88,
            "The best ML architecture is the one your team can actually maintain": 0.90,
            "Real-time inference is 90% engineering, 10% ML - plan accordingly": 0.93
        },
        "data_sources": ["TwitterAPI.io", "ScrapeBadger"],
        "source_attribution": {
            "core_expertise": ["TwitterAPI.io", "ScrapeBadger"],
            "unique_insights": ["ScrapeBadger", "TwitterAPI.io"],
            "communication_style": ["TwitterAPI.io"],
            "sample_posts": ["TwitterAPI.io", "ScrapeBadger"],
            "professional_background": ["ScrapeBadger"]
        },
        "quality_metrics": {
            "data_quality_score": 0.88,
            "content_volume_score": 0.85,
            "source_diversity_score": 1.0,
            "engagement_quality_score": 0.92,
            "expertise_validation_score": 0.90
        },
        "collection_metadata": {
            "total_tweets": 127,
            "high_engagement_tweets": 23,
            "total_sources": 2,
            "collection_duration": 18.7,
            "verified_account": True,
            "follower_count": 15420,
            "following_count": 892
        }
    })
    
    return EnhancedSkillProfile(**enhanced_data)


def demonstrate_enhanced_features():
    """Demonstrate the enhanced features of EnhancedSkillProfile."""
    
    print("🚀 Enhanced Skill Profile Demonstration")
    print("=" * 50)
    
    # Create sample profile
    profile = create_sample_enhanced_profile()
    
    print(f"\n👤 Profile: {profile.person_name} ({profile.x_handle})")
    print(f"📊 Overall Confidence: {profile.confidence_score:.2f}")
    print(f"📅 Generated: {profile.generation_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Demonstrate confidence scoring
    print("\n🎯 Confidence Scoring:")
    print("-" * 30)
    
    confidence_summary = profile.get_confidence_summary()
    print(f"Overall Confidence: {confidence_summary['overall_confidence']:.2f}")
    
    expertise_stats = confidence_summary['expertise_confidence']
    print(f"\nExpertise Confidence (avg: {expertise_stats['average']:.2f}):")
    for expertise, confidence in profile.expertise_confidence.items():
        print(f"  • {expertise}: {confidence:.2f}")
    
    insight_stats = confidence_summary['insight_confidence']
    print(f"\nInsight Confidence (avg: {insight_stats['average']:.2f}):")
    for i, (insight, confidence) in enumerate(profile.insight_confidence.items(), 1):
        print(f"  {i}. {insight[:60]}... ({confidence:.2f})")
    
    # Demonstrate source attribution
    print("\n📚 Source Attribution:")
    print("-" * 30)
    
    source_summary = profile.get_source_summary()
    print(f"Total Sources: {source_summary['total_sources']}")
    print(f"Sources Used: {', '.join(source_summary['sources_used'])}")
    print(f"Multi-source Validation: {'✅' if source_summary['has_multi_source_validation'] else '❌'}")
    
    print("\nSource Contributions:")
    for source, info in source_summary['source_contributions'].items():
        print(f"  • {source}: {info['count']} elements")
        for element in info['elements'][:3]:  # Show first 3
            print(f"    - {element}")
        if len(info['elements']) > 3:
            print(f"    - ... and {len(info['elements']) - 3} more")
    
    # Demonstrate quality validation
    print("\n✅ Quality Validation:")
    print("-" * 30)
    
    validations = profile.validate_profile_quality()
    passed = sum(1 for result in validations.values() if result)
    total = len(validations)
    
    print(f"Validation Score: {passed}/{total} ({passed/total*100:.1f}%)")
    
    # Show key validations
    key_validations = [
        "confidence_above_threshold",
        "multi_source_validation", 
        "expertise_confidence_adequate",
        "has_high_confidence_expertise",
        "sufficient_expertise"
    ]
    
    for validation in key_validations:
        status = "✅" if validations.get(validation, False) else "❌"
        print(f"  {status} {validation.replace('_', ' ').title()}")
    
    # Demonstrate quality report
    print("\n📋 Quality Report Summary:")
    print("-" * 30)
    
    report = profile.get_quality_report()
    print(f"Overall Quality Score: {report['overall_quality_score']:.2f}")
    
    if report['recommendations']:
        print("\nRecommendations:")
        for rec in report['recommendations'][:3]:  # Show first 3
            print(f"  • {rec}")
    else:
        print("✅ No recommendations - high quality profile!")
    
    # Demonstrate calculated confidence
    print("\n🧮 Confidence Calculation:")
    print("-" * 30)
    
    calculated = profile.calculate_overall_confidence()
    print(f"Current Confidence: {profile.confidence_score:.2f}")
    print(f"Calculated Confidence: {calculated:.2f}")
    
    if abs(calculated - profile.confidence_score) > 0.01:
        print("💡 Confidence can be updated based on current components")
        profile.update_confidence_score()
        print(f"Updated Confidence: {profile.confidence_score:.2f}")
    
    # Demonstrate JSON serialization
    print("\n💾 JSON Serialization:")
    print("-" * 30)
    
    profile_json = profile.model_dump_json(indent=2)
    print(f"JSON size: {len(profile_json)} characters")
    print("✅ Profile can be serialized to JSON for storage/API")
    
    # Show backward compatibility
    print("\n🔄 Backward Compatibility:")
    print("-" * 30)
    
    def process_skill_profile(skill_profile: SkillProfile) -> str:
        """Function that expects base SkillProfile."""
        return f"Processing {skill_profile.person_name} with {len(skill_profile.core_expertise)} expertise areas"
    
    result = process_skill_profile(profile)
    print(f"✅ {result}")
    print("✅ EnhancedSkillProfile works with existing SkillProfile APIs")
    
    print("\n🎉 Demonstration Complete!")
    print("=" * 50)


if __name__ == "__main__":
    demonstrate_enhanced_features()
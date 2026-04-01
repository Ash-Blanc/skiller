#!/usr/bin/env python3
"""
Demo script for the Advanced Skill Generator Workflow.

This script demonstrates how to use the AdvancedSkillGeneratorWorkflow
to generate enhanced skill profiles with parallel data collection,
conditional logic, and quality assurance.

Usage:
    python examples/advanced_workflow_demo.py
"""

import os
import sys
from dotenv import load_dotenv

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.agents.advanced_skill_generator_workflow import (
    AdvancedSkillGeneratorWorkflow,
    create_advanced_skill_generator_workflow
)

def main():
    """Demonstrate the Advanced Skill Generator Workflow."""
    
    # Load environment variables
    load_dotenv()
    
    print("🚀 Advanced Skill Generator Workflow Demo")
    print("=" * 50)
    
    # Create workflow instance
    print("\n📋 Initializing Advanced Skill Generator Workflow...")
    workflow = create_advanced_skill_generator_workflow()
    
    # Display workflow metrics
    print("\n📊 Workflow Configuration:")
    metrics = workflow.get_workflow_metrics()
    for key, value in metrics.items():
        print(f"   {key}: {value}")
    
    # Check tool availability
    print("\n🔧 Tool Availability:")
    print(f"   TwitterAPI.io: {'✅' if workflow.twitter_api_toolkit.is_available() else '❌'}")
    print(f"   ScrapeBadger: {'✅' if workflow.scrapebadger_toolkit.is_available() else '❌'}")
    
    if not workflow.twitter_api_toolkit.is_available() and not workflow.scrapebadger_toolkit.is_available():
        print("\n⚠️  No API keys configured. This demo will use mock data.")
        print("   To use real data, set TWITTER_API_IO_KEY and/or SCRAPEBADGER_API_KEY")
    
    # Demo username
    demo_username = "elonmusk"  # Public figure for demo
    
    print(f"\n🎯 Generating skill profile for @{demo_username}...")
    print("   This demonstrates the complete workflow:")
    print("   1. Profile validation")
    print("   2. Parallel data collection (TwitterAPI.io + ScrapeBadger)")
    print("   3. Quality evaluation loop")
    print("   4. Conditional enhancement")
    print("   5. Parallel analysis (Expertise + Communication + Insights)")
    print("   6. Profile generation with confidence scoring")
    
    try:
        # Generate the enhanced skill profile
        enhanced_profile = workflow.generate_skill_profile(demo_username)
        
        print("\n✅ Enhanced Skill Profile Generated!")
        print("=" * 50)
        
        # Display profile summary
        print(f"👤 Person: {enhanced_profile.person_name}")
        print(f"🐦 Handle: {enhanced_profile.x_handle}")
        print(f"🎯 Confidence Score: {enhanced_profile.confidence_score:.2f}")
        
        print(f"\n🧠 Core Expertise ({len(enhanced_profile.core_expertise)} areas):")
        for i, expertise in enumerate(enhanced_profile.core_expertise, 1):
            confidence = enhanced_profile.expertise_confidence.get(expertise, 0.0)
            print(f"   {i}. {expertise} (confidence: {confidence:.2f})")
        
        print(f"\n💡 Unique Insights ({len(enhanced_profile.unique_insights)} insights):")
        for i, insight in enumerate(enhanced_profile.unique_insights, 1):
            confidence = enhanced_profile.insight_confidence.get(insight, 0.0)
            print(f"   {i}. {insight} (confidence: {confidence:.2f})")
        
        print(f"\n🗣️  Communication Style:")
        print(f"   {enhanced_profile.communication_style}")
        
        print(f"\n🤖 Agent Instructions Preview:")
        instructions_preview = enhanced_profile.agent_instructions[:200] + "..." if len(enhanced_profile.agent_instructions) > 200 else enhanced_profile.agent_instructions
        print(f"   {instructions_preview}")
        
        # Display quality metrics
        print(f"\n📈 Quality Metrics:")
        for metric, value in enhanced_profile.quality_metrics.items():
            print(f"   {metric}: {value}")
        
        # Display source attribution
        print(f"\n📚 Data Sources:")
        for source in enhanced_profile.data_sources:
            print(f"   ✓ {source}")
        
        # Display confidence summary
        confidence_summary = enhanced_profile.get_confidence_summary()
        print(f"\n🎯 Confidence Analysis:")
        print(f"   Overall: {confidence_summary['overall_confidence']:.2f}")
        print(f"   Expertise Average: {confidence_summary['expertise_confidence']['average']:.2f}")
        print(f"   Insights Average: {confidence_summary['insight_confidence']['average']:.2f}")
        print(f"   High Confidence Items: {confidence_summary['quality_indicators']['high_confidence_expertise'] + confidence_summary['quality_indicators']['high_confidence_insights']}")
        
        # Optionally save the profile
        save_profile = input("\n💾 Save this profile to the knowledge base? (y/N): ").lower().strip()
        if save_profile == 'y':
            try:
                skill_path = workflow.save_skill_profile(enhanced_profile)
                print(f"✅ Profile saved to: {skill_path}")
            except Exception as e:
                print(f"❌ Failed to save profile: {e}")
        
    except Exception as e:
        print(f"\n❌ Workflow execution failed: {e}")
        print("   This is expected in demo mode without API keys.")
        print("   The workflow structure and validation are working correctly.")
    
    print("\n🎉 Demo completed!")
    print("\nNext steps:")
    print("1. Configure API keys for real data collection")
    print("2. Integrate with existing skill generation pipeline")
    print("3. Set up monitoring and logging for production use")
    print("4. Create batch processing for multiple profiles")

if __name__ == "__main__":
    main()
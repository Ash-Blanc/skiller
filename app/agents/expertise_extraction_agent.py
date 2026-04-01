"""
Expertise extraction agent for analyzing professional skills and knowledge areas.

This agent analyzes consolidated profile data to extract expertise areas,
technical skills, and authority signals using advanced NLP and pattern recognition.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import re

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.workflow import Step
import langwatch

from ..models.analysis import ExpertiseAnalysis, ExpertiseItem, ExpertiseType
from ..utils.workflow_metrics import get_workflow_monitor


@dataclass
class ExpertiseArea:
    """Individual expertise area with confidence scoring."""
    domain: str
    subdomain: Optional[str]
    confidence_score: float
    evidence_count: int
    authority_signals: List[str]
    key_topics: List[str]
    proficiency_level: str  # "beginner", "intermediate", "advanced", "expert"
    evidence_sources: List[str]


class ExpertiseExtractionAgent:
    """Agent for extracting expertise and authority signals from profile data."""
    
    def __init__(self):
        self.logger = logging.getLogger("expertise_extraction_agent")
        self.workflow_monitor = get_workflow_monitor()
        
        # Load expertise extraction prompt
        try:
            self.expertise_prompt = langwatch.prompts.get("expertise_extraction")
        except:
            # Fallback prompt if LangWatch is not available
            self.expertise_prompt = self._get_fallback_prompt()
        
        # Create the expertise extraction agent
        self.agent = Agent(
            name="Expertise Extraction Agent",
            instructions=self.expertise_prompt.prompt if hasattr(self.expertise_prompt, 'prompt') else self.expertise_prompt,
            model=OpenAIChat(id="gpt-4o"),
            output_schema=ExpertiseAnalysis
        )
        
        # Domain keywords for expertise detection
        self.domain_keywords = {
            "artificial_intelligence": [
                "ai", "artificial intelligence", "machine learning", "ml", "deep learning", 
                "neural networks", "nlp", "computer vision", "reinforcement learning"
            ],
            "software_engineering": [
                "software", "programming", "coding", "development", "engineer", "backend", 
                "frontend", "fullstack", "devops", "architecture"
            ],
            "data_science": [
                "data science", "data scientist", "analytics", "statistics", "python", 
                "r programming", "sql", "data analysis", "big data"
            ],
            "product_management": [
                "product manager", "pm", "product strategy", "roadmap", "user experience", 
                "product development", "agile", "scrum"
            ],
            "design": [
                "design", "ui", "ux", "user interface", "user experience", "graphic design", 
                "visual design", "interaction design", "design thinking"
            ],
            "marketing": [
                "marketing", "digital marketing", "content marketing", "seo", "sem", 
                "social media", "brand", "growth hacking"
            ],
            "entrepreneurship": [
                "entrepreneur", "startup", "founder", "ceo", "business", "venture capital", 
                "fundraising", "scaling"
            ],
            "research": [
                "research", "researcher", "phd", "academic", "publication", "paper", 
                "study", "analysis", "investigation"
            ]
        }
        
        # Authority signal patterns
        self.authority_patterns = {
            "verification": r"verified|✓|checkmark",
            "leadership": r"ceo|cto|founder|director|head of|lead|senior|principal",
            "education": r"phd|doctorate|master|mba|university|college|degree",
            "publications": r"author|published|paper|research|book|article",
            "speaking": r"speaker|keynote|conference|talk|presentation",
            "awards": r"award|winner|recognition|honor|achievement"
        }
    
    def extract_expertise(self, consolidated_data: Dict[str, Any], 
                         workflow_id: str = None) -> ExpertiseAnalysis:
        """
        Extract expertise areas and authority signals from consolidated profile data.
        
        Args:
            consolidated_data: Consolidated profile and content data
            workflow_id: Optional workflow ID for tracking
            
        Returns:
            ExpertiseAnalysis with extracted expertise and confidence scores
        """
        if workflow_id:
            self.workflow_monitor.start_timer(f"{workflow_id}_expertise_extraction")
        
        username = consolidated_data.get('consolidated_profile', {}).get('username', 'unknown')
        self.logger.info(f"Extracting expertise for {username}")
        
        # Prepare analysis context
        analysis_context = self._prepare_analysis_context(consolidated_data)
        
        # Extract expertise areas using pattern matching and AI analysis
        expertise_areas = self._extract_expertise_areas(analysis_context)
        
        # Detect authority signals
        authority_signals = self._detect_authority_signals(analysis_context)
        
        # Calculate overall confidence score
        overall_confidence = self._calculate_overall_confidence(expertise_areas, authority_signals)
        
        # Create expertise analysis result
        analysis = ExpertiseAnalysis(
            extraction_method="advanced_prompting_with_patterns",
            model_used="gpt-4o"
        )
        
        # Add expertise items
        for area in expertise_areas:
            analysis.add_expertise_item(
                name=area.domain,
                expertise_type=ExpertiseType.TECHNICAL if 'engineering' in area.domain.lower() or 'ai' in area.domain.lower() else ExpertiseType.DOMAIN_KNOWLEDGE,
                confidence_score=area.confidence_score,
                evidence_sources=area.evidence_sources,
                supporting_content=[f"Evidence count: {area.evidence_count}"],
                authority_signals=area.authority_signals
            )
        
        # Add authority signals to analysis
        analysis.authority_signals = [signal.description for signal in authority_signals]
        
        # Set content analyzed metadata
        analysis.content_analyzed = {
            'tweets': len(analysis_context.get('tweets', [])),
            'profile_fields': len(analysis_context.get('profile', {})),
            'highlights': len(analysis_context.get('highlights', []))
        }
        
        # Add source attribution
        analysis.source_attribution = {
            'profile': ['consolidated_profile'],
            'content': ['tweets', 'highlights'],
            'network': ['followings']
        }
        
        # Log extraction results
        if workflow_id:
            duration = self.workflow_monitor.end_timer(f"{workflow_id}_expertise_extraction", workflow_id)
            self.workflow_monitor.log_step_completion(
                workflow_id,
                "expertise_extraction",
                True,
                expertise_areas_found=len(expertise_areas),
                authority_signals_found=len(authority_signals),
                overall_confidence=analysis.overall_confidence,
                primary_domain=analysis.core_expertise[0].name if analysis.core_expertise else None
            )
        
        self.logger.info(
            f"Expertise extraction completed: {len(expertise_areas)} areas found, "
            f"confidence: {analysis.overall_confidence:.2f}, "
            f"primary domain: {analysis.core_expertise[0].name if analysis.core_expertise else 'None'}"
        )
        
        return analysis
    
    def _prepare_analysis_context(self, consolidated_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare analysis context from consolidated data."""
        
        profile = consolidated_data.get('consolidated_profile', {})
        tweets = consolidated_data.get('consolidated_tweets', [])
        followings = consolidated_data.get('consolidated_followings', [])
        highlights = consolidated_data.get('consolidated_highlights', [])
        
        # Combine all text content for analysis
        all_text_content = []
        
        # Profile text
        if profile.get('description'):
            all_text_content.append(profile['description'])
        if profile.get('location'):
            all_text_content.append(profile['location'])
        
        # Tweet content
        for tweet in tweets[:20]:  # Analyze recent tweets
            if tweet.get('text'):
                all_text_content.append(tweet['text'])
        
        # Highlight content
        for highlight in highlights:
            if highlight.get('text'):
                all_text_content.append(highlight['text'])
        
        # Following analysis (expertise by association)
        following_domains = self._analyze_following_domains(followings)
        
        return {
            'profile': profile,
            'tweets': tweets,
            'followings': followings,
            'highlights': highlights,
            'all_text': ' '.join(all_text_content),
            'following_domains': following_domains,
            'content_volume': len(tweets),
            'engagement_metrics': self._calculate_engagement_metrics(tweets)
        }
    
    def _extract_expertise_areas(self, context: Dict[str, Any]) -> List[ExpertiseArea]:
        """Extract expertise areas using pattern matching and AI analysis."""
        
        expertise_areas = []
        all_text = context['all_text'].lower()
        
        # Pattern-based expertise detection
        for domain, keywords in self.domain_keywords.items():
            matches = []
            evidence_count = 0
            
            for keyword in keywords:
                pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                keyword_matches = re.findall(pattern, all_text)
                matches.extend(keyword_matches)
                evidence_count += len(keyword_matches)
            
            if evidence_count > 0:
                # Calculate confidence based on evidence frequency and context
                confidence = min(evidence_count / 10.0, 1.0)  # Normalize to 0-1
                
                # Adjust confidence based on profile authority
                if context['profile'].get('verified'):
                    confidence *= 1.2
                
                if context['profile'].get('followers_count', 0) > 10000:
                    confidence *= 1.1
                
                confidence = min(confidence, 1.0)
                
                # Determine proficiency level
                proficiency = self._determine_proficiency_level(evidence_count, context)
                
                # Extract key topics for this domain
                key_topics = self._extract_key_topics_for_domain(domain, all_text)
                
                # Get authority signals for this domain
                domain_authority = self._get_domain_authority_signals(domain, context)
                
                expertise_area = ExpertiseArea(
                    domain=domain.replace('_', ' ').title(),
                    subdomain=None,  # Could be enhanced with more specific analysis
                    confidence_score=confidence,
                    evidence_count=evidence_count,
                    authority_signals=domain_authority,
                    key_topics=key_topics,
                    proficiency_level=proficiency,
                    evidence_sources=['profile', 'tweets', 'highlights']
                )
                
                expertise_areas.append(expertise_area)
        
        # Sort by confidence score
        expertise_areas.sort(key=lambda x: x.confidence_score, reverse=True)
        
        return expertise_areas[:10]  # Return top 10 expertise areas
    
    def _detect_authority_signals(self, context: Dict[str, Any]) -> List[str]:
        """Detect authority signals in profile and content."""
        
        authority_signals = []
        profile = context['profile']
        all_text = context['all_text'].lower()
        
        # Verification signal
        if profile.get('verified'):
            authority_signals.append("Verified account status")
        
        # Follower count signal
        followers = profile.get('followers_count', 0)
        if followers > 1000:
            authority_signals.append(f"High follower count ({followers:,})")
        
        # Engagement signal
        engagement_metrics = context.get('engagement_metrics', {})
        avg_engagement = engagement_metrics.get('average_engagement', 0)
        if avg_engagement > 10:
            authority_signals.append(f"High engagement rate ({avg_engagement:.1f} avg)")
        
        # Pattern-based authority signals
        for signal_type, pattern in self.authority_patterns.items():
            matches = re.findall(pattern, all_text, re.IGNORECASE)
            if matches:
                authority_signals.append(f"{signal_type.title()} indicators: {', '.join(matches[:3])}")
        
        return authority_signals
    
    def _calculate_overall_confidence(self, expertise_areas: List[ExpertiseArea], 
                                    authority_signals: List[str]) -> float:
        """Calculate overall confidence score for expertise analysis."""
        
        if not expertise_areas:
            return 0.0
        
        # Base confidence from expertise areas
        expertise_confidence = sum(area.confidence_score for area in expertise_areas) / len(expertise_areas)
        
        # Authority boost
        authority_boost = min(len(authority_signals) / 10.0, 0.3)  # Max 30% boost
        
        # Evidence volume boost
        total_evidence = sum(area.evidence_count for area in expertise_areas)
        evidence_boost = min(total_evidence / 50.0, 0.2)  # Max 20% boost
        
        overall_confidence = expertise_confidence + authority_boost + evidence_boost
        return min(overall_confidence, 1.0)
    
    def _identify_primary_domain(self, expertise_areas: List[ExpertiseArea]) -> Optional[str]:
        """Identify the primary domain of expertise."""
        if not expertise_areas:
            return None
        
        # Return the domain with highest confidence
        return expertise_areas[0].domain
    
    def _identify_secondary_domains(self, expertise_areas: List[ExpertiseArea]) -> List[str]:
        """Identify secondary domains of expertise."""
        if len(expertise_areas) <= 1:
            return []
        
        # Return domains with confidence > 0.3, excluding primary
        secondary = [area.domain for area in expertise_areas[1:] if area.confidence_score > 0.3]
        return secondary[:3]  # Max 3 secondary domains
    
    def _extract_proficiency_indicators(self, context: Dict[str, Any]) -> List[str]:
        """Extract indicators of proficiency level."""
        indicators = []
        
        profile = context['profile']
        all_text = context['all_text'].lower()
        
        # Experience indicators
        if re.search(r'\b(\d+)\s*years?\s*(of\s*)?(experience|exp)\b', all_text):
            indicators.append("years_of_experience")
        
        # Leadership indicators
        if re.search(r'\b(lead|senior|principal|architect|director)\b', all_text):
            indicators.append("leadership_role")
        
        # Education indicators
        if re.search(r'\b(phd|doctorate|master|degree)\b', all_text):
            indicators.append("advanced_education")
        
        # Publication indicators
        if re.search(r'\b(published|author|paper|research)\b', all_text):
            indicators.append("publications")
        
        # Speaking indicators
        if re.search(r'\b(speaker|keynote|conference|talk)\b', all_text):
            indicators.append("public_speaking")
        
        return indicators
    
    def _determine_proficiency_level(self, evidence_count: int, context: Dict[str, Any]) -> str:
        """Determine proficiency level based on evidence and context."""
        
        # Base level on evidence count
        if evidence_count >= 10:
            base_level = "expert"
        elif evidence_count >= 5:
            base_level = "advanced"
        elif evidence_count >= 2:
            base_level = "intermediate"
        else:
            base_level = "beginner"
        
        # Adjust based on authority signals
        if context['profile'].get('verified') and evidence_count >= 5:
            return "expert"
        
        if context['profile'].get('followers_count', 0) > 50000 and evidence_count >= 3:
            return "expert" if base_level in ["advanced", "expert"] else "advanced"
        
        return base_level
    
    def _extract_key_topics_for_domain(self, domain: str, text: str) -> List[str]:
        """Extract key topics for a specific domain."""
        
        domain_keywords = self.domain_keywords.get(domain, [])
        found_topics = []
        
        for keyword in domain_keywords:
            if keyword.lower() in text.lower():
                found_topics.append(keyword)
        
        return found_topics[:5]  # Return top 5 topics
    
    def _get_domain_authority_signals(self, domain: str, context: Dict[str, Any]) -> List[str]:
        """Get authority signals specific to a domain."""
        
        signals = []
        all_text = context['all_text'].lower()
        
        # Domain-specific authority patterns
        domain_patterns = {
            "artificial_intelligence": [r"ai researcher", r"ml engineer", r"data scientist"],
            "software_engineering": [r"software engineer", r"developer", r"programmer"],
            "product_management": [r"product manager", r"pm at", r"product lead"],
            "design": [r"designer", r"ux", r"ui designer"],
            "entrepreneurship": [r"founder", r"ceo", r"entrepreneur"]
        }
        
        patterns = domain_patterns.get(domain, [])
        for pattern in patterns:
            if re.search(pattern, all_text):
                signals.append(pattern.replace(r"\b", "").replace(r"\\", ""))
        
        return signals
    
    def _analyze_following_domains(self, followings: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze domains of people being followed for expertise by association."""
        
        domain_counts = {}
        
        for following in followings:
            username = following.get('username', '').lower()
            
            # Simple heuristic based on username patterns
            for domain, keywords in self.domain_keywords.items():
                for keyword in keywords[:3]:  # Check top keywords only
                    if keyword.replace(' ', '') in username:
                        domain_counts[domain] = domain_counts.get(domain, 0) + 1
                        break
        
        return domain_counts
    
    def _calculate_engagement_metrics(self, tweets: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate engagement metrics from tweets."""
        
        if not tweets:
            return {'average_engagement': 0.0, 'total_engagement': 0}
        
        total_engagement = 0
        for tweet in tweets:
            engagement = (tweet.get('like_count', 0) + 
                         tweet.get('retweet_count', 0) + 
                         tweet.get('reply_count', 0))
            total_engagement += engagement
        
        average_engagement = total_engagement / len(tweets)
        
        return {
            'average_engagement': average_engagement,
            'total_engagement': total_engagement
        }
    
    def _get_fallback_prompt(self) -> str:
        """Fallback prompt when LangWatch is not available."""
        return """
        You are an expert at analyzing professional profiles and extracting expertise areas.
        
        Analyze the provided profile data and identify:
        1. Primary areas of expertise and technical skills
        2. Professional domains and specializations  
        3. Authority signals and credibility indicators
        4. Proficiency levels and experience indicators
        
        Focus on:
        - Technical skills mentioned in profile and content
        - Professional roles and responsibilities
        - Industry domains and specializations
        - Educational background and certifications
        - Publications, speaking, and thought leadership
        - Network connections and associations
        
        Provide confidence scores (0.0-1.0) for each expertise area based on:
        - Frequency of mentions
        - Depth of knowledge demonstrated
        - Authority signals present
        - Consistency across content
        """


def create_expertise_extraction_agent() -> ExpertiseExtractionAgent:
    """Factory function to create an expertise extraction agent."""
    return ExpertiseExtractionAgent()


if __name__ == "__main__":
    # Demo expertise extraction
    print("Expertise Extraction Agent Demo")
    print("=" * 50)
    
    # Sample consolidated data
    sample_data = {
        'consolidated_profile': {
            'username': 'ai_researcher',
            'display_name': 'Dr. AI Researcher',
            'description': 'AI researcher and machine learning engineer. PhD in Computer Science. Published 20+ papers on deep learning and NLP.',
            'followers_count': 15000,
            'verified': True,
            'location': 'San Francisco, CA'
        },
        'consolidated_tweets': [
            {'text': 'Working on a new neural network architecture for natural language processing', 'like_count': 50},
            {'text': 'Just published our latest research on transformer models', 'like_count': 120},
            {'text': 'Speaking at the AI conference next week about deep learning advances', 'like_count': 80},
            {'text': 'Excited to share our breakthrough in computer vision applications', 'like_count': 95}
        ],
        'consolidated_followings': [
            {'username': 'deepmind', 'verified': True},
            {'username': 'openai', 'verified': True},
            {'username': 'pytorch', 'verified': True}
        ],
        'consolidated_highlights': [
            {'text': 'Lead AI researcher at top tech company', 'type': 'pinned'},
            {'text': 'Author of "Deep Learning Fundamentals" textbook', 'type': 'featured'}
        ]
    }
    
    # Create and run expertise extraction
    agent = ExpertiseExtractionAgent()
    analysis = agent.extract_expertise(sample_data, "demo_expertise_123")
    
    print(f"Expertise Analysis Results:")
    print(f"Overall Confidence: {analysis.overall_confidence:.2f}")
    print(f"Quality Score: {analysis.quality_score:.2f}")
    print(f"Total Expertise Items: {analysis.total_expertise_items}")
    
    print(f"\nExpertise Areas ({len(analysis.core_expertise)} found):")
    for i, item in enumerate(analysis.core_expertise[:5], 1):
        print(f"  {i}. {item.name}")
        print(f"     Confidence: {item.confidence_score:.2f}")
        print(f"     Type: {item.expertise_type.value}")
        print(f"     Evidence: {len(item.evidence_sources)} sources")
    
    print(f"\nAuthority Signals ({len(analysis.authority_signals)} found):")
    for signal in analysis.authority_signals[:5]:
        print(f"  • {signal}")
    
    print(f"\nTechnical Skills:")
    for skill in analysis.technical_skills:
        print(f"  • {skill}")
    
    print(f"\nDomain Knowledge:")
    for domain in analysis.domain_knowledge:
        print(f"  • {domain}")
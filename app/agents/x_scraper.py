from typing import List, Dict, Tuple
from agno.agent import Agent
from agno.models.mistral import MistralChat
from app.tools.x_scraping_tool import XScrapingToolkit
import langwatch

# Heuristics for quick human detection without LLM call
HUMAN_SIGNALS = [
    "dad", "mom", "father", "mother", "husband", "wife", "parent",
    "building", "prev @", "ex-", "formerly", "founder @", "ceo @",
    "engineer", "designer", "developer", "writer", "author", "investor",
    "he/him", "she/her", "they/them", "🇺🇸", "🇬🇧", "🇮🇳", "🇨🇦",
    "opinions", "my own", "personal", "i'm", "i am", "lover of",
]

ORG_SIGNALS = [
    "official", "™", "®", "inc.", "llc", "corp", "company",
    "we are", "our team", "our mission", "follow us", "join us",
    "news", "updates", "announcements", "customer support", "help desk",
]


class XScraperAgent:
    def __init__(self, model_id: str = "mistral-large-latest"):
        self.model_id = model_id
        self.prompt_config = langwatch.prompts.get("x_following_finder")
        self.x_tools = XScrapingToolkit()
        
        self.agent = Agent(
            model=MistralChat(id=model_id),
            tools=[self.x_tools],
            instructions=self.prompt_config.prompt,
            markdown=True
        )
        
        # Classifier agent for human/org detection
        self.classifier = Agent(
            model=MistralChat(id=model_id),
            instructions="""You are a classifier that determines if an X (Twitter) profile belongs to a HUMAN or an ORGANIZATION.

HUMAN profiles typically have:
- Personal names (not brand names)
- Bios mentioning: family (husband, wife, dad, mom), personal roles (building X, ex-Y), hobbies, personal opinions
- Pronouns (he/him, she/her)
- Job titles with personal context ("CEO @ Company" implies the person, not the company)

ORGANIZATION profiles typically have:
- Brand/company names
- Bios with: "official", "we are", "our team", "follow us", trademarks (™, ®)
- News/updates language
- Customer support mentions

Respond with ONLY one word: HUMAN or ORG""",
            markdown=False
        )

    def _quick_classify(self, bio: str) -> str:
        """Quick heuristic classification without LLM call."""
        bio_lower = bio.lower()
        
        human_score = sum(1 for signal in HUMAN_SIGNALS if signal in bio_lower)
        org_score = sum(1 for signal in ORG_SIGNALS if signal in bio_lower)
        
        if human_score > org_score + 1:
            return "HUMAN"
        elif org_score > human_score + 1:
            return "ORG"
        return "UNKNOWN"
    
    def classify_profile(self, handle: str, name: str, bio: str) -> bool:
        """
        Determines if a profile is a human (True) or organization (False).
        Uses heuristics first, falls back to LLM for ambiguous cases.
        """
        # Quick heuristic check
        quick_result = self._quick_classify(bio)
        if quick_result == "HUMAN":
            return True
        elif quick_result == "ORG":
            return False
        
        # Ambiguous - use LLM
        try:
            prompt = f"Profile: @{handle}\nName: {name}\nBio: {bio}\n\nIs this a HUMAN or ORG?"
            response = self.classifier.run(prompt)
            result = response.content.strip().upper() if response.content else "HUMAN"
            return "HUMAN" in result
        except Exception:
            # Default to human on error
            return True

    def get_following_profiles(self, username: str, verified_only: bool = True, humans_only: bool = True) -> List[str]:
        """
        Gets the list of handles the user follows.
        :param username: The X username to analyze.
        :param verified_only: If True, only return verified (blue tick) accounts.
        :param humans_only: If True, filter out organization accounts.
        """
        # Build the prompt based on filters
        filters = []
        if verified_only:
            filters.append("verified blue checkmark")
        if humans_only:
            filters.append("individual people (not organizations/companies)")
        
        filter_str = " that are " + " and ".join(filters) if filters else ""
        prompt = f"Find the handles followed by @{username}{filter_str}. Return ONLY a comma-separated list of handles, nothing else."
        
        response = self.agent.run(prompt)
        
        # Parse the response
        content = response.content
        if not content:
            return []
            
        handles = [h.strip().replace('@', '') for h in content.split(',') if h.strip()]
        return handles

    def get_posts_for_handle(self, handle: str, count: int = 10) -> str:
        """
        Gets recent posts for a specific handle.
        """
        # We use the raw output from scraping, the skill generator will process it.
        return self.x_tools.get_user_posts(handle, count)
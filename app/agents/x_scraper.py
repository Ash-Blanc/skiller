from typing import List, Dict, Tuple
from agno.agent import Agent
from agno.models.mistral import MistralChat
# CustomXToolkit commented out due to X API rate limits and paywalls
# from app.tools.x_custom_tool import CustomXToolkit
from app.tools.scraper_tools import UnifiedScraperToolkit
import langwatch
import json
import re

# X handle validation pattern: 1-15 alphanumeric chars or underscores
HANDLE_PATTERN = re.compile(r'^[a-zA-Z0-9_]{1,15}$')

def is_valid_handle(handle: str) -> bool:
    """Validate that a string is a valid X handle."""
    if not handle:
        return False
    return bool(HANDLE_PATTERN.match(handle))

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
        # Reload prompt for fallback LLM usage
        self.prompt_config = langwatch.prompts.get("x_following_finder")
        
        # Initialize unified scraper toolkit (BrightData primary → Firecrawl → WebsiteTools)
        self.scraper = UnifiedScraperToolkit()
        
        # Agent for fallback scraping method (LLM + Tools)
        self.scraper_agent = Agent(
            model=MistralChat(id=model_id),
            tools=[self.scraper],
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
        if not bio:
            return "UNKNOWN"
            
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
        Gets the list of handles the user follows using a cascading fallback strategy.
        1. UnifiedScraperToolkit (BrightData → Firecrawl → WebsiteTools)
        2. LLM Agent + Tools (Fallback)
        """
        profiles = []
        
        # Method 1: Direct scrape via UnifiedScraperToolkit
        print(f"   🔄 Attempting Method 1: Unified Scraper (BrightData → Firecrawl)...")
        raw_content = self.scraper.scrape_x_following(username)
        
        if "Error" not in raw_content and "Login wall" not in raw_content and len(raw_content) > 500:
            # We got content but parsing requires LLM
            print(f"   ⚠️ Method 1 got data but parsing requires LLM. Proceeding to LLM fallback...")
        else:
            print(f"   ⚠️ Method 1 failed ({raw_content[:50]}...)")

        # Method 2: Official X API - DISABLED due to rate limits and paywalls
        # print(f"   🔄 Attempting Method 2: Official X API (Fallback 1)...")
        # api_profiles = self.x_api.get_following_handles(username, verified_only=verified_only)
        # 
        # if api_profiles:
        #      print(f"   ✅ Method 2 succeeded, found {len(api_profiles)} handles.")
        #      profiles = api_profiles
        # else:
        #     print(f"   ⚠️ Method 2 failed or returned 0 results.")

        # Method 2 (was 3): LLM Agent + Web Tools (Fallback)
        print(f"   🔄 Attempting Method 2: LLM + Web/Firecrawl...")
        
        filters = []
        if verified_only:
            filters.append("verified blue checkmark")
        if humans_only:
            filters.append("individual people (not organizations/companies)")
        
        filter_str = " that are " + " and ".join(filters) if filters else ""
        prompt = f"Find the handles followed by @{username}{filter_str}. Return ONLY a comma-separated list of handles, nothing else. Use the available tools to scrape the profile or search for this information."
        
        try:
            response = self.scraper_agent.run(prompt)
            content = response.content
            if content:
                handles = [h.strip().replace('@', '') for h in content.split(',') if h.strip()]
                print(f"   ✅ Method 2 succeeded, found {len(handles)} handles.")
                
                # Construct dummy profile objects for the filter loop below
                # (LLM just gave strings, we lack bio/name for filtering unless we fetch,
                # but usually LLM has already done the filtering based on prompt)
                profiles = [{'username': h, 'name': '', 'description': ''} for h in handles]
                
        except Exception as e:
            print(f"   ❌ Method 2 failed: {e}")

        if not profiles:
            return []
            
        final_handles = []
        for p in profiles:
            handle = p.get('username')
            
            # Validate handle format first
            if not is_valid_handle(handle):
                print(f"   ⚠️ Skipping invalid handle: {handle[:30]}...")
                continue
            
            # If we got data from API, we have rich details to double-check.
            # If from LLM, we might have empty name/description.
            name = p.get('name', '')
            bio = p.get('description', '')
            
            # Apply human filter if we have bio data (API path)
            # If LLM path, we trust the LLM's filtering from the prompt
            if humans_only and bio:
                is_human = self.classify_profile(handle, name, bio)
                if not is_human:
                    continue
            
            final_handles.append(handle)
            
        return final_handles

    def get_posts_for_handle(self, handle: str, count: int = 10) -> str:
        """
        Gets recent posts for a specific handle using UnifiedScraperToolkit.
        Fallback chain: BrightData → Firecrawl → WebsiteTools
        
        Note: X API (Tweepy) disabled due to rate limits and paywalls.
        """
        print(f"   🔄 Getting posts for @{handle} (BrightData → Firecrawl → WebsiteTools)...")
        
        result = self.scraper.scrape_x_profile(handle)
        
        if "Error" not in result and "Login wall" not in result:
            return result
        
        print(f"   ⚠️ Scraping failed: {result[:80]}...")
        return result
from typing import List, Dict, Tuple
from agno.agent import Agent
from agno.models.mistral import MistralChat
from app.tools.scraper_tools import UnifiedScraperToolkit
from app.tools.scraper_tools import UnifiedScraperToolkit
from app.tools.twitterapiio_tool import TwitterAPIIOToolkit, get_twitterapiio_toolkit
from app.tools.scrapebadger_tool import ScrapeBadgerToolkit, get_scrapebadger_toolkit
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
        
        # Initialize ScrapeBadger toolkit (Primary)
        self.scrapebadger = get_scrapebadger_toolkit()
        
        # Initialize TwitterAPI.io toolkit (Secondary)
        self.twitterapiio = get_twitterapiio_toolkit()
        
        # Initialize unified scraper toolkit (fallback)
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
        
        Fallback chain:
        1. ScrapeBadger (Primary - most reliable)
        2. TwitterAPI.io (Secondary)
        
        Note: No LLM fallback - that causes hallucination.
        """
        profiles = []
        
        # Method 1: ScrapeBadger (Primary - most reliable)
        if self.scrapebadger and self.scrapebadger.is_available():
            print(f"   🔄 Attempting Method 1: ScrapeBadger...")
            try:
                import json
                followings_json = self.scrapebadger.get_user_followings(
                    username,
                    max_users=200,
                    verified_only=verified_only
                )
                if followings_json and "Error" not in followings_json:
                    followings = json.loads(followings_json)
                    if followings:
                        print(f"   ✅ Method 1 succeeded, found {len(followings)} handles.")
                        profiles = followings
            except Exception as e:
                print(f"   ⚠️ Method 1 failed: {e}")
        
        # Method 2: TwitterAPI.io (Secondary)
        if not profiles:
            if self.twitterapiio and self.twitterapiio.is_available():
                print(f"   🔄 Attempting Method 2: TwitterAPI.io...")
                try:
                    followings = self.twitterapiio.get_user_followings(
                        username, 
                        max_users=200,
                        verified_only=verified_only
                    )
                    if followings:
                        print(f"   ✅ Method 2 succeeded, found {len(followings)} handles.")
                        profiles = followings
                except Exception as e:
                    print(f"   ⚠️ Method 2 failed: {e}")
        
        # No LLM fallback - it causes hallucination!
        # If both methods fail, return empty list

        if not profiles:
            print(f"   ❌ All methods failed. No followings retrieved.")
            return []
            
        final_handles = []
        for p in profiles:
            handle = p.get('username')
            
            # Validate handle format first
            if not is_valid_handle(handle):
                print(f"   ⚠️ Skipping invalid handle: {str(handle)[:30]}...")
                continue
            
            name = p.get('name', '')
            bio = p.get('description', '')
            
            # Apply human filter if we have bio data
            if humans_only and bio:
                is_human = self.classify_profile(handle, name, bio)
                if not is_human:
                    continue
            
            final_handles.append(handle)
            
        return final_handles

    def get_posts_for_handle(self, handle: str, count: int = 10) -> str:
        """
        Gets recent posts for a specific handle.
        
        Fallback chain: TwitterAPI.io → UnifiedScraperToolkit
        """
        handle = handle.replace("@", "").strip()
        
        # Method 1: ScrapeBadger (Primary)
        if self.scrapebadger and self.scrapebadger.is_available():
            print(f"   🔄 Getting posts via ScrapeBadger...")
            try:
                result = self.scrapebadger.get_user_tweets(handle, max_tweets=count)
                if result and "Error" not in result:
                    return result
                print(f"   ⚠️ ScrapeBadger failed or returned empty, trying fallback...")
            except Exception as e:
                print(f"   ⚠️ ScrapeBadger error: {e}")

        # Method 2: TwitterAPI.io (Secondary)
        if self.twitterapiio and self.twitterapiio.is_available():
            print(f"   🔄 Getting posts via TwitterAPI.io...")
            try:
                result = self.twitterapiio.get_user_tweets(handle, max_tweets=count)
                if result and "Error" not in result and len(result) > 50:
                    return result
                print(f"   ⚠️ TwitterAPI.io insufficient, trying fallback...")
            except Exception as e:
                print(f"   ⚠️ TwitterAPI.io failed: {e}")
        
        # Method 3: UnifiedScraperToolkit
        print(f"   🔄 Getting posts via UnifiedScraperToolkit...")
        result = self.scraper.scrape_x_posts(handle, max_tweets=count)
        
        if "Error" not in result and "Login wall" not in result:
            return result
        
        print(f"   ⚠️ Scraping failed: {result[:80]}...")
        return result
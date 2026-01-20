from typing import List, Dict, Tuple
from agno.agent import Agent
from agno.models.mistral import MistralChat
from agno.tools.website import WebsiteTools
from app.tools.x_custom_tool import CustomXToolkit
from app.tools.x_scraping_tool import XScrapingToolkit
import langwatch
import json

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
        
        # Initialize toolkits
        self.firecrawl = XScrapingToolkit()      # Primary
        self.x_api = CustomXToolkit()            # Fallback 1
        self.web_tools = WebsiteTools()          # Fallback 2
        
        # Agent for fallback scraping method (LLM + Tools)
        self.scraper_agent = Agent(
            model=MistralChat(id=model_id),
            tools=[self.firecrawl, self.web_tools], # Giving it both Firecrawl and Generic Web tools
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
        1. Firecrawl Scrape (Primary)
        2. Official X API (Fallback 1)
        3. LLM Agent + Web Tools (Fallback 2)
        """
        profiles = []
        
        # Method 1: Firecrawl (Primary)
        print(f"   🔄 Attempting Method 1: Firecrawl Scrape...")
        raw_html = self.firecrawl.get_following_raw(username)
        
        if "Error" not in raw_html and len(raw_html) > 500:
            # We got raw HTML/content. Parsing this deterministically is hard without structure.
            # Best approach here is to let the LLM agent parse it if it's raw text, 
            # Or pass it to the agent as context?
            # For simplicity in this "Primary" step, we might need a parser.
            # But since Firecrawl returns markdown/text of the page, we can try to extract handles via Regex or simple split 
            # if the format is clean. Often it's mixed. 
            # So paradoxically, using the Agent (Method 3) is best for parsing Firecrawl output if direct API isn't used.
            # However, let's treat "Method 1" here as: Try to get data via Firecrawl and if it looks good, use it.
            # If Firecrawl returns "Sign in", we consider it a fail.
            if "Sign in" in raw_html:
                 print(f"   ⚠️ Method 1 failed (Login wall).")
            else:
                 # It's hard to extract structured data from raw crawl without LLM. 
                 # Let's proceed to Fallback 1 (API) which is more structured, 
                 # AND use Firecrawl data in Method 3 if API fails.
                 print(f"   ⚠️ Method 1 got data but parsing requires LLM. Deferring to Fallback usage if API fails.")
        else:
             print(f"   ⚠️ Method 1 failed ({raw_html[:50]}...)")

        # Method 2: Official X API (Fallback 1)
        print(f"   🔄 Attempting Method 2: Official X API (Fallback 1)...")
        api_profiles = self.x_api.get_following_handles(username, verified_only=verified_only)
        
        if api_profiles:
             print(f"   ✅ Method 2 succeeded, found {len(api_profiles)} handles.")
             profiles = api_profiles
        else:
            print(f"   ⚠️ Method 2 failed or returned 0 results. Attempting Method 3: LLM + Web/Firecrawl...")
            
            # Method 3: LLM Agent + Web Tools (Fallback 2)
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
                    print(f"   ✅ Method 3 succeeded, found {len(handles)} handles.")
                    
                    # Construct dummy profile objects for the filter loop below
                    # (LLM just gave strings, we lack bio/name for filtering unless we fetch,
                    # but usually LLM has already done the filtering based on prompt)
                    profiles = [{'username': h, 'name': '', 'description': ''} for h in handles]
                    
            except Exception as e:
                print(f"   ❌ Method 3 failed: {e}")

        if not profiles:
            return []
            
        final_handles = []
        for p in profiles:
            handle = p.get('username')
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
        Gets recent posts for a specific handle using fallback strategy.
        1. Firecrawl Scrape (Primary)
        2. Official X API (Fallback 1)
        3. Web Tools Scrape (Fallback 2)
        """
        print(f"   🔄 Getting posts for @{handle}...")
        
        # Method 1: Firecrawl (Primary)
        try:
             result = self.firecrawl.get_user_posts(handle, count)
             if "Error" not in result and "Sign in" not in result:
                 return result
             print(f"   ⚠️ Method 1 failed ({result[:50]}...). Attempting Method 2: Official API...")
        except Exception as e:
             print(f"   ⚠️ Method 1 failed with error: {e}")
        
        # Method 2: Official X API (Fallback 1)
        result = self.x_api.get_recent_posts(handle, count)
        if "Error" not in result and "402 Payment Required" not in result:
             return result
             
        print(f"   ⚠️ Method 2 failed ({result[:50]}...). Attempting Method 3: Web Tools fallback...")
        
        # Method 3: Web Tools (Fallback 2)
        try:
            url = f"https://x.com/{handle}"
            # This is a generic scrape, less reliable for X but worth a try as last resort
            web_result = self.web_tools.parse_url(url)
            return str(web_result)
        except Exception as e:
            return f"Error scraping posts: {e}"
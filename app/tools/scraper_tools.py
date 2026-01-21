"""
Unified Scraper Toolkit with cascading fallback strategy.

Fallback chain: BrightData (primary) → Firecrawl → WebsiteTools
"""
import os
from typing import Optional
from agno.tools import Toolkit
from agno.tools.firecrawl import FirecrawlTools
from agno.tools.website import WebsiteTools
from agno.utils.log import logger

# Attempt to import BrightData (optional dependency)
BRIGHTDATA_AVAILABLE = False
try:
    from agno.tools.brightdata import BrightDataTools
    BRIGHTDATA_AVAILABLE = True
except ImportError:
    logger.warning("BrightData not available. Install with: pip install requests")


class UnifiedScraperToolkit(Toolkit):
    """
    Unified scraper with cascading fallback: BrightData → Firecrawl → WebsiteTools.
    
    BrightData is preferred for X/Twitter content via web_data_feed.
    Falls back gracefully if API keys are missing or requests fail.
    """
    
    def __init__(
        self,
        brightdata_api_key: Optional[str] = None,
        firecrawl_api_key: Optional[str] = None,
    ):
        super().__init__(name="unified_scraper")
        
        # Initialize scrapers that are available
        self.brightdata: Optional[BrightDataTools] = None
        self.firecrawl: Optional[FirecrawlTools] = None
        self.web_tools = WebsiteTools()
        
        # BrightData (Primary)
        bd_api_key = brightdata_api_key or os.getenv("BRIGHT_DATA_API_KEY")
        if BRIGHTDATA_AVAILABLE and bd_api_key:
            try:
                self.brightdata = BrightDataTools(
                    api_key=bd_api_key,
                    enable_scrape_markdown=True,
                    enable_web_data_feed=True,
                    enable_screenshot=False,
                    enable_search_engine=False,
                )
                logger.info("✅ BrightData initialized as primary scraper")
            except Exception as e:
                logger.warning(f"Failed to initialize BrightData: {e}")
        else:
            if not BRIGHTDATA_AVAILABLE:
                logger.info("BrightData not installed, using Firecrawl as primary")
            else:
                logger.info("No BRIGHT_DATA_API_KEY, using Firecrawl as primary")
        
        # Firecrawl (Fallback 1)
        firecrawl_key = firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY")
        if firecrawl_key:
            try:
                self.firecrawl = FirecrawlTools(
                    api_key=firecrawl_key,
                    enable_scrape=True,
                    enable_crawl=True
                )
                logger.info("✅ Firecrawl initialized as fallback scraper")
            except Exception as e:
                logger.warning(f"Failed to initialize Firecrawl: {e}")
        else:
            logger.info("No FIRECRAWL_API_KEY, WebsiteTools will be only fallback")
        
        # Register our unified methods
        self.register(self.scrape_url)
        self.register(self.scrape_x_profile)
        self.register(self.scrape_x_posts)
        self.register(self.scrape_x_following)
    
    def scrape_url(self, url: str) -> str:
        """
        Scrape content from any URL using the fallback chain.
        
        Args:
            url: The URL to scrape
            
        Returns:
            Scraped content or error message
        """
        # Try BrightData first (best for JS-heavy sites)
        if self.brightdata:
            try:
                result = self.brightdata.scrape_as_markdown(url=url)
                if result and "Error" not in str(result) and len(str(result)) > 100:
                    return str(result)
                logger.info(f"BrightData insufficient result, trying Firecrawl...")
            except Exception as e:
                logger.warning(f"BrightData failed: {e}")
        
        # Try Firecrawl
        if self.firecrawl:
            try:
                result = self.firecrawl.scrape_website(url=url)
                if result and "Error" not in str(result):
                    return str(result)
                logger.info(f"Firecrawl insufficient result, trying WebsiteTools...")
            except Exception as e:
                logger.warning(f"Firecrawl failed: {e}")
        
        # Last resort: WebsiteTools
        try:
            result = self.web_tools.parse_url(url)
            return str(result)
        except Exception as e:
            return f"All scrapers failed for {url}: {e}"
    
    def scrape_x_posts(self, username: str) -> str:
        """
        Scrape X/Twitter posts using BrightData's web_data_feed.
        
        Args:
            username: X handle (without @)
            
        Returns:
            Posts content as JSON string or error message
        """
        url = f"https://x.com/{username}"
        
        # Try BrightData web_data_feed first (structured data)
        if self.brightdata:
            try:
                result = self.brightdata.web_data_feed(
                    source_type="x_posts",
                    url=url
                )
                if result and "Error" not in str(result):
                    return str(result)
                logger.info(f"BrightData web_data_feed insufficient, trying scrape...")
            except Exception as e:
                logger.warning(f"BrightData web_data_feed failed: {e}")
        
        # Fallback to general scraping
        return self._scrape_with_login_detection(url, username, "posts")
    
    def scrape_x_profile(self, username: str) -> str:
        """
        Scrape an X/Twitter profile page.
        
        Args:
            username: X handle (without @)
            
        Returns:
            Profile content or error message
        """
        url = f"https://x.com/{username}"
        
        # Try BrightData web_data_feed for posts (includes profile info)
        if self.brightdata:
            try:
                result = self.brightdata.web_data_feed(
                    source_type="x_posts",
                    url=url
                )
                if result and "Error" not in str(result):
                    return str(result)
                logger.info(f"BrightData web_data_feed insufficient, trying fallback...")
            except Exception as e:
                logger.warning(f"BrightData web_data_feed failed: {e}")
        
        return self._scrape_with_login_detection(url, username, "profile")
    
    def scrape_x_following(self, username: str) -> str:
        """
        Scrape the following list of an X/Twitter user.
        Note: This often requires authentication and may not work.
        
        Args:
            username: X handle (without @)
            
        Returns:
            Following list content or error message
        """
        url = f"https://x.com/{username}/following"
        return self._scrape_with_login_detection(url, username, "following")
    
    def _scrape_with_login_detection(self, url: str, username: str, context: str) -> str:
        """
        Scrape a URL with detection for login walls.
        
        Args:
            url: URL to scrape
            username: Username for context in error messages
            context: What we're trying to scrape (for error messages)
            
        Returns:
            Scraped content or error message
        """
        result = self.scrape_url(url)
        
        # Detect login walls
        login_indicators = ["Sign in to X", "Log in", "Sign up", "Create your account"]
        if any(indicator in result for indicator in login_indicators):
            return f"Login wall detected for {context} of @{username}. Authentication required."
        
        return result

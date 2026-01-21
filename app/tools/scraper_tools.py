"""
Unified Scraper Toolkit with cascading fallback strategy.

Fallback chain: TwitterAPI.io (primary for X) → Apify → ScrapeGraph → BrightData → Firecrawl → WebsiteTools
"""
import os
from typing import Optional
from agno.tools import Toolkit
from agno.tools.firecrawl import FirecrawlTools
from agno.tools.website import WebsiteTools
from agno.utils.log import logger

# Attempt to import optional dependencies
BRIGHTDATA_AVAILABLE = False
try:
    from agno.tools.brightdata import BrightDataTools
    BRIGHTDATA_AVAILABLE = True
except ImportError:
    pass

SCRAPEGRAPH_AVAILABLE = False
try:
    from agno.tools.scrapegraph import ScrapeGraphTools
    SCRAPEGRAPH_AVAILABLE = True
except ImportError:
    pass

# Import our custom toolkits
APIFY_AVAILABLE = False
try:
    from app.tools.apify_x_tool import ApifyXToolkit
    APIFY_AVAILABLE = True
except ImportError:
    pass

TWITTERAPIIO_AVAILABLE = False
try:
    from app.tools.twitterapiio_tool import TwitterAPIIOToolkit
    TWITTERAPIIO_AVAILABLE = True
except ImportError:
    pass


class UnifiedScraperToolkit(Toolkit):
    """
    Unified scraper with cascading fallback for X/Twitter content.
    
    Fallback chain for X content:
    1. TwitterAPI.io (best - dedicated X API, no auth required)
    2. Apify (pre-built actors)
    3. ScrapeGraph (AI-powered extraction with JS rendering)
    4. BrightData web_data_feed
    5. Firecrawl / WebsiteTools (last resort)
    """
    
    def __init__(
        self,
        brightdata_api_key: Optional[str] = None,
        firecrawl_api_key: Optional[str] = None,
        apify_api_token: Optional[str] = None,
        scrapegraph_api_key: Optional[str] = None,
        twitterapiio_key: Optional[str] = None,
    ):
        super().__init__(name="unified_scraper")
        
        # Initialize scrapers that are available
        self.twitterapiio: Optional[TwitterAPIIOToolkit] = None
        self.apify: Optional[ApifyXToolkit] = None
        self.scrapegraph: Optional[ScrapeGraphTools] = None
        self.brightdata: Optional[BrightDataTools] = None
        self.firecrawl: Optional[FirecrawlTools] = None
        self.web_tools = WebsiteTools()
        
        # TwitterAPI.io (Primary for X content - most reliable)
        if TWITTERAPIIO_AVAILABLE:
            twitterapiio_api_key = twitterapiio_key or os.getenv("TWITTER_API_IO_KEY")
            if twitterapiio_api_key:
                try:
                    self.twitterapiio = TwitterAPIIOToolkit(api_key=twitterapiio_api_key)
                    if self.twitterapiio.is_available():
                        logger.info("✅ TwitterAPI.io initialized as primary X scraper")
                    else:
                        self.twitterapiio = None
                except Exception as e:
                    logger.warning(f"Failed to initialize TwitterAPI.io: {e}")
        
        # Apify (Secondary for X content)
        if APIFY_AVAILABLE:
            apify_token = apify_api_token or os.getenv("APIFY_API_TOKEN")
            if apify_token:
                try:
                    self.apify = ApifyXToolkit(api_token=apify_token)
                    if self.apify.is_available():
                        logger.info("✅ Apify initialized as secondary X scraper")
                    else:
                        self.apify = None
                except Exception as e:
                    logger.warning(f"Failed to initialize Apify: {e}")
        
        # ScrapeGraph (Tertiary for X content - AI-powered with JS rendering)
        if SCRAPEGRAPH_AVAILABLE:
            sgai_key = scrapegraph_api_key or os.getenv("SGAI_API_KEY")
            if sgai_key:
                try:
                    self.scrapegraph = ScrapeGraphTools(
                        api_key=sgai_key,
                        enable_smartscraper=True,
                        render_heavy_js=True,
                    )
                    logger.info("✅ ScrapeGraph initialized as tertiary X scraper")
                except Exception as e:
                    logger.warning(f"Failed to initialize ScrapeGraph: {e}")
        
        # BrightData (Fallback)
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
                logger.info("✅ BrightData initialized as fallback scraper")
            except Exception as e:
                logger.warning(f"Failed to initialize BrightData: {e}")
        
        # Firecrawl (Fallback - but not for X)
        firecrawl_key = firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY")
        if firecrawl_key:
            try:
                self.firecrawl = FirecrawlTools(
                    api_key=firecrawl_key,
                    enable_scrape=True,
                    enable_crawl=True
                )
                logger.info("✅ Firecrawl initialized (non-X fallback)")
            except Exception as e:
                logger.warning(f"Failed to initialize Firecrawl: {e}")
        
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
    
    def scrape_x_posts(self, username: str, max_tweets: int = 20) -> str:
        """
        Scrape X/Twitter posts using cascading fallback.
        
        Fallback chain: TwitterAPI.io → Apify → ScrapeGraph → BrightData → general scraping
        
        Args:
            username: X handle (without @)
            max_tweets: Maximum number of tweets to retrieve
            
        Returns:
            Posts content as JSON string or error message
        """
        username = username.replace("@", "").strip()
        url = f"https://x.com/{username}"
        
        # Method 1: TwitterAPI.io (best - dedicated X API)
        if self.twitterapiio and self.twitterapiio.is_available():
            try:
                logger.info(f"Trying TwitterAPI.io for @{username} posts...")
                result = self.twitterapiio.get_user_tweets(username, max_tweets=max_tweets)
                if result and "Error" not in result and len(result) > 50:
                    return result
                logger.info(f"TwitterAPI.io insufficient result, trying Apify...")
            except Exception as e:
                logger.warning(f"TwitterAPI.io failed: {e}")
        
        # Method 2: Apify (pre-built actors)
        if self.apify and self.apify.is_available():
            try:
                logger.info(f"Trying Apify for @{username} posts...")
                result = self.apify.get_user_tweets(username, max_tweets=max_tweets)
                if result and "Error" not in result and len(result) > 50:
                    return result
                logger.info(f"Apify insufficient result, trying ScrapeGraph...")
            except Exception as e:
                logger.warning(f"Apify failed: {e}")
        
        # Method 3: ScrapeGraph (AI-powered with JS rendering)
        if self.scrapegraph:
            try:
                logger.info(f"Trying ScrapeGraph for @{username} posts...")
                result = self.scrapegraph.smartscraper(
                    url=url,
                    prompt=f"Extract the most recent tweets/posts from this X profile. For each tweet, extract: text content, timestamp, likes count, retweets count, replies count. Return as JSON array."
                )
                if result and "Error" not in str(result) and len(str(result)) > 50:
                    return str(result)
                logger.info(f"ScrapeGraph insufficient result, trying BrightData...")
            except Exception as e:
                logger.warning(f"ScrapeGraph failed: {e}")
        
        # Method 4: BrightData web_data_feed
        if self.brightdata:
            try:
                logger.info(f"Trying BrightData for @{username} posts...")
                result = self.brightdata.web_data_feed(
                    source_type="x_posts",
                    url=url
                )
                if result and "Error" not in str(result) and len(str(result)) > 50:
                    return str(result)
                logger.info(f"BrightData web_data_feed insufficient, trying fallback...")
            except Exception as e:
                logger.warning(f"BrightData web_data_feed failed: {e}")
        
        # Fallback to general scraping (unlikely to work for X)
        return self._scrape_with_login_detection(url, username, "posts")
    
    def scrape_x_profile(self, username: str) -> str:
        """
        Scrape an X/Twitter profile page.
        
        Fallback chain: TwitterAPI.io → Apify → ScrapeGraph → BrightData → general scraping
        
        Args:
            username: X handle (without @)
            
        Returns:
            Profile content or error message
        """
        username = username.replace("@", "").strip()
        url = f"https://x.com/{username}"
        
        # Method 1: TwitterAPI.io
        if self.twitterapiio and self.twitterapiio.is_available():
            try:
                logger.info(f"Trying TwitterAPI.io for @{username} profile...")
                result = self.twitterapiio.get_user_info(username)
                if result and "Error" not in result:
                    return result
                logger.info(f"TwitterAPI.io profile insufficient, trying Apify...")
            except Exception as e:
                logger.warning(f"TwitterAPI.io profile failed: {e}")
        
        # Method 2: Apify
        if self.apify and self.apify.is_available():
            try:
                logger.info(f"Trying Apify for @{username} profile...")
                result = self.apify.get_user_profile(username)
                if result and "Error" not in result:
                    return result
                logger.info(f"Apify profile insufficient, trying ScrapeGraph...")
            except Exception as e:
                logger.warning(f"Apify profile failed: {e}")
        
        # Method 3: ScrapeGraph
        if self.scrapegraph:
            try:
                logger.info(f"Trying ScrapeGraph for @{username} profile...")
                result = self.scrapegraph.smartscraper(
                    url=url,
                    prompt="Extract the user profile information: username, display name, bio/description, follower count, following count, verified status. Return as JSON."
                )
                if result and "Error" not in str(result):
                    return str(result)
                logger.info(f"ScrapeGraph profile insufficient, trying BrightData...")
            except Exception as e:
                logger.warning(f"ScrapeGraph profile failed: {e}")
        
        # Method 4: BrightData
        if self.brightdata:
            try:
                logger.info(f"Trying BrightData for @{username} profile...")
                result = self.brightdata.web_data_feed(
                    source_type="x_posts",
                    url=url
                )
                if result and "Error" not in str(result):
                    return str(result)
                logger.info(f"BrightData profile insufficient, trying fallback...")
            except Exception as e:
                logger.warning(f"BrightData profile failed: {e}")
        
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

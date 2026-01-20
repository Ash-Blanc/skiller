import os
from typing import List, Optional
from agno.tools import Toolkit
from agno.tools.firecrawl import FirecrawlTools

class XScrapingToolkit(Toolkit):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(name="x_scraper")
        self.firecrawl = FirecrawlTools(
            api_key=api_key or os.getenv("FIRECRAWL_API_KEY"),
            enable_scrape=True,
            enable_crawl=True
        )
        self.register(self.get_user_posts)
        self.register(self.get_following_raw)

    def get_user_posts(self, username: str, limit: int = 5) -> str:
        """
        Scrapes the user's X profile to get recent posts.
        :param username: The X handle (without @).
        :param limit: (Not used directly by simple scrape, but good for interface compat).
        """
        url = f"https://x.com/{username}"
        # Fallback to Nitter if X is blocking? Or just try X first.
        # Nitter instances come and go, sticking to X for now.
        # Alternatively, search query "from:username site:x.com"
        
        try:
            # Try direct profile scrape
            result = self.firecrawl.scrape_website(url=url)
            # If result is empty or blocked, try search
            if not result or "Sign in to X" in str(result):
                # Fallback: search for the user's posts
                # This might need the 'search' method if Firecrawl supports it directly or via scrape
                # FirecrawlTools has a search method? Let's check docs or just use scrape with a search URL
                # But Firecrawl 'crawl' might be better.
                pass
            return str(result)
        except Exception as e:
            return f"Error scraping posts for {username}: {str(e)}"

    def get_following_raw(self, username: str) -> str:
        """
        Attempts to scrape the 'following' page of a user.
        Note: This often requires authentication.
        :param username: The X handle.
        """
        url = f"https://x.com/{username}/following"
        try:
            result = self.firecrawl.scrape_website(url=url)
            return str(result)
        except Exception as e:
            return f"Error scraping following list for {username}: {str(e)}"

"""Primary/fallback web search toolkit for Agno agents."""

from __future__ import annotations

from typing import Optional, Any
import os

from agno.tools import Toolkit
from agno.tools.firecrawl import FirecrawlTools
from agno.tools.serper import SerperTools


class WebSearchToolkit(Toolkit):
    """Web search wrapper with Serper as primary and Firecrawl as fallback."""

    def __init__(
        self,
        serper_api_key: Optional[str] = None,
        firecrawl_api_key: Optional[str] = None,
        primary_tools: Optional[SerperTools] = None,
        fallback_tools: Optional[FirecrawlTools] = None,
    ):
        super().__init__(name="web_search")
        self.primary = primary_tools
        self.fallback = fallback_tools

        if self.primary is None:
            key = serper_api_key or os.getenv("SERPER_API_KEY")
            if key:
                try:
                    self.primary = SerperTools(
                        api_key=key,
                        enable_search=True,
                        enable_search_news=True,
                        enable_scrape_webpage=True,
                    )
                except Exception:
                    self.primary = None

        if self.fallback is None:
            key = firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY")
            if key:
                try:
                    self.fallback = FirecrawlTools(
                        api_key=key,
                        enable_search=True,
                        enable_scrape=True,
                        enable_crawl=False,
                    )
                except Exception:
                    self.fallback = None

        self.register(self.search_web)
        self.register(self.search_news)
        self.register(self.scrape_webpage)

    def _coerce(self, value: Any) -> str:
        return value if isinstance(value, str) else str(value)

    def search_web(self, query: str, limit: Optional[int] = None) -> str:
        """Search the web using Serper first, then Firecrawl."""
        if self.primary:
            try:
                result = self.primary.search_web(query=query, num_results=limit)
                if result:
                    return self._coerce(result)
            except Exception:
                pass

        if self.fallback:
            try:
                result = self.fallback.search_web(query=query, limit=limit)
                if result:
                    return self._coerce(result)
            except Exception:
                pass

        return f"No web search backend available for query: {query}"

    def search_news(self, query: str, limit: Optional[int] = None) -> str:
        """Search news with the same primary/fallback order."""
        if self.primary:
            try:
                result = self.primary.search_news(query=query, num_results=limit)
                if result:
                    return self._coerce(result)
            except Exception:
                pass

        return self.search_web(query=query, limit=limit)

    def scrape_webpage(self, url: str, markdown: bool = True) -> str:
        """Scrape a single webpage using Serper first, then Firecrawl."""
        if self.primary:
            try:
                result = self.primary.scrape_webpage(url=url, markdown=markdown)
                if result:
                    return self._coerce(result)
            except Exception:
                pass

        if self.fallback:
            try:
                result = self.fallback.scrape_website(url=url)
                if result:
                    return self._coerce(result)
            except Exception:
                pass

        return f"No web scraping backend available for {url}"

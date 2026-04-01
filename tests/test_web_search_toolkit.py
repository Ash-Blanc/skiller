from __future__ import annotations

from app.tools.web_search_tool import WebSearchToolkit


class _PrimaryStub:
    def __init__(self, search_result=None, news_result=None, scrape_result=None, raise_exc=False):
        self.search_result = search_result
        self.news_result = news_result
        self.scrape_result = scrape_result
        self.raise_exc = raise_exc
        self.calls = []

    def search_web(self, query: str, num_results=None):
        self.calls.append(("search_web", query, num_results))
        if self.raise_exc:
            raise RuntimeError("primary search failed")
        return self.search_result

    def search_news(self, query: str, num_results=None):
        self.calls.append(("search_news", query, num_results))
        if self.raise_exc:
            raise RuntimeError("primary news failed")
        return self.news_result

    def scrape_webpage(self, url: str, markdown: bool = False):
        self.calls.append(("scrape_webpage", url, markdown))
        if self.raise_exc:
            raise RuntimeError("primary scrape failed")
        return self.scrape_result


class _FallbackStub:
    def __init__(self, search_result=None, scrape_result=None):
        self.search_result = search_result
        self.scrape_result = scrape_result
        self.calls = []

    def search_web(self, query: str, limit=None):
        self.calls.append(("search_web", query, limit))
        return self.search_result

    def scrape_website(self, url: str):
        self.calls.append(("scrape_website", url))
        return self.scrape_result


def test_search_web_uses_primary_backend_first():
    primary = _PrimaryStub(search_result="primary search")
    fallback = _FallbackStub(search_result="fallback search")
    toolkit = WebSearchToolkit(primary_tools=primary, fallback_tools=fallback)

    result = toolkit.search_web("python agents", limit=5)

    assert result == "primary search"
    assert primary.calls == [("search_web", "python agents", 5)]
    assert fallback.calls == []


def test_search_web_falls_back_to_secondary_backend():
    primary = _PrimaryStub(raise_exc=True)
    fallback = _FallbackStub(search_result="fallback search")
    toolkit = WebSearchToolkit(primary_tools=primary, fallback_tools=fallback)

    result = toolkit.search_web("python agents", limit=5)

    assert result == "fallback search"
    assert primary.calls == [("search_web", "python agents", 5)]
    assert fallback.calls == [("search_web", "python agents", 5)]


def test_scrape_webpage_falls_back_to_secondary_backend():
    primary = _PrimaryStub(raise_exc=True)
    fallback = _FallbackStub(scrape_result="fallback page")
    toolkit = WebSearchToolkit(primary_tools=primary, fallback_tools=fallback)

    result = toolkit.scrape_webpage("https://example.com")

    assert result == "fallback page"
    assert primary.calls == [("scrape_webpage", "https://example.com", True)]
    assert fallback.calls == [("scrape_website", "https://example.com")]

import pytest
import asyncio
from nexgen_studio.config import settings
from nexgen_studio.providers import (
    TavilySearchProvider,
    FirecrawlScrapeProvider,
    E2BSandboxProvider
)

# Helper to check if API key is present
def has_api_key(key_name: str) -> bool:
    # Map env var names to settings attributes
    mapping = {
        "TAVILY_API_KEY": "tavily_api_key",
        "FIRECRAWL_API_KEY": "firecrawl_api_key",
        "E2B_API_KEY": "e2b_api_key"
    }
    attr = mapping.get(key_name)
    if not attr:
        return False
    return bool(getattr(settings, attr))

@pytest.mark.asyncio
@pytest.mark.skipif(not has_api_key("TAVILY_API_KEY"), reason="TAVILY_API_KEY not set")
async def test_tavily_search_real():
    """Test real Tavily search."""
    provider = TavilySearchProvider(api_key=settings.tavily_api_key)
    
    result = await provider.search("What is the latest version of Python?")
    
    assert result is not None
    assert "Python" in result
    assert "Sources:" in result
    print(f"\n[Tavily] Search Result:\n{result[:200]}...")

@pytest.mark.asyncio
@pytest.mark.skipif(not has_api_key("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not set")
async def test_firecrawl_scrape_real():
    """Test real Firecrawl scraping."""
    provider = FirecrawlScrapeProvider(api_key=settings.firecrawl_api_key)
    
    # Scrape a stable documentation page
    url = "https://example.com"
    markdown = await provider.scrape(url)
    
    assert markdown is not None
    assert "Example Domain" in markdown
    print(f"\n[Firecrawl] Scrape Result:\n{markdown[:200]}...")

@pytest.mark.asyncio
@pytest.mark.skipif(not has_api_key("E2B_API_KEY"), reason="E2B_API_KEY not set")
async def test_e2b_sandbox_real():
    """Test real E2B sandbox execution."""
    provider = E2BSandboxProvider(api_key=settings.e2b_api_key)
    
    code = """
import math
print(f"Sqrt of 16 is {math.sqrt(16)}")
"""
    result = await provider.run_code(code)
    
    assert result["error"] is None
    assert "Sqrt of 16 is 4.0" in result["stdout"]
    print(f"\n[E2B] Execution Result:\n{result}")

import pytest
import asyncio
import os

# Get API keys directly from environment (loaded by conftest.py)
def has_api_key(key_name: str) -> bool:
    """Check if API key is present in environment."""
    return bool(os.environ.get(key_name))

# Lazy load settings to ensure .env is loaded first
def get_settings():
    from lewis_ai_system.config import Settings
    return Settings()

@pytest.mark.asyncio
@pytest.mark.skipif(not has_api_key("TAVILY_API_KEY"), reason="TAVILY_API_KEY not set")
async def test_tavily_search_real():
    """Test real Tavily search."""
    from lewis_ai_system.providers import TavilySearchProvider
    settings = get_settings()
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
    from lewis_ai_system.providers import FirecrawlScrapeProvider
    settings = get_settings()
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
    from lewis_ai_system.providers import E2BSandboxProvider
    settings = get_settings()
    provider = E2BSandboxProvider(api_key=settings.e2b_api_key)
    
    code = """
import math
print(f"Sqrt of 16 is {math.sqrt(16)}")
"""
    result = await provider.run_code(code)
    
    assert result["error"] is None
    assert "Sqrt of 16 is 4.0" in result["stdout"]
    print(f"\n[E2B] Execution Result:\n{result}")

import pytest
from unittest.mock import MagicMock, AsyncMock
from nexgen_studio.tooling import WebSearchTool, PythonSandboxTool, WebScrapeTool, ToolRequest
from nexgen_studio.providers import TavilySearchProvider, E2BSandboxProvider, FirecrawlScrapeProvider

def test_web_search_tool_uses_provider():
    # Mock provider
    mock_provider = MagicMock(spec=TavilySearchProvider)
    mock_provider.search = AsyncMock(return_value="Search results")
    mock_provider.name = "tavily"
    
    tool = WebSearchTool()
    tool.provider = mock_provider # Inject mock
    
    result = tool.run({"query": "test"})
    
    assert result.output["result"] == "Search results"
    mock_provider.search.assert_called_once_with("test")

def test_sandbox_tool_uses_e2b_provider():
    from unittest.mock import patch
    from nexgen_studio.sandbox import EnhancedSandbox
    
    # Mock the EnhancedSandbox.execute_python method
    mock_sandbox = MagicMock(spec=EnhancedSandbox)
    mock_sandbox.execute_python = MagicMock(return_value={
        "stdout": "Hello",
        "stderr": "",
        "result": None,
        "results": [],
        "error": None
    })
    
    tool = PythonSandboxTool()
    # Inject mock sandbox
    tool._sandbox = mock_sandbox
    
    result = tool.run({"code": "print('Hello')"})
    
    assert result.output["stdout"] == "Hello"
    mock_sandbox.execute_python.assert_called_once()

def test_web_scrape_tool_uses_provider():
    mock_provider = MagicMock(spec=FirecrawlScrapeProvider)
    mock_provider.scrape = AsyncMock(return_value="# Markdown Content")
    mock_provider.name = "firecrawl"
    
    tool = WebScrapeTool()
    tool.provider = mock_provider
    
    result = tool.run({"url": "http://example.com"})
    
    assert result.output["content"] == "# Markdown Content"
    mock_provider.scrape.assert_called_once_with("http://example.com")


def test_web_search_tool_provider_override(monkeypatch):
    tool = WebSearchTool()
    mock_provider = MagicMock(spec=TavilySearchProvider)
    mock_provider.search = AsyncMock(return_value="override result")
    tool._provider_factory = MagicMock(return_value=mock_provider)

    result = tool.run({"query": "hello", "provider": "tavily"})

    assert result.output["result"] == "override result"
    tool._provider_factory.assert_called_once_with("tavily")
    mock_provider.search.assert_called_once_with("hello")


def test_web_scrape_tool_provider_override():
    tool = WebScrapeTool()
    mock_provider = MagicMock(spec=FirecrawlScrapeProvider)
    mock_provider.scrape = AsyncMock(return_value="content")
    tool._provider_factory = MagicMock(return_value=mock_provider)

    result = tool.run({"url": "http://example.com", "provider": "firecrawl"})

    assert result.output["content"] == "content"
    tool._provider_factory.assert_called_once_with("firecrawl")
    mock_provider.scrape.assert_called_once_with("http://example.com")

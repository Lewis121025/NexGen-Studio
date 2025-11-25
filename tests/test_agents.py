import pytest
from unittest.mock import AsyncMock, MagicMock
from nexgen_studio.agents import PlanningAgent, QualityAgent, OutputFormatterAgent
from nexgen_studio.providers import LLMProvider

@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=LLMProvider)
    provider.complete = AsyncMock()
    return provider

@pytest.mark.asyncio
async def test_planning_agent_expand_brief(mock_provider):
    mock_provider.complete.return_value = "Expanded brief content"
    agent = PlanningAgent(provider=mock_provider)
    
    result = await agent.expand_brief("Make a video", mode="creative")
    
    assert result["summary"] == "Expanded brief content"
    assert result["mode"] == "creative"
    assert "hash" in result
    mock_provider.complete.assert_called_once()

@pytest.mark.asyncio
async def test_quality_agent_evaluate(mock_provider):
    mock_provider.complete.return_value = "The score is 0.9 because it is good."
    agent = QualityAgent(provider=mock_provider)
    
    result = await agent.evaluate("Some content", criteria=["clarity"])
    
    assert result["score"] == 0.9
    assert result["notes"] == "The score is 0.9 because it is good."
    assert result["criteria"] == ["clarity"]
    mock_provider.complete.assert_called_once()

@pytest.mark.asyncio
async def test_output_formatter_agent_summarize(mock_provider):
    mock_provider.complete.return_value = "Summary"
    agent = OutputFormatterAgent(provider=mock_provider)
    
    result = await agent.summarize("Long content")
    
    assert result == "Summary"
    mock_provider.complete.assert_called_once()

import pytest
from unittest.mock import MagicMock, AsyncMock
from nexgen_studio.general.session import GeneralModeOrchestrator, SessionRecordingToolRuntime
from nexgen_studio.general.models import GeneralSessionCreateRequest, GeneralSessionState
from nexgen_studio.general.repository import InMemoryGeneralSessionRepository
from nexgen_studio.tooling import ToolRuntime, Tool, ToolResult
from nexgen_studio.agents import agent_pool

class MockTool(Tool):
    name = "mock_tool"
    description = "A mock tool"
    
    def run(self, payload):
        return ToolResult(output="mock_result", cost_usd=0.01)

@pytest.fixture
def mock_llm_provider():
    provider = AsyncMock()
    return provider

@pytest.mark.asyncio
async def test_general_react_loop_execution(mock_llm_provider):
    # Setup
    runtime = ToolRuntime()
    runtime.register(MockTool())
    
    # Mock LLM responses for ReAct loop
    # 1. Thought + Action
    # 2. Final Answer
    mock_llm_provider.complete.side_effect = [
        'Thought: I need to use the mock tool.\nAction: mock_tool\nAction Input: {"key": "value"}',
        'Thought: I have the result.\nFinal Answer: The result is mock_result'
    ]
    
    # Patch agent provider
    with pytest.MonkeyPatch.context() as m:
        m.setattr(agent_pool.general, "provider", mock_llm_provider)
        
        repo = InMemoryGeneralSessionRepository()
        orchestrator = GeneralModeOrchestrator(repository=repo, tool_runtime=runtime)
        
        # Create session
        session = await orchestrator.create_session(
            GeneralSessionCreateRequest(goal="Test Goal", tenant_id="test")
        )
        
        # Run iteration (which runs the whole loop now)
        updated_session = await orchestrator.run_iteration(session.id)
        
        # Verify
        assert updated_session.state == GeneralSessionState.COMPLETED
        assert "The result is mock_result" in updated_session.summary
        
        # Verify tool calls were recorded
        assert len(updated_session.tool_calls) == 1
        assert updated_session.tool_calls[0].tool == "mock_tool"
        assert updated_session.tool_calls[0].output == {"text": "mock_result"}
        
        # Verify LLM calls
        assert mock_llm_provider.complete.call_count == 2

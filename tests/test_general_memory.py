import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nexgen_studio.general.models import GeneralSessionCreateRequest, GeneralSessionState
from nexgen_studio.general.repository import InMemoryGeneralSessionRepository
from nexgen_studio.general.session import GeneralModeOrchestrator


@pytest.mark.asyncio
async def test_general_session_records_memory_and_compresses_history():
    repo = InMemoryGeneralSessionRepository()
    orchestrator = GeneralModeOrchestrator(
        repository=repo,
        memory_window=2,
        compression_threshold=4,
    )

    session = await orchestrator.create_session(GeneralSessionCreateRequest(goal="test"))
    session.messages = [f"msg-{i}" for i in range(6)]
    await repo.upsert(session)

    dummy_runtime = MagicMock()

    class _Result:
        def __init__(self) -> None:
            self.output = {"text": "ok"}
            self.cost_usd = 0.0

    dummy_runtime.execute.return_value = _Result()
    orchestrator.tool_runtime = dummy_runtime

    with patch("nexgen_studio.agents.agent_pool.general.react_loop", AsyncMock(return_value="done")):
        with patch("nexgen_studio.vector_db.vector_db.store_conversation_memory", AsyncMock()) as mock_store:
            with patch("nexgen_studio.agents.agent_pool.formatter.summarize", AsyncMock(return_value="summary")):
                updated = await orchestrator.run_iteration(session.id)

    assert updated.state == GeneralSessionState.COMPLETED
    assert any(msg.startswith("[历史摘要]") for msg in updated.messages)
    mock_store.assert_called_once()

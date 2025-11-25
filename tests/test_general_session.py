import pytest

from nexgen_studio.agents import agent_pool
from nexgen_studio.general.models import (
    GeneralSessionCreateRequest,
    GeneralSessionState,
)
from nexgen_studio.general.repository import InMemoryGeneralSessionRepository
from nexgen_studio.general.session import GeneralModeOrchestrator
from nexgen_studio.tooling import PythonSandboxTool, ToolRequest, ToolRuntime, WebSearchTool


@pytest.mark.asyncio
async def test_general_session_runs_iteration():
    repo = InMemoryGeneralSessionRepository()
    runtime = ToolRuntime()
    runtime.register(PythonSandboxTool())
    runtime.register(WebSearchTool())

    orchestrator = GeneralModeOrchestrator(repository=repo, tool_runtime=runtime)

    with pytest.MonkeyPatch.context() as patcher:
        async def fake_react_loop(goal, recording_runtime, max_steps=None):
            recording_runtime.execute(
                ToolRequest(name="python_sandbox", input={"code": "print(2+2)"})
            )
            return "Finished"

        patcher.setattr(agent_pool.general, "react_loop", fake_react_loop)

        session = await orchestrator.create_session(
            GeneralSessionCreateRequest(goal="Find latest trends about AI", max_iterations=2)
        )
        session = await orchestrator.run_iteration(session.id)
    assert session.iteration == 1
    assert session.tool_calls, "iteration should record a tool call"


@pytest.mark.asyncio
async def test_general_session_completes_when_limit_reached():
    repo = InMemoryGeneralSessionRepository()
    runtime = ToolRuntime()
    runtime.register(PythonSandboxTool())

    orchestrator = GeneralModeOrchestrator(repository=repo, tool_runtime=runtime)
    with pytest.MonkeyPatch.context() as patcher:
        async def fake_react_loop(goal, recording_runtime, max_steps=None):
            return "Done"

        patcher.setattr(agent_pool.general, "react_loop", fake_react_loop)

        session = await orchestrator.create_session(
            GeneralSessionCreateRequest(goal="Calculate something", max_iterations=1)
        )
        session = await orchestrator.run_iteration(session.id)
    assert session.state == GeneralSessionState.COMPLETED
    assert session.summary is not None

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from nexgen_studio.agents import agent_pool
from nexgen_studio.creative.models import CreativeProjectCreateRequest, CreativeProjectState
from nexgen_studio.creative.repository import InMemoryCreativeProjectRepository
from nexgen_studio.creative.workflow import CreativeOrchestrator
from nexgen_studio.general.models import GeneralSessionCreateRequest, GeneralSessionState
from nexgen_studio.general.repository import InMemoryGeneralSessionRepository
from nexgen_studio.general.session import GeneralModeOrchestrator
from nexgen_studio.storage import ArtifactStorage


class DummyToolRuntime:
    """Minimal runtime to satisfy SessionRecordingToolRuntime."""

    def __init__(self) -> None:
        self._tools: dict[str, object] = {}
        self.executed = False

    def execute(self, request):  # pragma: no cover - defensive fallback
        self.executed = True

        class _Result:
            def __init__(self) -> None:
                self.output = {"echo": request.input}
                self.cost_usd = 0.0

        return _Result()


@pytest.mark.asyncio
async def test_creative_mode_e2e_flow(tmp_path):
    with pytest.MonkeyPatch.context() as patcher:
        planning_agent = AsyncMock()
        planning_agent.expand_brief.return_value = {
            "summary": "Expanded brief summary",
            "hash": "deadbeef",
            "mode": "creative",
        }

        creative_agent = AsyncMock()
        creative_agent.write_script.return_value = "SCENE 1: LAB\nAction\n\nSCENE 2: STREET\nAction"
        creative_agent.split_script.return_value = [
            {"description": "Scene 1", "visual_cues": "Wide", "estimated_duration": 5},
            {"description": "Scene 2", "visual_cues": "Close", "estimated_duration": 5},
        ]
        creative_agent.generate_panel_visual.side_effect = [
            "https://mock.assets/scene-1.jpg",
            "https://mock.assets/scene-2.jpg",
        ]

        quality_agent = AsyncMock()
        quality_agent.evaluate.return_value = {
            "score": 0.92,
            "criteria": ["composition"],
            "notes": "Looks good",
        }

        patcher.setattr(agent_pool, "planning", planning_agent)
        patcher.setattr(agent_pool, "creative", creative_agent)
        patcher.setattr(agent_pool, "quality", quality_agent)

        repo = InMemoryCreativeProjectRepository()
        orchestrator = CreativeOrchestrator(repository=repo, storage=ArtifactStorage(tmp_path))

        project = await orchestrator.create_project(
            CreativeProjectCreateRequest(title="Ad Spot", brief="Showcase EV launch")
        )
        assert project.state == CreativeProjectState.SCRIPT_REVIEW
        assert project.summary == "Expanded brief summary"
        assert "SCENE 1" in project.script

        approved = await orchestrator.approve_script(project.id)
        assert approved.state == CreativeProjectState.STORYBOARD_READY
        assert len(approved.storyboard) == 2
        assert approved.storyboard[0].visual_reference_path == "https://mock.assets/scene-1.jpg"
        assert approved.storyboard[0].quality_score == 0.92


@pytest.mark.asyncio
async def test_general_mode_e2e_flow():
    dummy_runtime = DummyToolRuntime()
    repo = InMemoryGeneralSessionRepository()
    orchestrator = GeneralModeOrchestrator(repository=repo, tool_runtime=dummy_runtime)

    with pytest.MonkeyPatch.context() as patcher:
        general_agent = AsyncMock()
        general_agent.react_loop.return_value = "105"
        patcher.setattr(agent_pool, "general", general_agent)

        session = await orchestrator.create_session(
            GeneralSessionCreateRequest(goal="What is 15 * 7?", max_iterations=1)
        )
        updated = await orchestrator.run_iteration(session.id)

        assert updated.state == GeneralSessionState.COMPLETED
        assert updated.summary == "105"
        assert any("Final Answer" in message for message in updated.messages)
        assert not dummy_runtime.executed


import pytest
import json
from unittest.mock import MagicMock, AsyncMock

from nexgen_studio.creative.models import CreativeProjectCreateRequest, CreativeProjectState
from nexgen_studio.creative.repository import InMemoryCreativeProjectRepository
from nexgen_studio.creative.workflow import CreativeOrchestrator
from nexgen_studio.storage import ArtifactStorage
from nexgen_studio.providers import LLMProvider
from nexgen_studio.agents import agent_pool

@pytest.fixture
def mock_llm_provider():
    provider = MagicMock(spec=LLMProvider)
    provider.complete = AsyncMock()
    return provider

@pytest.mark.asyncio
async def test_creative_workflow_reaches_script_review(tmp_path, mock_llm_provider):
    # Mock agents
    mock_creative = AsyncMock()
    mock_creative.write_script.return_value = "SCENE 1: INT. LAB - DAY\nA scientist works."
    
    mock_planning = AsyncMock()
    mock_planning.expand_brief.return_value = {"summary": "Expanded brief summary", "hash": "123", "mode": "creative"}

    with pytest.MonkeyPatch.context() as m:
        m.setattr(agent_pool, "creative", mock_creative)
        m.setattr(agent_pool, "planning", mock_planning)
        
        repo = InMemoryCreativeProjectRepository()
        orchestrator = CreativeOrchestrator(repository=repo, storage=ArtifactStorage(tmp_path))
        request = CreativeProjectCreateRequest(
            title="Test Project",
            brief="Create a short inspirational story.",
        )
        project = await orchestrator.create_project(request)
        
        assert project.state == CreativeProjectState.SCRIPT_REVIEW
        assert project.summary == "Expanded brief summary"
        assert project.script == "SCENE 1: INT. LAB - DAY\nA scientist works."
        
        # Verify calls
        mock_planning.expand_brief.assert_called_once()
        mock_creative.write_script.assert_called_once()

@pytest.mark.asyncio
async def test_creative_approval_builds_storyboard_with_json_parsing(tmp_path, mock_llm_provider):
    scenes_data = [
        {
            "description": "Scene 1 description",
            "visual_cues": "Wide shot",
            "estimated_duration": 5
        },
        {
            "description": "Scene 2 description",
            "visual_cues": "Close up",
            "estimated_duration": 5
        }
    ]
    
    # Mock agents
    mock_creative = AsyncMock()
    mock_creative.write_script.return_value = "Script content"
    mock_creative.split_script.return_value = scenes_data
    mock_creative.generate_panel_visual.side_effect = [
        "http://mock/1.jpg",
        "http://mock/2.jpg"
    ]
    
    mock_planning = AsyncMock()
    mock_planning.expand_brief.return_value = {"summary": "Expanded brief", "hash": "123", "mode": "creative"}
    
    mock_quality = AsyncMock()
    mock_quality.evaluate.return_value = {"score": 0.9, "criteria": [], "notes": "Good"}

    with pytest.MonkeyPatch.context() as m:
        m.setattr(agent_pool, "creative", mock_creative)
        m.setattr(agent_pool, "planning", mock_planning)
        m.setattr(agent_pool, "quality", mock_quality)

        repo = InMemoryCreativeProjectRepository()
        orchestrator = CreativeOrchestrator(repository=repo, storage=ArtifactStorage(tmp_path))
        
        # Create project in SCRIPT_REVIEW state
        project = await orchestrator.create_project(
            CreativeProjectCreateRequest(
                title="Storyboard Demo",
                brief="Tell a tale about explorers on Mars.",
            )
        )
        # Manually set script and state to skip previous steps for this specific test
        project.script = "SCENE 1...\nSCENE 2..."
        project.state = CreativeProjectState.SCRIPT_REVIEW
        await repo.upsert(project)
        
        # Approve
        updated = await orchestrator.approve_script(project.id)
        
        assert updated.state == CreativeProjectState.STORYBOARD_READY
        assert len(updated.storyboard) == 2
        assert updated.storyboard[0].description == "Scene 1 description"
        assert updated.storyboard[0].camera_notes == "Wide shot"
        assert updated.storyboard[0].quality_score == 0.9
        assert updated.storyboard[0].visual_reference_path == "http://mock/1.jpg"
        
        # Verify calls
        mock_creative.split_script.assert_called_once()
        assert mock_creative.generate_panel_visual.call_count == 2

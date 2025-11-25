import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock
from nexgen_studio.creative.workflow import CreativeOrchestrator, CreativeProject, CreativeProjectState
from nexgen_studio.agents import agent_pool

@pytest.mark.asyncio
async def test_parallel_storyboard_generation():
    # Setup
    orchestrator = CreativeOrchestrator()
    
    # Mock project
    project = MagicMock(spec=CreativeProject)
    project.id = "test_project"
    project.script = "Scene 1\n\nScene 2\n\nScene 3"
    project.duration_seconds = 15
    project.budget_limit_usd = 100.0
    project.cost_usd = 0.0
    project.auto_pause_enabled = False
    
    # Mock repository
    orchestrator.repository = AsyncMock()
    orchestrator.repository.get.return_value = project
    orchestrator.repository.upsert.return_value = project
    
    # Mock storage
    orchestrator.storage = MagicMock()
    
    # Mock agents
    # We want to verify parallelism, so we'll add a delay to the mock methods
    delay = 0.1
    
    async def delayed_generate(*args, **kwargs):
        await asyncio.sleep(delay)
        return "http://mock.url/image.jpg"
        
    async def delayed_evaluate(*args, **kwargs):
        await asyncio.sleep(delay)
        return {"score": 0.9, "notes": "Good"}
        
    async def delayed_split(*args, **kwargs):
        return [
            {"description": "Scene 1", "estimated_duration": 5},
            {"description": "Scene 2", "estimated_duration": 5},
            {"description": "Scene 3", "estimated_duration": 5},
        ]

    with pytest.MonkeyPatch.context() as m:
        m.setattr(agent_pool.creative, "generate_panel_visual", AsyncMock(side_effect=delayed_generate))
        m.setattr(agent_pool.quality, "evaluate", AsyncMock(side_effect=delayed_evaluate))
        m.setattr(agent_pool.creative, "split_script", AsyncMock(side_effect=delayed_split))
        
        # Mock internal methods to avoid side effects but keep _generate_storyboard logic
        # actually we want to test _generate_storyboard, so we don't mock it.
        # We need to mock _record_cost_guardrail to avoid side effects
        m.setattr(orchestrator, "_record_cost_guardrail", MagicMock(return_value=False))
        
        start_time = time.perf_counter()
        await orchestrator._generate_storyboard(project)
        end_time = time.perf_counter()
        
        duration = end_time - start_time
        
        # If sequential: 3 scenes * (generate + evaluate) = 3 * (0.1 + 0.1) = 0.6s (approx, since gen/eval are parallel per scene)
        # Actually, per scene: generate and evaluate are parallel? 
        # Let's check workflow.py:
        # evaluation, visual_url = await asyncio.gather(...) -> parallel within scene
        # panels = await asyncio.gather(*tasks) -> parallel across scenes
        
        # So total time should be roughly equal to max(generate, evaluate) = 0.1s
        # If it was fully sequential it would be 3 * 0.1 = 0.3s
        
        print(f"Execution time: {duration:.4f}s")
        
        # We allow some overhead, but it should be much faster than sequential
        # 3 scenes * 0.1s = 0.3s. Parallel should be close to 0.1s.
        assert duration < 0.25, f"Execution took {duration}s, expected < 0.25s for parallel execution"
        
        # Verify results
        assert len(project.storyboard) == 3
        assert project.storyboard[0].visual_reference_path == "http://mock.url/image.jpg"

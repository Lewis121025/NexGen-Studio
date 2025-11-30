"""测试一致性控制功能"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from lewis_ai_system.creative.consistency_manager import consistency_manager
from lewis_ai_system.creative.models import CreativeProject, CreativeProjectCreateRequest
from lewis_ai_system.creative.workflow import CreativeOrchestrator


@pytest.mark.asyncio
async def test_consistency_manager_feature_extraction():
    """测试一致性管理器的特征提取功能"""
    # 测试特征提取
    features = await consistency_manager.extract_consistency_features("https://example.com/image.jpg")
    
    assert "character_features" in features
    assert "scene_features" in features
    assert "style_features" in features
    assert isinstance(features["character_features"], dict)
    assert isinstance(features["scene_features"], dict)
    assert isinstance(features["style_features"], dict)


@pytest.mark.asyncio
async def test_consistency_manager_prompt_generation():
    """测试一致性提示词生成"""
    base_prompt = "A person walking in the park"
    features = {
        "character_features": {
            "gender": "male",
            "age_range": "adult",
            "hair_style": "short"
        },
        "scene_features": {
            "environment": "park",
            "lighting": "natural"
        }
    }
    
    # 测试不同级别的一致性提示词
    low_prompt = await consistency_manager.generate_consistency_prompt(
        base_prompt, features, "low"
    )
    medium_prompt = await consistency_manager.generate_consistency_prompt(
        base_prompt, features, "medium"
    )
    high_prompt = await consistency_manager.generate_consistency_prompt(
        base_prompt, features, "high"
    )
    
    assert base_prompt in low_prompt
    assert base_prompt in medium_prompt
    assert base_prompt in high_prompt
    
    # 高级别应该包含更多细节
    assert len(high_prompt) >= len(medium_prompt) >= len(low_prompt)


@pytest.mark.asyncio
async def test_consistency_manager_evaluation():
    """测试一致性评估"""
    images = [
        "https://example.com/image1.jpg",
        "https://example.com/image2.jpg",
        "https://example.com/image3.jpg"
    ]
    
    result = await consistency_manager.evaluate_consistency(images, threshold=0.7)
    
    assert "overall_score" in result
    assert "character_consistency" in result
    assert "scene_consistency" in result
    assert "style_consistency" in result
    assert "passed" in result
    assert "recommendations" in result
    
    assert 0.0 <= result["overall_score"] <= 1.0
    assert isinstance(result["passed"], bool)
    assert isinstance(result["recommendations"], list)


@pytest.mark.asyncio
async def test_enhanced_project_model():
    """测试增强的项目模型"""
    # 测试创建请求包含一致性字段
    request = CreativeProjectCreateRequest(
        title="Test Project",
        brief="Test brief",
        consistency_level="high",
        character_reference="A young woman with long hair",
        scene_reference="Modern office environment"
    )
    
    assert request.consistency_level == "high"
    assert request.character_reference == "A young woman with long hair"
    assert request.scene_reference == "Modern office environment"
    
    # 测试项目模型
    project = CreativeProject(
        id="test-project",
        tenant_id="test-tenant",
        title="Test Project",
        brief="Test brief",
        consistency_level="medium",
        consistency_seed=12345,
        reference_images=["https://example.com/ref1.jpg"],
        overall_consistency_score=0.85
    )
    
    assert project.consistency_level == "medium"
    assert project.consistency_seed == 12345
    assert len(project.reference_images) == 1
    assert project.overall_consistency_score == 0.85


@pytest.mark.asyncio
async def test_consistency_seed_generation():
    """测试一致性种子生成"""
    # 为同一项目生成种子应该一致
    seed1 = consistency_manager.generate_consistency_seed("project-123", 1)
    seed2 = consistency_manager.generate_consistency_seed("project-123", 1)
    seed3 = consistency_manager.generate_consistency_seed("project-123", 2)
    seed4 = consistency_manager.generate_consistency_seed("project-456", 1)
    
    assert seed1 == seed2  # 同一项目同一场景应该相同
    assert seed1 != seed3  # 不同场景应该不同
    assert seed1 != seed4  # 不同项目应该不同


@pytest.mark.asyncio
async def test_enhanced_storyboard_panel():
    """测试增强的分镜面板模型"""
    from lewis_ai_system.creative.models import StoryboardPanel
    
    panel = StoryboardPanel(
        scene_number=1,
        description="A person walking",
        duration_seconds=5,
        consistency_prompt="Maintain character appearance",
        reference_image_url="https://example.com/ref.jpg",
        character_features={
            "gender": "female",
            "age_range": "young adult"
        },
        consistency_score=0.9
    )
    
    assert panel.consistency_prompt == "Maintain character appearance"
    assert panel.reference_image_url == "https://example.com/ref.jpg"
    assert panel.character_features["gender"] == "female"
    assert panel.consistency_score == 0.9


@pytest.mark.asyncio
async def test_enhanced_shot_asset():
    """测试增强的镜头资源模型"""
    from lewis_ai_system.creative.models import GeneratedShotAsset
    
    shot = GeneratedShotAsset(
        scene_number=1,
        prompt="Test prompt",
        provider="doubao",
        reference_image_url="https://example.com/ref.jpg",
        consistency_seed=12345,
        character_prompt="Young woman with long hair",
        consistency_score=0.88
    )
    
    assert shot.reference_image_url == "https://example.com/ref.jpg"
    assert shot.consistency_seed == 12345
    assert shot.character_prompt == "Young woman with long hair"
    assert shot.consistency_score == 0.88


@pytest.mark.asyncio
async def test_workflow_with_consistency():
    """测试工作流集成一致性控制"""
    # 创建orchestrator
    orchestrator = CreativeOrchestrator()
    
    # Mock项目
    project = MagicMock()
    project.id = "test-project"
    project.script = "Scene 1\n\nScene 2"
    project.duration_seconds = 10
    project.consistency_seed = 12345
    project.consistency_level = "medium"
    project.reference_images = []
    project.character_reference = None
    project.scene_reference = None
    project.style = "cinematic"
    project.storyboard = []
    
    # Mock依赖
    orchestrator.repository = AsyncMock()
    orchestrator.repository.get.return_value = project
    orchestrator.repository.upsert.return_value = project
    orchestrator.storage = MagicMock()
    
    # Mock agents
    with pytest.MonkeyPatch.context() as m:
        # Mock split_script
        m.setattr(orchestrator, "_split_into_scenes", AsyncMock(return_value=[
            {"description": "Scene 1", "estimated_duration": 5},
            {"description": "Scene 2", "estimated_duration": 5}
        ]))
        
        # Mock consistency manager
        m.setattr(consistency_manager, "create_reference_images", AsyncMock(return_value=[]))
        m.setattr(consistency_manager, "evaluate_consistency", AsyncMock(return_value={
            "overall_score": 0.8,
            "passed": True,
            "recommendations": []
        }))
        
        # Mock cost guardrail
        m.setattr(orchestrator, "_record_cost_guardrail", MagicMock(return_value=False))
        
        # 执行
        result = await orchestrator._generate_storyboard(project)
        
        # 验证
        assert result is False  # _record_cost_guardrail返回False
        assert len(project.storyboard) == 2
        assert project.overall_consistency_score == 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
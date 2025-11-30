"""端到端集成测试 - 完整的用户工作流程测试。"""

import asyncio
import pytest
from typing import Any

from lewis_ai_system.config import settings
from lewis_ai_system.creative.workflow import CreativeOrchestrator
from lewis_ai_system.creative.repository import InMemoryCreativeProjectRepository
from lewis_ai_system.creative.models import CreativeProject, StoryboardPanel, CreativeProjectCreateRequest
from lewis_ai_system.creative.consistency_manager import ConsistencyManager
from lewis_ai_system.creative.batch_processing import BatchProcessingService


class TestEndToEndWorkflows:
    """端到端工作流程测试。"""

    @pytest.fixture
    def repository(self):
        """创建内存存储库用于测试。"""
        return InMemoryCreativeProjectRepository()

    @pytest.fixture
    def orchestrator(self, repository):
        """创建编排器用于测试。"""
        return CreativeOrchestrator(repository=repository)

    @pytest.fixture
    def batch_service(self):
        """创建批量处理服务用于测试。"""
        return BatchProcessingService()

    @pytest.mark.asyncio
    async def test_complete_creative_workflow(self, orchestrator, repository):
        """测试完整的创作工作流程。"""
        # 1. 创建项目
        project_data = {
            "title": "E2E Test Project",
            "brief": "创建一个展示现代办公室场景的短视频",
            "consistency_level": "medium",
            "character_reference": "一位年轻的职业女性",
            "scene_reference": "现代化的办公环境"
        }

        project = await orchestrator.create_project(project_data)
        assert project.id is not None
        assert project.title == "E2E Test Project"

        # 2. 扩展简报
        expanded_brief = await orchestrator.expand_project_brief(
            project.id, 
            "需要突出团队合作和技术创新的主题"
        )
        assert expanded_brief is not None
        assert len(expanded_brief) > 0

        # 3. 生成脚本
        script = await orchestrator.generate_script(project.id)
        assert script is not None
        assert isinstance(script, str)
        assert len(script) > 50  # 脚本应该有一定长度

        # 4. 拆分为分镜
        storyboard = await orchestrator.split_script_to_storyboard(project.id)
        assert storyboard is not None
        assert len(storyboard.panels) > 0

        # 验证分镜面板格式
        for panel in storyboard.panels:
            assert panel.scene_number is not None
            assert panel.description is not None
            assert len(panel.description) > 0

    @pytest.mark.asyncio 
    async def test_consistency_control_workflow(self, repository):
        """测试一致性控制工作流程。"""
        consistency_manager = ConsistencyManager()

        # 模拟一致性特征提取
        features = await consistency_manager.extract_consistency_features(
            "https://example.com/test-image.jpg"
        )

        assert "character_features" in features
        assert "scene_features" in features
        assert "style_features" in features

        # 生成一致性提示词
        base_prompt = "Generate a professional office scene"
        enhanced_prompt = await consistency_manager.generate_consistency_prompt(
            base_prompt, features, "medium"
        )

        assert enhanced_prompt is not None
        assert len(enhanced_prompt) > len(base_prompt)

    @pytest.mark.asyncio
    async def test_batch_processing_workflow(self, batch_service, repository):
        """测试批量处理工作流程。"""
        # 创建多个测试项目
        project_ids = []
        for i in range(3):
            project = CreativeProject(
                id=f"batch_test_{i}",
                tenant_id="test_tenant",
                title=f"Batch Test Project {i}",
                brief="Test project for batch processing",
                consistency_level="medium"
            )
            await repository.create(project)
            project_ids.append(project.id)

        # 执行批量一致性评估
        result = await batch_service.batch_evaluate_consistency(project_ids)

        assert result["total_projects"] == 3
        assert "results" in result

        # 验证所有项目都被处理
        for project_id in project_ids:
            assert project_id in result["results"]

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, orchestrator):
        """测试错误处理工作流程。"""
        # 测试不存在的项目
        with pytest.raises(ValueError):
            await orchestrator.generate_script("non_existent_project")

        # 测试无效的项目数据
        invalid_data = {
            "title": "",  # 空标题
            "brief": "Valid brief",
            "consistency_level": "invalid_level"
        }

        project = await orchestrator.create_project(invalid_data)
        assert project is not None  # 应该创建项目，但可能使用默认值

    @pytest.mark.asyncio
    async def test_workflow_state_transitions(self, orchestrator, repository):
        """测试工作流程状态转换。"""
        # 创建项目
        project_data = {
            "title": "State Transition Test",
            "brief": "Test state transitions",
            "consistency_level": "high"
        }

        project = await orchestrator.create_project(project_data)
        initial_state = project.status
        assert initial_state in ["brief_pending", "script_pending", "storyboard_pending"]

        # 模拟状态转换
        expanded_brief = await orchestrator.expand_project_brief(project.id, "Additional context")
        # Note: 实际的状态转换逻辑可能需要根据具体实现调整

    @pytest.mark.asyncio
    async def test_performance_benchmarks(self, orchestrator, repository):
        """测试性能基准。"""
        import time

        # 创建多个项目测试并发性能
        start_time = time.time()

        project_data = {
            "title": "Performance Test Project",
            "brief": "Benchmark test project",
            "consistency_level": "medium"
        }

        # 连续创建多个项目
        projects = []
        for i in range(5):
            project = await orchestrator.create_project(project_data)
            projects.append(project)

        end_time = time.time()
        total_time = end_time - start_time

        # 验证性能
        assert total_time < 10.0  # 应该在10秒内完成
        assert len(projects) == 5
        assert all(p.id is not None for p in projects)


class TestRealWorldScenarios:
    """真实世界场景测试。"""

    @pytest.mark.asyncio
    async def test_marketing_video_workflow(self, repository):
        """测试营销视频工作流程。"""
        orchestrator = CreativeOrchestrator(repository=repository)

        # 模拟营销视频的完整流程
        project_data = {
            "title": "产品介绍视频",
            "brief": "制作一个5分钟的产品介绍视频，展示我们的新AI工具的特点和优势",
            "consistency_level": "high",
            "character_reference": "专业的技术演讲者",
            "scene_reference": "现代化会议室"
        }

        project = await orchestrator.create_project(project_data)

        # 扩展简报
        expanded = await orchestrator.expand_project_brief(
            project.id,
            "强调技术创新和用户体验，目标受众是技术决策者"
        )

        # 生成脚本
        script = await orchestrator.generate_script(project.id)

        # 拆分为分镜
        storyboard = await orchestrator.split_script_to_storyboard(project.id)

        # 验证结果
        assert expanded is not None
        assert script is not None
        assert storyboard is not None
        assert len(storyboard.panels) >= 3  # 营销视频应该有多个分镜

    @pytest.mark.asyncio
    async def test_educational_content_workflow(self, repository):
        """测试教育内容工作流程。"""
        orchestrator = CreativeOrchestrator(repository=repository)

        # 模拟教学视频的创建
        project_data = {
            "title": "编程教程视频",
            "brief": "创建一个关于Python基础语法的教学视频，时长3-5分钟",
            "consistency_level": "medium",
            "character_reference": "友好的编程讲师",
            "scene_reference": "简洁的代码演示环境"
        }

        project = await orchestrator.create_project(project_data)
        script = await orchestrator.generate_script(project.id)
        storyboard = await orchestrator.split_script_to_storyboard(project.id)

        # 验证教育内容特点
        assert script is not None
        assert "学习" in script or "教程" in script or "代码" in script
        assert storyboard is not None

    @pytest.mark.asyncio
    async def test_consistency_heavy_workflow(self, repository):
        """测试高度依赖一致性的工作流程。"""
        consistency_manager = ConsistencyManager()

        # 测试多张图片的一致性评估
        test_images = [
            "https://example.com/character1.jpg",
            "https://example.com/character2.jpg",
            "https://example.com/character3.jpg"
        ]

        # 评估一致性
        result = await consistency_manager.evaluate_consistency(test_images)

        assert "overall_score" in result
        assert "character_consistency" in result
        assert "scene_consistency" in result
        assert "style_consistency" in result

        # 验证评分范围
        for score in [result["overall_score"], result["character_consistency"]]:
            assert 0 <= score <= 1

    @pytest.mark.asyncio
    async def test_multi_project_coordination(self, repository, batch_service):
        """测试多项目协调工作流程。"""
        orchestrator = CreativeOrchestrator(repository=repository)

        # 创建多个相关项目
        projects_data = [
            {
                "title": "产品系列介绍1",
                "brief": "介绍产品A的特点",
                "consistency_level": "high"
            },
            {
                "title": "产品系列介绍2", 
                "brief": "介绍产品B的特点",
                "consistency_level": "high"
            },
            {
                "title": "产品系列介绍3",
                "brief": "介绍产品C的特点", 
                "consistency_level": "high"
            }
        ]

        # 创建所有项目
        projects = []
        for data in projects_data:
            project = await orchestrator.create_project(data)
            projects.append(project)

        # 验证所有项目都创建成功
        assert len(projects) == 3
        assert all(p.id is not None for p in projects)

        # 获取项目ID进行批量处理
        project_ids = [p.id for p in projects]
        batch_result = await batch_service.batch_evaluate_consistency(project_ids)

        # 验证批量处理结果
        assert batch_result["total_projects"] == 3
        assert len(batch_result["results"]) == 3
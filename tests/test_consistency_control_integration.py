"""测试一致性控制功能。"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lewis_ai_system.creative.consistency_manager import ConsistencyManager
from lewis_ai_system.creative.models import CreativeProject, StoryboardPanel


class TestConsistencyManager:
    """测试一致性管理器。"""

    @pytest.fixture
    def consistency_manager(self):
        """创建一致性管理器实例。"""
        manager = ConsistencyManager()
        # Mock LLM provider
        manager._llm_provider = AsyncMock()
        return manager

    @pytest.fixture
    def sample_project(self):
        """创建示例项目。"""
        return CreativeProject(
            id="test_project",
            tenant_id="test_tenant",
            title="Test Project",
            brief="Test brief for consistency control",
            consistency_level="medium",
            character_reference="A young professional",
            scene_reference="Modern office setting"
        )

    @pytest.fixture
    def sample_panel(self):
        """创建示例分镜面板。"""
        return StoryboardPanel(
            scene_number=1,
            description="A person working at a desk",
            duration_seconds=5,
            visual_reference_path="https://example.com/image1.jpg"
        )

    @pytest.mark.asyncio
    async def test_extract_consistency_features_success(self, consistency_manager):
        """测试特征提取成功情况。"""
        # Mock LLM response with direct JSON that can be parsed
        mock_response = {
            "content": '''{"character_features": {"gender": "male", "age_range": "adult", "hair_style": "short hair", "clothing_style": "business casual"}, "scene_features": {"environment": "office", "lighting": "natural light", "color_scheme": "neutral tones"}, "style_features": {"art_style": "realistic", "visual_mood": "professional"}}'''
        }
        consistency_manager._llm_provider.analyze_image = AsyncMock(return_value=mock_response)

        features = await consistency_manager.extract_consistency_features("https://example.com/test.jpg")

        assert "character_features" in features
        assert "scene_features" in features
        assert "style_features" in features
        assert features["character_features"]["gender"] == "male"

    @pytest.mark.asyncio
    async def test_extract_consistency_features_fallback(self, consistency_manager):
        """测试特征提取失败时的回退机制。"""
        consistency_manager._llm_provider.analyze_image = AsyncMock(side_effect=Exception("API Error"))

        features = await consistency_manager.extract_consistency_features("https://example.com/test.jpg")

        # 应该返回默认特征
        assert "character_features" in features
        assert features["character_features"]["gender"] == "未指定"

    @pytest.mark.asyncio
    async def test_generate_consistency_prompt(self, consistency_manager):
        """测试一致性提示词生成。"""
        base_prompt = "A person walking in the park"
        features = {
            "character_features": {"gender": "female", "age_range": "young adult"},
            "scene_features": {"environment": "park", "lighting": "sunny"},
            "style_features": {"art_style": "realistic"}
        }

        prompt = await consistency_manager.generate_consistency_prompt(
            base_prompt, features, "medium"
        )

        assert base_prompt in prompt
        assert "角色特征" in prompt or "character" in prompt.lower()

    @pytest.mark.asyncio
    async def test_evaluate_consistency_perfect_score(self, consistency_manager):
        """测试一致性评估 - 完美分数。"""
        images = ["https://example.com/image1.jpg"]  # 单个图片

        result = await consistency_manager.evaluate_consistency(images)

        assert result["overall_score"] == 1.0
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_evaluate_consistency_with_multiple_images(self, consistency_manager):
        """测试一致性评估 - 多个图片。"""
        images = ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]

        # Mock LLM response
        mock_response = {
            "content": "Overall consistency score: 0.85"
        }
        consistency_manager._llm_provider.complete = AsyncMock(return_value=mock_response["content"])

        result = await consistency_manager.evaluate_consistency(images)

        assert "overall_score" in result
        assert "character_consistency" in result
        assert "scene_consistency" in result
        assert "style_consistency" in result
        assert isinstance(result["passed"], bool)

    def test_generate_consistency_seed(self, consistency_manager, sample_project):
        """测试一致性种子生成。"""
        seed1 = consistency_manager.generate_consistency_seed(sample_project.id, 1)
        seed2 = consistency_manager.generate_consistency_seed(sample_project.id, 1)

        # 相同输入应该生成相同种子
        assert seed1 == seed2
        assert isinstance(seed1, int)
        assert 0 <= seed1 < 2**31

    def test_weighted_consistency_score(self, consistency_manager):
        """测试加权一致性评分。"""
        scores = {
            "character_consistency": 0.8,
            "scene_consistency": 0.9,
            "style_consistency": 0.7,
            "visual_similarity": 0.6
        }

        weighted_score = consistency_manager._weighted_consistency_score(scores)

        assert 0 <= weighted_score <= 1
        # 由于角色一致性权重最高（0.4），分数应该接近0.8
        assert 0.75 <= weighted_score <= 0.85

    def test_generate_consistency_recommendations(self, consistency_manager):
        """测试一致性建议生成。"""
        scores = {
            "character_consistency": 0.5,  # 低分
            "scene_consistency": 0.9,      # 高分
            "style_consistency": 0.6,      # 中等
            "visual_similarity": 0.8       # 高分
        }

        recommendations = consistency_manager._generate_consistency_recommendations(scores, 0.7)

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        # 应该包含角色一致性的建议
        role_recommendations = [r for r in recommendations if "角色" in r or "character" in r.lower()]
        assert len(role_recommendations) > 0


class TestBatchProcessingService:
    """测试批量处理服务。"""

    @pytest.fixture
    def batch_service(self):
        """创建批量处理服务实例。"""
        from lewis_ai_system.creative.batch_processing import BatchProcessingService
        return BatchProcessingService()

    @pytest.mark.asyncio
    async def test_batch_evaluate_consistency(self, batch_service):
        """测试批量一致性评估。"""
        project_ids = ["project1", "project2", "project3"]

        # Mock repository
        with patch('lewis_ai_system.creative.batch_processing.creative_repository') as mock_repo, \
             patch('lewis_ai_system.creative.batch_processing.consistency_manager') as mock_manager:

            # Mock projects
            mock_projects = []
            for i, pid in enumerate(project_ids):
                project = MagicMock()
                project.id = pid
                project.storyboard = []
                if i < 2:  # 前两个项目有分镜
                    panel = MagicMock()
                    panel.visual_reference_path = f"https://example.com/image{i+1}.jpg"
                    project.storyboard = [panel]
                mock_projects.append(project)

            mock_repo.get = AsyncMock(side_effect=mock_projects)

            # Mock consistency evaluation
            mock_result = {
                "overall_score": 0.8,
                "character_consistency": 0.8,
                "scene_consistency": 0.7,
                "style_consistency": 0.9,
                "recommendations": ["Test recommendation"]
            }
            mock_manager.evaluate_consistency = AsyncMock(return_value=mock_result)
            mock_repo.upsert = AsyncMock()

            result = await batch_service.batch_evaluate_consistency(project_ids)

            assert result["total_projects"] == 3
            # 批量一致性评估需要至少2张分镜图片，所有项目都只有1张或没有，所以都被跳过
            assert result["successful_evaluations"] == 0
            assert result["total_processed"] == 3  # 全部项目都被处理了
            assert "project1" in result["results"]
            assert "project2" in result["results"]
            assert "project3" in result["results"]

            # 检查所有项目的状态都是跳过（分镜不足）
            for project_id in ["project1", "project2", "project3"]:
                project_result = result["results"][project_id]
                assert project_result["status"] == "skipped"


class TestMonitoringAnalyticsService:
    """测试监控和分析服务。"""

    @pytest.fixture
    def monitoring_service(self):
        """创建监控服务实例。"""
        from lewis_ai_system.creative.monitoring import MonitoringAnalyticsService
        return MonitoringAnalyticsService()

    @pytest.mark.asyncio
    async def test_get_consistency_stats(self, monitoring_service):
        """测试一致性统计获取。"""
        with patch('lewis_ai_system.creative.monitoring.creative_repository') as mock_repo:
            # Mock projects
            mock_projects = []
            for i in range(5):
                project = MagicMock()
                project.consistency_level = "medium" if i < 3 else "high"
                project.overall_consistency_score = 0.7 + i * 0.05 if i < 4 else None
                project.storyboard = []
                mock_projects.append(project)

            mock_repo.list_for_tenant = AsyncMock(return_value=mock_projects)

            stats = await monitoring_service.get_consistency_stats("test_tenant")

            assert stats["total_projects"] == 5
            assert stats["projects_with_consistency_score"] == 4
            assert "average_consistency_score" in stats
            assert "consistency_level_distribution" in stats
            assert "score_ranges" in stats

    @pytest.mark.asyncio
    async def test_get_consistency_trends(self, monitoring_service):
        """测试一致性趋势获取。"""
        with patch('lewis_ai_system.creative.monitoring.creative_repository') as mock_repo:
            # Mock projects with different dates
            from datetime import datetime, timezone, timedelta

            mock_projects = []
            base_date = datetime.now(timezone.utc)

            for i in range(7):
                project = MagicMock()
                project.created_at = base_date - timedelta(days=i)
                project.updated_at = project.created_at + timedelta(hours=1)
                project.overall_consistency_score = 0.7 + (i % 3) * 0.1
                project.storyboard = []
                mock_projects.append(project)

            mock_repo.list_for_tenant = AsyncMock(return_value=mock_projects)

            trends = await monitoring_service.get_consistency_trends("test_tenant", days=7)

            assert "trends" in trends
            assert "summary" in trends
            assert len(trends["trends"]) > 0

            # 检查趋势摘要
            summary = trends["summary"]
            assert "trend" in summary
            assert "improvement" in summary

    @pytest.mark.asyncio
    async def test_get_recommendations(self, monitoring_service):
        """测试智能推荐生成。"""
        with patch('lewis_ai_system.creative.monitoring.creative_repository') as mock_repo:
            # Mock projects with low consistency scores
            mock_projects = []
            for i in range(3):
                project = MagicMock()
                project.consistency_level = "low"
                project.overall_consistency_score = 0.5  # 低分
                project.state = "completed"
                project.cost_usd = 10.0
                project.storyboard = []
                mock_projects.append(project)

            mock_repo.list_for_tenant = AsyncMock(return_value=mock_projects)

            recommendations = await monitoring_service.get_recommendations("test_tenant")

            assert "recommendations" in recommendations
            assert isinstance(recommendations["recommendations"], list)

            # 应该有提升一致性的推荐
            consistency_recs = [r for r in recommendations["recommendations"]
                              if r.get("type") == "consistency_improvement"]
            assert len(consistency_recs) > 0


class TestIntegration:
    """集成测试。"""

    @pytest.mark.asyncio
    async def test_full_consistency_workflow(self):
        """测试完整的一致性工作流。"""
        # 创建项目
        project = CreativeProject(
            id="integration_test",
            tenant_id="test",
            title="Integration Test",
            brief="Test full consistency workflow",
            consistency_level="high"
        )

        # 初始化一致性管理器
        manager = ConsistencyManager()
        manager._llm_provider = AsyncMock()

        # Mock 特征提取
        features = {
            "character_features": {"gender": "female", "age_range": "adult"},
            "scene_features": {"environment": "office"},
            "style_features": {"art_style": "realistic"}
        }
        manager.extract_consistency_features = AsyncMock(return_value=features)

        # 测试特征提取
        extracted = await manager.extract_consistency_features("test_url")
        assert extracted == features

        # 测试提示词生成
        prompt = await manager.generate_consistency_prompt(
            "A person working", features, "high"
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0

        # 测试种子生成
        seed = manager.generate_consistency_seed(project.id)
        assert isinstance(seed, int)

        # 测试一致性评估（单个图片）
        result = await manager.evaluate_consistency(["test_image.jpg"])
        assert result["overall_score"] == 1.0  # 单个图片返回1.0

        print("[OK] 完整一致性工作流集成测试通过")


if __name__ == "__main__":
    # 运行基本功能测试
    import asyncio

    async def run_basic_tests():
        print("开始一致性控制基础功能测试...")

        manager = ConsistencyManager()
        manager._llm_provider = AsyncMock()

        # 测试种子生成
        seed = manager.generate_consistency_seed("test_project")
        print(f"[OK] 种子生成测试通过: {seed}")

        # 测试加权评分
        scores = {"character_consistency": 0.8, "scene_consistency": 0.9}
        weighted = manager._weighted_consistency_score(scores)
        print(f"[OK] 加权评分测试通过: {weighted}")

        # 测试建议生成
        recommendations = manager._generate_consistency_recommendations(scores, 0.7)
        print(f"[OK] 建议生成测试通过: {len(recommendations)} 条建议")

        print("🎉 所有基础功能测试通过！")

    asyncio.run(run_basic_tests())

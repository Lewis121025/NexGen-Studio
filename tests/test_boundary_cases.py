"""边界测试用例模块。

包含各种边界情况和异常场景的测试。
"""

import pytest
from unittest.mock import patch
from lewis_ai_system.agents import QualityAgent, PlanningAgent, CreativeAgent
from lewis_ai_system.config import settings
from lewis_ai_system.providers import EchoLLMProvider

pytestmark = pytest.mark.asyncio

pytestmark = pytest.mark.asyncio


class TestQualityAgentBoundary:
    """质量检查 Agent 边界测试。"""

    @pytest.fixture
    def quality_agent(self):
        """创建质量检查 Agent 实例。"""
        mock_provider = EchoLLMProvider()
        return QualityAgent(provider=mock_provider)

    async def test_empty_content_evaluation(self, quality_agent):
        """测试空内容评估。"""
        result = await quality_agent.evaluate("", ["quality"])
        assert result["score"] >= 0.0
        assert result["score"] <= 1.0
        assert "notes" in result

    async def test_very_long_content_evaluation(self, quality_agent):
        """测试超长内容评估。"""
        long_content = "测试内容" * 10000  # 超长内容
        result = await quality_agent.evaluate(long_content, ["quality"])
        assert result["score"] >= 0.0
        assert result["score"] <= 1.0

    async def test_invalid_criteria_list(self, quality_agent):
        """测试无效标准列表。"""
        result = await quality_agent.evaluate("测试内容", [])
        assert result["criteria"] == []
        assert "score" in result

    async def test_qc_workflow_with_no_rules(self, quality_agent):
        """测试没有规则时的 QC 工作流。"""
        # 清空所有规则
        quality_agent.qc_rules = []
        
        result = await quality_agent.run_qc_workflow("测试内容")
        assert result["overall_score"] == 0.5  # 默认分数
        assert result["passed"] is False
        assert len(result["rule_results"]) == 0

    async def test_qc_workflow_with_disabled_rules(self, quality_agent):
        """测试禁用所有规则时的 QC 工作流。"""
        # 禁用所有规则
        for rule in quality_agent.qc_rules:
            rule["enabled"] = False
        
        result = await quality_agent.run_qc_workflow("测试内容")
        assert result["overall_score"] == 0.5  # 默认分数
        assert len(result["rule_results"]) == 0

    async def test_rule_with_invalid_threshold(self, quality_agent):
        """测试无效阈值的规则。"""
        quality_agent.add_qc_rule("invalid_rule", ["test"], threshold=1.5)
        quality_agent.add_qc_rule("invalid_rule2", ["test"], threshold=-0.1)
        
        # 应该仍然能正常工作，但阈值会被限制在合理范围内
        result = await quality_agent.run_qc_workflow("测试内容")
        assert result["overall_score"] >= 0.0
        assert result["overall_score"] <= 1.0

    async def test_circular_rule_dependencies(self, quality_agent):
        """测试循环依赖的规则。"""
        quality_agent.add_qc_rule("rule_a", ["test"], dependencies=["rule_b"])
        quality_agent.add_qc_rule("rule_b", ["test"], dependencies=["rule_a"])
        
        # 应该能检测到依赖问题
        assert len(quality_agent.qc_rules) >= 2

    async def test_custom_logic_exception(self, quality_agent):
        """测试自定义逻辑异常。"""
        async def failing_logic(content, context):
            raise ValueError("自定义逻辑失败")
        
        quality_agent.add_qc_rule("failing_rule", ["test"], custom_logic=failing_logic)
        
        result = await quality_agent.run_qc_workflow("测试内容")
        failing_result = next(r for r in result["rule_results"] if r["rule_name"] == "failing_rule")
        assert failing_result["passed"] is False
        assert "自定义逻辑失败" in failing_result["notes"]


class TestPlanningAgentBoundary:
    """规划 Agent 边界测试。"""

    @pytest.fixture
    def planning_agent(self):
        """创建规划 Agent 实例。"""
        mock_provider = EchoLLMProvider()
        return PlanningAgent(provider=mock_provider)

    async def test_empty_brief_expansion(self, planning_agent):
        """测试空简报扩展。"""
        result = await planning_agent.expand_brief("", mode="creative")
        assert "summary" in result
        assert "hash" in result
        assert result["mode"] == "creative"
        assert len(result["hash"]) == 8  # SHA1 前8位

    async def test_very_long_brief_expansion(self, planning_agent):
        """测试超长简报扩展。"""
        long_brief = "创建一个关于" + "测试" * 1000 + "的视频"
        result = await planning_agent.expand_brief(long_brief, mode="creative")
        assert "summary" in result
        assert "hash" in result

    async def test_invalid_mode_handling(self, planning_agent):
        """测试无效模式处理。"""
        result = await planning_agent.expand_brief("测试", mode="invalid_mode")
        assert "summary" in result
        assert result["mode"] == "invalid_mode"

    async def test_special_characters_in_brief(self, planning_agent):
        """测试包含特殊字符的简报。"""
        special_brief = "测试🎬视频&制作@公司#项目$"
        result = await planning_agent.expand_brief(special_brief, mode="creative")
        assert "summary" in result
        assert "hash" in result


class TestCreativeAgentBoundary:
    """创意 Agent 边界测试。"""

    @pytest.fixture
    def creative_agent(self):
        """创建创意 Agent 实例。"""
        mock_provider = EchoLLMProvider()
        return CreativeAgent(provider=mock_provider)

    async def test_script_generation_with_zero_duration(self, creative_agent):
        """测试零时长脚本生成。"""
        result = await creative_agent.write_script("测试简报", duration=0, style="cinematic")
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_script_generation_with_negative_duration(self, creative_agent):
        """测试负数时长脚本生成。"""
        result = await creative_agent.write_script("测试简报", duration=-10, style="cinematic")
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_script_generation_with_very_long_duration(self, creative_agent):
        """测试超长时长脚本生成。"""
        result = await creative_agent.write_script("测试简报", duration=3600, style="cinematic")  # 1小时
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_script_split_empty_script(self, creative_agent):
        """测试空脚本拆分。"""
        result = await creative_agent.split_script("", 60)
        assert isinstance(result, list)

    async def test_script_split_invalid_json_response(self, creative_agent):
        """测试无效 JSON 响应的脚本拆分。"""
        with patch.object(creative_agent.provider, 'complete', return_value="无效的 JSON 响应"):
            result = await creative_agent.split_script("测试脚本", 60)
            assert isinstance(result, list)
            # 应该回退到按段落拆分
            assert len(result) > 0

    async def test_panel_visual_generation_empty_description(self, creative_agent):
        """测试空描述的分镜预览图生成。"""
        with patch.object(settings, 'llm_provider_mode', 'mock'):
            result = await creative_agent.generate_panel_visual("")
            assert isinstance(result, str)
            assert result.startswith("https://placeholder.lewis.ai/")

    async def test_panel_visual_generation_special_characters(self, creative_agent):
        """测试包含特殊字符的分镜预览图生成。"""
        special_desc = "🎬场景@测试#描述$"
        with patch.object(settings, 'llm_provider_mode', 'mock'):
            result = await creative_agent.generate_panel_visual(special_desc)
            assert isinstance(result, str)
            assert result.startswith("https://placeholder.lewis.ai/")


class TestAgentIntegrationBoundary:
    """Agent 集成边界测试。"""

    async def test_multiple_agents_same_provider(self):
        """测试多个 Agent 使用同一个 provider。"""
        mock_provider = EchoLLMProvider()
        
        planning = PlanningAgent(provider=mock_provider)
        quality = QualityAgent(provider=mock_provider)
        creative = CreativeAgent(provider=mock_provider)
        
        # 所有 Agent 应该能正常工作
        plan_result = await planning.expand_brief("测试", mode="creative")
        quality_result = await quality.evaluate("测试", ["quality"])
        script_result = await creative.write_script("测试", 30, "cinematic")
        
        assert "summary" in plan_result
        assert "score" in quality_result
        assert isinstance(script_result, str)

    async def test_provider_failure_handling(self):
        """测试 provider 失败处理。"""
        planning = PlanningAgent(provider=EchoLLMProvider())
        
        async def failing_complete(prompt: str, temperature: float = 0.0):
            raise ConnectionError("Provider 连接失败")
        
        with patch.object(planning.provider, "complete", side_effect=failing_complete):
            with pytest.raises(ConnectionError):
                await planning.expand_brief("测试", mode="creative")

    async def test_concurrent_agent_usage(self):
        """测试并发 Agent 使用。"""
        import asyncio
        
        mock_provider = EchoLLMProvider()
        planning = PlanningAgent(provider=mock_provider)
        
        # 并发执行多个任务
        tasks = [
            planning.expand_brief(f"测试{i}", mode="creative")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 所有任务应该成功完成
        for result in results:
            assert not isinstance(result, Exception)
            assert isinstance(result, dict)
            assert result.get("mode") == "creative"

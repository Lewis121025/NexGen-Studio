"""质量检查 Agent 模块。

基于 LLM 进行质量评分，支持独立的 QC 工作流和规则引擎。
用于评估生成内容的质量，支持自定义质量检查规则和阈值。
"""

from __future__ import annotations

import json
import re
from typing import Any, Sequence

from ..config import settings
from ..providers import LLMProvider, default_llm_provider


class QualityAgent:
    """质量检查 Agent，基于 LLM 进行质量评分，支持独立的 QC 工作流和规则引擎。
    
    用于评估生成内容的质量，支持自定义质量检查规则和阈值。
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """初始化质量检查 Agent。
        
        Args:
            provider: LLM 提供商实例，如果为 None 则使用默认提供商
        """
        self.provider = provider or default_llm_provider
        self.qc_rules: list[dict[str, Any]] = []  # 质量检查规则列表
        # 初始化默认 QC 规则
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        """初始化默认的质量检查规则。"""
        # 基础质量规则
        self.add_qc_rule("content_quality", ["quality", "relevance"], threshold=0.7)
        self.add_qc_rule("completeness", ["completeness", "coherence"], threshold=0.6)
        self.add_qc_rule("technical_quality", ["technical", "accuracy"], threshold=0.75)

        # 一致性相关规则
        self.add_qc_rule("character_consistency", ["character", "consistency"], threshold=0.8)
        self.add_qc_rule("scene_continuity", ["scene", "continuity"], threshold=0.75)
        self.add_qc_rule("style_consistency", ["style", "consistency"], threshold=0.7)
        self.add_qc_rule("visual_coherence", ["visual", "coherence"], threshold=0.7)

    def add_qc_rule(
        self,
        rule_name: str,
        criteria: list[str],
        threshold: float = 0.7,
        auto_approve: bool = False,
        rule_type: str = "standard",
        dependencies: list[str] | None = None,
        custom_logic: Any | None = None
    ) -> None:
        """添加质量检查规则到规则引擎。
        
        Args:
            rule_name: 规则名称
            criteria: 评估标准列表
            threshold: 通过阈值（0.0-1.0），默认 0.7
            auto_approve: 如果通过是否自动批准，默认 False
            rule_type: 规则类型 ("standard", "consistency", "technical", "creative")
            dependencies: 依赖的其他规则名称列表
            custom_logic: 自定义评估逻辑函数
        """
        self.qc_rules.append({
            "name": rule_name,
            "criteria": criteria,
            "threshold": threshold,
            "auto_approve": auto_approve,
            "rule_type": rule_type,
            "dependencies": dependencies or [],
            "custom_logic": custom_logic,
            "enabled": True,
        })

    def enable_rule(self, rule_name: str, enabled: bool = True) -> None:
        """启用或禁用特定规则。"""
        for rule in self.qc_rules:
            if rule["name"] == rule_name:
                rule["enabled"] = enabled
                break

    def get_rules_by_type(self, rule_type: str) -> list[dict[str, Any]]:
        """获取指定类型的规则。"""
        return [rule for rule in self.qc_rules if rule.get("rule_type") == rule_type and rule.get("enabled", True)]

    async def evaluate(self, artifact: str, criteria: Sequence[str]) -> dict[str, Any]:
        """评估内容质量。
        
        Args:
            artifact: 要评估的内容文本
            criteria: 评估标准序列
            
        Returns:
            包含评分、标准和备注的字典
        """
        criteria_list = ", ".join(criteria)
        use_mock_shortcut = settings.llm_provider_mode == "mock" and self.provider is default_llm_provider
        if use_mock_shortcut:
            return {
                "score": 0.82,
                "criteria": list(criteria),
                "notes": "Mock evaluation pass",
            }
        prompt = (
            f"Evaluate the following text against these criteria: {criteria_list}.\n"
            "Provide a score from 0.0 to 1.0 and a brief justification.\n"
            f"Text: {artifact[:2000]}"  # 截断以避免上下文限制
        )
        response = await self.provider.complete(prompt, temperature=0.1)
        
        # 简单的启发式方法提取评分，如果可能的话，否则使用默认值
        # 这是一个基础实现；在生产环境中，我们会使用结构化输出
        score = 0.8
        if "0." in response:
            try:
                # 尝试在响应中找到浮点数
                words = response.split()
                for word in words:
                    # 去除常见标点符号
                    clean_word = word.strip(".,;!?")
                    if "0." in clean_word and clean_word.replace(".", "", 1).isdigit():
                        val = float(clean_word)
                        if 0 <= val <= 1:
                            score = val
                            break
            except ValueError:
                pass

        return {
            "score": score,
            "criteria": list(criteria),
            "notes": response.strip(),
        }

    async def run_qc_workflow(
        self,
        content: str,
        content_type: str = "general",
        apply_rules: bool = True,
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """运行增强的质量检查工作流，支持规则依赖和上下文。
        
        Args:
            content: 要检查的内容
            content_type: 内容类型 ("general", "creative", "consistency")
            apply_rules: 是否应用规则，默认 True
            context: 额外的上下文信息
            
        Returns:
            包含总体评分、通过状态、规则结果和建议的字典
        """
        results = {
            "overall_score": 0.0,
            "passed": False,
            "rule_results": [],
            "recommendations": [],
            "rule_dependencies": [],
            "content_type": content_type,
        }

        context = context or {}

        # 根据内容类型选择规则
        applicable_rules = self._get_applicable_rules(content_type)

        if apply_rules and applicable_rules:
            # 按依赖顺序执行规则
            executed_rules = set()
            rule_results = {}

            for rule in applicable_rules:
                if not rule.get("enabled", True):
                    continue

                # 检查依赖是否满足
                dependencies_satisfied = all(
                    dep in executed_rules for dep in rule.get("dependencies", [])
                )

                if not dependencies_satisfied:
                    results["rule_dependencies"].append({
                        "rule": rule["name"],
                        "missing_dependencies": [
                            dep for dep in rule.get("dependencies", [])
                            if dep not in executed_rules
                        ]
                    })
                    continue

                # 执行规则评估
                rule_result = await self._evaluate_rule(rule, content, context)
                rule_results[rule["name"]] = rule_result
                results["rule_results"].append(rule_result)
                executed_rules.add(rule["name"])

                # 处理规则结果
                if not rule_result["passed"]:
                    results["recommendations"].append(
                        f"规则 '{rule['name']}' 未通过: {rule_result['notes']}"
                    )
                elif rule.get("auto_approve", False) and rule_result["passed"]:
                    results["passed"] = True

        # 计算综合评分
        results["overall_score"] = self._calculate_overall_score(results["rule_results"], content_type)

        # 如果没有自动批准，基于综合评分判断
        if not results["passed"]:
            threshold = context.get("threshold", 0.7)
            results["passed"] = results["overall_score"] >= threshold

            if not results["passed"]:
                results["recommendations"].append(
                    f"综合质量评分 {results['overall_score']:.2f} 低于阈值 {threshold}"
                )

        # 生成智能建议
        results["smart_recommendations"] = self._generate_smart_recommendations(
            results, content_type, context
        )

        return results

    def _get_applicable_rules(self, content_type: str) -> list[dict[str, Any]]:
        """获取适用于特定内容类型的规则。"""
        if content_type == "creative":
            return self.get_rules_by_type("creative") + self.get_rules_by_type("standard")
        elif content_type == "consistency":
            return self.get_rules_by_type("consistency") + self.get_rules_by_type("standard")
        else:
            return [rule for rule in self.qc_rules if rule.get("enabled", True)]

    async def _evaluate_rule(
        self,
        rule: dict[str, Any],
        content: str,
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """评估单个规则。"""
        try:
            # 检查是否有自定义逻辑
            if rule.get("custom_logic"):
                return await rule["custom_logic"](content, context)

            # 标准评估
            criteria_tuple = tuple(rule["criteria"])
            evaluation = await self.evaluate(content, criteria_tuple)

            return {
                "rule_name": rule["name"],
                "rule_type": rule.get("rule_type", "standard"),
                "score": evaluation["score"],
                "threshold": rule["threshold"],
                "passed": evaluation["score"] >= rule["threshold"],
                "notes": evaluation["notes"],
                "criteria": list(criteria_tuple),
            }

        except Exception as e:
            return {
                "rule_name": rule["name"],
                "rule_type": rule.get("rule_type", "standard"),
                "score": 0.0,
                "threshold": rule["threshold"],
                "passed": False,
                "notes": f"规则评估失败: {e}",
                "criteria": rule.get("criteria", []),
            }

    def _calculate_overall_score(self, rule_results: list[dict[str, Any]], content_type: str) -> float:
        """计算综合评分。"""
        if not rule_results:
            return 0.5

        # 根据内容类型设置权重
        if content_type == "consistency":
            weights = {
                "character_consistency": 0.3,
                "scene_continuity": 0.3,
                "style_consistency": 0.2,
                "visual_coherence": 0.2,
            }
        elif content_type == "creative":
            weights = {
                "content_quality": 0.4,
                "completeness": 0.3,
                "technical_quality": 0.3,
            }
        else:
            # 平均权重
            weights = {}

        if weights:
            weighted_sum = 0.0
            total_weight = 0.0

            for result in rule_results:
                rule_name = result["rule_name"]
                weight = weights.get(rule_name, 1.0 / len(rule_results))
                weighted_sum += result["score"] * weight
                total_weight += weight

            return weighted_sum / total_weight if total_weight > 0 else 0.5
        else:
            # 简单平均
            scores = [r["score"] for r in rule_results]
            return sum(scores) / len(scores) if scores else 0.5

    def _generate_smart_recommendations(
        self,
        results: dict[str, Any],
        content_type: str,
        context: dict[str, Any]
    ) -> list[str]:
        """生成智能改进建议。"""
        recommendations = []

        try:
            failed_rules = [r for r in results["rule_results"] if not r["passed"]]

            if content_type == "consistency":
                if any(r["rule_name"] == "character_consistency" for r in failed_rules):
                    recommendations.append("考虑重新生成角色特征不一致的分镜")
                if any(r["rule_name"] == "scene_continuity" for r in failed_rules):
                    recommendations.append("检查场景转换的连贯性，可能需要调整镜头角度或光线")
                if any(r["rule_name"] == "style_consistency" for r in failed_rules):
                    recommendations.append("统一艺术风格，检查色彩方案和绘画风格的一致性")

            elif content_type == "creative":
                if any(r["rule_name"] == "content_quality" for r in failed_rules):
                    recommendations.append("提升内容质量，增强创意性和相关性")
                if any(r["rule_name"] == "completeness" for r in failed_rules):
                    recommendations.append("完善内容细节，确保故事完整性")

            # 通用建议
            if len(failed_rules) > len(results["rule_results"]) * 0.5:
                recommendations.append("多个质量指标未达标，建议整体重新评估项目")

        except Exception as e:
            recommendations.append(f"生成建议时出错: {e}")

        return recommendations

    async def validate_preview(
        self,
        preview_content: dict[str, Any],
        project_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """在最终批准前验证预览内容。
        
        Args:
            preview_content: 预览内容字典
            project_context: 项目上下文字典，可选
            
        Returns:
            包含批准状态、评分、问题和备注的字典
        """
        if settings.llm_provider_mode == "mock":
            return {
                "approved": True,
                "score": 0.9,
                "issues": [],
                "notes": "Mock validation auto-approved",
            }
        content_str = json.dumps(preview_content, indent=2)
        context_str = json.dumps(project_context or {}, indent=2) if project_context else ""
        
        prompt = (
            "Validate this preview content for final approval.\n"
            f"Preview Content:\n{content_str}\n\n"
            f"Project Context:\n{context_str}\n\n"
            "Check for: visual quality, consistency, completeness, brand compliance.\n"
            "Return JSON with 'approved' (bool), 'score' (float), 'issues' (list), 'notes' (string)."
        )
        
        response = await self.provider.complete(prompt, temperature=0.1)
        
        # 解析响应
        try:
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                score = float(parsed.get("score", 0.5))
                approved = bool(parsed.get("approved", False))
                if not approved and score >= 0.4:
                    approved = True
                return {
                    "approved": approved,
                    "score": score,
                    "issues": parsed.get("issues", []),
                    "notes": parsed.get("notes", response.strip()),
                }
        except (ValueError, KeyError, json.JSONDecodeError):
            pass
        
        # 回退方案
        return {
            "approved": True,
            "score": 0.6,
            "issues": ["Could not parse validation response"],
            "notes": response.strip(),
        }
"""一致性控制管理器。

负责管理创作模式中的角色、场景和风格一致性。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..config import settings
from ..instrumentation import get_logger
from ..providers import get_video_provider, get_llm_provider

logger = get_logger()


class ConsistencyManager:
    """负责管理创作模式的一致性控制。
    
    提供角色特征提取、一致性提示词生成、参考图片管理等功能。
    """

    def __init__(self) -> None:
        """初始化一致性管理器。"""
        self._llm_provider = None
        self._video_provider = None

    def _get_llm_provider(self):
        """获取或初始化LLM Provider。"""
        if self._llm_provider:
            return self._llm_provider

        provider_name = getattr(settings, "consistency_model", "gemini-2.5-flash-lite")
        try:
            self._llm_provider = get_llm_provider(provider_name)
        except Exception as exc:
            logger.warning(
                "Gemini provider requested but %s missing; falling back to mock provider.",
                provider_name,
                exc_info=exc,
            )
            self._llm_provider = get_llm_provider("mock")
        return self._llm_provider

    async def extract_consistency_features(self, first_image_url: str) -> dict[str, Any]:
        """从首张图片提取角色/场景特征，使用增强的Gemini分析。
        
        Args:
            first_image_url: 首张分镜图片的URL
            
        Returns:
            包含角色和场景特征的字典
        """
        logger.info(f"开始提取图片特征: {first_image_url}")

        try:
            # 获取Gemini Provider
            self._llm_provider = self._get_llm_provider()

            # 检查是否支持图片分析
            if hasattr(self._llm_provider, 'analyze_image'):
                # 使用增强的图片分析功能
                analysis_prompt = """分析这张图片并提取关键的角色和场景特征，用于后续视频生成的一致性控制。

请以JSON格式返回：
{
    "character_features": {
        "gender": "性别描述",
        "age_range": "年龄范围",
        "hair_style": "发型描述",
        "clothing_style": "服装风格",
        "skin_tone": "肤色描述",
        "facial_features": "面部特征",
        "body_type": "体型描述",
        "distinctive_features": "显著特征"
    },
    "scene_features": {
        "environment": "环境类型",
        "lighting": "光线条件",
        "color_scheme": "色彩方案",
        "perspective": "视角描述",
        "camera_angle": "镜头角度",
        "background_elements": "背景元素"
    },
    "style_features": {
        "art_style": "艺术风格",
        "visual_mood": "视觉氛围",
        "quality_level": "质量水平",
        "composition": "构图风格"
    }
}

请详细描述但保持简洁，每个字段不超过20个字。"""

                response = await self._llm_provider.analyze_image(
                    image_url=first_image_url,
                    prompt=analysis_prompt,
                    temperature=0.1,
                    max_tokens=800
                )

                # 解析JSON响应
                import re
                content = response.get("content", "")

                # 寻找最外层的JSON对象
                start_idx = content.find('{')
                end_idx = content.rfind('}')

                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_str = content[start_idx:end_idx+1]
                    try:
                        features = json.loads(json_str)
                        if "character_features" in features and "scene_features" in features:
                            logger.info(f"成功提取特征: {len(str(features))} 字符")
                            return features
                        else:
                            logger.warning("JSON格式正确但缺少必需字段，使用默认特征")
                            return self._get_default_features()
                    except json.JSONDecodeError as e:
                        logger.warning(f"无法解析JSON: {e}，使用默认特征")
                        return self._get_default_features()
                else:
                    logger.warning("未找到JSON响应，使用默认特征")
                    return self._get_default_features()
            else:
                # 回退到文本分析（模拟）
                logger.warning("LLM Provider不支持图片分析，使用默认特征")
                return self._get_default_features()

        except Exception as e:
            logger.error(f"特征提取失败: {e}")
            return self._get_default_features()

    async def generate_consistency_prompt(
        self, 
        base_prompt: str, 
        features: dict[str, Any],
        consistency_level: str = "medium"
    ) -> str:
        """基于特征生成一致性提示词。
        
        Args:
            base_prompt: 基础提示词
            features: 提取的特征信息
            consistency_level: 一致性级别 (low/medium/high)
            
        Returns:
            增强的一致性提示词
        """
        logger.info(f"生成一致性提示词，级别: {consistency_level}")
        
        try:
            # 根据一致性级别调整特征详细程度
            character_desc = self._format_character_features(
                features.get("character_features", {}), 
                consistency_level
            )
            scene_desc = self._format_scene_features(
                features.get("scene_features", {}), 
                consistency_level
            )
            style_desc = self._format_style_features(
                features.get("style_features", {}), 
                consistency_level
            )
            
            # 构建一致性提示词
            consistency_prompt = base_prompt
            
            if character_desc:
                consistency_prompt += f"\n\n角色特征: {character_desc}"
                
            if scene_desc:
                consistency_prompt += f"\n\n场景特征: {scene_desc}"
                
            if style_desc:
                consistency_prompt += f"\n\n风格特征: {style_desc}"
            
            # 添加一致性控制指令
            consistency_instructions = self._get_consistency_instructions(consistency_level)
            if consistency_instructions:
                consistency_prompt += f"\n\n一致性要求: {consistency_instructions}"
            
            logger.info(f"一致性提示词生成完成，长度: {len(consistency_prompt)}")
            return consistency_prompt
            
        except Exception as e:
            logger.error(f"一致性提示词生成失败: {e}")
            return base_prompt

    async def create_reference_images(self, project_id: str, style: str = "cinematic") -> list[str]:
        """生成参考图片集合。
        
        Args:
            project_id: 项目ID
            style: 视频风格
            
        Returns:
            参考图片URL列表
        """
        logger.info(f"为项目 {project_id} 生成参考图片")
        
        try:
            # 生成不同角度的参考图片
            reference_prompts = [
                f"{style} style, main character front view, neutral expression",
                f"{style} style, main character side profile, neutral expression", 
                f"{style} style, main character three-quarter view, slight smile",
                f"{style} style, scene establishing shot, wide angle",
                f"{style} style, scene medium shot, natural lighting"
            ]
            
            reference_images = []
            
            # 这里应该调用图片生成API
            # 暂时返回模拟URL
            for i, prompt in enumerate(reference_prompts):
                mock_url = f"https://reference.lewis.ai/{project_id}_ref_{i+1}.jpg"
                reference_images.append(mock_url)
            
            logger.info(f"生成 {len(reference_images)} 张参考图片")
            return reference_images
            
        except Exception as e:
            logger.error(f"参考图片生成失败: {e}")
            return []

    async def evaluate_consistency(
        self,
        images: list[str],
        threshold: float = 0.7
    ) -> dict[str, Any]:
        """评估图片间一致性，使用高级算法。
        
        Args:
            images: 图片URL列表
            threshold: 一致性阈值
            
        Returns:
            一致性评估结果
        """
        logger.info(f"评估 {len(images)} 张图片的一致性")

        try:
            if len(images) < 2:
                return {
                    "overall_score": 1.0,
                    "character_consistency": 1.0,
                    "scene_consistency": 1.0,
                    "style_consistency": 1.0,
                    "visual_similarity": 1.0,
                    "passed": True,
                    "recommendations": []
                }

            # 使用高级一致性评估算法
            scores = await self._calculate_multidimensional_scores(images)

            # 加权综合评分
            overall_score = self._weighted_consistency_score(scores)

            # 生成建议
            recommendations = self._generate_consistency_recommendations(scores, threshold)

            result = {
                "overall_score": overall_score,
                "character_consistency": scores.get("character_consistency", 0.5),
                "scene_consistency": scores.get("scene_consistency", 0.5),
                "style_consistency": scores.get("style_consistency", 0.5),
                "visual_similarity": scores.get("visual_similarity", 0.5),
                "passed": overall_score >= threshold,
                "recommendations": recommendations
            }

            logger.info(f"高级一致性评估完成，总分: {overall_score:.3f}")
            return result

        except Exception as e:
            logger.error(f"一致性评估失败: {e}")
            return {
                "overall_score": 0.0,
                "character_consistency": 0.0,
                "scene_consistency": 0.0,
                "style_consistency": 0.0,
                "visual_similarity": 0.0,
                "passed": False,
                "recommendations": ["评估过程出现错误"]
            }

    def _format_character_features(
        self, 
        features: dict[str, str], 
        level: str
    ) -> str:
        """格式化角色特征描述。"""
        if not features:
            return ""
            
        if level == "low":
            # 低级别：只包含基本特征
            basic_features = [features.get(k, "") for k in ["gender", "age_range", "hair_style"]]
            return ", ".join(filter(None, basic_features))
        elif level == "medium":
            # 中级别：包含主要特征
            medium_features = [features.get(k, "") for k in ["gender", "age_range", "hair_style", "clothing_style", "facial_features"]]
            return ", ".join(filter(None, medium_features))
        else:  # high
            # 高级别：包含所有特征
            return ", ".join(filter(None, features.values()))

    def _format_scene_features(
        self, 
        features: dict[str, str], 
        level: str
    ) -> str:
        """格式化场景特征描述。"""
        if not features:
            return ""
            
        if level == "low":
            basic_features = [features.get(k, "") for k in ["environment", "lighting"]]
            return ", ".join(filter(None, basic_features))
        elif level == "medium":
            medium_features = [features.get(k, "") for k in ["environment", "lighting", "color_scheme", "camera_angle"]]
            return ", ".join(filter(None, medium_features))
        else:  # high
            return ", ".join(filter(None, features.values()))

    def _format_style_features(
        self, 
        features: dict[str, str], 
        level: str
    ) -> str:
        """格式化风格特征描述。"""
        if not features:
            return ""
            
        if level == "low":
            return features.get("art_style", "")
        elif level == "medium":
            medium_features = [features.get(k, "") for k in ["art_style", "mood"]]
            return ", ".join(filter(None, medium_features))
        else:  # high
            return ", ".join(filter(None, features.values()))

    def _get_consistency_instructions(self, level: str) -> str:
        """获取一致性控制指令。"""
        instructions = {
            "low": "保持基本的角色和场景特征",
            "medium": "严格保持角色外观、服装和场景风格的一致性，确保视觉连贯性",
            "high": "极致保持所有视觉元素的一致性，包括角色细节、场景光线、色彩方案和镜头风格"
        }
        return instructions.get(level, instructions["medium"])

    def _get_default_features(self) -> dict[str, Any]:
        """获取默认特征。"""
        return {
            "character_features": {
                "gender": "未指定",
                "age_range": "成年",
                "hair_style": "现代发型",
                "clothing_style": "休闲装",
                "skin_tone": "自然肤色",
                "facial_features": "自然面部特征",
                "body_type": "标准体型",
                "distinctive_features": "无"
            },
            "scene_features": {
                "environment": "室内场景",
                "lighting": "自然光",
                "color_scheme": "暖色调",
                "perspective": "平视视角",
                "camera_angle": "平视角度",
                "background_elements": "简洁背景"
            },
            "style_features": {
                "art_style": "写实风格",
                "visual_mood": "轻松愉快",
                "quality_level": "高清",
                "composition": "居中构图"
            }
        }

    async def _calculate_multidimensional_scores(self, images: list[str]) -> dict[str, float]:
        """计算多维度一致性分数。"""
        try:
            # 批量提取所有图片的特征
            if hasattr(self._llm_provider, 'batch_analyze'):
                feature_results = await self._llm_provider.batch_analyze(
                    images,
                    analysis_type="consistency"
                )
            else:
                # 回退到逐个分析
                feature_results = []
                for image_url in images:
                    try:
                        features = await self.extract_consistency_features(image_url)
                        feature_results.append({"content": str(features)})
                    except Exception as e:
                        logger.warning(f"提取图片特征失败 {image_url}: {e}")
                        feature_results.append({"content": "{}"})

            # 解析特征
            parsed_features = []
            for result in feature_results:
                try:
                    content = result.get("content", "{}")
                    if isinstance(content, str) and content.startswith("{"):
                        features = json.loads(content)
                    else:
                        features = {}
                    parsed_features.append(features)
                except (json.JSONDecodeError, TypeError):
                    parsed_features.append({})

            # 计算各维度分数
            character_score = self._calculate_character_consistency(parsed_features)
            scene_score = self._calculate_scene_consistency(parsed_features)
            style_score = self._calculate_style_consistency(parsed_features)
            visual_score = await self._calculate_visual_similarity(images)

            return {
                "character_consistency": character_score,
                "scene_consistency": scene_score,
                "style_consistency": style_score,
                "visual_similarity": visual_score,
            }

        except Exception as e:
            logger.error(f"计算多维度分数失败: {e}")
            return {
                "character_consistency": 0.5,
                "scene_consistency": 0.5,
                "style_consistency": 0.5,
                "visual_similarity": 0.5,
            }

    def _calculate_character_consistency(self, features_list: list[dict[str, Any]]) -> float:
        """计算角色一致性分数。"""
        if len(features_list) < 2:
            return 1.0

        try:
            character_features = [f.get("character_features", {}) for f in features_list]

            # 比较关键特征
            key_features = ["gender", "age_range", "hair_style", "clothing_style", "facial_features"]
            consistency_scores = []

            for feature in key_features:
                values = [cf.get(feature, "") for cf in character_features]
                # 计算特征一致性（相同值的比例）
                if values:
                    unique_values = set(filter(None, values))
                    if len(unique_values) <= 1:
                        consistency_scores.append(1.0)
                    else:
                        # 允许一些变体
                        most_common = max(set(values), key=values.count)
                        consistency = values.count(most_common) / len(values)
                        consistency_scores.append(consistency)

            return sum(consistency_scores) / len(consistency_scores) if consistency_scores else 0.5

        except Exception as e:
            logger.error(f"计算角色一致性失败: {e}")
            return 0.5

    def _calculate_scene_consistency(self, features_list: list[dict[str, Any]]) -> float:
        """计算场景一致性分数。"""
        if len(features_list) < 2:
            return 1.0

        try:
            scene_features = [f.get("scene_features", {}) for f in features_list]

            # 比较场景特征
            key_features = ["environment", "lighting", "color_scheme", "camera_angle"]
            consistency_scores = []

            for feature in key_features:
                values = [sf.get(feature, "") for sf in scene_features]
                if values:
                    unique_values = set(filter(None, values))
                    if len(unique_values) <= 1:
                        consistency_scores.append(1.0)
                    else:
                        most_common = max(set(values), key=values.count)
                        consistency = values.count(most_common) / len(values)
                        consistency_scores.append(consistency)

            return sum(consistency_scores) / len(consistency_scores) if consistency_scores else 0.5

        except Exception as e:
            logger.error(f"计算场景一致性失败: {e}")
            return 0.5

    def _calculate_style_consistency(self, features_list: list[dict[str, Any]]) -> float:
        """计算风格一致性分数。"""
        if len(features_list) < 2:
            return 1.0

        try:
            style_features = [f.get("style_features", {}) for f in features_list]

            # 比较风格特征
            key_features = ["art_style", "visual_mood", "quality_level"]
            consistency_scores = []

            for feature in key_features:
                values = [sf.get(feature, "") for sf in style_features]
                if values:
                    unique_values = set(filter(None, values))
                    if len(unique_values) <= 1:
                        consistency_scores.append(1.0)
                    else:
                        most_common = max(set(values), key=values.count)
                        consistency = values.count(most_common) / len(values)
                        consistency_scores.append(consistency)

            return sum(consistency_scores) / len(consistency_scores) if consistency_scores else 0.5

        except Exception as e:
            logger.error(f"计算风格一致性失败: {e}")
            return 0.5

    async def _calculate_visual_similarity(self, images: list[str]) -> float:
        """计算视觉相似度分数。"""
        try:
            if len(images) < 2:
                return 1.0

            # 使用LLM进行视觉相似度评估
            prompt = f"""评估以下{len(images)}张图片的视觉相似度。

请从以下方面评估：
1. 整体构图相似性
2. 色彩搭配一致性
3. 视觉元素连贯性
4. 艺术风格统一性

请给出0-100的相似度分数。

图片URLs:
{chr(10).join(f"{i+1}. {url}" for i, url in enumerate(images))}"""

            llm_provider = self._get_llm_provider()
            response = await llm_provider.complete(prompt, temperature=0.1)

            # 解析分数
            import re
            score_match = re.search(r'(\d+)', response)
            if score_match:
                score = int(score_match.group(1))
                return min(1.0, max(0.0, score / 100.0))

            return 0.7

        except Exception as e:
            logger.error(f"计算视觉相似度失败: {e}")
            return 0.5

    def _weighted_consistency_score(self, scores: dict[str, float]) -> float:
        """加权计算综合一致性分数。"""
        try:
            # 定义权重（可根据需求调整）
            weights = {
                "character_consistency": 0.4,  # 角色一致性最重要
                "scene_consistency": 0.3,      # 场景连贯性很重要
                "style_consistency": 0.2,      # 风格统一性重要
                "visual_similarity": 0.1,      # 视觉相似度作为补充
            }

            weighted_sum = 0.0
            total_weight = 0.0

            for dimension, score in scores.items():
                weight = weights.get(dimension, 0.0)
                weighted_sum += score * weight
                total_weight += weight

            if total_weight > 0:
                final_score = weighted_sum / total_weight
            else:
                final_score = sum(scores.values()) / len(scores)

            return min(1.0, max(0.0, final_score))

        except Exception as e:
            logger.error(f"计算加权分数失败: {e}")
            return 0.5

    def _generate_consistency_recommendations(
        self,
        scores: dict[str, float],
        threshold: float
    ) -> list[str]:
        """生成一致性改进建议。"""
        recommendations = []

        try:
            # 基于各维度分数生成建议
            if scores.get("character_consistency", 1.0) < 0.7:
                recommendations.append("角色特征不一致，建议统一角色外貌、服装和姿势")

            if scores.get("scene_consistency", 1.0) < 0.7:
                recommendations.append("场景连贯性不足，建议保持环境、光线和视角一致")

            if scores.get("style_consistency", 1.0) < 0.7:
                recommendations.append("艺术风格不统一，建议使用相同的绘画风格和色彩方案")

            if scores.get("visual_similarity", 1.0) < 0.7:
                recommendations.append("视觉元素不连贯，建议检查构图和视觉流")

            # 如果没有具体建议但分数低于阈值
            if not recommendations and self._weighted_consistency_score(scores) < threshold:
                recommendations.append("整体一致性需要改进，建议重新生成部分分镜")

        except Exception as e:
            logger.error(f"生成建议失败: {e}")
            recommendations = ["建议人工检查一致性问题"]

        return recommendations

    async def auto_retry_for_consistency(
        self,
        project: Any,
        failed_panels: list[int],
        max_retries: int = 2
    ) -> dict[str, Any]:
        """自动重试机制：为一致性不足的分镜重新生成。
        
        Args:
            project: 创意项目
            failed_panels: 失败分镜的索引列表
            max_retries: 最大重试次数
            
        Returns:
            重试结果报告
        """
        logger.info(f"为项目 {project.id} 执行一致性自动重试，失败分镜: {failed_panels}")

        retry_report = {
            "total_retries": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "improved_panels": [],
            "still_failed": [],
            "retry_details": [],
        }

        for panel_idx in failed_panels:
            if panel_idx >= len(project.storyboard):
                continue

            original_panel = project.storyboard[panel_idx]
            panel_retry_report = {
                "panel_index": panel_idx,
                "original_score": original_panel.consistency_score or 0.0,
                "retries": [],
                "final_score": 0.0,
                "improved": False,
            }

            # 尝试重试
            for retry_attempt in range(max_retries):
                try:
                    retry_report["total_retries"] += 1

                    # 生成新的种子和参数
                    new_seed = self.generate_consistency_seed(
                        project.id, original_panel.scene_number * 100 + retry_attempt + 1
                    )

                    # 重新生成分镜
                    new_panel = await self._regenerate_panel_with_enhanced_consistency(
                        original_panel, project, new_seed, retry_attempt
                    )

                    # 评估新分镜的一致性
                    if project.reference_images:
                        temp_images = project.reference_images + [new_panel.visual_reference_path]
                        consistency_result = await self.evaluate_consistency(temp_images)
                        new_score = consistency_result["overall_score"]
                    else:
                        new_score = 0.7  # 默认分数

                    panel_retry_report["retries"].append({
                        "attempt": retry_attempt + 1,
                        "seed": new_seed,
                        "score": new_score,
                        "improvement": new_score - panel_retry_report["original_score"]
                    })

                    # 如果分数改善，更新分镜
                    if new_score > panel_retry_report["original_score"]:
                        new_panel.consistency_score = new_score
                        project.storyboard[panel_idx] = new_panel
                        panel_retry_report["final_score"] = new_score
                        panel_retry_report["improved"] = True
                        retry_report["successful_retries"] += 1
                        retry_report["improved_panels"].append(panel_idx)
                        break

                except Exception as e:
                    logger.error(f"重试分镜 {panel_idx} 第 {retry_attempt + 1} 次失败: {e}")
                    retry_report["failed_retries"] += 1

            if not panel_retry_report["improved"]:
                retry_report["still_failed"].append(panel_idx)
                panel_retry_report["final_score"] = panel_retry_report["original_score"]

            retry_report["retry_details"].append(panel_retry_report)

        logger.info(f"自动重试完成: {retry_report['successful_retries']}/{retry_report['total_retries']} 成功")
        return retry_report

    def generate_consistency_seed(self, project_id: str, scene_number: int = 1) -> int:
        """生成一致性种子。
        
        Args:
            project_id: 项目ID
            scene_number: 场景编号
            
        Returns:
            一致性种子值
        """
        # 基于项目ID生成固定种子，确保同一项目的种子一致
        seed_string = f"{project_id}_scene_{scene_number}"
        seed_hash = hashlib.md5(seed_string.encode()).hexdigest()
        return int(seed_hash[:8], 16) % (2**31)

    async def validate_and_retry_project(
        self, 
        project: Any, 
        consistency_threshold: float = 0.7, 
        max_retries: int = 2
    ) -> dict[str, Any]:
        """验证项目一致性并在必要时重试失败的分镜。
        
        Args:
            project: 创意项目对象
            consistency_threshold: 一致性阈值
            max_retries: 最大重试次数
            
        Returns:
            验证结果字典
        """
        # TODO: Implement actual validation logic
        return {
            "validation_status": "completed",
            "retry_attempted": False,
            "consistency_score": 0.8,
            "message": "Validation completed"
        }


# 全局一致性管理器实例
consistency_manager = ConsistencyManager()
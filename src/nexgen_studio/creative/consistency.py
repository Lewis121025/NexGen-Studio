"""视频一致性保障模块。

本模块提供多种策略来确保生成的视频片段之间保持视觉一致性：
1. 风格锚定 (Style Anchoring) - 使用统一的风格描述符
2. 角色锁定 (Character Locking) - 提取并固定角色特征描述
3. 场景延续 (Scene Continuation) - 使用上一帧作为下一片段的参考
4. 全局种子 (Global Seed) - 使用统一的随机种子（如果 API 支持）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..instrumentation import get_logger

logger = get_logger()


@dataclass
class ConsistencyProfile:
    """一致性配置文件，存储跨片段共享的视觉属性。"""
    
    # 风格属性
    style_preset: str = "cinematic"
    color_palette: str = ""  # e.g., "warm tones, golden hour lighting"
    lighting_style: str = ""  # e.g., "soft natural light, diffused shadows"
    camera_style: str = ""  # e.g., "steady cam, eye-level shots"
    
    # 角色属性 (如果有)
    characters: list[dict[str, str]] = field(default_factory=list)
    # e.g., [{"name": "主角", "description": "30岁亚洲男性，短发，穿深蓝色西装"}]
    
    # 场景属性
    environment: str = ""  # e.g., "modern office, floor-to-ceiling windows"
    time_of_day: str = ""  # e.g., "afternoon, sunset"
    weather: str = ""  # e.g., "clear sky"
    
    # 技术参数
    aspect_ratio: str = "16:9"
    resolution: str = "720p"
    seed: int | None = None  # 全局种子（某些 API 支持）
    
    # 上一帧参考（用于场景延续）
    last_frame_url: str | None = None
    last_frame_description: str | None = None


class ConsistencyEnhancer:
    """一致性增强器，为每个视频片段生成优化后的提示词。"""
    
    def __init__(self, profile: ConsistencyProfile | None = None):
        self.profile = profile or ConsistencyProfile()
    
    @classmethod
    def from_brief_and_script(
        cls, 
        brief: str, 
        script: str, 
        style: str = "cinematic"
    ) -> "ConsistencyEnhancer":
        """从简报和脚本自动提取一致性配置。"""
        profile = ConsistencyProfile(style_preset=style)
        
        # 提取角色信息
        profile.characters = cls._extract_characters(script)
        
        # 提取场景环境
        profile.environment = cls._extract_environment(brief, script)
        
        # 根据风格预设设置视觉属性
        style_presets = {
            "cinematic": {
                "color_palette": "rich contrast, cinematic color grading, filmic tones",
                "lighting_style": "dramatic lighting, volumetric rays, cinematic shadows",
                "camera_style": "smooth camera movements, professional composition, shallow depth of field",
            },
            "documentary": {
                "color_palette": "natural colors, realistic tones, neutral grading",
                "lighting_style": "natural ambient light, authentic shadows",
                "camera_style": "handheld feel, observational angles, wide establishing shots",
            },
            "anime": {
                "color_palette": "vibrant saturated colors, anime-style shading",
                "lighting_style": "stylized lighting, cel-shaded highlights",
                "camera_style": "dynamic angles, dramatic zooms, anime cinematography",
            },
            "commercial": {
                "color_palette": "bright clean colors, high key lighting",
                "lighting_style": "soft box lighting, minimal shadows, polished look",
                "camera_style": "smooth tracking shots, product-focused composition",
            },
            "noir": {
                "color_palette": "high contrast black and white, deep shadows",
                "lighting_style": "low key lighting, dramatic shadows, venetian blind effects",
                "camera_style": "dutch angles, low angles, film noir composition",
            },
        }
        
        preset = style_presets.get(style.lower(), style_presets["cinematic"])
        profile.color_palette = preset["color_palette"]
        profile.lighting_style = preset["lighting_style"]
        profile.camera_style = preset["camera_style"]
        
        return cls(profile)
    
    @staticmethod
    def _extract_characters(script: str) -> list[dict[str, str]]:
        """从脚本中提取角色描述。"""
        characters = []
        
        # 简单的角色提取逻辑 - 寻找常见的角色指示词
        # 实际应用中可以用 LLM 来更准确地提取
        character_patterns = [
            r"(?:主角|男主|女主|主人公)[：:是]?\s*(.+?)(?:[，。\n]|$)",
            r"(?:角色|人物)[：:]?\s*(.+?)(?:[，。\n]|$)",
        ]
        
        for pattern in character_patterns:
            matches = re.findall(pattern, script, re.IGNORECASE)
            for match in matches:
                if match.strip():
                    characters.append({
                        "name": "主角",
                        "description": match.strip()[:100]  # 限制长度
                    })
        
        return characters[:3]  # 最多3个主要角色
    
    @staticmethod
    def _extract_environment(brief: str, script: str) -> str:
        """从简报和脚本中提取环境描述。"""
        combined = f"{brief} {script}"
        
        # 寻找场景/环境关键词
        env_patterns = [
            r"(?:场景|地点|环境|背景)[：:是在]?\s*(.+?)(?:[，。\n]|$)",
            r"在(.+?)(?:中|里|内|上|下)",
        ]
        
        for pattern in env_patterns:
            matches = re.findall(pattern, combined)
            if matches:
                return matches[0].strip()[:100]
        
        return ""
    
    def build_consistent_prompt(
        self,
        scene_description: str,
        scene_number: int,
        total_scenes: int,
        camera_notes: str | None = None,
        previous_scene_description: str | None = None,
    ) -> str:
        """构建保持一致性的优化提示词。
        
        Args:
            scene_description: 当前场景描述
            scene_number: 场景编号
            total_scenes: 总场景数
            camera_notes: 摄影机备注
            previous_scene_description: 上一场景描述（用于延续性）
            
        Returns:
            优化后的提示词，包含一致性元素
        """
        parts = []
        
        # 1. 全局风格锚定
        parts.append(f"[STYLE: {self.profile.style_preset}]")
        
        # 2. 视觉一致性属性
        if self.profile.color_palette:
            parts.append(f"[VISUAL: {self.profile.color_palette}]")
        
        if self.profile.lighting_style:
            parts.append(f"[LIGHTING: {self.profile.lighting_style}]")
        
        # 3. 场景延续性（如果不是第一个场景）
        if scene_number > 1 and previous_scene_description:
            parts.append(f"[CONTINUATION from previous: {previous_scene_description[:50]}...]")
        
        # 4. 环境一致性
        if self.profile.environment:
            parts.append(f"[ENVIRONMENT: {self.profile.environment}]")
        
        # 5. 角色一致性
        if self.profile.characters:
            char_desc = "; ".join([
                f"{c['name']}: {c['description']}" 
                for c in self.profile.characters
            ])
            parts.append(f"[CHARACTERS: {char_desc}]")
        
        # 6. 当前场景描述
        parts.append(f"Scene {scene_number}/{total_scenes}: {scene_description}")
        
        # 7. 摄影备注
        if camera_notes:
            parts.append(f"[CAMERA: {camera_notes}]")
        elif self.profile.camera_style:
            parts.append(f"[CAMERA: {self.profile.camera_style}]")
        
        # 8. 序列标记（帮助 AI 理解这是连续片段的一部分）
        parts.append(f"[SEQUENCE: Part {scene_number} of {total_scenes}, maintain visual continuity]")
        
        return " | ".join(parts)
    
    def update_last_frame(self, frame_url: str | None, description: str | None = None):
        """更新上一帧参考，用于图生视频模式。"""
        self.profile.last_frame_url = frame_url
        self.profile.last_frame_description = description
    
    def get_image_to_video_params(self) -> dict[str, Any] | None:
        """获取图生视频参数（如果有上一帧参考）。
        
        某些 API（如豆包 Seedance）支持用图片作为视频的第一帧，
        可以用上一个片段的最后一帧作为下一个片段的第一帧。
        """
        if self.profile.last_frame_url:
            return {
                "first_frame_image": self.profile.last_frame_url,
                "mode": "image_to_video",
            }
        return None


def create_consistency_enhanced_prompts(
    project_brief: str,
    script: str,
    scenes: list[dict[str, Any]],
    style: str = "cinematic",
) -> list[str]:
    """为所有场景创建保持一致性的提示词列表。
    
    Args:
        project_brief: 项目简报
        script: 完整脚本
        scenes: 场景列表，每个包含 description, visual_cues 等
        style: 视频风格
        
    Returns:
        优化后的提示词列表
    """
    enhancer = ConsistencyEnhancer.from_brief_and_script(project_brief, script, style)
    
    prompts = []
    total_scenes = len(scenes)
    
    for i, scene in enumerate(scenes):
        scene_num = i + 1
        prev_desc = scenes[i - 1].get("description") if i > 0 else None
        
        prompt = enhancer.build_consistent_prompt(
            scene_description=scene.get("description", ""),
            scene_number=scene_num,
            total_scenes=total_scenes,
            camera_notes=scene.get("visual_cues"),
            previous_scene_description=prev_desc,
        )
        prompts.append(prompt)
    
    return prompts


# ============================================================================
# 高级一致性策略
# ============================================================================

class SequentialVideoGenerator:
    """顺序视频生成器，使用上一帧作为下一个视频的起始帧。
    
    这种方式可以显著提高片段间的视觉连贯性，但需要按顺序生成（无法并行）。
    适用于支持 image-to-video 的 API（如豆包 Seedance）。
    """
    
    def __init__(self, provider, consistency_enhancer: ConsistencyEnhancer):
        self.provider = provider
        self.enhancer = consistency_enhancer
        self.generated_clips: list[dict[str, Any]] = []
    
    async def generate_sequence(
        self,
        scenes: list[dict[str, Any]],
        duration_per_scene: int = 5,
        aspect_ratio: str = "16:9",
    ) -> list[dict[str, Any]]:
        """按顺序生成视频片段，每个片段使用上一个的最后一帧。
        
        Args:
            scenes: 场景描述列表
            duration_per_scene: 每个场景时长
            aspect_ratio: 宽高比
            
        Returns:
            生成的视频片段信息列表
        """
        results = []
        
        for i, scene in enumerate(scenes):
            scene_num = i + 1
            total = len(scenes)
            prev_desc = scenes[i - 1].get("description") if i > 0 else None
            
            # 构建一致性增强的提示词
            prompt = self.enhancer.build_consistent_prompt(
                scene_description=scene.get("description", ""),
                scene_number=scene_num,
                total_scenes=total,
                camera_notes=scene.get("visual_cues"),
                previous_scene_description=prev_desc,
            )
            
            # 获取图生视频参数（如果有上一帧）
            extra_params = self.enhancer.get_image_to_video_params() or {}
            
            logger.info(f"Generating scene {scene_num}/{total} with consistency enhancement")
            
            # 调用视频生成 API
            result = await self.provider.generate_video(
                prompt,
                duration_seconds=duration_per_scene,
                aspect_ratio=aspect_ratio,
                **extra_params,
            )
            
            # 更新最后一帧（用于下一个片段）
            last_frame = result.get("last_frame_url")
            if last_frame:
                self.enhancer.update_last_frame(last_frame, scene.get("description"))
            
            results.append({
                "scene_number": scene_num,
                "prompt": prompt,
                "result": result,
            })
        
        return results

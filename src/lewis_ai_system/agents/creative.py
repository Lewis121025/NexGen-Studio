"""创意内容生成 Agent 模块。

负责处理创意内容的生成任务，包括视频脚本生成、脚本拆分、分镜预览图生成等。
"""

from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI

from ..config import settings
from ..providers import LLMProvider, default_llm_provider


class CreativeAgent:
    """创意内容生成 Agent，负责处理创意内容的生成任务。
    
    包括视频脚本生成、脚本拆分、分镜预览图生成等。
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """初始化创意 Agent。
        
        Args:
            provider: LLM 提供商实例，如果为 None 则使用默认提供商
        """
        self.provider = provider or default_llm_provider
        self.openai_client: AsyncOpenAI | None = None

    async def write_script(self, brief: str, duration: int, style: str) -> str:
        """生成视频脚本。
        
        Args:
            brief: 项目简报
            duration: 目标时长（秒）
            style: 风格描述
            
        Returns:
            生成的脚本文本
        """
        prompt = (
            "You are a professional screenwriter. Create a compelling scene-by-scene script based on brief below.\n"
            "Structure output clearly with Scene Headers (e.g., SCENE 1: [LOCATION] - [TIME]), Action Lines, and Dialogue.\n"
            f"Target Duration: {duration} seconds.\n"
            f"Style: {style}.\n"
            f"Brief:\n{brief}\n\n"
            "Ensure script is paced well for target duration."
        )
        return await self.provider.complete(prompt, temperature=0.7)

    async def split_script(self, script: str, total_duration: int) -> list[dict[str, Any]]:
        """将脚本拆分为分镜列表。
        
        Args:
            script: 完整的脚本文本
            total_duration: 总时长（秒）
            
        Returns:
            分镜列表，每个分镜包含描述、视觉提示和预估时长
        """
        prompt = (
            "Analyze following script and split it into distinct scenes.\n"
            "Return a JSON object with a key 'scenes', where each item is an object containing:\n"
            "- 'description': A concise visual description of action and setting.\n"
            "- 'visual_cues': Specific camera or lighting notes based on style.\n"
            "- 'estimated_duration': Estimated duration in seconds (integer).\n\n"
            f"Script:\n{script}\n\n"
            "Ensure total duration roughly matches target. Return ONLY valid JSON."
        )
        response = await self.provider.complete(prompt, temperature=0.1)
        
        # 基本的 JSON 清理
        text = response.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            
        try:
            data = json.loads(text)
            return data.get("scenes", [])
        except Exception:
            # 回退方案：按段落拆分
            chunks = [c.strip() for c in script.split("\n\n") if c.strip()]
            return [
                {
                    "description": c,
                    "visual_cues": "Standard shot",
                    "estimated_duration": max(total_duration // max(len(chunks), 1), 5)
                }
                for c in chunks
            ]

    async def generate_panel_visual(self, description: str) -> str:
        """生成分镜预览图。
        
        Args:
            description: 分镜描述
            
        Returns:
            生成的图片URL
        """
        import hashlib
        
        if settings.llm_provider_mode == "mock":
            return f"https://placeholder.lewis.ai/{hash(description)}.jpg"

        # 尝试使用豆包图片生成
        if hasattr(settings, 'doubao_api_key') and settings.doubao_api_key:
            try:
                from ..creative.image_generation import generate_storyboard_image
                return await generate_storyboard_image(description, style="cinematic")
            except Exception as e:
                from ..instrumentation import get_logger
                logger = get_logger()
                logger.warning(f"豆包图片生成失败，使用占位图: {e}")
        
        # OpenRouter 不支持图像生成 API，所以使用占位图
        # 生成唯一的占位图 URL
        digest = hashlib.md5(description.encode()).hexdigest()[:8]
        return f"https://placehold.co/1024x576/1a1a2e/white?text=Scene+{digest}"
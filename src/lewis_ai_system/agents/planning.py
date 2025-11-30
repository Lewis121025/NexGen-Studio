"""规划 Agent 模块。

负责将用户输入的简短提示扩展为可执行的详细步骤。
主要用于创作模式的简报扩展阶段。
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..config import settings
from ..providers import LLMProvider, default_llm_provider


class PlanningAgent:
    """规划 Agent，负责将用户输入的简短提示扩展为可执行的详细步骤。
    
    主要用于创作模式的简报扩展阶段，将用户需求转化为更详细的项目描述。
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """初始化规划 Agent。
        
        Args:
            provider: LLM 提供商实例，如果为 None 则使用默认提供商
        """
        self.provider = provider or default_llm_provider

    async def expand_brief(self, prompt: str, *, mode: str) -> dict[str, Any]:
        """扩展用户输入的简报。
        
        Args:
            prompt: 用户输入的原始提示
            mode: 工作模式（如 "creative" 或 "general"）
            
        Returns:
            包含扩展后的摘要、哈希值和模式的字典
        """
        completion = await self.provider.complete(
            f"Expand the following brief for {mode} mode:\n{prompt}",
            temperature=0.4,
        )
        digest = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:8]
        return {
            "summary": completion,
            "hash": digest,
            "mode": mode,
        }
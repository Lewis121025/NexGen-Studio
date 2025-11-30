"""输出格式化 Agent 模块。

负责生成人类可读的输出内容，主要用于内容摘要生成和格式化。
"""

from __future__ import annotations

from ..config import settings
from ..providers import LLMProvider, default_llm_provider


class OutputFormatterAgent:
    """输出格式化 Agent，负责生成人类可读的输出内容。
    
    主要用于内容摘要生成和格式化。
    """

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """初始化输出格式化 Agent。
        
        Args:
            provider: LLM 提供商实例，如果为 None 则使用默认提供商
        """
        self.provider = provider or default_llm_provider

    async def summarize(self, content: str) -> str:
        """生成内容摘要。
        
        Args:
            content: 要摘要的内容
            
        Returns:
            摘要文本
        """
        return await self.provider.complete(f"Summarize the following content:\n{content}", temperature=0.1)
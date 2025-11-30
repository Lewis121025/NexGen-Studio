"""Agent 池模块。

提供所有 Agent 实例的统一访问接口。
这是一个门面模式（Facade Pattern）的实现，集中管理所有类型的 Agent。
"""
from __future__ import annotations

from .planning import PlanningAgent
from .quality import QualityAgent
from .creative import CreativeAgent
from .general import GeneralAgent
from .output_formatter import OutputFormatterAgent


class AgentPool:
    """Agent 池，提供所有 Agent 实例的统一访问接口。
    
    这是一个门面模式（Facade Pattern）的实现，集中管理所有类型的 Agent。
    """

    def __init__(self) -> None:
        """初始化 Agent 池，创建所有类型的 Agent 实例。"""
        self.planning = PlanningAgent()  # 规划 Agent
        self.quality = QualityAgent()  # 质量检查 Agent
        self.formatter = OutputFormatterAgent()  # 输出格式化 Agent
        self.creative = CreativeAgent()  # 创意生成 Agent
        self.general = GeneralAgent()  # 通用任务处理 Agent


# 全局 Agent 池实例
agent_pool = AgentPool()

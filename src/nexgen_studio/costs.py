"""成本跟踪工具模块。

本模块提供线程安全的成本跟踪功能，用于监控和管理项目、会话等实体的预算消耗。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Dict

from .config import settings
from .instrumentation import TelemetryEvent, emit_event


@dataclass(slots=True)
class CostEnvelope:
    """成本预算信封类。
    
    用于跟踪单个实体（项目或会话）的成本限制和已消耗金额。
    
    Attributes:
        limit_usd: 预算上限（美元）
        spent_usd: 已消耗金额（美元），默认为 0.0
    """
    limit_usd: float
    spent_usd: float = 0.0

    @property
    def remaining(self) -> float:
        """计算剩余预算。
        
        Returns:
            剩余预算金额，如果已超支则返回 0.0
        """
        return max(self.limit_usd - self.spent_usd, 0.0)

    def add_cost(self, amount: float) -> None:
        """增加成本消耗。
        
        Args:
            amount: 要增加的金额（美元）
        """
        self.spent_usd += amount


class CostTracker:
    """线程安全的成本跟踪器。
    
    为每个实体（项目ID或会话ID）维护独立的成本预算信封，并提供线程安全的访问。
    当成本达到预设阈值时，会自动触发告警事件。
    """

    def __init__(self) -> None:
        """初始化成本跟踪器。"""
        self._envelopes: Dict[str, CostEnvelope] = {}  # 实体ID到成本信封的映射
        self._lock = Lock()  # 线程锁，保证并发安全

    def ensure_envelope(
        self,
        entity_id: str,
        limit_usd: float | None = None,
    ) -> CostEnvelope:
        """确保实体存在成本信封，如果不存在则创建。
        
        Args:
            entity_id: 实体标识符（项目ID或会话ID）
            limit_usd: 预算上限，如果为 None 则使用默认值
            
        Returns:
            该实体的成本信封对象
        """
        with self._lock:
            if entity_id not in self._envelopes:
                self._envelopes[entity_id] = CostEnvelope(
                    limit_usd=limit_usd or settings.budget.default_project_limit_usd
                )
            return self._envelopes[entity_id]

    def record(self, entity_id: str, amount: float) -> CostEnvelope:
        """记录成本消耗并检查告警阈值。
        
        Args:
            entity_id: 实体标识符
            amount: 消耗的金额（美元）
            
        Returns:
            更新后的成本信封对象
            
        Note:
            当成本消耗达到配置的告警百分比阈值时，会触发成本告警事件。
        """
        envelope = self.ensure_envelope(entity_id)
        envelope.add_cost(amount)

        # 计算消耗百分比并检查告警阈值
        pct = (envelope.spent_usd / envelope.limit_usd) * 100 if envelope.limit_usd else 0
        for threshold in settings.budget.cost_alert_percentages:
            if pct >= threshold:
                emit_event(
                    TelemetryEvent(
                        name="cost_threshold",
                        attributes={"entity_id": entity_id, "threshold": threshold, "spent": envelope.spent_usd},
                    )
                )
                break
        return envelope


# 全局成本跟踪器实例
cost_tracker = CostTracker()


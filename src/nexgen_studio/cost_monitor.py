"""Cost monitoring and anomaly detection for budget management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from .config import settings
from .instrumentation import TelemetryEvent, emit_event, get_logger

logger = get_logger()


@dataclass
class CostSnapshot:
    """Represents a cost measurement at a point in time."""
    
    timestamp: datetime
    entity_id: str  # project_id or session_id
    entity_type: Literal["project", "session"]
    cumulative_cost: float
    phase: str | None = None


@dataclass
class CostAnomaly:
    """Detected cost anomaly."""
    
    entity_id: str
    entity_type: Literal["project", "session"]
    alert_type: Literal["rate_spike", "budget_exceeded", "projected_overrun"]
    current_rate: float
    expected_rate: float
    projected_total: float
    budget_limit: float
    timestamp: datetime
    message: str


class CostMonitor:
    """Monitors costs and detects anomalies."""
    
    def __init__(self):
        self.snapshots: dict[str, list[CostSnapshot]] = {}
        self.anomalies: list[CostAnomaly] = []
        self.paused_entities: set[str] = set()
        self.budget_limits: dict[str, float] = {}
    
    def record_snapshot(
        self,
        entity_id: str,
        entity_type: Literal["project", "session"],
        cumulative_cost: float,
        phase: str | None = None,
        budget_limit: float | None = None,
    ):
        """Record a cost snapshot."""
        snapshot = CostSnapshot(
            timestamp=datetime.now(timezone.utc),
            entity_id=entity_id,
            entity_type=entity_type,
            cumulative_cost=cumulative_cost,
            phase=phase
        )

        if budget_limit is not None:
            self.budget_limits[entity_id] = budget_limit
        
        if entity_id not in self.snapshots:
            self.snapshots[entity_id] = []
        
        self.snapshots[entity_id].append(snapshot)
        
        # Keep only recent snapshots (last 24 hours)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        self.snapshots[entity_id] = [
            s for s in self.snapshots[entity_id] if s.timestamp > cutoff
        ]
    
    def calculate_cost_rate(self, entity_id: str, window_minutes: int = 10) -> float:
        """Calculate cost per minute over recent window."""
        if entity_id not in self.snapshots or len(self.snapshots[entity_id]) < 2:
            return 0.0
        
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=window_minutes)
        
        recent = [s for s in self.snapshots[entity_id] if s.timestamp > cutoff]
        if len(recent) < 2:
            return 0.0
        
        # Calculate rate between oldest and newest in window
        oldest = recent[0]
        newest = recent[-1]
        
        time_delta = (newest.timestamp - oldest.timestamp).total_seconds() / 60.0
        cost_delta = newest.cumulative_cost - oldest.cumulative_cost
        
        if time_delta == 0:
            return 0.0
        
        return cost_delta / time_delta
    
    def calculate_historical_rate(self, entity_id: str, percentile: float = 0.95) -> float:
        """Calculate historical cost rate at given percentile."""
        if entity_id not in self.snapshots or len(self.snapshots[entity_id]) < 10:
            return 0.0
        
        # Calculate rates between consecutive snapshots
        snapshots = sorted(self.snapshots[entity_id], key=lambda s: s.timestamp)
        rates = []
        
        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1]
            curr = snapshots[i]
            
            time_delta = (curr.timestamp - prev.timestamp).total_seconds() / 60.0
            cost_delta = curr.cumulative_cost - prev.cumulative_cost
            
            if time_delta > 0:
                rates.append(cost_delta / time_delta)
        
        if not rates:
            return 0.0
        
        # Calculate percentile
        sorted_rates = sorted(rates)
        index = int(len(sorted_rates) * percentile)
        return sorted_rates[min(index, len(sorted_rates) - 1)]
    
    def project_final_cost(
        self,
        entity_id: str,
        completion_percentage: float
    ) -> float | None:
        """Project final cost based on current progress."""
        if entity_id not in self.snapshots or not self.snapshots[entity_id]:
            return None
        
        if completion_percentage <= 0:
            return None
        
        current_cost = self.snapshots[entity_id][-1].cumulative_cost
        projected = current_cost / completion_percentage
        
        return projected
    
    def check_for_anomalies(
        self,
        entity_id: str,
        entity_type: Literal["project", "session"],
        budget_limit: float | None = None,
        completion_percentage: float = 0.5,
        threshold_multiplier: float = 2.0
    ) -> list[CostAnomaly]:
        """
        Check for cost anomalies.
        
        Args:
            entity_id: Project or session ID
            entity_type: Type of entity
            budget_limit: Budget limit for the entity
            completion_percentage: Current completion progress (0-1)
            threshold_multiplier: Rate spike threshold (e.g., 2.0 = 200% of historical)
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        if entity_id not in self.snapshots or not self.snapshots[entity_id]:
            return anomalies
        
        if budget_limit is None:
            budget_limit = self.budget_limits.get(entity_id, settings.budget.default_project_limit_usd)
        
        current_cost = self.snapshots[entity_id][-1].cumulative_cost
        current_rate = self.calculate_cost_rate(entity_id, window_minutes=10)
        historical_rate = self.calculate_historical_rate(entity_id, percentile=0.95)
        
        # Check 1: Budget exceeded
        if current_cost >= budget_limit:
            anomaly = CostAnomaly(
                entity_id=entity_id,
                entity_type=entity_type,
                alert_type="budget_exceeded",
                current_rate=current_rate,
                expected_rate=historical_rate,
                projected_total=current_cost,
                budget_limit=budget_limit,
                timestamp=datetime.now(timezone.utc),
                message=f"Budget exceeded: ${current_cost:.2f} >= ${budget_limit:.2f}"
            )
            anomalies.append(anomaly)
            logger.warning(anomaly.message)
        
        # Check 2: Rate spike
        if historical_rate > 0 and current_rate > historical_rate * threshold_multiplier:
            projected = self.project_final_cost(entity_id, completion_percentage)
            anomaly = CostAnomaly(
                entity_id=entity_id,
                entity_type=entity_type,
                alert_type="rate_spike",
                current_rate=current_rate,
                expected_rate=historical_rate,
                projected_total=projected or current_cost,
                budget_limit=budget_limit,
                timestamp=datetime.now(timezone.utc),
                message=(
                    f"Cost rate spike detected: ${current_rate:.4f}/min "
                    f"(expected: ${historical_rate:.4f}/min, "
                    f"threshold: {threshold_multiplier}x)"
                )
            )
            anomalies.append(anomaly)
            logger.warning(anomaly.message)
        
        # Check 3: Projected overrun
        if completion_percentage > 0:
            projected = self.project_final_cost(entity_id, completion_percentage)
            if projected and projected > budget_limit * 1.1:  # 10% buffer
                anomaly = CostAnomaly(
                    entity_id=entity_id,
                    entity_type=entity_type,
                    alert_type="projected_overrun",
                    current_rate=current_rate,
                    expected_rate=historical_rate,
                    projected_total=projected,
                    budget_limit=budget_limit,
                    timestamp=datetime.now(timezone.utc),
                    message=(
                        f"Projected cost overrun: ${projected:.2f} > ${budget_limit:.2f} "
                        f"(current: ${current_cost:.2f} at {completion_percentage*100:.1f}% complete)"
                    )
                )
                anomalies.append(anomaly)
                logger.warning(anomaly.message)
        
        # Store anomalies
        self.anomalies.extend(anomalies)
        
        # Emit telemetry events
        for anomaly in anomalies:
            emit_event(
                TelemetryEvent(
                    name="cost_anomaly_detected",
                    attributes={
                        "entity_id": anomaly.entity_id,
                        "entity_type": anomaly.entity_type,
                        "alert_type": anomaly.alert_type,
                        "current_rate": anomaly.current_rate,
                        "expected_rate": anomaly.expected_rate,
                        "projected_total": anomaly.projected_total,
                        "budget_limit": anomaly.budget_limit,
                    }
                )
            )
        
        return anomalies
    
    def should_pause_entity(
        self,
        entity_id: str,
        entity_type: Literal["project", "session"],
        budget_limit: float | None = None,
        auto_pause_enabled: bool = True
    ) -> tuple[bool, str | None]:
        """
        Determine if an entity should be paused due to cost issues.
        
        Returns:
            (should_pause, reason)
        """
        if not auto_pause_enabled:
            return False, None
        
        if entity_id in self.paused_entities:
            return False, None  # Already paused
        
        if entity_id not in self.snapshots or not self.snapshots[entity_id]:
            return False, None
        
        if budget_limit is None:
            budget_limit = self.budget_limits.get(entity_id, settings.budget.default_project_limit_usd)
        
        current_cost = self.snapshots[entity_id][-1].cumulative_cost
        
        # Pause if budget exceeded
        if current_cost >= budget_limit:
            self.paused_entities.add(entity_id)
            return True, "paused_budget"
        
        # Check for recent anomalies
        recent_anomalies = [
            a for a in self.anomalies
            if a.entity_id == entity_id and 
            (datetime.now(timezone.utc) - a.timestamp).total_seconds() < 300  # 5 minutes
        ]
        
        # Pause if multiple anomalies detected
        if len(recent_anomalies) >= 2:
            self.paused_entities.add(entity_id)
            return True, "paused_anomaly"
        
        return False, None
    
    def resume_entity(self, entity_id: str):
        """Mark entity as resumed."""
        self.paused_entities.discard(entity_id)
    
    def get_cost_summary(self, entity_id: str) -> dict:
        """Get cost summary for an entity."""
        if entity_id not in self.snapshots or not self.snapshots[entity_id]:
            return {
                "current_cost": 0.0,
                "current_rate": 0.0,
                "historical_rate": 0.0,
                "snapshot_count": 0,
                "anomaly_count": 0,
                "entity_type": None,
                "budget_limit": self.budget_limits.get(entity_id),
            }
        
        current_cost = self.snapshots[entity_id][-1].cumulative_cost
        current_rate = self.calculate_cost_rate(entity_id)
        historical_rate = self.calculate_historical_rate(entity_id)
        anomaly_count = len([a for a in self.anomalies if a.entity_id == entity_id])
        entity_type = self.snapshots[entity_id][-1].entity_type
        budget_limit = self.budget_limits.get(entity_id)
        
        return {
            "current_cost": current_cost,
            "current_rate": current_rate,
            "historical_rate": historical_rate,
            "snapshot_count": len(self.snapshots[entity_id]),
            "anomaly_count": anomaly_count,
            "is_paused": entity_id in self.paused_entities,
            "entity_type": entity_type,
            "budget_limit": budget_limit,
        }
    
    def cleanup_old_data(self, days: int = 7):
        """Remove old snapshots and anomalies."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Clean snapshots
        for entity_id in list(self.snapshots.keys()):
            self.snapshots[entity_id] = [
                s for s in self.snapshots[entity_id] if s.timestamp > cutoff
            ]
            if not self.snapshots[entity_id]:
                del self.snapshots[entity_id]
        
        # Clean anomalies
        self.anomalies = [a for a in self.anomalies if a.timestamp > cutoff]
        
        logger.info(f"Cleaned up cost data older than {days} days")

    def reset(self) -> None:
        """Reset monitor state (useful for tests)."""
        self.snapshots.clear()
        self.anomalies.clear()
        self.paused_entities.clear()
        self.budget_limits.clear()


# Global instance
cost_monitor = CostMonitor()

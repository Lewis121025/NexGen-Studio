"""监控和分析服务 - 一致性控制的监控和分析工具。"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import settings
from ..instrumentation import get_logger
from .repository import creative_repository

logger = get_logger()


class MonitoringAnalyticsService:
    """监控和分析服务，提供一致性控制的监控和分析功能。"""

    def __init__(self) -> None:
        """初始化监控和分析服务。"""
        self.metrics_cache = {}
        self.cache_ttl = 300  # 缓存5分钟

    async def get_consistency_stats(self, tenant_id: str = "demo") -> dict[str, Any]:
        """获取一致性统计数据。

        Args:
            tenant_id: 租户ID

        Returns:
            一致性统计数据
        """
        cache_key = f"consistency_stats_{tenant_id}"
        if self._is_cache_valid(cache_key):
            return self.metrics_cache[cache_key]

        try:
            projects = await creative_repository.list_for_tenant(tenant_id)

            stats = {
                "total_projects": len(projects),
                "projects_with_consistency_score": 0,
                "average_consistency_score": 0.0,
                "consistency_level_distribution": {
                    "low": 0,
                    "medium": 0,
                    "high": 0
                },
                "score_ranges": {
                    "excellent": 0,  # 0.9-1.0
                    "good": 0,       # 0.7-0.9
                    "fair": 0,       # 0.5-0.7
                    "poor": 0        # 0.0-0.5
                },
                "retry_stats": {
                    "total_retries": 0,
                    "successful_retries": 0,
                    "average_retry_improvement": 0.0
                }
            }

            total_score = 0.0
            scored_projects = 0
            retry_improvements = []

            for project in projects:
                # 一致性级别分布
                level = getattr(project, 'consistency_level', 'medium')
                stats["consistency_level_distribution"][level] += 1

                # 一致性分数统计
                score = getattr(project, 'overall_consistency_score', None)
                if score is not None:
                    scored_projects += 1
                    total_score += score

                    # 分数范围统计
                    if score >= 0.9:
                        stats["score_ranges"]["excellent"] += 1
                    elif score >= 0.7:
                        stats["score_ranges"]["good"] += 1
                    elif score >= 0.5:
                        stats["score_ranges"]["fair"] += 1
                    else:
                        stats["score_ranges"]["poor"] += 1

                # 重试统计（从分镜数据中提取）
                for panel in project.storyboard:
                    retry_count = getattr(panel, 'retry_count', 0)
                    stats["retry_stats"]["total_retries"] += retry_count

                    # 如果有重试且分数改善，算作成功重试
                    if retry_count > 0 and getattr(panel, 'consistency_score', 0) > 0.7:
                        stats["retry_stats"]["successful_retries"] += 1

            stats["projects_with_consistency_score"] = scored_projects
            if scored_projects > 0:
                stats["average_consistency_score"] = total_score / scored_projects

            # 计算平均重试改善
            if stats["retry_stats"]["successful_retries"] > 0:
                # 简化计算：假设每次成功重试改善0.1分
                stats["retry_stats"]["average_retry_improvement"] = 0.1

            self.metrics_cache[cache_key] = stats
            return stats

        except Exception as exc:
            logger.error(f"Error getting consistency stats for tenant {tenant_id}: {exc}")
            return {
                "total_projects": 0,
                "error": str(exc)
            }

    async def get_consistency_trends(
        self,
        tenant_id: str = "demo",
        days: int = 30
    ) -> dict[str, Any]:
        """获取一致性趋势数据。

        Args:
            tenant_id: 租户ID
            days: 分析天数

        Returns:
            一致性趋势数据
        """
        cache_key = f"consistency_trends_{tenant_id}_{days}"
        if self._is_cache_valid(cache_key):
            return self.metrics_cache[cache_key]

        try:
            projects = await creative_repository.list_for_tenant(tenant_id)

            # 按日期分组统计
            daily_stats = defaultdict(lambda: {
                "count": 0,
                "total_score": 0.0,
                "scored_projects": 0,
                "retry_count": 0,
                "improved_projects": 0
            })

            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            for project in projects:
                if project.created_at < cutoff_date:
                    continue

                created_date = project.created_at.date().isoformat()
                daily_stats[created_date]["count"] += 1

                score = getattr(project, 'overall_consistency_score', None)
                if score is not None:
                    daily_stats[created_date]["total_score"] += score
                    daily_stats[created_date]["scored_projects"] += 1

                # 统计重试情况
                for panel in project.storyboard:
                    retry_count = getattr(panel, 'retry_count', 0)
                    daily_stats[created_date]["retry_count"] += retry_count

                    if retry_count > 0 and getattr(panel, 'consistency_score', 0) > 0.7:
                        daily_stats[created_date]["improved_projects"] += 1

            # 计算每日平均分
            trends = []
            for date, stats in sorted(daily_stats.items()):
                avg_score = None
                if stats["scored_projects"] > 0:
                    avg_score = stats["total_score"] / stats["scored_projects"]

                trends.append({
                    "date": date,
                    "total_projects": stats["count"],
                    "scored_projects": stats["scored_projects"],
                    "average_consistency_score": avg_score,
                    "total_retries": stats["retry_count"],
                    "improved_projects": stats["improved_projects"]
                })

            result = {
                "trends": trends,
                "period_days": days,
                "total_data_points": len(trends),
                "summary": self._calculate_trend_summary(trends)
            }

            self.metrics_cache[cache_key] = result
            return result

        except Exception as exc:
            logger.error(f"Error getting consistency trends for tenant {tenant_id}: {exc}")
            return {
                "trends": [],
                "error": str(exc)
            }

    async def get_performance_metrics(self, tenant_id: str = "demo") -> dict[str, Any]:
        """获取性能指标。

        Args:
            tenant_id: 租户ID

        Returns:
            性能指标数据
        """
        cache_key = f"performance_metrics_{tenant_id}"
        if self._is_cache_valid(cache_key):
            return self.metrics_cache[cache_key]

        try:
            projects = await creative_repository.list_for_tenant(tenant_id)

            metrics = {
                "total_projects": len(projects),
                "completion_rate": 0.0,
                "average_processing_time": 0.0,
                "cost_efficiency": 0.0,
                "quality_distribution": {},
                "bottlenecks": []
            }

            completed_projects = 0
            total_cost = 0.0
            total_time = 0.0

            for project in projects:
                if project.state == "completed":
                    completed_projects += 1

                # 计算处理时间（简化）
                if project.created_at and project.updated_at:
                    processing_time = (project.updated_at - project.created_at).total_seconds()
                    total_time += processing_time

                # 累加成本
                total_cost += getattr(project, 'cost_usd', 0)

            # 计算完成率
            if projects:
                metrics["completion_rate"] = completed_projects / len(projects)

            # 计算平均处理时间
            if completed_projects > 0:
                metrics["average_processing_time"] = total_time / completed_projects

            # 计算成本效率（每美元的完成率）
            if total_cost > 0:
                metrics["cost_efficiency"] = completed_projects / total_cost

            # 质量分布
            quality_ranges = {
                "high_quality": 0,
                "medium_quality": 0,
                "low_quality": 0
            }

            for project in projects:
                score = getattr(project, 'overall_consistency_score', 0)
                if score >= 0.8:
                    quality_ranges["high_quality"] += 1
                elif score >= 0.6:
                    quality_ranges["medium_quality"] += 1
                else:
                    quality_ranges["low_quality"] += 1

            metrics["quality_distribution"] = quality_ranges

            # 识别瓶颈
            metrics["bottlenecks"] = self._identify_bottlenecks(projects)

            self.metrics_cache[cache_key] = metrics
            return metrics

        except Exception as exc:
            logger.error(f"Error getting performance metrics for tenant {tenant_id}: {exc}")
            return {
                "total_projects": 0,
                "error": str(exc)
            }

    async def get_recommendations(self, tenant_id: str = "demo") -> dict[str, Any]:
        """获取智能推荐。

        Args:
            tenant_id: 租户ID

        Returns:
            智能推荐数据
        """
        try:
            # 获取统计数据
            stats = await self.get_consistency_stats(tenant_id)
            trends = await self.get_consistency_trends(tenant_id, days=7)
            metrics = await self.get_performance_metrics(tenant_id)

            recommendations = []

            # 基于一致性分数的推荐
            avg_score = stats.get("average_consistency_score", 0)
            if avg_score < 0.7:
                recommendations.append({
                    "type": "consistency_improvement",
                    "priority": "high",
                    "title": "提升一致性质量",
                    "description": f"当前平均一致性分数为{avg_score:.2f}，建议启用高级一致性控制",
                    "actions": [
                        "将一致性级别从'medium'调整为'high'",
                        "启用自动重试机制",
                        "增加角色和场景参考描述"
                    ]
                })

            # 基于重试统计的推荐
            retry_rate = stats.get("retry_stats", {}).get("successful_retries", 0)
            if retry_rate > 10:  # 如果重试次数过多
                recommendations.append({
                    "type": "optimization",
                    "priority": "medium",
                    "title": "优化重试策略",
                    "description": "重试次数较多，建议优化初始生成质量",
                    "actions": [
                        "改进提示词质量",
                        "调整AI模型参数",
                        "增加特征提取准确性"
                    ]
                })

            # 基于趋势的推荐
            recent_trends = trends.get("trends", [])[-7:]  # 最近7天
            if recent_trends:
                recent_avg = sum(t.get("average_consistency_score", 0) or 0 for t in recent_trends) / len(recent_trends)
                if recent_avg < avg_score * 0.9:  # 如果最近质量下降
                    recommendations.append({
                        "type": "monitoring",
                        "priority": "medium",
                        "title": "质量趋势监控",
                        "description": "最近一致性质量有所下降，需要关注",
                        "actions": [
                            "检查AI模型性能",
                            "审核最近的项目配置",
                            "分析失败案例"
                        ]
                    })

            # 基于性能的推荐
            completion_rate = metrics.get("completion_rate", 0)
            if completion_rate < 0.8:
                recommendations.append({
                    "type": "performance",
                    "priority": "high",
                    "title": "提升完成率",
                    "description": f"项目完成率为{completion_rate:.1%}，需要改进",
                    "actions": [
                        "优化工作流自动化",
                        "减少人工干预步骤",
                        "改进错误处理机制"
                    ]
                })

            return {
                "recommendations": recommendations,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "based_on": {
                    "stats": stats,
                    "trends": trends,
                    "metrics": metrics
                }
            }

        except Exception as exc:
            logger.error(f"Error generating recommendations for tenant {tenant_id}: {exc}")
            return {
                "recommendations": [],
                "error": str(exc)
            }

    async def export_metrics_report(
        self,
        tenant_id: str = "demo",
        format: str = "json"
    ) -> dict[str, Any]:
        """导出指标报告。

        Args:
            tenant_id: 租户ID
            format: 导出格式

        Returns:
            导出的报告数据
        """
        try:
            # 收集所有指标
            stats = await self.get_consistency_stats(tenant_id)
            trends = await self.get_consistency_trends(tenant_id)
            metrics = await self.get_performance_metrics(tenant_id)
            recommendations = await self.get_recommendations(tenant_id)

            report = {
                "tenant_id": tenant_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "report_period": "30_days",
                "summary": {
                    "total_projects": stats.get("total_projects", 0),
                    "average_consistency_score": stats.get("average_consistency_score", 0),
                    "completion_rate": metrics.get("completion_rate", 0),
                    "total_retries": stats.get("retry_stats", {}).get("total_retries", 0)
                },
                "detailed_stats": stats,
                "trends": trends,
                "performance_metrics": metrics,
                "recommendations": recommendations
            }

            if format == "json":
                return report
            else:
                # 可以扩展支持其他格式
                return report

        except Exception as exc:
            logger.error(f"Error exporting metrics report for tenant {tenant_id}: {exc}")
            return {
                "error": str(exc),
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效。"""
        if cache_key not in self.metrics_cache:
            return False

        cached_data = self.metrics_cache[cache_key]
        if not isinstance(cached_data, dict) or "cached_at" not in cached_data:
            return False

        cached_time = datetime.fromisoformat(cached_data["cached_at"])
        return (datetime.now(timezone.utc) - cached_time).seconds < self.cache_ttl

    def _calculate_trend_summary(self, trends: list[dict[str, Any]]) -> dict[str, Any]:
        """计算趋势摘要。"""
        if not trends:
            return {"trend": "insufficient_data"}

        scores = [t.get("average_consistency_score") or 0 for t in trends]
        if len(scores) < 2:
            return {"trend": "stable", "average_score": sum(scores) / len(scores)}

        # 计算趋势
        first_half = scores[:len(scores)//2]
        second_half = scores[len(scores)//2:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        improvement = second_avg - first_avg

        if improvement > 0.05:
            trend = "improving"
        elif improvement < -0.05:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "improvement": improvement,
            "first_half_average": first_avg,
            "second_half_average": second_avg,
            "overall_average": sum(scores) / len(scores)
        }

    def _identify_bottlenecks(self, projects: list) -> list[str]:
        """识别性能瓶颈。"""
        bottlenecks = []

        # 检查是否有长时间运行的项目
        long_running = []
        for project in projects:
            if project.created_at and project.updated_at:
                duration = (project.updated_at - project.created_at).total_seconds()
                if duration > 3600:  # 超过1小时
                    long_running.append(project.id)

        if long_running:
            bottlenecks.append(f"发现{len(long_running)}个长时间运行的项目")

        # 检查失败率
        failed_projects = [p for p in projects if p.state == "failed"]
        if len(failed_projects) > len(projects) * 0.1:  # 失败率超过10%
            bottlenecks.append(f"失败率较高: {len(failed_projects)}/{len(projects)}")

        # 检查一致性分数低的趋势
        low_quality = [p for p in projects if getattr(p, 'overall_consistency_score', 1) < 0.6]
        if len(low_quality) > len(projects) * 0.2:  # 低质量项目超过20%
            bottlenecks.append(f"质量问题突出: {len(low_quality)}个项目一致性分数偏低")

        return bottlenecks


# 全局监控和分析服务实例
monitoring_service = MonitoringAnalyticsService()
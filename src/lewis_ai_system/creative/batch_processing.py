"""批量处理服务 - 支持一致性控制的批量操作。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..config import settings
from ..instrumentation import get_logger
from .consistency_manager import consistency_manager
from .repository import creative_repository

logger = get_logger()


class BatchProcessingService:
    """批量处理服务，支持一致性控制的批量操作。"""

    def __init__(self) -> None:
        """初始化批量处理服务。"""
        self.max_concurrent_tasks = 5  # 最大并发任务数
        self.batch_timeout = 300  # 批量操作超时时间（秒）

    async def batch_evaluate_consistency(
        self,
        project_ids: list[str],
        concurrency: int | None = None
    ) -> dict[str, Any]:
        """批量评估多个项目的一致性。

        Args:
            project_ids: 项目ID列表
            concurrency: 并发数，默认使用配置值

        Returns:
            批量评估结果
        """
        logger.info(f"开始批量评估 {len(project_ids)} 个项目的一致性")

        max_concurrent = concurrency or self.max_concurrent_tasks
        semaphore = asyncio.Semaphore(max_concurrent)

        async def evaluate_single_project(project_id: str) -> dict[str, Any]:
            async with semaphore:
                try:
                    project = await creative_repository.get(project_id)

                    # 收集分镜图片
                    panel_images = [
                        p.visual_reference_path
                        for p in project.storyboard
                        if p.visual_reference_path
                    ]

                    if len(panel_images) < 2:
                        return {
                            "project_id": project_id,
                            "status": "skipped",
                            "reason": "分镜图片不足，至少需要2张图片"
                        }

                    # 评估一致性
                    consistency_result = await consistency_manager.evaluate_consistency(panel_images)

                    # 更新项目一致性分数
                    project.overall_consistency_score = consistency_result["overall_score"]
                    await creative_repository.upsert(project)

                    return {
                        "project_id": project_id,
                        "status": "success",
                        "consistency_score": consistency_result["overall_score"],
                        "character_consistency": consistency_result.get("character_consistency", 0),
                        "scene_consistency": consistency_result.get("scene_consistency", 0),
                        "style_consistency": consistency_result.get("style_consistency", 0),
                        "recommendations": consistency_result.get("recommendations", [])
                    }

                except Exception as e:
                    logger.error(f"评估项目 {project_id} 失败: {e}")
                    return {
                        "project_id": project_id,
                        "status": "error",
                        "error": str(e)
                    }

        # 执行批量评估
        tasks = [evaluate_single_project(pid) for pid in project_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        processed_results = {}
        successful_evaluations = 0
        total_processed = 0

        for i, result in enumerate(results):
            project_id = project_ids[i]
            if isinstance(result, Exception):
                processed_results[project_id] = {
                    "status": "error",
                    "error": f"任务执行异常: {str(result)}"
                }
            else:
                processed_results[project_id] = result
                total_processed += 1
                if result["status"] == "success":
                    successful_evaluations += 1

        batch_result = {
            "total_projects": len(project_ids),
            "total_processed": total_processed,
            "successful_evaluations": successful_evaluations,
            "results": processed_results,
            "batch_stats": self._calculate_batch_stats(processed_results)
        }

        logger.info(f"批量评估完成: {successful_evaluations}/{total_processed} 成功")
        return batch_result

    async def batch_auto_retry_consistency(
        self,
        project_ids: list[str],
        max_retries: int = 2,
        concurrency: int | None = None
    ) -> dict[str, Any]:
        """批量自动重试多个项目的一致性。

        Args:
            project_ids: 项目ID列表
            max_retries: 最大重试次数
            concurrency: 并发数

        Returns:
            批量重试结果
        """
        logger.info(f"开始批量重试 {len(project_ids)} 个项目的一致性")

        max_concurrent = concurrency or self.max_concurrent_tasks
        semaphore = asyncio.Semaphore(max_concurrent)

        async def retry_single_project(project_id: str) -> dict[str, Any]:
            async with semaphore:
                try:
                    project = await creative_repository.get(project_id)

                    # 执行验证和重试
                    validation_result = await consistency_manager.validate_and_retry_project(
                        project, max_retries=max_retries
                    )

                    # 保存更新
                    await creative_repository.upsert(project)

                    return {
                        "project_id": project_id,
                        "status": "success",
                        "validation_result": validation_result,
                        "improvement": validation_result.get("overall_improvement", 0),
                        "final_score": project.overall_consistency_score
                    }

                except Exception as e:
                    logger.error(f"重试项目 {project_id} 失败: {e}")
                    return {
                        "project_id": project_id,
                        "status": "error",
                        "error": str(e)
                    }

        # 执行批量重试
        tasks = [retry_single_project(pid) for pid in project_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        processed_results = {}
        projects_improved = 0
        total_processed = 0

        for i, result in enumerate(results):
            project_id = project_ids[i]
            if isinstance(result, Exception):
                processed_results[project_id] = {
                    "status": "error",
                    "error": f"任务执行异常: {str(result)}"
                }
            else:
                processed_results[project_id] = result
                total_processed += 1
                if result.get("improvement", 0) > 0:
                    projects_improved += 1

        batch_result = {
            "total_projects": len(project_ids),
            "total_processed": total_processed,
            "projects_improved": projects_improved,
            "results": processed_results,
            "batch_stats": self._calculate_retry_batch_stats(processed_results)
        }

        logger.info(f"批量重试完成: {projects_improved}/{total_processed} 项目得到改善")
        return batch_result

    async def batch_regenerate_consistency(
        self,
        project_ids: list[str],
        consistency_level: str = "medium",
        concurrency: int | None = None
    ) -> dict[str, Any]:
        """批量重新生成项目，使用指定的高级一致性级别。

        Args:
            project_ids: 项目ID列表
            consistency_level: 一致性级别
            concurrency: 并发数

        Returns:
            批量重新生成结果
        """
        logger.info(f"开始批量重新生成 {len(project_ids)} 个项目，使用一致性级别: {consistency_level}")

        max_concurrent = concurrency or self.max_concurrent_tasks
        semaphore = asyncio.Semaphore(max_concurrent)

        async def regenerate_single_project(project_id: str) -> dict[str, Any]:
            async with semaphore:
                try:
                    from .workflow import creative_orchestrator

                    project = await creative_repository.get(project_id)

                    # 更新一致性级别
                    project.consistency_level = consistency_level

                    # 重新生成一致性种子
                    project.consistency_seed = consistency_manager.generate_consistency_seed(project_id)

                    # 清除旧的参考图片和特征
                    project.reference_images = []
                    for panel in project.storyboard:
                        panel.consistency_score = None
                        panel.character_features = None

                    project.overall_consistency_score = None

                    # 重新开始工作流
                    project.mark_state("storyboard_pending")

                    await creative_repository.upsert(project)

                    # 触发重新生成
                    updated_project = await creative_orchestrator.advance(project_id)

                    return {
                        "project_id": project_id,
                        "status": "success",
                        "new_consistency_level": consistency_level,
                        "new_seed": project.consistency_seed,
                        "new_state": updated_project.state
                    }

                except Exception as e:
                    logger.error(f"重新生成项目 {project_id} 失败: {e}")
                    return {
                        "project_id": project_id,
                        "status": "error",
                        "error": str(e)
                    }

        # 执行批量重新生成
        tasks = [regenerate_single_project(pid) for pid in project_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        processed_results = {}
        successful_regenerations = 0
        total_processed = 0

        for i, result in enumerate(results):
            project_id = project_ids[i]
            if isinstance(result, Exception):
                processed_results[project_id] = {
                    "status": "error",
                    "error": f"任务执行异常: {str(result)}"
                }
            else:
                processed_results[project_id] = result
                total_processed += 1
                if result["status"] == "success":
                    successful_regenerations += 1

        batch_result = {
            "total_projects": len(project_ids),
            "total_processed": total_processed,
            "successful_regenerations": successful_regenerations,
            "consistency_level": consistency_level,
            "results": processed_results
        }

        logger.info(f"批量重新生成完成: {successful_regenerations}/{total_processed} 成功")
        return batch_result

    async def batch_update_consistency_config(
        self,
        project_ids: list[str],
        config_updates: dict[str, Any],
        concurrency: int | None = None
    ) -> dict[str, Any]:
        """批量更新多个项目的一致性配置。

        Args:
            project_ids: 项目ID列表
            config_updates: 配置更新字典
            concurrency: 并发数

        Returns:
            批量更新结果
        """
        logger.info(f"开始批量更新 {len(project_ids)} 个项目的一致性配置")

        max_concurrent = concurrency or self.max_concurrent_tasks
        semaphore = asyncio.Semaphore(max_concurrent)

        async def update_single_project(project_id: str) -> dict[str, Any]:
            async with semaphore:
                try:
                    project = await creative_repository.get(project_id)

                    # 应用配置更新
                    for key, value in config_updates.items():
                        if hasattr(project, key):
                            setattr(project, key, value)

                    # 如果更新了参考信息，重新生成种子
                    if any(key in config_updates for key in ["character_reference", "scene_reference"]):
                        project.consistency_seed = consistency_manager.generate_consistency_seed(project_id)

                    await creative_repository.upsert(project)

                    return {
                        "project_id": project_id,
                        "status": "success",
                        "config_updates": config_updates
                    }

                except Exception as e:
                    logger.error(f"更新项目 {project_id} 配置失败: {e}")
                    return {
                        "project_id": project_id,
                        "status": "error",
                        "error": str(e)
                    }

        # 执行批量更新
        tasks = [update_single_project(pid) for pid in project_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        processed_results = {}
        successful_updates = 0
        total_processed = 0

        for i, result in enumerate(results):
            project_id = project_ids[i]
            if isinstance(result, Exception):
                processed_results[project_id] = {
                    "status": "error",
                    "error": f"任务执行异常: {str(result)}"
                }
            else:
                processed_results[project_id] = result
                total_processed += 1
                if result["status"] == "success":
                    successful_updates += 1

        batch_result = {
            "total_projects": len(project_ids),
            "total_processed": total_processed,
            "successful_updates": successful_updates,
            "config_updates": config_updates,
            "results": processed_results
        }

        logger.info(f"批量配置更新完成: {successful_updates}/{total_processed} 成功")
        return batch_result

    def _calculate_batch_stats(self, results: dict[str, Any]) -> dict[str, Any]:
        """计算批量评估统计信息。"""
        successful_results = [
            r for r in results.values()
            if r.get("status") == "success"
        ]

        if not successful_results:
            return {"average_score": 0, "score_distribution": {}}

        scores = [r["consistency_score"] for r in successful_results]

        # 分数分布
        distribution = {
            "excellent": len([s for s in scores if s >= 0.9]),
            "good": len([s for s in scores if 0.7 <= s < 0.9]),
            "fair": len([s for s in scores if 0.5 <= s < 0.7]),
            "poor": len([s for s in scores if s < 0.5])
        }

        return {
            "average_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "score_distribution": distribution
        }

    def _calculate_retry_batch_stats(self, results: dict[str, Any]) -> dict[str, Any]:
        """计算批量重试统计信息。"""
        successful_results = [
            r for r in results.values()
            if r.get("status") == "success"
        ]

        if not successful_results:
            return {"average_improvement": 0, "improvement_distribution": {}}

        improvements = [r.get("improvement", 0) for r in successful_results]

        # 改善分布
        distribution = {
            "significant": len([i for i in improvements if i >= 0.2]),
            "moderate": len([i for i in improvements if 0.1 <= i < 0.2]),
            "slight": len([i for i in improvements if 0 < i < 0.1]),
            "no_change": len([i for i in improvements if i == 0]),
            "worse": len([i for i in improvements if i < 0])
        }

        return {
            "average_improvement": sum(improvements) / len(improvements),
            "max_improvement": max(improvements),
            "min_improvement": min(improvements),
            "improvement_distribution": distribution
        }


# 全局批量处理服务实例
batch_processing_service = BatchProcessingService()
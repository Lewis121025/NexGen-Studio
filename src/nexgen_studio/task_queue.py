"""
异步任务队列封装 - 使用 ARQ (Async Redis Queue)
处理视频生成等耗时任务，避免阻塞 API 进程。
"""

from __future__ import annotations

from typing import Any

from arq import create_pool
from arq.connections import RedisSettings, ArqRedis

from .config import settings
from .instrumentation import get_logger

logger = get_logger()


# ==================== Worker 配置 ====================
class WorkerSettings:
    """ARQ Worker 配置"""

    redis_settings = RedisSettings(
        host=settings.redis_url.split("://")[-1].split(":")[0] if settings.redis_url else "localhost",
        port=int(settings.redis_url.split(":")[-1].split("/")[0]) if settings.redis_url and ":" in settings.redis_url else 6379,
    )

    # 注册的任务函数
    functions = []

    # Worker 参数
    max_jobs = 10
    job_timeout = 3600  # 1h
    keep_result = 3600  # 1h


# ==================== 任务状态枚举 ====================
class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ==================== 任务队列客户端 ====================
class TaskQueue:
    """提供提交/查询任务的客户端接口"""

    def __init__(self):
        self.pool: ArqRedis | None = None

    async def connect(self):
        if not self.pool:
            self.pool = await create_pool(WorkerSettings.redis_settings)
            logger.info("Task queue connected to Redis")

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Task queue disconnected")

    async def enqueue_video_generation(
        self,
        project_id: str,
        script: str,
        storyboard: list[dict[str, Any]],
        **kwargs,
    ) -> str:
        """提交 Creative 项目视频生成任务"""
        if not self.pool:
            await self.connect()

        job = await self.pool.enqueue_job(
            "generate_video_task",
            project_id,
            script,
            storyboard,
            **kwargs,
        )

        logger.info(f"Enqueued video generation task: {job.job_id} for project {project_id}")
        return job.job_id

    async def enqueue_generic_video(self, payload: dict[str, Any]) -> str:
        """提交通用视频生成任务（工具调用）"""
        if not self.pool:
            await self.connect()
        job = await self.pool.enqueue_job("generate_video_task", None, None, None, payload)
        return job.job_id

    async def get_task_status(self, task_id: str) -> dict[str, Any]:
        if not self.pool:
            await self.connect()

        job = await self.pool.get_job(task_id)

        if not job:
            return {"status": TaskStatus.CANCELLED, "progress": 0.0, "error": "Task not found"}

        job_result = await job.result()
        job_info = await job.info()

        status = TaskStatus.PENDING
        if job_info.job_try and job_info.job_try > 0:
            status = TaskStatus.RUNNING
        if job_result is not None:
            status = TaskStatus.COMPLETED
        if job_info.job_try and job_info.job_try >= 3:
            status = TaskStatus.FAILED

        return {
            "status": status,
            "progress": job_info.job_try / 3 if job_info.job_try else 0.0,
            "result": job_result,
            "error": None,
        }


# ==================== Worker 任务函数 ====================
async def generate_video_task(
    ctx: dict[str, Any],
    project_id: str | None = None,
    script: str | None = None,
    storyboard: list[dict[str, Any]] | None = None,
    payload: dict[str, Any] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """
    视频生成任务 (Worker 进程执行)
    支持两种入口：
      1) 传入 project_id/script/storyboard （Creative workflow）
      2) 传入 payload (prompt/duration/aspect_ratio/quality)（工具调用）
    """
    logger.info(f"Starting video generation task (project={project_id})")

    try:
        from .providers import get_video_provider
        from .creative.repository import creative_repository

        video_provider = get_video_provider(settings.video_provider_default)

        if project_id:
            project = await creative_repository.get(project_id)
            result = await video_provider.generate_video(
                prompt=script or project.script or "",
                duration_seconds=project.duration_seconds,
                aspect_ratio=getattr(project, "aspect_ratio", "16:9"),
                quality="preview",
            )

            project.video_url = result.get("video_url")
            project.cost_usd += float(result.get("cost_usd", 0.0))
            project.state = "rendering_complete"
            await creative_repository.upsert(project)

            logger.info(f"Video generation completed for project {project_id}: {result.get('video_url')}")
            return {
                "video_url": result.get("video_url"),
                "cost_usd": result.get("cost_usd", 0.0),
                "duration": result.get("duration"),
            }

        if payload:
            result = await video_provider.generate_video(
                prompt=payload.get("prompt", ""),
                duration_seconds=payload.get("duration_seconds", 5),
                aspect_ratio=payload.get("aspect_ratio", "16:9"),
                quality=payload.get("quality", "preview"),
            )
            return result

        raise ValueError("generate_video_task requires project_id or payload")

    except Exception as e:
        logger.error(f"Video generation failed (project={project_id}): {e}", exc_info=True)
        if project_id:
            try:
                project = await creative_repository.get(project_id)
                project.error_message = str(e)  # type: ignore[attr-defined]
                await creative_repository.upsert(project)
            except Exception:
                pass
        raise


WorkerSettings.functions = [generate_video_task]


# ==================== 全局队列实例 ====================
task_queue = TaskQueue()


# ==================== FastAPI 生命周期钩子 ====================
async def init_task_queue():
    if settings.redis_enabled and settings.redis_url:
        await task_queue.connect()
        logger.info("Task queue initialized")
    else:
        logger.warning("Task queue disabled (REDIS_ENABLED=false or REDIS_URL not set)")


async def shutdown_task_queue():
    await task_queue.disconnect()
    logger.info("Task queue shut down")

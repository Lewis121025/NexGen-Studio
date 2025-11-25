"""FastAPI router for Creative Mode."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..creative.models import CreativeProjectCreateRequest, CreativeProjectResponse, CreativeProjectListResponse
from ..creative.repository import creative_repository
from ..creative.workflow import creative_orchestrator

router = APIRouter(prefix="/creative", tags=["creative"])


@router.post("/projects", response_model=CreativeProjectResponse, status_code=201)
async def create_project(payload: CreativeProjectCreateRequest) -> CreativeProjectResponse:
    try:
        project = await creative_orchestrator.create_project(payload)
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error creating project: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(exc)}") from exc
    return CreativeProjectResponse(project=project)


@router.post("/projects/{project_id}/approve-script", response_model=CreativeProjectResponse)
async def approve_script(project_id: str) -> CreativeProjectResponse:
    try:
        project = await creative_orchestrator.approve_script(project_id)
    except KeyError as exc:  # pragma: no cover - FastAPI handles
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error approving script for project {project_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to approve script: {str(exc)}") from exc
    return CreativeProjectResponse(project=project)


@router.post("/projects/{project_id}/advance", response_model=CreativeProjectResponse)
async def advance_project(project_id: str) -> CreativeProjectResponse:
    try:
        project = await creative_orchestrator.advance(project_id)
    except KeyError as exc:  # pragma: no cover - FastAPI handles
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error advancing project {project_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to advance project: {str(exc)}") from exc
    return CreativeProjectResponse(project=project)


@router.post("/projects/{project_id}/approve-preview", response_model=CreativeProjectResponse)
async def approve_preview(project_id: str) -> CreativeProjectResponse:
    try:
        project = await creative_orchestrator.approve_preview(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error approving preview for project {project_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to approve preview: {str(exc)}") from exc
    return CreativeProjectResponse(project=project)


@router.get("/projects", response_model=CreativeProjectListResponse)
async def list_projects(tenant_id: str = "demo") -> CreativeProjectListResponse:
    try:
        projects = await creative_repository.list_for_tenant(tenant_id)
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error listing projects for tenant {tenant_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(exc)}") from exc

    return CreativeProjectListResponse(projects=list(projects))


@router.get("/projects/{project_id}", response_model=CreativeProjectResponse)
async def get_project(project_id: str) -> CreativeProjectResponse:
    from ..instrumentation import get_logger
    logger = get_logger()
    
    try:
        # Get project
        project = await creative_repository.get(project_id)
        logger.debug(f"Retrieved project {project_id}, state: {project.state}, type: {type(project)}")
    except KeyError as exc:  # pragma: no cover
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Error getting project {project_id}: {exc}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(exc)}") from exc
    
    try:
        # Validate the project can be serialized
        response = CreativeProjectResponse(project=project)
        # Try to serialize to catch any serialization errors early
        _ = response.model_dump(mode="json")
        return response
    except Exception as exc:
        logger.error(f"Error serializing project {project_id}: {exc}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Serialization error: {str(exc)}") from exc


@router.post("/projects/{project_id}/generate-video", status_code=202)
async def generate_video(project_id: str) -> dict[str, Any]:
    """
    提交视频生成任务 (异步)
    
    Returns:
        202 Accepted + task_id (用于轮询状态)
    """
    from ..task_queue import task_queue
    from ..instrumentation import get_logger
    
    logger = get_logger()
    
    try:
        # 获取项目信息
        project = await creative_repository.get(project_id)
        
        # 检查项目状态
        if not project.script:
            raise HTTPException(status_code=400, detail="Project has no script")
        if not project.storyboard:
            raise HTTPException(status_code=400, detail="Project has no storyboard")
        
        # 提交任务到队列
        task_id = await task_queue.enqueue_video_generation(
            project_id=project.id,
            script=project.script,
            storyboard=project.storyboard,
        )
        
        logger.info(f"Video generation task queued: {task_id} for project {project_id}")
        
        return {
            "task_id": task_id,
            "status": "queued",
            "message": "视频生成任务已提交,请使用 task_id 查询进度"
        }
    
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Error queuing video generation for project {project_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(exc)}") from exc


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str) -> dict[str, Any]:
    """查询任务状态"""
    from ..task_queue import task_queue
    
    try:
        status = await task_queue.get_task_status(task_id)
        return status
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(exc)}") from exc

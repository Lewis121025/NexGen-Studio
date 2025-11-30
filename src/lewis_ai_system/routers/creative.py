"""FastAPI router for Creative Mode projects."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..creative.models import (
    CreativeProjectCreateRequest,
    CreativeProjectResponse,
    CreativeProjectListResponse,
)
from ..creative.workflow import creative_orchestrator
from ..creative.repository import creative_repository
from ..config import settings

router = APIRouter()


@router.get("/video-providers")
async def get_available_video_providers() -> dict:
    """获取可用的视频提供商列表。"""
    return {"providers": settings.available_video_providers}


@router.post("/projects", response_model=CreativeProjectResponse, status_code=201)
async def create_project(payload: CreativeProjectCreateRequest) -> CreativeProjectResponse:
    """创建新的创作项目。"""
    try:
        project = await creative_orchestrator.create_project(payload)
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error creating creative project: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(exc)}") from exc
    return CreativeProjectResponse(project=project)


@router.get("/projects/{project_id}", response_model=CreativeProjectResponse)
async def get_project(project_id: str) -> CreativeProjectResponse:
    """获取创作项目详情。"""
    try:
        project = await creative_repository.get(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error getting project {project_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(exc)}") from exc
    return CreativeProjectResponse(project=project)


@router.get("/projects", response_model=CreativeProjectListResponse)
async def list_projects(tenant_id: str = "demo", limit: int = 50) -> CreativeProjectListResponse:
    """列出租户的所有创作项目。"""
    try:
        projects = await creative_repository.list_for_tenant(tenant_id)
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error listing projects for tenant {tenant_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(exc)}") from exc
    return CreativeProjectListResponse(projects=list(projects)[:limit])


@router.post("/projects/{project_id}/approve-script", response_model=CreativeProjectResponse)
async def approve_script(project_id: str) -> CreativeProjectResponse:
    """批准脚本并继续到分镜阶段。"""
    try:
        project = await creative_orchestrator.approve_script(project_id)
    except KeyError as exc:
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
    """推进项目到下一个自动阶段。"""
    try:
        project = await creative_orchestrator.advance(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error advancing project {project_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to advance project: {str(exc)}") from exc
    return CreativeProjectResponse(project=project)


@router.post("/projects/{project_id}/pause", response_model=CreativeProjectResponse)
async def pause_project(project_id: str, reason: str = "user_request") -> CreativeProjectResponse:
    """暂停项目。"""
    try:
        project = await creative_repository.get(project_id)
        from ..creative.models import CreativeProjectState
        from datetime import datetime, timezone
        
        if project.state == CreativeProjectState.PAUSED:
            raise ValueError("Project is already paused")
        
        project.pre_pause_state = project.state
        project.pause_reason = reason
        project.paused_at = datetime.now(timezone.utc)
        project.mark_state(CreativeProjectState.PAUSED)
        
        await creative_repository.upsert(project)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error pausing project {project_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to pause project: {str(exc)}") from exc
    return CreativeProjectResponse(project=project)


@router.post("/projects/{project_id}/resume", response_model=CreativeProjectResponse)
async def resume_project(project_id: str) -> CreativeProjectResponse:
    """恢复暂停的项目。"""
    try:
        project = await creative_repository.get(project_id)
        from ..creative.models import CreativeProjectState
        
        if project.state != CreativeProjectState.PAUSED:
            raise ValueError("Project is not paused")
        
        if project.pre_pause_state:
            project.mark_state(project.pre_pause_state)
        else:
            project.mark_state(CreativeProjectState.BRIEF_PENDING)
        
        project.pre_pause_state = None
        project.pause_reason = None
        project.paused_at = None
        
        await creative_repository.upsert(project)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error resuming project {project_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to resume project: {str(exc)}") from exc
    return CreativeProjectResponse(project=project)

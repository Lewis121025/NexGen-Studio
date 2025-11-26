"""FastAPI router for General Mode sessions."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ..general.models import GeneralSessionCreateRequest, GeneralSessionResponse, GeneralSessionListResponse
from ..general.repository import general_repository
from ..general.session import general_orchestrator
from ..storage import default_storage


MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB per file


from pydantic import BaseModel


class RunIterationRequest(BaseModel):
    prompt: str | None = None

router = APIRouter(prefix="/general", tags=["general"])


@router.post("/sessions", response_model=GeneralSessionResponse, status_code=201)
async def create_session(payload: GeneralSessionCreateRequest) -> GeneralSessionResponse:
    try:
        session = await general_orchestrator.create_session(payload)
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error creating session: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(exc)}") from exc
    return GeneralSessionResponse(session=session)


@router.post("/sessions/{session_id}/iterate", response_model=GeneralSessionResponse)
async def run_iteration(session_id: str, payload: RunIterationRequest | None = None) -> GeneralSessionResponse:
    try:
        session = await general_orchestrator.run_iteration(session_id, prompt_text=payload.prompt if payload else None)
    except KeyError as exc:  # pragma: no cover
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error running iteration for session {session_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to run iteration: {str(exc)}") from exc
    return GeneralSessionResponse(session=session)


@router.get("/sessions/{session_id}", response_model=GeneralSessionResponse)
async def get_session(session_id: str) -> GeneralSessionResponse:
    try:
        session = await general_repository.get(session_id)
    except KeyError as exc:  # pragma: no cover
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error getting session {session_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(exc)}") from exc
    return GeneralSessionResponse(session=session)


@router.get("/sessions", response_model=GeneralSessionListResponse)
async def list_sessions(tenant_id: str = "demo", limit: int = 50) -> GeneralSessionListResponse:
    try:
        sessions = await general_repository.list_for_tenant(tenant_id, limit)
    except Exception as exc:
        from ..instrumentation import get_logger
        logger = get_logger()
        logger.error(f"Error listing sessions for tenant {tenant_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(exc)}") from exc

    return GeneralSessionListResponse(sessions=list(sessions))


@router.post("/sessions/{session_id}/message")
async def send_message_with_files(
    session_id: str,
    prompt: str | None = Form(default=None),
    files: list[UploadFile] | None = None,
) -> StreamingResponse:
    """
    接收用户消息/附件并通过 SSE 流式返回处理状态。
    
    事件顺序：thinking -> processing -> completed/failed，data 字段为 JSON。
    """
    from ..instrumentation import get_logger
    from ..serialization import sse_event as sse

    logger = get_logger()

    async def event_stream() -> AsyncGenerator[bytes, None]:
        try:
            session = await general_repository.get(session_id)
        except KeyError as exc:
            yield sse({"status": "error", "message": str(exc)})
            return
        except Exception as exc:
            logger.error(f"Failed to load session {session_id}: {exc}", exc_info=True)
            yield sse({"status": "error", "message": "failed to load session"})
            return

        yield sse({"status": "thinking", "message": "Processing request"})

        saved_paths: list[str] = []
        if files:
            for f in files:
                data = await f.read()
                if len(data) > MAX_UPLOAD_BYTES:
                    yield sse({"status": "error", "message": f"File {f.filename} exceeds 10MB limit"})
                    return
                safe_name = f.filename or "upload.bin"
                relative_path = str(Path("general") / session_id / safe_name)
                path = default_storage.save_bytes(relative_path, data)
                session.uploads.append(
                    {
                        "name": safe_name,
                        "content_type": f.content_type,
                        "size_bytes": len(data),
                        "local_path": path,
                    }
                )
                saved_paths.append(path)

            if saved_paths:
                session.messages.append(f"User uploaded files: {', '.join(saved_paths)}")

        if prompt:
            session.goal = prompt
            session.messages.append(f"User: {prompt}")

        try:
            await general_repository.upsert(session)
        except Exception as exc:
            logger.error(f"Failed to persist session {session_id}: {exc}", exc_info=True)
            yield sse({"status": "error", "message": "failed to persist session"})
            return

        yield sse({"status": "processing", "message": "Running agent"})

        try:
            session = await general_orchestrator.run_iteration(session_id, prompt_text=None)
            yield sse(
                {
                    "status": "completed",
                    "session": session.model_dump(mode="json"),
                }
            )
        except Exception as exc:
            logger.error(f"Iteration error for session {session_id}: {exc}", exc_info=True)
            yield sse({"status": "error", "message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")

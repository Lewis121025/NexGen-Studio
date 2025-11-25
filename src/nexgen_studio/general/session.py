"""通用模式编排器，实现 ReAct 风格的循环执行。

本模块实现了通用模式的会话管理和任务执行逻辑，使用 ReAct (Reasoning + Acting) 循环
来逐步解决用户任务。
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..agents import agent_pool
from ..costs import cost_tracker
from ..instrumentation import TelemetryEvent, emit_event
from ..tooling import ToolRequest, ToolRuntime, default_tool_runtime
from ..vector_db import vector_db
from .models import GuardrailTriggered, GeneralSession, GeneralSessionCreateRequest, GeneralSessionState, ToolCallRecord

# Maintain compatibility with older imports that expected SessionState here.
SessionState = GeneralSessionState
from .repository import BaseGeneralSessionRepository, general_repository


class GeneralModeOrchestrator:
    """通用模式编排器，管理 ReAct 循环的执行和会话状态。
    
    负责创建会话、执行迭代、管理内存和压缩历史记录。
    """
    
    def __init__(
        self,
        repository: BaseGeneralSessionRepository | None = None,
        tool_runtime: ToolRuntime | None = None,
        memory_window: int = 5,
        compression_threshold: int = 25,
    ) -> None:
        """初始化通用模式编排器。
        
        Args:
            repository: 会话存储库，如果为 None 则使用默认存储库
            tool_runtime: 工具运行时，如果为 None 则使用默认运行时
            memory_window: 内存窗口大小（保留的最近消息数），默认 5
            compression_threshold: 压缩阈值（超过此数量的消息将被压缩），默认 25
        """
        self.repository = repository or general_repository
        self.tool_runtime = tool_runtime or default_tool_runtime
        self.memory_window = max(memory_window, 1)
        self.compression_threshold = max(compression_threshold, self.memory_window + 1)

    async def create_session(self, payload: GeneralSessionCreateRequest) -> GeneralSession:
        """创建新的通用会话。
        
        Args:
            payload: 会话创建请求
            
        Returns:
            创建的会话对象
        """
        session = await self.repository.create(payload)
        session.messages.append(f"Goal registered: {payload.goal}")
        await self.repository.upsert(session)
        return session

    async def run_iteration(self, session_id: str, prompt_text: str | None = None) -> GeneralSession:
        """运行一次迭代，执行 ReAct 循环。
        
        Args:
            session_id: 会话 ID
            prompt_text: 可选的提示文本，如果提供则更新会话目标
            
        Returns:
            更新后的会话对象
            
        Raises:
            ValueError: 如果会话不存在或状态不正确
            GuardrailTriggered: 如果触发保护机制（预算超限等）
        """
        from ..instrumentation import get_logger
        logger = get_logger()
        
        try:
            session = await self.repository.get(session_id)
        except KeyError:
            raise
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}", exc_info=True)
            raise ValueError(f"Failed to retrieve session: {str(e)}") from e
        
        if session.state != GeneralSessionState.ACTIVE:
            raise ValueError(f"Session is not active (current state: {session.state})")

        if not self._can_continue(session):
            return await self._persist_guardrail_pause(session)

        if prompt_text:
            session.goal = prompt_text
            session.messages.append(f"User: {prompt_text}")

        remaining_steps = max(session.max_iterations - session.iteration, 1)

        # Wrap tool runtime to record steps
        recording_runtime = SessionRecordingToolRuntime(self.tool_runtime, session)

        try:
            # Delegate the entire loop to the GeneralAgent
            final_answer = await agent_pool.general.react_loop(session.goal, recording_runtime, max_steps=remaining_steps)
            
            session.summary = final_answer
            session.messages.append(f"Final Answer: {final_answer}")
            session.mark_state(GeneralSessionState.COMPLETED)
            
        except GuardrailTriggered as exc:
            # Guardrail handlers already stamped the session; just persist
            session.pause_reason = getattr(exc, "reason", str(exc))
            session.mark_state(GeneralSessionState.PAUSED)
            emit_event(TelemetryEvent(name="general_session_paused", attributes={"session_id": session.id, "reason": exc.reason}))

        except Exception as e:
            logger.error(f"Error in react_loop for session {session_id}: {e}", exc_info=True)
            session.messages.append(f"Error: {str(e)}")
            session.mark_state(GeneralSessionState.FAILED)
            emit_event(TelemetryEvent(name="general_session_error", attributes={"session_id": session.id, "error": str(e)}))

        try:
            await self._maybe_store_memory(session)
            await self._maybe_compress_history(session)
            return await self.repository.upsert(session)
        except Exception as e:
            logger.error(f"Error persisting session {session_id}: {e}", exc_info=True)
            # Return session even if persistence fails, so user can see the result
            return session

    def _can_continue(self, session: GeneralSession) -> bool:
        """Early guard check before entering the loop."""
        if not session.auto_pause_enabled:
            return True

        if session.iteration >= session.max_iterations:
            session.pause_reason = f"Reached max iterations ({session.max_iterations})"
            session.messages.append(session.pause_reason)
            session.mark_state(GeneralSessionState.PAUSED)
            emit_event(
                TelemetryEvent(
                    name="general_guardrail_triggered",
                    attributes={"session_id": session.id, "reason": "max_iterations"},
                )
            )
            return False

        if session.spent_usd >= session.budget_limit_usd:
            session.pause_reason = f"Budget limit hit (${session.budget_limit_usd:.2f})"
            session.messages.append(session.pause_reason)
            session.mark_state(GeneralSessionState.PAUSED)
            emit_event(
                TelemetryEvent(
                    name="general_guardrail_triggered",
                    attributes={"session_id": session.id, "reason": "budget"},
                )
            )
            return False

        return True

    async def _persist_guardrail_pause(self, session: GeneralSession) -> GeneralSession:
        try:
            return await self.repository.upsert(session)
        except Exception:
            return session

    async def _maybe_store_memory(self, session: GeneralSession) -> None:
        if not session.messages:
            return

        snippet = "\n".join(session.messages[-self.memory_window :])
        embedding = self._embed_text(snippet)
        metadata = {
            "tenant_id": session.tenant_id,
            "goal": session.goal,
            "iteration": session.iteration,
            "state": session.state.value,
        }

        try:
            await vector_db.store_conversation_memory(
                session.id,
                snippet,
                embedding,
                metadata,
            )
        except Exception as exc:  # pragma: no cover - telemetry for unexpected provider failures
            emit_event(
                TelemetryEvent(
                    name="general_memory_error",
                    attributes={"session_id": session.id, "error": str(exc)},
                )
            )

    async def _maybe_compress_history(self, session: GeneralSession) -> None:
        if len(session.messages) <= self.compression_threshold:
            return

        preserved = session.messages[-self.memory_window :]
        history_to_summarize = "\n".join(session.messages[:-self.memory_window])

        try:
            summary = await agent_pool.formatter.summarize(history_to_summarize)
        except Exception as exc:  # pragma: no cover - avoid blocking flows on summarizer issues
            emit_event(
                TelemetryEvent(
                    name="general_compression_error",
                    attributes={"session_id": session.id, "error": str(exc)},
                )
            )
            return

        session.messages = [f"[历史摘要]\n{summary.strip()}"] + preserved

    def _embed_text(self, text: str, dims: int = 32) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = list(digest)
        while len(values) < dims:
            values.extend(values)
        normalized = [(value / 255.0) for value in values[:dims]]
        return normalized


class SessionRecordingToolRuntime:
    """Wraps ToolRuntime to record calls to a session."""
    
    def __init__(self, runtime: ToolRuntime, session: GeneralSession) -> None:
        self._runtime = runtime
        self._session = session
        # Expose _tools for the agent to inspect
        self._tools = runtime._tools

    def _ensure_budget_and_iterations(self) -> None:
        if self._session.state != GeneralSessionState.ACTIVE:
            raise GuardrailTriggered("session_not_active", f"Session is {self._session.state}")

        if not self._session.auto_pause_enabled:
            return

        if self._session.iteration >= self._session.max_iterations:
            self._session.pause_reason = f"Reached max iterations ({self._session.max_iterations})"
            self._session.mark_state(GeneralSessionState.PAUSED)
            self._session.messages.append(self._session.pause_reason)
            raise GuardrailTriggered("max_iterations", self._session.pause_reason)

        if self._session.spent_usd >= self._session.budget_limit_usd:
            self._session.pause_reason = f"Budget limit hit (${self._session.budget_limit_usd:.2f})"
            self._session.mark_state(GeneralSessionState.PAUSED)
            self._session.messages.append(self._session.pause_reason)
            raise GuardrailTriggered("budget_exceeded", self._session.pause_reason)

    def execute(self, request: ToolRequest) -> Any:
        self._ensure_budget_and_iterations()

        # Record start
        emit_event(
            TelemetryEvent(
                name="general_iteration_start",
                attributes={"session_id": self._session.id, "tool": request.name},
            )
        )
        
        try:
            result = self._runtime.execute(request)
            output = result.output
            cost = result.cost_usd
        except GuardrailTriggered:
            raise
        except Exception as e:
            output = {"error": str(e)}
            cost = 0.0
            emit_event(TelemetryEvent(name="general_tool_error", attributes={"session_id": self._session.id, "tool": request.name, "error": str(e)}))

        # Update session
        self._session.spent_usd += cost
        self._session.iteration += 1
        cost_tracker.record(self._session.id, cost)
        
        self._session.tool_calls.append(
            ToolCallRecord(
                step=self._session.iteration,
                tool=request.name,
                arguments=request.input,
                output=output if isinstance(output, dict) else {"text": str(output)},
                cost_usd=cost,
                decision_path="ReAct Agent Action",
            )
        )
        self._session.messages.append(f"Tool: {request.name}\nOutput: {str(output)[:500]}...")

        self._ensure_budget_and_iterations()
        
        # Check guardrails (simplified for synchronous execution context)
        # Note: In a real async loop, we might want to stop the agent if guardrails hit.
        # For now, we just record.
        
        return result


general_orchestrator = GeneralModeOrchestrator()

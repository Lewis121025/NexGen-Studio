"""工具运行时和沙箱执行模块。

本模块提供工具注册、执行和沙箱代码执行功能，支持安全的 Python 代码执行。
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict

from .config import settings
from .instrumentation import TelemetryEvent, emit_event
from .sandbox import EnhancedSandbox


@dataclass(slots=True)
class ToolRequest:
    """工具执行请求。
    
    Attributes:
        name: 工具名称
        input: 工具输入参数字典
    """
    name: str
    input: dict[str, Any]


@dataclass(slots=True)
class ToolResult:
    """工具执行结果。
    
    Attributes:
        output: 工具输出结果
        cost_usd: 执行成本（美元），默认 0.0
        metadata: 元数据字典，可选
    """
    output: Any
    cost_usd: float = 0.0
    metadata: dict[str, Any] | None = None


class ToolExecutionError(RuntimeError):
    """工具执行错误异常。
    
    当工具无法执行时抛出此异常。
    """


class Tool:
    """工具基类。
    
    所有工具必须继承此类并实现 run 或 run_async 方法。
    """
    name: str  # 工具名称
    description: str  # 工具描述
    cost_estimate: float = 0.001  # 预估成本（美元）

    def run(self, payload: dict[str, Any]) -> ToolResult:  # pragma: no cover - interface
        """执行工具（同步版本）。
        
        Args:
            payload: 工具输入参数字典
            
        Returns:
            工具执行结果
            
        Raises:
            NotImplementedError: 子类必须实现此方法或 run_async
        """
        raise NotImplementedError
    
    async def run_async(self, payload: dict[str, Any]) -> ToolResult:
        """执行工具（异步版本）。
        
        默认实现调用同步版本，子类可以覆盖此方法提供真正的异步实现。
        """
        return self.run(payload)

    @property
    def parameters(self) -> dict[str, Any]:
        """获取工具参数的 JSON Schema 定义。
        
        Returns:
            参数定义的 JSON Schema 字典
        """
        return {}


class PythonSandboxTool(Tool):
    """Execute Python securely via the E2B sandbox."""

    name = "python_sandbox"
    description = "Execute Python code in the E2B sandbox with isolation."

    def __init__(self) -> None:
        self._sandbox: EnhancedSandbox | None = None

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute. Must be valid, complete Python code."
                }
            },
            "required": ["code"]
        }

    def _get_sandbox(self) -> EnhancedSandbox:
        if self._sandbox is None:
            if not settings.e2b_api_key:
                raise ToolExecutionError("E2B_API_KEY is required to execute python_sandbox.")
            self._sandbox = EnhancedSandbox(api_key=settings.e2b_api_key)
        return self._sandbox

    def run(self, payload: dict[str, Any]) -> ToolResult:
        code = payload.get("code")
        if not isinstance(code, str):
            raise ToolExecutionError("python_sandbox requires 'code' string input")

        code = textwrap.dedent(code).strip()

        try:
            execution = self._get_sandbox().execute_python(code)
        except Exception as exc:  # pragma: no cover - defensive
            raise ToolExecutionError(f"Sandbox execution failed: {exc}") from exc

        if execution.get("error"):
            raise ToolExecutionError(f"Sandbox execution failed: {execution['error']}")

        return ToolResult(output=execution, cost_usd=0.01)

    async def run_async(self, payload: dict[str, Any]) -> ToolResult:
        """异步执行 Python 代码（实际执行是同步的，但不会阻塞事件循环检查）。"""
        import asyncio
        # 在线程池中运行同步代码，避免阻塞事件循环
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run, payload)


class WebSearchTool(Tool):
    """网页搜索工具，使用配置的搜索提供商。
    
    支持 Tavily 等搜索 API，可以返回汇总的搜索结果。
    """

    name = "web_search"
    description = "查询网页搜索 API 并返回汇总结果。"

    def __init__(self) -> None:
        """初始化网页搜索工具。"""
        from .providers import get_search_provider
        self._provider_factory = get_search_provider
        self.provider = self._provider_factory()

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string."
                },
                "provider": {
                    "type": "string",
                    "description": "Optional provider override (e.g. 'tavily', 'mock')."
                }
            },
            "required": ["query"]
        }

    def run(self, payload: dict[str, Any]) -> ToolResult:
        """同步执行（仅用于非异步上下文）。"""
        import asyncio
        try:
            # 尝试在新事件循环中运行
            return asyncio.run(self.run_async(payload))
        except RuntimeError:
            # 如果已有循环在运行，返回错误
            return ToolResult(output={"error": "Use run_async in async context"}, cost_usd=0.0)

    async def run_async(self, payload: dict[str, Any]) -> ToolResult:
        """异步执行网页搜索。"""
        query = payload.get("query", "")
        provider_override = payload.get("provider")
        if provider_override:
            self.provider = self._provider_factory(provider_override)
        
        try:
            result = await self.provider.search(query)
            return ToolResult(output={"query": query, "result": result}, cost_usd=0.01)
        except Exception as e:
            return ToolResult(output={"error": str(e)}, cost_usd=0.0)


class WebScrapeTool(Tool):
    """网页抓取工具，使用 Firecrawl 等提供商。
    
    从指定 URL 提取内容并转换为 Markdown 格式。
    """
    
    name = "web_scrape"
    description = "从 URL 提取内容并转换为 Markdown。"
    
    def __init__(self) -> None:
        """初始化网页抓取工具。"""
        from .providers import get_scrape_provider
        self._provider_factory = get_scrape_provider
        self.provider = self._provider_factory()
        
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to scrape content from."
                },
                "provider": {
                    "type": "string",
                    "description": "Optional provider override (e.g. 'firecrawl', 'mock')."
                }
            },
            "required": ["url"]
        }
        
    def run(self, payload: dict[str, Any]) -> ToolResult:
        """同步执行（仅用于非异步上下文）。"""
        import asyncio
        try:
            return asyncio.run(self.run_async(payload))
        except RuntimeError:
            return ToolResult(output={"error": "Use run_async in async context"}, cost_usd=0.0)

    async def run_async(self, payload: dict[str, Any]) -> ToolResult:
        """异步执行网页抓取。"""
        url = payload.get("url")
        if not url:
            raise ToolExecutionError("web_scrape requires 'url' string input")

        provider_override = payload.get("provider")
        if provider_override:
            self.provider = self._provider_factory(provider_override)
            
        try:
            content = await self.provider.scrape(url)
            return ToolResult(output={"url": url, "content": content[:5000]}, cost_usd=0.005)
        except Exception as e:
            return ToolResult(output={"error": str(e)}, cost_usd=0.0)


class VideoGenerationTool(Tool):
    """视频生成工具，改为异步队列（ARQ/Celery 等）提交."""

    name = "generate_video"
    description = "Enqueue video generation and return task id for status polling."
    cost_estimate = 0.0

    def __init__(self, provider_name: str | None = None) -> None:
        self.provider_name = provider_name or "default"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Text description of the video to generate."
                },
                "duration_seconds": {
                    "type": "integer",
                    "description": "Duration in seconds (default 5).",
                    "default": 5
                },
                "aspect_ratio": {
                    "type": "string",
                    "description": "Aspect ratio (e.g., '16:9', '9:16').",
                    "default": "16:9"
                },
                "quality": {
                    "type": "string",
                    "enum": ["preview", "final"],
                    "default": "preview"
                },
            },
            "required": ["prompt"]
        }

    def run(self, payload: dict[str, Any]) -> ToolResult:
        """同步执行（仅用于非异步上下文）。"""
        import asyncio
        try:
            return asyncio.run(self.run_async(payload))
        except RuntimeError:
            return ToolResult(output={"error": "Use run_async in async context"}, cost_usd=0.0)

    async def run_async(self, payload: dict[str, Any]) -> ToolResult:
        """异步执行视频生成任务入队。"""
        from .task_queue import task_queue

        prompt = payload.get("prompt")
        if not isinstance(prompt, str):
            raise ToolExecutionError("generate_video requires 'prompt' string input")

        duration = payload.get("duration_seconds", 5)
        aspect_ratio = payload.get("aspect_ratio", "16:9")
        quality = payload.get("quality", "preview")

        try:
            await task_queue.connect()
            job_id = await task_queue.enqueue_generic_video(
                {
                    "prompt": prompt,
                    "duration_seconds": duration,
                    "aspect_ratio": aspect_ratio,
                    "quality": quality,
                }
            )
            return ToolResult(output={"task_id": job_id, "status": "pending"})
        except Exception as e:
            return ToolResult(output={"error": str(e)}, cost_usd=0.0)


class TTSTool(Tool):
    """Tool for text-to-speech synthesis."""

    name = "text_to_speech"
    description = "Converts text to speech audio using TTS provider."
    cost_estimate = 0.15  # Per 1000 characters

    def __init__(self, provider_name: str = "elevenlabs") -> None:
        from .providers import get_tts_provider
        self.provider = get_tts_provider(provider_name)
        self.provider_name = provider_name

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to convert to speech."
                },
                "voice": {
                    "type": "string",
                    "description": "Voice ID or name.",
                    "default": "default"
                }
            },
            "required": ["text"]
        }

    def run(self, payload: dict[str, Any]) -> ToolResult:
        """同步执行（仅用于非异步上下文）。"""
        import asyncio
        try:
            return asyncio.run(self.run_async(payload))
        except RuntimeError:
            return ToolResult(output={"error": "Use run_async in async context"}, cost_usd=0.0)

    async def run_async(self, payload: dict[str, Any]) -> ToolResult:
        """异步执行文本转语音。"""
        text = payload.get("text")
        if not isinstance(text, str):
            raise ToolExecutionError("text_to_speech requires 'text' string input")
        
        voice = payload.get("voice", "default")
        
        try:
            result = await self.provider.synthesize(text, voice=voice)
            # Calculate cost based on character count
            cost = (len(text) / 1000) * self.cost_estimate
            return ToolResult(output=result, cost_usd=cost, metadata={"provider": self.provider_name})
        except Exception as e:
            return ToolResult(output={"error": str(e)}, cost_usd=0.0)


class ToolRuntime:
    """工具运行时，负责工具注册、执行和遥测。
    
    这是工具系统的核心类，管理所有已注册的工具并提供统一的执行接口。
    """

    def __init__(self, sandbox_timeout: int = settings.sandbox.execution_timeout_seconds) -> None:
        self._tools: Dict[str, Tool] = {}
        self._lock = Lock()
        self.sandbox_timeout = sandbox_timeout

    def register(self, tool: Tool) -> None:
        with self._lock:
            self._tools[tool.name] = tool

    def execute(self, request: ToolRequest) -> ToolResult:
        """同步执行工具（不推荐在异步上下文中使用）。"""
        tool = self._tools.get(request.name)
        if not tool:
            raise ToolExecutionError(f"Unknown tool '{request.name}'")

        emit_event(TelemetryEvent(name="tool_start", attributes={"tool": request.name}))
        result = tool.run(request.input)
        emit_event(TelemetryEvent(name="tool_complete", attributes={"tool": request.name, "cost": result.cost_usd}))
        return result

    async def execute_async(self, request: ToolRequest) -> ToolResult:
        """异步执行工具（推荐在 FastAPI 等异步框架中使用）。"""
        tool = self._tools.get(request.name)
        if not tool:
            raise ToolExecutionError(f"Unknown tool '{request.name}'")

        emit_event(TelemetryEvent(name="tool_start", attributes={"tool": request.name}))
        
        # 使用异步方法执行
        if hasattr(tool, 'run_async'):
            result = await tool.run_async(request.input)
        else:
            # 兼容没有 run_async 的工具
            result = tool.run(request.input)
        
        emit_event(TelemetryEvent(name="tool_complete", attributes={"tool": request.name, "cost": result.cost_usd}))
        return result


default_tool_runtime = ToolRuntime()
default_tool_runtime.register(PythonSandboxTool())
default_tool_runtime.register(WebSearchTool())
default_tool_runtime.register(WebScrapeTool())
default_tool_runtime.register(VideoGenerationTool(provider_name=settings.video_provider_default))
default_tool_runtime.register(TTSTool(provider_name="elevenlabs"))

"""工具运行时和沙箱执行模块。

本模块提供工具注册、执行和沙箱代码执行功能，支持安全的 Python 代码执行。
"""

from __future__ import annotations

import math
import textwrap
from dataclasses import dataclass
from threading import Lock
from types import MappingProxyType
from typing import Any, Callable, Dict

from .config import settings
from .instrumentation import TelemetryEvent, emit_event


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
    
    所有工具必须继承此类并实现 run 方法。
    """
    name: str  # 工具名称
    description: str  # 工具描述
    cost_estimate: float = 0.001  # 预估成本（美元）

    def run(self, payload: dict[str, Any]) -> ToolResult:  # pragma: no cover - interface
        """执行工具。
        
        Args:
            payload: 工具输入参数字典
            
        Returns:
            工具执行结果
            
        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError

    @property
    def parameters(self) -> dict[str, Any]:
        """获取工具参数的 JSON Schema 定义。
        
        Returns:
            参数定义的 JSON Schema 字典
        """
        return {}


class PythonSandboxTool(Tool):
    """增强的 Python 沙箱工具，支持安全的代码执行和资源限制。
    
    支持使用 E2B 沙箱或本地回退执行 Python 代码。
    """

    name = "python_sandbox"
    description = "在安全的沙箱中执行 Python 代码，具有 CPU/内存限制。"

    def __init__(self) -> None:
        """初始化 Python 沙箱工具。"""
        from .providers import get_sandbox_provider
        self.provider = get_sandbox_provider()
        
        # 如果提供商是本地，保留本地回退逻辑
        self.allowed_builtins = MappingProxyType(
            {
                "abs": abs,
                "min": min,
                "max": max,
                "sum": sum,
                "len": len,
                "range": range,
                "round": round,
                "math": math,
            }
        )

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

    def run(self, payload: dict[str, Any]) -> ToolResult:
        import asyncio
        code = payload.get("code")
        if not isinstance(code, str):
            raise ToolExecutionError("python_sandbox requires 'code' string input")

        code = textwrap.dedent(code).strip()
        
        # 如果使用 E2B，委托给提供商
        if self.provider.name == "e2b":
            try:
                # 如果已经在事件循环中（常见于异步工作流），
                # 在工作线程上运行提供商的协程以避免嵌套循环错误
                try:
                    asyncio.get_running_loop()
                    loop_running = True
                except RuntimeError:
                    loop_running = False

                if loop_running:
                    import concurrent.futures

                    def _invoke() -> dict[str, Any]:
                        return asyncio.run(self.provider.run_code(code))

                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(_invoke)
                        result = future.result()
                else:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(self.provider.run_code(code))
            except Exception as exc:  # pragma: no cover - defensive
                raise ToolExecutionError(f"Sandbox execution failed: {exc}") from exc

            if result.get("error"):
                raise ToolExecutionError(f"Sandbox execution failed: {result['error']}")
            
            return ToolResult(output=result, cost_usd=0.01)  # E2B 成本估算

        # 生产环境必须使用 E2B,不允许本地 fallback
        if settings.environment == "production":
            raise ToolExecutionError(
                "生产环境代码执行失败! E2B Provider 不可用。"
                "请确保已配置 E2B_API_KEY 环境变量。"
            )
        
        # 开发环境的本地 fallback (仅用于测试)
        logger.warning(
            "⚠️  使用本地沙箱执行代码 - 仅供开发使用! "
            "生产环境请务必配置 E2B_API_KEY。"
        )
        
        try:
            from .sandbox import get_sandbox
            sandbox = get_sandbox()
            execution_result = sandbox.execute_python(
                code,
                restricted_builtins=dict(self.allowed_builtins)
            )
            
            if execution_result["error"]:
                raise ToolExecutionError(f"Sandbox execution failed: {execution_result['error']}")
            
            output = {
                "result": execution_result["result"],
                "stdout": execution_result["stdout"],
                "execution_time": execution_result["execution_time"]
            }
            return ToolResult(output=output, cost_usd=self.cost_estimate)
            
        except Exception as exc:
            raise ToolExecutionError(f"本地沙箱执行失败: {exc}") from exc


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
        import asyncio
        query = payload.get("query", "")
        provider_override = payload.get("provider")
        if provider_override:
            self.provider = self._provider_factory(provider_override)
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        result = loop.run_until_complete(self.provider.search(query))
        return ToolResult(output={"query": query, "result": result}, cost_usd=0.01)


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
        import asyncio
        url = payload.get("url")
        if not url:
            raise ToolExecutionError("web_scrape requires 'url' string input")

        provider_override = payload.get("provider")
        if provider_override:
            self.provider = self._provider_factory(provider_override)
            
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        content = loop.run_until_complete(self.provider.scrape(url))
        return ToolResult(output={"url": url, "content": content[:5000]}, cost_usd=0.005)


class VideoGenerationTool(Tool):
    """视频生成工具，通过提供商 API（Runway/Pika/Runware）生成视频。
    
    支持多个视频生成服务提供商，可以根据配置或请求参数选择。
    """

    name = "generate_video"
    description = "Generates video from text prompt using configured provider."
    cost_estimate = 2.5  # Average cost per 5-second video

    def __init__(self, provider_name: str | None = None) -> None:
        from .providers import get_video_provider

        self._provider_factory = get_video_provider
        self.provider_name = provider_name or settings.video_provider_default
        self.provider = self._provider_factory(self.provider_name)

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
                "provider": {
                    "type": "string",
                    "description": "Optional provider override."
                }
            },
            "required": ["prompt"]
        }

    def _resolve_provider(self, override: str | None) -> tuple[str, Any]:
        if not override or override == self.provider_name:
            return self.provider_name, self.provider
        resolved = self._provider_factory(override)
        return override, resolved

    def run(self, payload: dict[str, Any]) -> ToolResult:
        import asyncio

        prompt = payload.get("prompt")
        if not isinstance(prompt, str):
            raise ToolExecutionError("generate_video requires 'prompt' string input")

        duration = payload.get("duration_seconds", 5)
        aspect_ratio = payload.get("aspect_ratio", "16:9")
        quality = payload.get("quality", "preview")
        provider_override = payload.get("provider")
        provider_name, provider = self._resolve_provider(provider_override)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            provider.generate_video(
                prompt,
                duration_seconds=duration,
                aspect_ratio=aspect_ratio,
                quality=quality,
            )
        )

        cost_multiplier = 1.5 if quality == "final" else 0.3
        cost = self.cost_estimate * (duration / 5) * cost_multiplier

        return ToolResult(output=result, cost_usd=cost, metadata={"provider": provider_name})


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
        import asyncio
        
        text = payload.get("text")
        if not isinstance(text, str):
            raise ToolExecutionError("text_to_speech requires 'text' string input")
        
        voice = payload.get("voice", "default")
        
        # Run async provider call
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(self.provider.synthesize(text, voice=voice))
        
        # Calculate cost based on character count
        cost = (len(text) / 1000) * self.cost_estimate
        
        return ToolResult(output=result, cost_usd=cost, metadata={"provider": self.provider_name})


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
        tool = self._tools.get(request.name)
        if not tool:
            raise ToolExecutionError(f"Unknown tool '{request.name}'")

        emit_event(TelemetryEvent(name="tool_start", attributes={"tool": request.name}))
        result = tool.run(request.input)
        emit_event(TelemetryEvent(name="tool_complete", attributes={"tool": request.name, "cost": result.cost_usd}))
        return result


default_tool_runtime = ToolRuntime()
default_tool_runtime.register(PythonSandboxTool())
default_tool_runtime.register(WebSearchTool())
default_tool_runtime.register(WebScrapeTool())
default_tool_runtime.register(VideoGenerationTool(provider_name=settings.video_provider_default))
default_tool_runtime.register(TTSTool(provider_name="elevenlabs"))

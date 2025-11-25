"""Provider abstractions for LLM/video APIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import asyncio
from uuid import uuid4

from .config import settings
from .instrumentation import get_logger

logger = get_logger()


class LLMProvider(Protocol):
    """Protocol for LLM completion providers."""

    name: str

    async def complete(self, prompt: str, *, temperature: float = 0.2) -> str:  # pragma: no cover - protocol
        ...


@dataclass(slots=True)
class EchoLLMProvider:
    """Simple provider that echoes prompts for deterministic tests."""

    name: str = settings.llm_provider.name

    async def complete(self, prompt: str, *, temperature: float = 0.2) -> str:
        return f"[{self.name}::temp={temperature}] {prompt.strip()}"


@dataclass(slots=True)
class OpenRouterLLMProvider:
    """LLM provider that forwards requests to OpenRouter."""

    api_key: str
    model: str = "gpt-4o-mini"
    base_url: str = "https://openrouter.ai/api/v1"
    name: str = "openrouter"

    async def complete(self, prompt: str, *, temperature: float = 0.2) -> str:
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": "You are the Lewis AI System reasoning engine."},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            client_kwargs = {"timeout": 60}
            if settings.httpx_proxies:
                client_kwargs["proxy"] = settings.httpx_proxies
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network failure path
            raise RuntimeError(f"OpenRouter request failed: {exc}") from exc

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover - defensive
            raise RuntimeError("Malformed OpenRouter response") from exc


def _build_default_llm_provider() -> LLMProvider:
    if settings.llm_provider_mode == "openrouter":
        if not settings.openrouter_api_key:
            logger.warning("LLM_PROVIDER_MODE=openrouter but OPENROUTER_API_KEY missing; falling back to mock provider.")
            return EchoLLMProvider()
        return OpenRouterLLMProvider(api_key=settings.openrouter_api_key)
    return EchoLLMProvider()


default_llm_provider: LLMProvider = _build_default_llm_provider()


# ============================================================================
# Video Generation Providers
# ============================================================================


class VideoGenerationProvider(Protocol):
    """Protocol for video generation providers."""

    name: str

    async def generate_video(
        self,
        prompt: str,
        *,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        quality: str = "preview",
    ) -> dict[str, str]:
        """Generate video and return metadata including URL.
        
        Returns:
            dict with keys: 'video_url', 'status', 'job_id', etc.
        """
        ...


@dataclass(slots=True)
class RunwayVideoProvider:
    """Runway Gen-3 video generation provider."""

    api_key: str
    base_url: str = "https://api.runwayml.com/v1"
    name: str = "runway"

    async def generate_video(
        self,
        prompt: str,
        *,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        quality: str = "preview",
    ) -> dict[str, str]:
        """Submit video generation job to Runway API."""
        payload = {
            "prompt": prompt,
            "duration": duration_seconds,
            "aspect_ratio": aspect_ratio,
            "quality": quality,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            client_kwargs = {"timeout": 120}
            if settings.httpx_proxies:
                client_kwargs["proxy"] = settings.httpx_proxies
            async with httpx.AsyncClient(**client_kwargs) as client:
                # Submit generation job
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/generations",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                
                job_id = data.get("id")
                if not job_id:
                    raise RuntimeError("No job_id in Runway response")
                
                # Poll for completion (simplified for MVP)
                return {
                    "video_url": data.get("output_url", ""),
                    "status": data.get("status", "processing"),
                    "job_id": job_id,
                    "provider": self.name,
                }
        except httpx.HTTPError as exc:
            logger.error(f"Runway API request failed: {exc}")
            raise RuntimeError(f"Runway video generation failed: {exc}") from exc


@dataclass(slots=True)
class RunwareVideoProvider:
    """Runware REST provider using the task-based API."""

    api_key: str
    base_url: str = "https://api.runware.ai/v1"
    default_model: str = "klingai:5@3"
    poll_interval_seconds: float = 5.0
    max_poll_attempts: int = 24
    name: str = "runware"

    async def generate_video(
        self,
        prompt: str,
        *,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        quality: str = "preview",
    ) -> dict[str, str]:
        """Submit videoInference job and poll for completion."""

        width, height = self._aspect_ratio_to_resolution(aspect_ratio)
        task_uuid = str(uuid4())
        payload = [
            {
                "taskType": "videoInference",
                "taskUUID": task_uuid,
                "positivePrompt": prompt,
                "model": self.default_model,
                "duration": duration_seconds,
                "width": width,
                "height": height,
                "outputType": "URL",
                "format": "MP4",
                "deliveryMethod": "async",
                "numberResults": 1,
                "includeCost": quality != "preview",
            }
        ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        client_kwargs: dict[str, object] = {"timeout": 120}
        if settings.httpx_proxies:
            client_kwargs["proxy"] = settings.httpx_proxies

        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.post(self.base_url, json=payload, headers=headers)
            if response.status_code != 200:
                error_body = response.text
                raise RuntimeError(f"Runware API returned {response.status_code}: {error_body}")
            submission = response.json()
            if errors := submission.get("errors"):
                raise RuntimeError(f"Runware task submission failed: {errors}")

            poll_payload = [{"taskType": "getResponse", "taskUUID": task_uuid}]
            for _ in range(self.max_poll_attempts):
                await asyncio.sleep(self.poll_interval_seconds)
                poll_response = await client.post(self.base_url, json=poll_payload, headers=headers)
                poll_response.raise_for_status()
                poll_data = poll_response.json()
                if errors := poll_data.get("errors"):
                    raise RuntimeError(f"Runware polling failed: {errors}")
                entry = self._extract_entry(poll_data, task_uuid)
                if not entry:
                    continue
                if entry.get("status") == "success":
                    return {
                        "video_url": entry.get("videoURL", ""),
                        "status": entry.get("status", "unknown"),
                        "job_id": task_uuid,
                        "provider": self.name,
                    }
                if entry.get("status") == "processing":
                    continue
            raise RuntimeError("Runware video generation timed out before completion")

    @staticmethod
    def _aspect_ratio_to_resolution(aspect_ratio: str) -> tuple[int, int]:
        presets = {
            "16:9": (1280, 720),
            "9:16": (720, 1280),
            "4:3": (1024, 768),
            "1:1": (768, 768),
        }
        if aspect_ratio in presets:
            return presets[aspect_ratio]
        try:
            left, right = (int(part) for part in aspect_ratio.split(":", 1))
            height = 720 - (720 % 8)
            width = int(height * (left / right))
            width -= width % 8
            return max(width, 8), max(height, 8)
        except Exception:  # pragma: no cover - defensive fallback
            return presets["16:9"]

    @staticmethod
    def _extract_entry(payload: dict[str, object], task_uuid: str) -> dict[str, object] | None:
        for item in payload.get("data", []) or []:
            if isinstance(item, dict) and item.get("taskUUID") == task_uuid:
                return item
        return None

@dataclass(slots=True)
class DoubaoVideoProvider:
    """Doubao (豆包) video generation provider using Seedance model.
    
    Reference: https://www.volcengine.com/docs/82379/1520757
    """

    api_key: str
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3/contents"
    model: str = "doubao-seedance-1-0-pro-fast-251015"
    poll_interval_seconds: float = 5.0
    max_poll_attempts: int = 60  # 最多等待5分钟
    name: str = "doubao"

    async def generate_video(
        self,
        prompt: str,
        *,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        quality: str = "preview",
    ) -> dict[str, str]:
        """Submit video generation job to Doubao API and poll for completion.
        
        According to official docs: https://www.volcengine.com/docs/82379/1520757
        """
        # Build payload according to official API (https://www.volcengine.com/docs/82379/1520757)
        payload: dict[str, Any] = {
            "model": self.model,
            "content": [
                {
                    "type": "text",
                    "text": prompt,
                }
            ],
            "ratio": aspect_ratio,
            "duration": max(1, int(duration_seconds)),
            "framespersecond": 24,
            "watermark": False,
            # Resolution defaults to 720p if not specified; allow doc defaults to take over.
        }
        
        # Doubao API also accepts callback_url/return_last_frame etc. when needed.
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        client_kwargs: dict[str, object] = {"timeout": 300}
        if settings.httpx_proxies:
            client_kwargs["proxy"] = settings.httpx_proxies
        
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                # Submit job - 根据官方文档，端点是 /generations/tasks
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/generations/tasks",
                    json=payload,
                    headers=headers,
                )
                
                if response.status_code != 200:
                    error_body = response.text
                    logger.error(f"Doubao API error: {response.status_code} - {error_body}")
                    raise RuntimeError(f"Doubao API returned {response.status_code}: {error_body}")
                
                data = response.json()
                
                # 根据官方文档，响应可能包含 task_id 或直接返回结果
                task_id = data.get("id") or data.get("task_id") or data.get("taskId")
                
                if not task_id:
                    # 如果同步返回视频URL（某些情况下可能直接返回）
                    if "video_url" in data or "output_url" in data or "videoUrl" in data:
                        return {
                            "video_url": data.get("video_url") or data.get("output_url") or data.get("videoUrl", ""),
                            "status": "completed",
                            "job_id": data.get("task_id", ""),
                            "provider": self.name,
                        }
                    raise RuntimeError(f"No task_id in Doubao response: {data}")
                
                # Poll for completion - 根据官方文档轮询任务状态
                for attempt in range(self.max_poll_attempts):
                    await asyncio.sleep(self.poll_interval_seconds)
                    
                    # 轮询任务状态
                    poll_response = await client.get(
                        f"{self.base_url.rstrip('/')}/generations/tasks/{task_id}",
                        headers=headers,
                    )
                    
                    if poll_response.status_code == 404:
                        # 任务不存在，可能已完成或失败
                        logger.warning(f"Task {task_id} not found, may be completed")
                        continue
                    
                    poll_response.raise_for_status()
                    poll_data = poll_response.json()
                    
                    status = (poll_data.get("status") or "").lower()
                    if status in ["completed", "success", "done", "succeeded"]:
                        content_block = poll_data.get("content") or {}
                        if not isinstance(content_block, dict):
                            content_block = {}
                        video_url = (
                            content_block.get("video_url")
                            or content_block.get("videoUrl")
                            or poll_data.get("video_url")
                            or poll_data.get("output_url")
                            or ""
                        )
                        if not video_url:
                            raise RuntimeError("Doubao returned success without video_url")
                        last_frame_url = (
                            content_block.get("last_frame_url")
                            or content_block.get("lastFrameUrl")
                            or ""
                        )
                        normalized_status = "completed"
                        return {
                            "video_url": video_url,
                            "status": normalized_status,
                            "job_id": task_id,
                            "provider": self.name,
                            "last_frame_url": last_frame_url,
                        }
                    elif status in ["failed", "error", "failure"]:
                        error_block = poll_data.get("error") or {}
                        error_msg = (
                            (error_block or {}).get("message")
                            or (error_block or {}).get("msg")
                            or poll_data.get("error")
                            or poll_data.get("message")
                            or poll_data.get("error_message")
                            or "Unknown error"
                        )
                        raise RuntimeError(f"Doubao video generation failed: {error_msg}")
                    elif status in ["processing", "pending", "running", "in_progress", "queued"]:
                        logger.debug(f"Doubao task {task_id} status: {status}, waiting...")
                        continue
                    else:
                        logger.warning(f"Unknown status '{status}' for task {task_id}, continuing to poll...")
                        continue
                
                raise RuntimeError(f"Doubao video generation timed out after {self.max_poll_attempts} attempts ({(self.max_poll_attempts * self.poll_interval_seconds) / 60:.1f} minutes)")
                
        except httpx.HTTPError as exc:
            logger.error(f"Doubao API request failed: {exc}")
            raise RuntimeError(f"Doubao video generation failed: {exc}") from exc


@dataclass(slots=True)
class PikaVideoProvider:
    """Pika Labs video generation provider."""

    api_key: str
    base_url: str = "https://api.pika.art/v1"
    name: str = "pika"

    async def generate_video(
        self,
        prompt: str,
        *,
        duration_seconds: int = 3,
        aspect_ratio: str = "16:9",
        quality: str = "preview",
    ) -> dict[str, str]:
        """Submit video generation job to Pika API."""
        payload = {
            "prompt": prompt,
            "duration": duration_seconds,
            "aspect_ratio": aspect_ratio,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            client_kwargs = {"timeout": 120}
            if settings.httpx_proxies:
                client_kwargs["proxy"] = settings.httpx_proxies
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/generate",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                
                return {
                    "video_url": data.get("video_url", ""),
                    "status": data.get("status", "processing"),
                    "job_id": data.get("job_id", ""),
                    "provider": self.name,
                }
        except httpx.HTTPError as exc:
            logger.error(f"Pika API request failed: {exc}")
            raise RuntimeError(f"Pika video generation failed: {exc}") from exc


@dataclass(slots=True)
class MockVideoProvider:
    """Mock video provider for testing."""

    name: str = "mock_video"

    async def generate_video(
        self,
        prompt: str,
        *,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        quality: str = "preview",
    ) -> dict[str, str]:
        """Return mock video generation result."""
        import hashlib
        job_id = hashlib.md5(prompt.encode()).hexdigest()[:12]
        return {
            "video_url": f"https://mock.video/{job_id}.mp4",
            "status": "completed",
            "job_id": job_id,
            "provider": self.name,
            "prompt": prompt,
            "duration": duration_seconds,
        }


def get_video_provider(provider_name: str = "runway") -> VideoGenerationProvider:
    """Factory function to get video provider by name."""
    if provider_name == "runway" and settings.runway_api_key:
        return RunwayVideoProvider(api_key=settings.runway_api_key)
    elif provider_name == "pika" and settings.pika_api_key:
        return PikaVideoProvider(api_key=settings.pika_api_key)
    elif provider_name == "runware" and settings.runware_api_key:
        return RunwareVideoProvider(api_key=settings.runware_api_key)
    elif provider_name == "doubao" and settings.doubao_api_key:
        return DoubaoVideoProvider(api_key=settings.doubao_api_key)
    else:
        logger.warning(f"Video provider '{provider_name}' not configured; using mock provider.")
        return MockVideoProvider()


# ============================================================================
# TTS (Text-to-Speech) Providers
# ============================================================================


class TTSProvider(Protocol):
    """Protocol for text-to-speech providers."""

    name: str

    async def synthesize(self, text: str, *, voice: str = "default") -> dict[str, str]:
        """Synthesize speech from text.
        
        Returns:
            dict with keys: 'audio_url', 'duration_ms', etc.
        """
        ...


@dataclass(slots=True)
class ElevenLabsTTSProvider:
    """ElevenLabs text-to-speech provider."""

    api_key: str
    base_url: str = "https://api.elevenlabs.io/v1"
    name: str = "elevenlabs"

    async def synthesize(self, text: str, *, voice: str = "default") -> dict[str, str]:
        """Generate speech using ElevenLabs API."""
        voice_id = voice if voice != "default" else "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
        
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5,
            }
        }
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        
        try:
            client_kwargs = {"timeout": 60}
            if settings.httpx_proxies:
                client_kwargs["proxy"] = settings.httpx_proxies
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/text-to-speech/{voice_id}",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                
                # ElevenLabs returns audio bytes directly
                audio_data = response.content
                # In production, upload to S3 and return URL
                return {
                    "audio_url": f"data:audio/mpeg;base64,{audio_data[:100].hex()}",  # Simplified
                    "duration_ms": len(text) * 50,  # Rough estimate
                    "provider": self.name,
                }
        except httpx.HTTPError as exc:
            logger.error(f"ElevenLabs API request failed: {exc}")
            raise RuntimeError(f"TTS synthesis failed: {exc}") from exc


@dataclass(slots=True)
class MockTTSProvider:
    """Mock TTS provider for testing."""

    name: str = "mock_tts"

    async def synthesize(self, text: str, *, voice: str = "default") -> dict[str, str]:
        """Return mock TTS result."""
        import hashlib
        audio_id = hashlib.md5(text.encode()).hexdigest()[:12]
        return {
            "audio_url": f"https://mock.audio/{audio_id}.mp3",
            "duration_ms": len(text) * 50,
            "provider": self.name,
            "text": text[:50],
        }


def get_tts_provider(provider_name: str = "elevenlabs") -> TTSProvider:
    """Factory function to get TTS provider by name."""
    if provider_name == "elevenlabs" and settings.elevenlabs_api_key:
        return ElevenLabsTTSProvider(api_key=settings.elevenlabs_api_key)
    else:
        logger.warning(f"TTS provider '{provider_name}' not configured; using mock provider.")
        return MockTTSProvider()


# ============================================================================
# Search Providers
# ============================================================================


class SearchProvider(Protocol):
    """Protocol for web search providers."""

    name: str

    async def search(self, query: str) -> str:
        """Perform a web search and return a summary string."""
        ...


@dataclass(slots=True)
class TavilySearchProvider:
    """Tavily AI search provider."""

    api_key: str
    name: str = "tavily"
    base_url: str = "https://api.tavily.com"

    async def search(self, query: str) -> str:
        payload = {
            "query": query,
            "search_depth": "basic",
            "include_answer": True,
            "max_results": 5,
        }
        headers = {"Content-Type": "application/json"}
        
        # Tavily accepts API key in payload or header, using payload for simplicity with their client style
        # but here we use raw HTTP, so let's put it in payload as per docs
        payload["api_key"] = self.api_key

        try:
            client_kwargs = {"timeout": 30}
            if settings.httpx_proxies:
                client_kwargs["proxy"] = settings.httpx_proxies
                
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.post(f"{self.base_url}/search", json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                answer = data.get("answer", "")
                results = data.get("results", [])
                
                snippets = [f"- {r['title']}: {r['content']}" for r in results]
                combined = f"Answer: {answer}\n\nSources:\n" + "\n".join(snippets)
                return combined
        except httpx.HTTPError as exc:
            logger.error(f"Tavily search failed: {exc}")
            return f"Search failed: {exc}"


@dataclass(slots=True)
class MockSearchProvider:
    """Mock search provider."""
    
    name: str = "mock_search"
    
    async def search(self, query: str) -> str:
        return f"Mock search results for: {query}"


def get_search_provider(provider_name: str | None = None) -> SearchProvider:
    name = (provider_name or "").lower()

    if name == "mock":
        return MockSearchProvider()

    if name == "tavily":
        if not settings.tavily_api_key:
            raise RuntimeError("Tavily provider requested but TAVILY_API_KEY is not configured")
        return TavilySearchProvider(api_key=settings.tavily_api_key)

    if settings.tavily_api_key:
        return TavilySearchProvider(api_key=settings.tavily_api_key)

    return MockSearchProvider()


# ============================================================================
# Sandbox Providers
# ============================================================================


class SandboxProvider(Protocol):
    """Protocol for code execution sandboxes."""
    
    name: str
    
    async def run_code(self, code: str) -> dict[str, Any]:
        """Execute code and return stdout/stderr/result."""
        ...


@dataclass(slots=True)
class E2BSandboxProvider:
    """E2B cloud sandbox provider."""
    
    api_key: str
    name: str = "e2b"
    
    async def run_code(self, code: str) -> dict[str, Any]:
        # Note: This requires the 'e2b_code_interpreter' package installed
        try:
            from e2b_code_interpreter import Sandbox
            
            # Sandbox.create appears to be synchronous in this version
            sandbox = Sandbox.create(api_key=self.api_key)
            
            try:
                execution = sandbox.run_code(code)
            finally:
                sandbox.kill()
            
            return {
                "stdout": "".join(execution.logs.stdout),
                "stderr": "".join(execution.logs.stderr),
                "results": [r.text for r in execution.results] if execution.results else [],
                "error": execution.error.name if execution.error else None
            }
        except ImportError:
            return {"error": "e2b_code_interpreter package not installed"}
        except Exception as e:
            logger.error(f"E2B execution failed: {e}")
            return {"error": str(e)}


@dataclass(slots=True)
class LocalSandboxProvider:
    """Local Python execution (fallback)."""
    
    name: str = "local"
    
    async def run_code(self, code: str) -> dict[str, Any]:
        # Re-using the logic from tooling.py's PythonSandboxTool but decoupled
        # For now, we'll just return a placeholder as the logic is currently embedded in the tool
        # Ideally, tooling.py should delegate to this.
        return {"error": "Local sandbox logic is currently embedded in PythonSandboxTool"}


def get_sandbox_provider() -> SandboxProvider:
    if settings.e2b_api_key:
        return E2BSandboxProvider(api_key=settings.e2b_api_key)
    return LocalSandboxProvider()


# ============================================================================
# Scrape Providers
# ============================================================================


class ScrapeProvider(Protocol):
    """Protocol for web scraping."""
    
    name: str
    
    async def scrape(self, url: str) -> str:
        """Scrape content from a URL."""
        ...


@dataclass(slots=True)
class FirecrawlScrapeProvider:
    """Firecrawl scraping provider."""
    
    api_key: str
    name: str = "firecrawl"
    base_url: str = "https://api.firecrawl.dev/v0"
    
    async def scrape(self, url: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"url": url}
        
        try:
            client_kwargs = {"timeout": 60}
            if settings.httpx_proxies:
                client_kwargs["proxy"] = settings.httpx_proxies
                
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.post(f"{self.base_url}/scrape", json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                if not data.get("success"):
                    raise RuntimeError(f"Firecrawl failed: {data.get('error')}")
                
                return data.get("data", {}).get("markdown", "")
        except httpx.HTTPError as exc:
            logger.error(f"Firecrawl scrape failed: {exc}")
            return f"Scrape failed: {exc}"


@dataclass(slots=True)
class MockScrapeProvider:
    name: str = "mock_scrape"
    
    async def scrape(self, url: str) -> str:
        return f"Mock scraped content for {url}"


def get_scrape_provider(provider_name: str | None = None) -> ScrapeProvider:
    name = (provider_name or "").lower()
    if name == "mock":
        return MockScrapeProvider()
    if name == "firecrawl":
        if not settings.firecrawl_api_key:
            raise RuntimeError("Firecrawl provider requested but FIRECRAWL_API_KEY is not configured")
        return FirecrawlScrapeProvider(api_key=settings.firecrawl_api_key)
    if settings.firecrawl_api_key:
        return FirecrawlScrapeProvider(api_key=settings.firecrawl_api_key)
    return MockScrapeProvider()

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

    async def generate_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None
    ) -> dict[str, Any]:  # pragma: no cover - protocol
        """Generate completion with message history and optional structured output."""
        ...

    async def analyze_image(
        self,
        image_url: str,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int | None = None
    ) -> dict[str, Any]:  # pragma: no cover - protocol
        """Analyze image content with multimodal capabilities."""
        ...


@dataclass
class EchoLLMProvider:
    """Simple provider that echoes prompts for deterministic tests."""

    name: str = settings.llm_provider.name

    async def complete(self, prompt: str, *, temperature: float = 0.2) -> str:
        return f"[{self.name}::temp={temperature}] {prompt.strip()} | \u5b66\u4e60 \u6559\u7a0b \u6559\u80b2"

    async def generate_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Mock implementation for testing."""
        last_message = messages[-1]["content"] if messages else ""
        return {
            "content": f"[MOCK::{self.name}] {last_message.strip()}",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }

    async def analyze_image(
        self,
        image_url: str,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int | None = None
    ) -> dict[str, Any]:
        """Mock image analysis for testing."""
        return {
            "content": f"[MOCK_IMAGE_ANALYSIS] {prompt[:50]}... for image: {image_url}",
            "image_url": image_url,
            "model": self.name,
        }


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
            client_kwargs: dict[str, object] = {"timeout": 60}
            if settings.httpx_proxies:
                client_kwargs["proxy"] = settings.httpx_proxies  # type: ignore
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

    async def generate_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Generate completion with message history."""
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": messages,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if response_format:
            payload["response_format"] = response_format

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
        except httpx.HTTPError as exc:
            raise RuntimeError(f"OpenRouter request failed: {exc}") from exc

        data = response.json()
        try:
            return {
                "content": data["choices"][0]["message"]["content"].strip(),
                "usage": data.get("usage", {}),
            }
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Malformed OpenRouter response") from exc

    async def analyze_image(
        self,
        image_url: str,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int | None = None
    ) -> dict[str, Any]:
        """Analyze image using vision-capable models via OpenRouter."""
        # Note: OpenRouter may not support all vision models, this is a fallback
        messages = [
            {
                "role": "system",
                "content": "You are a professional visual analyst."
            },
            {
                "role": "user",
                "content": f"Analyze this image: {image_url}\n\n{prompt}"
            }
        ]

        result = await self.generate_completion(
            messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        return {
            "content": result["content"],
            "image_url": image_url,
            "model": self.model,
        }


@dataclass(slots=True)
class GeminiLLMProvider:
    """LLM provider that forwards requests to Google Gemini via OpenRouter.
    
    Enhanced for creative content analysis, consistency control, and multimodal understanding.
    """

    api_key: str
    model: str = "google/gemini-2.5-flash-lite-preview-09-2025"
    base_url: str = "https://openrouter.ai/api/v1"
    name: str = "gemini"
    max_tokens: int = 8192
    timeout: int = 120

    async def complete(self, prompt: str, *, temperature: float = 0.2) -> str:
        """Basic text completion."""
        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": "You are Lewis AI System reasoning engine, specialized in creative content analysis and consistency control."},
                {"role": "user", "content": prompt},
            ],
        }
        return await self._make_request(payload)

    async def generate_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Generate completion with message history and optional structured output.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            response_format: Optional JSON schema for structured output
            
        Returns:
            Dict with 'content', 'usage', and other metadata
        """
        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": messages,
        }
        
        if response_format:
            payload["response_format"] = response_format
            
        response_text = await self._make_request(payload)
        
        # Parse usage information if available
        usage = {}
        try:
            # This would be populated from actual API response
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        except (KeyError, TypeError):
            pass
            
        return {
            "content": response_text,
            "usage": usage,
            "model": self.model,
        }

    async def analyze_image(
        self,
        image_url: str,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int | None = None
    ) -> dict[str, Any]:
        """Analyze image content with multimodal capabilities.
        
        Args:
            image_url: URL of the image to analyze
            prompt: Analysis prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Analysis result with content and metadata
        """
        messages = [
            {
                "role": "system", 
                "content": "You are a professional visual analyst specializing in character and scene feature extraction for video consistency control."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]
        
        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": messages,
        }
        
        response_text = await self._make_request(payload)
        
        return {
            "content": response_text,
            "image_url": image_url,
            "model": self.model,
        }

    async def batch_analyze(
        self,
        items: list[dict[str, Any]],
        analysis_type: str = "consistency"
    ) -> list[dict[str, Any]]:
        """Batch analyze multiple items for efficiency.
        
        Args:
            items: List of items to analyze (images, texts, etc.)
            analysis_type: Type of analysis to perform
            
        Returns:
            List of analysis results
        """
        if analysis_type == "consistency":
            return await self._batch_consistency_analysis(items)
        elif analysis_type == "quality":
            return await self._batch_quality_analysis(items)
        else:
            # Generic batch processing
            results = []
            for item in items:
                try:
                    if isinstance(item, str) and item.startswith("http"):
                        # Assume it's an image URL
                        result = await self.analyze_image(
                            item, 
                            "Analyze this image for key features."
                        )
                    else:
                        # Assume it's text
                        result = await self.complete(str(item))
                        result = {"content": result}
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to analyze item {item}: {e}")
                    results.append({"content": "", "error": str(e)})
            return results

    async def _make_request(self, payload: dict[str, Any]) -> str:
        """Make HTTP request to OpenRouter API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        client_kwargs = {"timeout": self.timeout}
        if settings.httpx_proxies:
            client_kwargs["proxy"] = settings.httpx_proxies
            
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Malformed Gemini response") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Gemini API request failed: {exc}") from exc

    async def _batch_consistency_analysis(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Specialized batch analysis for consistency evaluation."""
        # For consistency analysis, we need to compare multiple items
        if len(items) < 2:
            return [{"content": "Insufficient items for consistency analysis", "score": 1.0}]
        
        # Build comparison prompt
        prompt = f"""
        Analyze consistency across these {len(items)} visual items.
        
        Items to analyze:
        {chr(10).join(f"{i+1}. {item.get('url', item.get('content', ''))}" for i, item in enumerate(items))}
        
        Evaluate:
        1. Character consistency (facial features, clothing, proportions)
        2. Scene continuity (lighting, background, camera angles)
        3. Style consistency (artistic style, color palette, quality)
        
        Return JSON with:
        {{
            "overall_score": float (0.0-1.0),
            "character_consistency": float (0.0-1.0),
            "scene_consistency": float (0.0-1.0),
            "style_consistency": float (0.0-1.0),
            "issues": [string],
            "recommendations": [string]
        }}
        """
        
        try:
            response = await self.complete(prompt, temperature=0.1)
            # Try to parse JSON response
            import json
            import re
            
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                return [parsed]
            else:
                # Fallback to text analysis
                return [{"content": response, "score": 0.7}]
        except Exception as e:
            logger.error(f"Batch consistency analysis failed: {e}")
            return [{"content": f"Analysis failed: {e}", "score": 0.5}]

    async def _batch_quality_analysis(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Specialized batch analysis for quality evaluation."""
        results = []
        for item in items:
            try:
                if item.get("url"):
                    result = await self.analyze_image(
                        item["url"],
                        "Evaluate the visual quality of this image. Consider composition, clarity, lighting, and overall appeal. Return a score from 0.0 to 1.0."
                    )
                else:
                    result = await self.complete(
                        f"Evaluate the quality of this content: {item.get('content', '')}. Return a score from 0.0 to 1.0."
                    )
                    result = {"content": result}
                
                # Extract score if present
                content = result.get("content", "")
                score = 0.7  # default
                import re
                score_match = re.search(r'0\.\d+|1\.0|0\.0', content)
                if score_match:
                    try:
                        score = float(score_match.group())
                    except ValueError:
                        pass
                
                result["score"] = score
                results.append(result)
                
            except Exception as e:
                logger.error(f"Quality analysis failed for item {item}: {e}")
                results.append({"content": f"Analysis failed: {e}", "score": 0.5})
        
        return results


def _build_default_llm_provider() -> LLMProvider:
    if settings.llm_provider_mode == "openrouter":
        if not settings.openrouter_api_key:
            logger.warning("LLM_PROVIDER_MODE=openrouter but OPENROUTER_API_KEY missing; falling back to mock provider.")
            return EchoLLMProvider()
        return OpenRouterLLMProvider(api_key=settings.openrouter_api_key)
    elif settings.llm_provider_mode == "gemini":
        if not settings.openrouter_api_key:
            logger.warning("LLM_PROVIDER_MODE=gemini but OPENROUTER_API_KEY missing; falling back to mock provider.")
            return EchoLLMProvider()
        return GeminiLLMProvider(api_key=settings.openrouter_api_key)
    return EchoLLMProvider()


default_llm_provider: LLMProvider = _build_default_llm_provider()


def get_llm_provider(provider_name: str = "default") -> LLMProvider:
    """Factory function to get LLM provider by name."""
    if provider_name == "default":
        return default_llm_provider
    elif provider_name == "gemini" or provider_name == "gemini-2.5-flash-lite":
        if not settings.openrouter_api_key:
            logger.warning("Gemini provider requested but OPENROUTER_API_KEY missing; falling back to mock provider.")
            return EchoLLMProvider()
        return GeminiLLMProvider(api_key=settings.openrouter_api_key)
    elif provider_name == "openrouter":
        if not settings.openrouter_api_key:
            logger.warning("OpenRouter provider requested but OPENROUTER_API_KEY missing; falling back to mock provider.")
            return EchoLLMProvider()
        return OpenRouterLLMProvider(api_key=settings.openrouter_api_key)
    else:
        logger.warning(f"Unknown LLM provider '{provider_name}'; using default provider.")
        return default_llm_provider


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
        # 新增参数支持一致性控制
        reference_image: str | None = None,
        consistency_seed: int | None = None,
        character_prompt: str | None = None,
    ) -> dict[str, str]:
        """Generate video and return metadata including URL.
        
        Args:
            prompt: Text description of the video to generate
            duration_seconds: Duration in seconds
            aspect_ratio: Video aspect ratio (e.g., "16:9")
            quality: Video quality ("preview" or "final")
            reference_image: Optional reference image URL for consistency
            consistency_seed: Optional seed for consistent generation
            character_prompt: Optional character consistency prompt
        
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
        # 新增参数（Runway可能不支持，但需要接口兼容）
        reference_image: str | None = None,
        consistency_seed: int | None = None,
        character_prompt: str | None = None,
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
        # 新增参数（Runware可能不支持，但需要接口兼容）
        reference_image: str | None = None,
        consistency_seed: int | None = None,
        character_prompt: str | None = None,
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
        # 新增参数支持一致性控制
        reference_image: str | None = None,
        consistency_seed: int | None = None,
        character_prompt: str | None = None,
    ) -> dict[str, str]:
        """Submit video generation job to Doubao API and poll for completion.
        
        According to official docs: https://www.volcengine.com/docs/82379/1520757
        """
        # Build payload according to official API (https://www.volcengine.com/docs/82379/1520757)
        content = []
        
        # 添加文本内容
        content.append({
            "type": "text", 
            "text": prompt
        })
        
        # 添加首帧图片（如果提供）
        if reference_image:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": reference_image
                }
            })
        
        # 添加角色一致性提示（如果提供）
        if character_prompt:
            content.append({
                "type": "text",
                "text": f"\n\nCharacter consistency requirements: {character_prompt}"
            })
        
        payload: dict[str, Any] = {
            "model": self.model,
            "content": content,
            "ratio": aspect_ratio,
            "duration": max(1, int(duration_seconds)),
            "framespersecond": 24,
            "watermark": False,
            # Resolution defaults to 720p if not specified; allow doc defaults to take over.
        }
        
        # 添加一致性种子（如果提供）
        if consistency_seed:
            payload["seed"] = consistency_seed
        
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
        # 新增参数（Pika可能不支持，但需要接口兼容）
        reference_image: str | None = None,
        consistency_seed: int | None = None,
        character_prompt: str | None = None,
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
        # 新增参数（Mock Provider支持用于测试）
        reference_image: str | None = None,
        consistency_seed: int | None = None,
        character_prompt: str | None = None,
    ) -> dict[str, str]:
        """Return mock video generation result."""
        import hashlib
        
        # 构建包含一致性信息的prompt用于生成唯一ID
        enhanced_prompt = prompt
        if character_prompt:
            enhanced_prompt += f" | Character: {character_prompt}"
        if reference_image:
            enhanced_prompt += f" | Reference: {reference_image}"
        if consistency_seed:
            enhanced_prompt += f" | Seed: {consistency_seed}"
            
        job_id = hashlib.md5(enhanced_prompt.encode()).hexdigest()[:12]
        return {
            "video_url": f"https://mock.video/{job_id}.mp4",
            "status": "completed",
            "job_id": job_id,
            "provider": self.name,
            "prompt": prompt,
            "duration": duration_seconds,
            "reference_image": reference_image,
            "consistency_seed": consistency_seed,
            "character_prompt": character_prompt,
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

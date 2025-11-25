"""真实的图片生成集成 - DALL-E 3 / Replicate / Stable Diffusion"""

from __future__ import annotations

import httpx
from typing import Literal

from ..config import settings
from ..instrumentation import get_logger

logger = get_logger()


class ImageGenerationError(Exception):
    """图片生成失败异常"""
    pass


async def generate_storyboard_image(
    description: str,
    style: Literal["sketch", "cinematic", "comic", "realistic"] = "sketch",
    size: tuple[int, int] = (1024, 576),
) -> str:
    """
    生成分镜图片 (支持多个 Provider)
    
    优先级: DALL-E 3 > Replicate > Stable Diffusion > Mock
    
    Args:
        description: 场景描述
        style: 风格 (sketch=草图, cinematic=电影感, comic=漫画, realistic=写实)
        size: 尺寸 (宽, 高)
    
    Returns:
        生成图片的 URL
    """
    
    # 构造风格化提示词
    style_prompts = {
        "sketch": "professional storyboard sketch, clean linework, black and white",
        "cinematic": "cinematic shot, dramatic lighting, film composition",
        "comic": "comic book style, bold inks, dynamic composition",
        "realistic": "photorealistic, high detail, professional photography"
    }
    
    full_prompt = f"{style_prompts.get(style, style_prompts['sketch'])}: {description}"
    
    # 1. 尝试 DALL-E 3 (通过 OpenAI API)
    if hasattr(settings, 'openai_api_key') and settings.openai_api_key:
        try:
            return await _generate_with_dalle3(full_prompt, size)
        except Exception as e:
            logger.warning(f"DALL-E 3 生成失败,尝试 Fallback: {e}")
    
    # 2. 尝试 Replicate (Stable Diffusion XL)
    if hasattr(settings, 'replicate_api_key') and settings.replicate_api_key:
        try:
            return await _generate_with_replicate(full_prompt, size)
        except Exception as e:
            logger.warning(f"Replicate 生成失败,尝试 Fallback: {e}")
    
    # 3. 开发环境 Fallback
    if settings.environment != "production":
        logger.info("使用 Mock 图片生成 (开发模式)")
        return _generate_mock_image(description, size)
    
    # 4. 生产环境强制要求配置
    raise ImageGenerationError(
        "生产环境必须配置图片生成 API Key! "
        "请设置 OPENAI_API_KEY 或 REPLICATE_API_KEY"
    )


async def _generate_with_dalle3(prompt: str, size: tuple[int, int]) -> str:
    """使用 OpenAI DALL-E 3 生成图片"""
    from openai import AsyncOpenAI
    
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    # DALL-E 3 只支持特定尺寸
    dalle_size = "1792x1024" if size[0] > size[1] else "1024x1792"
    if abs(size[0] - size[1]) < 200:
        dalle_size = "1024x1024"
    
    logger.info(f"调用 DALL-E 3 生成图片: {prompt[:50]}...")
    
    response = await client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size=dalle_size,
        quality="standard",  # "standard" 或 "hd"
        n=1,
    )
    
    image_url = response.data[0].url
    logger.info(f"DALL-E 3 生成成功: {image_url}")
    
    return image_url


async def _generate_with_replicate(prompt: str, size: tuple[int, int]) -> str:
    """使用 Replicate (Stable Diffusion XL) 生成图片"""
    
    logger.info(f"调用 Replicate SDXL 生成图片: {prompt[:50]}...")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Replicate API 调用示例
        response = await client.post(
            "https://api.replicate.com/v1/predictions",
            headers={
                "Authorization": f"Token {settings.replicate_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "version": "39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",  # SDXL
                "input": {
                    "prompt": prompt,
                    "width": size[0],
                    "height": size[1],
                    "num_inference_steps": 25,
                },
            },
        )
        response.raise_for_status()
        prediction = response.json()
        
        # 轮询直到完成
        prediction_id = prediction["id"]
        get_url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        
        import asyncio
        for _ in range(60):  # 最多等待 60 秒
            await asyncio.sleep(1)
            status_response = await client.get(
                get_url,
                headers={"Authorization": f"Token {settings.replicate_api_key}"}
            )
            status_response.raise_for_status()
            result = status_response.json()
            
            if result["status"] == "succeeded":
                image_url = result["output"][0] if isinstance(result["output"], list) else result["output"]
                logger.info(f"Replicate 生成成功: {image_url}")
                return image_url
            elif result["status"] == "failed":
                raise ImageGenerationError(f"Replicate 生成失败: {result.get('error')}")
        
        raise ImageGenerationError("Replicate 生成超时")


def _generate_mock_image(description: str, size: tuple[int, int]) -> str:
    """生成 Mock 占位图 (仅用于开发/测试)"""
    import hashlib
    
    digest = hashlib.md5(description.encode()).hexdigest()[:8]
    width, height = size
    
    # 使用 placehold.co 服务生成占位图
    return f"https://placehold.co/{width}x{height}/1a1a1a/white?text=Storyboard+{digest}"


# 导出主函数
__all__ = ["generate_storyboard_image", "ImageGenerationError"]

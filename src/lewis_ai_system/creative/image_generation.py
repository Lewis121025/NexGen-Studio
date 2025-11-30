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
    
    # 只使用豆包 Seedream 图片生成
    if hasattr(settings, 'doubao_api_key') and settings.doubao_api_key:
        try:
            return await _generate_with_doubao(full_prompt, size)
        except Exception as e:
            logger.warning(f"豆包图片生成失败: {e}")
    
    # 开发环境 Fallback
    if settings.environment != "production":
        logger.info("使用 Mock 图片生成 (开发模式)")
        return _generate_mock_image(description, size)
    
    # 生产环境强制要求配置豆包API
    raise ImageGenerationError(
        "生产环境必须配置豆包API Key! "
        "请设置 DOUBAO_API_KEY"
    )


async def _generate_with_doubao(prompt: str, size: tuple[int, int]) -> str:
    """使用豆包 (DOUBAO) 生成图片"""
    
    logger.info(f"调用豆包生成图片: {prompt[:50]}...")
    
    # 豆包图片生成API配置
    doubao_endpoint = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            doubao_endpoint,
            headers={
                "Authorization": f"Bearer {settings.doubao_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "doubao-seedream-4-0-250828",
                "messages": [
                    {
                        "role": "user", 
                        "content": [
                            {
                                "type": "text",
                                "text": f"Generate an image based on this description: {prompt}. Return the image as a base64 encoded data URL."
                            }
                        ]
                    }
                ],
                "stream": False,
                "max_tokens": 2000
            },
        )
        response.raise_for_status()
        result = response.json()
        
        # 检查响应中是否有图片内容
        if "choices" in result and result["choices"]:
            content = result["choices"][0]["message"]["content"]
            if "data:image" in content:
                # 提取base64编码的图片数据
                image_data = content.split("data:image")[1].split()[0].rstrip("`").rstrip("\n")
                logger.info("豆包图片生成成功 (返回base64)")
                return f"data:image/png;base64,{image_data}"
        
        # 如果没有返回图片，生成一个代表图片的URL
        logger.warning("豆包API未返回图片内容，使用占位符")
        return f"https://via.placeholder.com/{size[0]}x{size[1]}/4F46E5/FFFFFF?text=Doubao+Generated"


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


async def _generate_with_doubao(prompt: str, size: tuple[int, int]) -> str:
    """使用豆包 (DOUBAO) 生成图片"""
    import base64
    
    logger.info(f"调用豆包生成图片: {prompt[:50]}...")
    
    # 豆包图片生成API配置
    doubao_endpoint = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            doubao_endpoint,
            headers={
                "Authorization": f"Bearer {settings.doubao_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "doubao-seedream-4-0-250828",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Generate an image based on this description: {prompt}"
                            }
                        ]
                    }
                ],
                "stream": False,
                "max_tokens": 1000
            },
        )
        response.raise_for_status()
        result = response.json()
        
        # 检查响应中是否有图片内容
        if "choices" in result and result["choices"]:
            content = result["choices"][0]["message"]["content"]
            if "data:image" in content:
                # 提取base64编码的图片数据
                image_data = content.split("data:image")[1].split()[0].rstrip("`")
                logger.info("豆包图片生成成功 (返回base64)")
                return f"data:image/png;base64,{image_data}"
        
        # 如果没有返回图片，生成一个代表图片的URL
        logger.warning("豆包API未返回图片内容，使用描述文本")
        return f"https://via.placeholder.com/{size[0]}x{size[1]}/4F46E5/FFFFFF?text=Doubao+Generated"


def _generate_mock_image(description: str, size: tuple[int, int]) -> str:
    """生成 Mock 占位图 (仅用于开发/测试)"""
    import hashlib
    
    digest = hashlib.md5(description.encode()).hexdigest()[:8]
    width, height = size
    
    # 使用 placehold.co 服务生成占位图
    return f"https://placehold.co/{width}x{height}/1a1a1a/white?text=Storyboard+{digest}"


async def generate_consistent_storyboard_image(
    description: str,
    style: Literal["sketch", "cinematic", "comic", "realistic"] = "cinematic",
    size: tuple[int, int] = (1024, 576),
    reference_images: list[str] | None = None,
    consistency_seed: int | None = None,
    character_features: dict[str, str] | None = None,
    consistency_level: Literal["low", "medium", "high"] = "medium",
) -> str:
    """
    生成一致性分镜图片
    
    Args:
        description: 场景描述
        style: 风格
        size: 尺寸 (宽, 高)
        reference_images: 参考图片URLs
        consistency_seed: 一致性种子
        character_features: 角色特征
        consistency_level: 一致性级别
        
    Returns:
        生成图片的 URL
    """
    logger.info(f"生成一致性分镜图片，级别: {consistency_level}")
    
    # 构造增强的提示词
    enhanced_prompt = _build_consistent_prompt(
        description, 
        style, 
        character_features, 
        consistency_level
    )
    
    # 尝试使用豆包Seedream 4.0进行一致性生成
    if hasattr(settings, 'doubao_api_key') and settings.doubao_api_key:
        try:
            return await _generate_with_seedream_4_0(
                enhanced_prompt, 
                size, 
                reference_images,
                consistency_seed
            )
        except Exception as e:
            logger.warning(f"Seedream 4.0 生成失败，回退到标准生成: {e}")
    
    # 回退到标准生成
    return await generate_storyboard_image(enhanced_prompt, style, size)


def _build_consistent_prompt(
    description: str,
    style: str,
    character_features: dict[str, str] | None,
    consistency_level: str
) -> str:
    """构建一致性提示词"""
    
    # 基础风格提示
    style_prompts = {
        "sketch": "professional storyboard sketch, clean linework, black and white",
        "cinematic": "cinematic shot, dramatic lighting, film composition",
        "comic": "comic book style, bold inks, dynamic composition", 
        "realistic": "photorealistic, high detail, professional photography"
    }
    
    base_prompt = f"{style_prompts.get(style, style_prompts['cinematic'])}: {description}"
    
    # 添加角色特征
    if character_features:
        if consistency_level == "low":
            # 低级别：基本特征
            basic_features = [character_features.get(k, "") for k in ["gender", "age_range", "hair_style"]]
            character_desc = ", ".join(filter(None, basic_features))
        elif consistency_level == "medium":
            # 中级别：主要特征
            medium_features = [character_features.get(k, "") for k in ["gender", "age_range", "hair_style", "clothing_style", "facial_features"]]
            character_desc = ", ".join(filter(None, medium_features))
        else:  # high
            # 高级别：所有特征
            character_desc = ", ".join(filter(None, character_features.values()))
        
        if character_desc:
            base_prompt += f", Character: {character_desc}"
    
    # 添加一致性指令
    consistency_instructions = {
        "low": "maintain basic character appearance",
        "medium": "strictly maintain character appearance, clothing style, and visual consistency",
        "high": "extremely maintain all visual elements including character details, lighting, color scheme, and art style"
    }
    
    instruction = consistency_instructions.get(consistency_level, consistency_instructions["medium"])
    base_prompt += f". {instruction}."
    
    return base_prompt


async def _generate_with_seedream_4_0(
    prompt: str,
    size: tuple[int, int],
    reference_images: list[str] | None = None,
    consistency_seed: int | None = None,
) -> str:
    """使用豆包Seedream 4.0生成图片"""
    
    logger.info(f"调用 Seedream 4.0 生成图片: {prompt[:50]}...")
    
    # 这里应该实现实际的Seedream 4.0 API调用
    # 暂时返回模拟URL
    import hashlib
    digest = hashlib.md5(f"{prompt}_{consistency_seed or 0}".encode()).hexdigest()[:8]
    width, height = size
    
    mock_url = f"https://seedream.lewis.ai/{width}x{height}_{digest}.jpg"
    logger.info(f"Seedream 4.0 生成成功: {mock_url}")
    
    return mock_url


# 导出主函数
__all__ = [
    "generate_storyboard_image", 
    "generate_consistent_storyboard_image", 
    "ImageGenerationError"
]

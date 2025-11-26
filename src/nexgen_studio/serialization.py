"""统一的 JSON 序列化工具，处理 datetime 等特殊类型。"""

from __future__ import annotations

import json
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


def json_serializer(obj: Any) -> Any:
    """
    自定义 JSON 序列化器，处理常见的非标准类型。
    
    支持的类型：
    - datetime, date: 转换为 ISO 格式字符串
    - Decimal: 转换为 float
    - UUID: 转换为字符串
    - Enum: 转换为其值
    - Pydantic BaseModel: 调用 model_dump(mode='json')
    - 带有 __dict__ 的对象: 转换为字典
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Enum):
        return obj.value
    # Pydantic model
    if hasattr(obj, 'model_dump'):
        return obj.model_dump(mode='json')
    # 普通对象
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def dumps(data: Any, **kwargs) -> str:
    """
    将数据序列化为 JSON 字符串，自动处理特殊类型。
    
    Args:
        data: 要序列化的数据
        **kwargs: 传递给 json.dumps 的额外参数
        
    Returns:
        JSON 字符串
    """
    return json.dumps(data, default=json_serializer, ensure_ascii=False, **kwargs)


def loads(s: str, **kwargs) -> Any:
    """
    从 JSON 字符串反序列化数据。
    
    Args:
        s: JSON 字符串
        **kwargs: 传递给 json.loads 的额外参数
        
    Returns:
        反序列化后的数据
    """
    return json.loads(s, **kwargs)


def sse_event(data: dict[str, Any]) -> bytes:
    """
    将数据格式化为 Server-Sent Events (SSE) 格式。
    
    Args:
        data: 要发送的数据字典
        
    Returns:
        SSE 格式的字节串
    """
    return f"data: {dumps(data)}\n\n".encode("utf-8")

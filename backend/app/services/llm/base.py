"""
PetPal - LLM 抽象基类与 JSON 提取工具

设计原则：
- 接口最小：只提供 complete() / complete_json() 两个方法
- 输入统一为 OpenAI 风格 messages，便于在 provider 内部转换
- 输出统一为 str（自然语言）或 dict（结构化）
- 所有失败抛 LLMException，由 router 决定要不要 failover
"""
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Literal, Union


Role = Literal["system", "user", "assistant"]


@dataclass
class LLMMessage:
    role: Role
    content: str

    def to_openai(self) -> dict:
        return {"role": self.role, "content": self.content}


class LLMException(Exception):
    """LLM 调用统一异常类型，包含 provider / status / 原文"""

    def __init__(self, message: str, *, provider: str = "unknown",
                 status: Optional[int] = None, raw: Optional[str] = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status = status
        self.raw = raw

    def __repr__(self) -> str:
        return f"<LLMException provider={self.provider} status={self.status}>"


class LLMClient(ABC):
    """LLM 客户端抽象基类"""

    name: str = "abstract"

    def __init__(self, *, api_key: str, model: str, base_url: Optional[str] = None,
                 timeout: float = 20.0, max_output_tokens: int = 1024) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens

    @abstractmethod
    async def complete(
        self,
        messages: Union[List[LLMMessage], List[Dict[str, Any]]],
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        """返回纯文本回复。"""

    async def complete_json(
        self,
        messages: Union[List[LLMMessage], List[Dict[str, Any]]],
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """要求 LLM 返回 JSON，并解析为 dict。"""
        text = await self.complete(messages, temperature=temperature, max_tokens=max_tokens, json_mode=True)
        return parse_json_response(text)


# ==================== 工具：JSON 解析 ====================

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})", re.DOTALL)


def parse_json_response(text: str) -> Dict[str, Any]:
    """
    从 LLM 输出中提取 JSON。容忍以下情况：
    - 直接是合法 JSON
    - 包在 ```json ... ``` 围栏里
    - 前后有自然语言解释
    - 多余的 BOM / 空白
    """
    if text is None:
        raise LLMException("LLM 返回为空")
    s = text.strip().lstrip("﻿")

    # 1. 直接尝试
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. 尝试代码围栏
    m = _JSON_FENCE_RE.search(s)
    if m:
        try:
            return json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    # 3. 找第一个完整 {...}
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = s[start:end + 1]
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            pass

    raise LLMException(f"LLM 返回不是合法 JSON: {s[:200]}", raw=s)


def normalize_messages(messages) -> List[LLMMessage]:
    """把 messages 归一化为 LLMMessage 列表。"""
    out: List[LLMMessage] = []
    for m in messages:
        if isinstance(m, LLMMessage):
            out.append(m)
        elif isinstance(m, dict):
            out.append(LLMMessage(role=m.get("role", "user"), content=m.get("content", "")))
        else:
            raise TypeError(f"不支持的消息类型: {type(m)}")
    return out

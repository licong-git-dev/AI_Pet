"""
PetPal - OpenAI 兼容协议提供商

走 /chat/completions 接口；同样可用于任何 OpenAI 兼容网关
（Ollama / 本地 vLLM / DashScope OpenAI 兼容端点等）。
"""
import json
from typing import List, Dict, Any, Optional

import httpx
from loguru import logger

from app.services.llm.base import (
    LLMClient, LLMException, normalize_messages,
)


class OpenAIClient(LLMClient):
    name = "openai"

    async def complete(
        self,
        messages,
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        msgs = normalize_messages(messages)
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_openai() for m in msgs],
            "temperature": temperature,
            "max_tokens": max_tokens or self.max_output_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        url = f"{(self.base_url or 'https://api.openai.com/v1').rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, headers=headers, json=body)
        except httpx.RequestError as e:
            raise LLMException(f"OpenAI 网络错误: {e}", provider=self.name) from e

        if resp.status_code >= 400:
            raise LLMException(
                f"OpenAI HTTP {resp.status_code}",
                provider=self.name,
                status=resp.status_code,
                raw=resp.text[:500],
            )

        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            raise LLMException(f"OpenAI 返回非 JSON: {e}", provider=self.name, raw=resp.text[:500]) from e

        choices = data.get("choices") or []
        if not choices:
            raise LLMException("OpenAI 无 choices", provider=self.name, raw=resp.text[:500])
        message = choices[0].get("message") or {}
        text = (message.get("content") or "").strip()
        if not text:
            finish = choices[0].get("finish_reason")
            raise LLMException(
                f"OpenAI 返回空文本 (finish_reason={finish})",
                provider=self.name,
                raw=resp.text[:500],
            )
        return text

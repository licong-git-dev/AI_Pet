"""
PetPal - Google Gemini 提供商

REST 端点：
  POST {base_url}/models/{model}:generateContent
请求头：X-goog-api-key: <key>

把 OpenAI 风格 messages 转成 Gemini 的 contents/system_instruction 结构。
"""
import json
from typing import List, Dict, Any, Optional

import httpx
from loguru import logger

from app.services.llm.base import (
    LLMClient, LLMMessage, LLMException, normalize_messages,
)


class GeminiClient(LLMClient):
    name = "gemini"

    async def complete(
        self,
        messages,
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        msgs = normalize_messages(messages)
        system_text = "\n".join(m.content for m in msgs if m.role == "system").strip()
        contents: List[Dict[str, Any]] = []
        for m in msgs:
            if m.role == "system":
                continue
            role = "user" if m.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m.content}]})

        body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens or self.max_output_tokens,
            },
        }
        if system_text:
            body["systemInstruction"] = {"parts": [{"text": system_text}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, headers=headers, json=body)
        except httpx.RequestError as e:
            raise LLMException(f"Gemini 网络错误: {e}", provider=self.name) from e

        if resp.status_code >= 400:
            raise LLMException(
                f"Gemini HTTP {resp.status_code}",
                provider=self.name,
                status=resp.status_code,
                raw=resp.text[:500],
            )

        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            raise LLMException(f"Gemini 返回非 JSON: {e}", provider=self.name, raw=resp.text[:500]) from e

        # 路径：candidates[0].content.parts[0].text
        candidates = data.get("candidates") or []
        if not candidates:
            block_reason = (data.get("promptFeedback") or {}).get("blockReason")
            raise LLMException(
                f"Gemini 未返回 candidates" + (f" (blockReason={block_reason})" if block_reason else ""),
                provider=self.name,
                raw=resp.text[:500],
            )
        first = candidates[0]
        parts = ((first.get("content") or {}).get("parts")) or []
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            finish = first.get("finishReason")
            raise LLMException(
                f"Gemini 返回空文本 (finishReason={finish})",
                provider=self.name,
                raw=resp.text[:500],
            )
        return text

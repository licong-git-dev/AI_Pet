"""
PetPal - LLM 路由器

主提供商失败时自动降级到 fallback。统一对外暴露 LLMClient 接口。
"""
from typing import Optional, List, Dict, Any
from loguru import logger

from app.config import settings
from app.services.llm.base import LLMClient, LLMException
from app.services.llm.providers.gemini import GeminiClient
from app.services.llm.providers.openai_like import OpenAIClient


def _build_provider(name: str) -> Optional[LLMClient]:
    """根据名字构建提供商实例。无 key 时返回 None。"""
    name = (name or "").lower().strip()
    if name == "gemini":
        if not settings.gemini_api_key:
            return None
        return GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            base_url=settings.gemini_base_url,
            timeout=settings.llm_timeout_seconds,
            max_output_tokens=settings.llm_max_output_tokens,
        )
    if name == "openai":
        if not settings.openai_api_key:
            return None
        return OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout=settings.llm_timeout_seconds,
            max_output_tokens=settings.llm_max_output_tokens,
        )
    if name == "dashscope":
        # DashScope 提供 OpenAI 兼容端点
        if not settings.dashscope_api_key:
            return None
        return OpenAIClient(
            api_key=settings.dashscope_api_key,
            model=settings.dashscope_chat_model,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            timeout=settings.llm_timeout_seconds,
            max_output_tokens=settings.llm_max_output_tokens,
        )
    return None


class LLMRouter(LLMClient):
    """带 fallback 的路由器。对外行为与 LLMClient 一致。"""

    name = "router"

    def __init__(self) -> None:
        self.primary = _build_provider(settings.llm_primary_provider)
        self.fallback = _build_provider(settings.llm_fallback_provider) if settings.llm_fallback_provider else None
        if self.primary is None and self.fallback is None:
            logger.warning("[llm] 未配置任何 LLM 提供商；记忆抽取/周摘要/画像将使用规则兜底")
        # 抽象基类构造参数仅作占位，实际通过下游 provider 调用
        super().__init__(api_key="", model="", base_url=None,
                         timeout=settings.llm_timeout_seconds,
                         max_output_tokens=settings.llm_max_output_tokens)

    @property
    def is_available(self) -> bool:
        return self.primary is not None or self.fallback is not None

    async def complete(
        self,
        messages,
        *,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        last_err: Optional[Exception] = None
        for provider in (self.primary, self.fallback):
            if provider is None:
                continue
            try:
                return await provider.complete(
                    messages, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode,
                )
            except LLMException as e:
                logger.warning(f"[llm] provider={provider.name} 失败: {e}; 尝试下一个")
                last_err = e
            except Exception as e:
                logger.warning(f"[llm] provider={provider.name} 未知异常: {e}; 尝试下一个")
                last_err = e
        if last_err is None:
            raise LLMException("无可用 LLM 提供商，请配置 GEMINI_API_KEY 或 OPENAI_API_KEY")
        raise last_err  # 抛出最后一次失败原因


_router: Optional[LLMRouter] = None


def get_llm() -> LLMRouter:
    """进程级单例。"""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router

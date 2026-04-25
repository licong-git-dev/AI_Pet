"""
PetPal - 通用 LLM 网关

为长期记忆抽取 / 周摘要 / 主人画像构建提供统一的 LLM 接口。
不影响现有 dashscope_chat / qwen_vl 路径，二者并存。

主要类：
- LLMClient: 抽象基类
- GeminiClient / OpenAIClient: 两个具体实现
- LLMRouter: 主提供商 + 失败 fallback 的路由器
- get_llm(): 进程级单例

使用示例：
    from app.services.llm import get_llm
    llm = get_llm()
    text = await llm.complete([{"role": "user", "content": "..."}])
    obj = await llm.complete_json([...])  # 强制要求返回 JSON
"""
from app.services.llm.base import LLMClient, LLMMessage, LLMException
from app.services.llm.providers.gemini import GeminiClient
from app.services.llm.providers.openai_like import OpenAIClient
from app.services.llm.router import LLMRouter, get_llm
from app.services.llm import prompts

__all__ = [
    "LLMClient", "LLMMessage", "LLMException",
    "GeminiClient", "OpenAIClient",
    "LLMRouter", "get_llm",
    "prompts",
]

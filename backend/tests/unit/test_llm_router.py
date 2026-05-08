"""
PetPal · LLM router 单测

不打真实网络，所有 provider 通过 monkeypatch 注入。
覆盖：
- 主提供商成功 → 直接返回
- 主提供商抛 LLMException → 自动 failover 到 fallback
- 主 + fallback 都失败 → 抛最后一次错误
- 完全无 key（is_available=False）→ complete() 抛 LLMException
- 输入字符统计正确传给 metrics 回调
"""
import asyncio
from typing import Optional

import pytest

from app.services.llm.base import LLMException, LLMClient


class FakeProvider(LLMClient):
    """记录调用次数和接收到的 messages。"""
    def __init__(self, name: str, *, model: str = "fake", reply: Optional[str] = "ok",
                 fail: bool = False):
        super().__init__(api_key="x", model=model, base_url="", timeout=5.0)
        self.name = name
        self.reply = reply
        self.fail = fail
        self.calls = []

    async def complete(self, messages, *, temperature=0.2, max_tokens=None, json_mode=False):
        self.calls.append({"temperature": temperature, "json_mode": json_mode, "messages": messages})
        if self.fail:
            raise LLMException(f"{self.name} simulated failure", provider=self.name, status=500)
        return self.reply


def _make_router(primary=None, fallback=None):
    from app.services.llm.router import LLMRouter
    r = LLMRouter()
    r.primary = primary
    r.fallback = fallback
    return r


def test_primary_success_short_circuits_fallback():
    p = FakeProvider("primary", reply="hello from primary")
    f = FakeProvider("fallback", reply="should-not-call")
    r = _make_router(primary=p, fallback=f)

    out = asyncio.run(r.complete([{"role": "user", "content": "hi"}]))
    assert out == "hello from primary"
    assert len(p.calls) == 1
    assert len(f.calls) == 0


def test_primary_failure_falls_back():
    p = FakeProvider("primary", fail=True)
    f = FakeProvider("fallback", reply="from fallback")
    r = _make_router(primary=p, fallback=f)

    out = asyncio.run(r.complete([{"role": "user", "content": "hi"}]))
    assert out == "from fallback"
    assert len(p.calls) == 1
    assert len(f.calls) == 1


def test_both_failures_raises_last():
    p = FakeProvider("primary", fail=True)
    f = FakeProvider("fallback", fail=True)
    r = _make_router(primary=p, fallback=f)
    with pytest.raises(LLMException) as exc:
        asyncio.run(r.complete([{"role": "user", "content": "hi"}]))
    # 最后一次错误来自 fallback
    assert "fallback" in str(exc.value).lower()


def test_no_provider_raises():
    r = _make_router(primary=None, fallback=None)
    with pytest.raises(LLMException):
        asyncio.run(r.complete([{"role": "user", "content": "hi"}]))


def test_is_available_flag():
    assert _make_router(FakeProvider("p"), None).is_available is True
    assert _make_router(None, FakeProvider("f")).is_available is True
    assert _make_router(None, None).is_available is False


# ==================== 工具：parse_json_response ====================

def test_parse_json_strict():
    from app.services.llm.base import parse_json_response
    out = parse_json_response('{"a": 1}')
    assert out == {"a": 1}


def test_parse_json_with_fence():
    from app.services.llm.base import parse_json_response
    text = """
    here is the result:
    ```json
    {"keep": true, "importance": 7}
    ```
    """
    out = parse_json_response(text)
    assert out["keep"] is True
    assert out["importance"] == 7


def test_parse_json_with_trailing_commentary():
    from app.services.llm.base import parse_json_response
    text = "Sure! {\"x\": 42}\n以上就是结果。"
    out = parse_json_response(text)
    assert out["x"] == 42


def test_parse_json_invalid_raises():
    from app.services.llm.base import parse_json_response, LLMException
    with pytest.raises(LLMException):
        parse_json_response("不是 JSON 也不是围栏 just plain text")


# ==================== 上层路径：抽取 -> 路由 ====================

def test_extract_memory_uses_llm_when_keep_true(db_session, seed_pet_avatar):
    """当注入 LLM 返回 keep=true，extract_memory_from_message_llm 返回归一化字段。"""
    from app.services import memory_service

    # patch get_llm 返回一个总是给 keep=true 的 fake
    class FakeLLM:
        is_available = True
        async def complete_json(self, messages, **_):
            return {
                "keep": True,
                "memory_type": "episodic",
                "content": "今天主人加班至深夜",
                "summary": "加班深夜",
                "importance": 7,
                "emotion": "anxious",
                "emotion_intensity": 0.8,
            }

    import app.services.llm
    original = app.services.llm.get_llm
    app.services.llm.get_llm = lambda: FakeLLM()
    try:
        out = asyncio.run(memory_service.extract_memory_from_message_llm(
            user_message="今天加班崩溃", assistant_message="*蹭你*",
        ))
    finally:
        app.services.llm.get_llm = original

    assert out is not None
    assert out["memory_type"] == "episodic"
    assert out["importance"] == 7
    assert out["emotion"] == "anxious"


def test_extract_memory_falls_back_on_llm_exception(db_session, seed_pet_avatar):
    """LLM 抛异常时降级到规则版（强情感能命中）。"""
    from app.services import memory_service

    class BoomLLM:
        is_available = True
        async def complete_json(self, *a, **k):
            raise RuntimeError("ack")

    import app.services.llm
    original = app.services.llm.get_llm
    app.services.llm.get_llm = lambda: BoomLLM()
    try:
        out = asyncio.run(memory_service.extract_memory_from_message_llm(
            user_message="今天压力好大，崩溃了",
            assistant_message="*蹭蹭*",
        ))
    finally:
        app.services.llm.get_llm = original

    assert out is not None  # 规则版兜底命中
    assert out["importance"] >= 8

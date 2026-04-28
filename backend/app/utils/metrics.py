"""
PetPal · Prometheus 指标定义

四套核心业务指标 + HTTP 标准指标（由 instrumentator 自动注入）：
1. LLM 网关 — 调用次数 / 延迟 / 失败 / token 估算
2. 长期记忆 — 写入数 / 类型分布 / 重要度直方图 / 检索耗时
3. Wrapped 月报 — 生成数 / 卡片数 / LLM 是否被使用
4. ASP 渲染 — 事件 broadcast 的 sent / failed / skipped

prometheus_client 是进程级单例；多 worker 部署时 instrumentator 会处理聚合。
"""
from typing import Optional
from prometheus_client import Counter, Histogram, Gauge


# ==================== LLM 网关 ====================

llm_calls_total = Counter(
    "petpal_llm_calls_total",
    "LLM 调用总数",
    ["provider", "model", "outcome"],  # outcome: success | failure | fallback
)

llm_call_duration_seconds = Histogram(
    "petpal_llm_call_duration_seconds",
    "LLM 调用耗时",
    ["provider", "model"],
    buckets=(0.1, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0),
)

llm_input_chars = Histogram(
    "petpal_llm_input_chars",
    "LLM 输入消息总字符数（用于估算 token）",
    ["provider"],
    buckets=(50, 200, 500, 1000, 2000, 5000, 10000, 20000),
)

llm_output_chars = Histogram(
    "petpal_llm_output_chars",
    "LLM 输出字符数",
    ["provider"],
    buckets=(20, 100, 300, 800, 2000, 5000),
)


# ==================== 长期记忆 ====================

memory_writes_total = Counter(
    "petpal_memory_writes_total",
    "长期记忆写入次数",
    ["memory_type", "source"],
)

memory_extract_decisions_total = Counter(
    "petpal_memory_extract_decisions_total",
    "对话后是否抽取出值得长期记忆的内容",
    ["decision", "extractor"],  # decision: kept | dropped, extractor: llm | rule
)

memory_importance_histogram = Histogram(
    "petpal_memory_importance",
    "新增记忆的重要度分布 0-10",
    ["memory_type"],
    buckets=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
)

memory_retrieval_duration_seconds = Histogram(
    "petpal_memory_retrieval_duration_seconds",
    "对话前检索 top-K 记忆耗时",
    buckets=(0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
)

memory_retrieved_count = Histogram(
    "petpal_memory_retrieved_count",
    "对话前检索到的记忆条数",
    buckets=(0, 1, 2, 3, 5, 10, 20),
)


# ==================== Wrapped 月报 ====================

wrapped_generated_total = Counter(
    "petpal_wrapped_generated_total",
    "月报生成次数",
    ["llm_used", "outcome"],  # outcome: ok | empty | error
)

wrapped_cards_count = Histogram(
    "petpal_wrapped_cards",
    "单份月报包含的卡片数",
    buckets=(1, 3, 5, 7, 9, 12),
)

wrapped_secrets_count = Histogram(
    "petpal_wrapped_secrets",
    "单份月报五个秘密的实际命中数",
    buckets=(0, 1, 2, 3, 4, 5),
)


# ==================== ASP 渲染适配层 ====================

asp_broadcast_total = Counter(
    "petpal_asp_broadcast_total",
    "ASP 事件 fan-out 投递结果",
    ["event_type", "outcome"],  # outcome: sent | failed | skipped
)

asp_drivers_active = Gauge(
    "petpal_asp_drivers_active",
    "当前进程持有的活跃 driver 实例数",
)


# ==================== 工具：上下文管理 ====================

def observe_llm_call(provider: str, model: str, *,
                     outcome: str, duration: float,
                     input_chars: Optional[int] = None,
                     output_chars: Optional[int] = None) -> None:
    """统一观测一次 LLM 调用。"""
    llm_calls_total.labels(provider=provider, model=model, outcome=outcome).inc()
    llm_call_duration_seconds.labels(provider=provider, model=model).observe(duration)
    if input_chars is not None:
        llm_input_chars.labels(provider=provider).observe(input_chars)
    if output_chars is not None:
        llm_output_chars.labels(provider=provider).observe(output_chars)


def observe_memory_write(memory_type: str, source: str, importance: int) -> None:
    memory_writes_total.labels(memory_type=memory_type, source=source).inc()
    memory_importance_histogram.labels(memory_type=memory_type).observe(max(0, min(10, int(importance))))


def observe_extract_decision(*, kept: bool, extractor: str) -> None:
    memory_extract_decisions_total.labels(
        decision="kept" if kept else "dropped",
        extractor=extractor,
    ).inc()


def observe_memory_retrieval(duration: float, count: int) -> None:
    memory_retrieval_duration_seconds.observe(duration)
    memory_retrieved_count.observe(count)


def observe_wrapped(*, llm_used: bool, outcome: str, cards: int, secrets: int) -> None:
    wrapped_generated_total.labels(llm_used=str(llm_used).lower(), outcome=outcome).inc()
    wrapped_cards_count.observe(cards)
    wrapped_secrets_count.observe(secrets)


def observe_asp_broadcast(event_type: str, *, sent: int, failed: int, skipped: int) -> None:
    asp_broadcast_total.labels(event_type=event_type, outcome="sent").inc(sent)
    asp_broadcast_total.labels(event_type=event_type, outcome="failed").inc(failed)
    asp_broadcast_total.labels(event_type=event_type, outcome="skipped").inc(skipped)

"""
PetPal - LLM 提示词模板

三个核心场景：
1. extract_memory: 从一次对话中抽取值得长期记住的内容（结构化 JSON）
2. weekly_digest: 把 7 天内的若干 episodic 记忆蒸馏为一段 semantic 总结
3. build_owner_profile: 从信号流推断主人画像

约定：所有 prompt 都强制输出 JSON，schema 在描述中明确说明。
返回值由 base.parse_json_response() 统一解析。
"""
from typing import List, Dict, Any


# ==================== 1. 记忆抽取 ====================

EXTRACT_MEMORY_SYSTEM = """你是一个负责为"宠物数字分身"维护长期记忆的助手。
分身的目标是比真实宠物更懂主人，所以需要从主人和分身的对话中识别"值得长期记住"的内容。

判断标准：
- 平淡寒暄（"你好""吃了吗"）→ 不值得记，返回 keep=false
- 主人的强情绪事件（开心 / 难过 / 焦虑 / 愤怒）→ 值得记，importance 7-9
- 重要纪念日 / 里程碑（生日 / 领养日 / 搬家 / 入职 / 离职 / 结婚）→ 必记，importance 9-10
- 主人的稳定偏好或角色（"我是程序员""我家狗叫豆包"）→ 必记为 preference，importance 8
- 客观事实（"今天我去了爬山""周末加班"）→ 视情绪强度记为 episodic，importance 4-7

严格按以下 JSON 格式返回，不要包含 ```json 围栏，不要解释：
{
  "keep": true | false,
  "memory_type": "episodic" | "semantic" | "preference" | "event",
  "content": "完整记忆原文，第三人称叙述，60-200 字",
  "summary": "一句话摘要，不超过 50 字",
  "importance": 0-10 整数,
  "emotion": "happy|loving|proud|neutral|sad|anxious|worried|lonely|angry",
  "emotion_intensity": 0.0-1.0
}

如果 keep=false，其它字段可省略或填空。"""


def extract_memory_messages(user_message: str, assistant_message: str) -> List[Dict[str, Any]]:
    user_block = f"""【主人对分身说】
{user_message}

【分身的回复】
{assistant_message}

请按 system 中的格式返回 JSON。"""
    return [
        {"role": "system", "content": EXTRACT_MEMORY_SYSTEM},
        {"role": "user", "content": user_block},
    ]


# ==================== 2. 周摘要 ====================

WEEKLY_DIGEST_SYSTEM = """你是一个温柔细致的观察者，正在为宠物分身整理"过去一周关于主人的记忆"。

把多条情景记忆蒸馏成一段总结，并提取关键主题和主导情绪。

严格按以下 JSON 格式返回，不要包含 ```json 围栏：
{
  "summary": "180-300 字的中文段落，自然语言；不要分点，像一段日记。重点放在主人的状态、生活节律变化、值得分身记住的关键事件",
  "key_themes": ["3-6 个关键词，例如 加班/失眠/旅行/聚会"],
  "dominant_emotion": "happy|loving|proud|neutral|sad|anxious|worried|lonely|angry"
}"""


def weekly_digest_messages(memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """memories: [{content, importance, emotion, happened_at}, ...]"""
    lines = ["以下是过去一周的若干记忆片段（按时间从新到旧）："]
    for i, m in enumerate(memories, 1):
        when = m.get("happened_at") or m.get("created_at") or ""
        emo = m.get("emotion") or "neutral"
        imp = m.get("importance", 5)
        content = m.get("content", "")[:300]
        lines.append(f"{i}. [{when}|{emo}|imp={imp}] {content}")
    user_block = "\n".join(lines)
    return [
        {"role": "system", "content": WEEKLY_DIGEST_SYSTEM},
        {"role": "user", "content": user_block},
    ]


# ==================== 3. 主人画像构建 ====================

BUILD_PROFILE_SYSTEM = """你是一个负责给宠物分身搭建"主人画像"的助手。

从给定的行为信号 + 情感信号中，推断主人的：
- daily_rhythm: 作息规律
- emotional_baseline: 情绪基线
- relationships: 关系角色（家人 / 工作 / 爱好）
- communication: 沟通偏好
- pet_attachment: 主人对宠物的依恋方式

【底线约束】
- 数据不足以判断的字段必须为 null（不要瞎猜）
- 涉及隐私敏感（健康/性取向/政治/财务）→ 一律不写入
- 所有结论要"温柔"，不要做负面评判

严格按以下 JSON 格式返回（不要 ```json 围栏）：
{
  "daily_rhythm": {
    "wake_time": "HH:MM 或 null",
    "sleep_time": "HH:MM 或 null",
    "peak_active_hours": [0-23 的小时数组] 或 null,
    "weekend_pattern": "简短描述 或 null"
  },
  "emotional_baseline": {
    "dominant_moods": ["主导情绪标签"],
    "stress_triggers": ["可能的压力来源"] 或 null,
    "comfort_topics": ["让主人放松的话题"] 或 null
  },
  "relationships": {
    "family_members": null,
    "work_role": "若能从信号推断出工作角色则填，否则 null",
    "hobbies": ["爱好"] 或 null
  },
  "communication": {
    "tone_preference": "gentle|playful|concise 或 null",
    "length": "short|medium|long 或 null",
    "emoji_usage": "rare|moderate|heavy 或 null",
    "taboos": null
  },
  "pet_attachment": {
    "nicknames": ["主人称呼宠物的昵称"] 或 null,
    "special_dates": null,
    "ritual_moments": ["每日仪式时刻"] 或 null
  }
}"""


def build_profile_messages(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """signals: [{signal_type, recorded_at, sentiment_label, text_excerpt, payload}, ...]"""
    lines = [f"以下是过去 30 天采集的 {len(signals)} 条信号（按时间从新到旧，节选）："]
    for i, s in enumerate(signals[:200], 1):  # 限制喂入量
        t = s.get("signal_type")
        rec = s.get("recorded_at") or ""
        senti = s.get("sentiment_label") or "-"
        text = (s.get("text_excerpt") or "")[:120]
        extras = s.get("payload") or {}
        extras_str = ""
        if extras:
            extras_str = " " + " ".join(f"{k}={v}" for k, v in list(extras.items())[:3])
        lines.append(f"{i}. [{rec}|{t}|{senti}]{extras_str} {text}")
    user_block = "\n".join(lines)
    return [
        {"role": "system", "content": BUILD_PROFILE_SYSTEM},
        {"role": "user", "content": user_block},
    ]

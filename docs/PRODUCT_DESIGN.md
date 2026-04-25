# AI_Pet · 产品设计文档（v1）

> **核心承诺**：让宠物拥有第二条数字生命，最终**比宠物本身更懂主人**。
> 文档作者视角：业务专家 + 产品专家 + 技术架构师三合一
> 最后更新：2026-04-25

---

## 0. 战略全景

### 0.1 问题与机会

| 主人侧痛点 | 现有方案的不足 | AI_Pet 切入点 |
|---|---|---|
| 上班 8 小时宠物独自在家，缺陪伴 | 摄像头只看不互动 | 数字分身能主动陪聊、回应 |
| 宠物离世后情感断崖 | 无形可追忆 | 分身延续记忆，温柔过渡 |
| "我家狗不懂我心情"的孤独感 | 真实宠物有限的认知 | AI 分身懂我的作息、情绪、偏好 |
| 想分享宠物可爱瞬间没动力做内容 | 拍视频 / 剪辑成本高 | 分身自动生成表情包 / 短文 |

### 0.2 三支柱的商业逻辑

```
[长期记忆] ──→ 留存（聊得越久越离不开）
     │
     ↓
[主人画像] ──→ 付费理由（个性化深度 = 订阅价值）
     │
     ↓
[硬件适配层] ──→ 渠道护城河（一次开发，全终端分发）
```

**为什么必须是这三个**：缺记忆 = 每天重新认识；缺画像 = 千人一面；缺适配层 = 永远困在 App 里，无法成为家里的"一员"。

### 0.3 北极星与里程碑

| 阶段 | 北极星指标 | 关键 OKR |
|---|---|---|
| 0→1（已完成） | 单只宠物可被创建为分身 | ✅ 性格分析 + 5 风格对话 + 表情包 |
| **1→10（本次）** | **D30 留存 ≥ 35%（带记忆功能用户）** | 长期记忆上线、画像 v1、设备绑定协议草案 |
| 10→100 | ARPPU ≥ ¥30 / 月（订阅会员） | 记忆云端备份、主人画像导出报告、桌宠首批硬件出货 |

---

## 1. 支柱一：长期记忆（Long-Term Memory）

### 1.1 产品要义

让分身**像一个真正认识你三年的朋友一样**记得你。

- 不是简单存日志，而是**有重要度、有情感、会遗忘**
- 用户能"参观"宠物的记忆（**"记忆花园" UI**：愿景层，目前先建数据基础）

### 1.2 记忆三层模型

| 层级 | 类型 | 例子 | 存储 |
|---|---|---|---|
| **情景记忆** (episodic) | 一次性事件 | "2026-04-25 下午主人加班到 11 点回家，看起来很累" | `pet_memories` 表，单条 |
| **语义记忆** (semantic) | 周期总结的"一般性事实" | "主人通常 23:30 后睡觉，周末睡到 10 点" | `pet_memories` 表，type=semantic |
| **偏好记忆** (preference) | 主人/宠物的稳定偏好 | "主人喜欢叫我'豆包'" / "主人讨厌被在工作时打断" | `pet_memories` 表，type=preference，importance ≥ 8 |

### 1.3 核心机制

#### a) 写入：双通道
- **被动**：每次对话结束后，由 LLM 提取"值得记住的瞬间"（`memory_writer`）
- **主动**：主人手动添加（"今天我们去公园了"，写入为 episodic）

#### b) 检索：混合排序
对话发起前，组合三个权重检索 top-K：
```
score = α·相关度（语义检索） + β·新鲜度（时间衰减） + γ·重要度 + δ·情感强度
```
默认 α=0.4 β=0.2 γ=0.25 δ=0.15。

#### c) 遗忘曲线：艾宾浩斯改造
- 每条记忆有 `importance` (0–10) 和 `last_recalled_at`
- 后台 Celery 每日任务计算 `effective_strength = importance × exp(-days_since_recall / τ)`
- 当 `effective_strength < 0.5` 且非 preference 类型 → 标记 `archived`（不删，主人能在"记忆花园"恢复）

#### d) 周期性整理：每周一早 6 点
- 把过去 7 天的 episodic 记忆喂给 LLM，输出 1–3 条 semantic（"这周主人状态不好，开会很多"）
- 旧 episodic 进入低权重池

### 1.4 数据模型

```python
class PetMemory(Base):
    __tablename__ = "pet_memories"
    id, pet_avatar_id, user_id
    memory_type: episodic | semantic | preference | event
    content: Text                 # 记忆原文
    summary: String(255)          # 一句话摘要
    importance: SmallInt 0-10
    emotion: String(20)           # happy / sad / anxious / loving / proud / worried / neutral
    source: String(20)            # conversation / observation / user_input / weekly_digest
    happened_at: DateTime         # 事件发生时间
    embedding_vector_id: String(64)  # 向量 ID（指向 Milvus / pgvector）
    last_recalled_at: DateTime
    recall_count: Int
    effective_strength: Float     # 缓存的衰减强度
    is_archived: Boolean
    created_at, updated_at
```

> **向量检索**：v1 先用 MySQL 全文索引 + LLM 重排兜底；v1.5 接 Milvus / pgvector。

### 1.5 隐私

- 记忆全部归属用户，提供**全量导出**和**全量擦除**接口
- 默认仅供本人和其分身使用，不进入训练数据

---

## 2. 支柱二：主人画像（Owner Profile）

### 2.1 产品要义

分身"懂主人"必须**可见、可调、可信**。这就是主人画像。

- 像 Spotify Wrapped 一样，让用户感叹"哦原来它这么了解我"
- 像健康类 App 一样有可视化和趋势

### 2.2 画像维度

| 维度 | 字段 | 示例 |
|---|---|---|
| **生活节律** | wake_time, sleep_time, peak_active_hours | 23:30 睡 / 8:00 起 / 21:00–23:00 最活跃 |
| **情感基线** | dominant_moods, stress_triggers, comfort_topics | 主导情绪偏疲惫 / 被项目截止日触发 / 聊宠物会松弛 |
| **关系网络** | family_members, work_role, hobbies | 同居伴侣"小王" / 产品经理 / 喜欢爬山 |
| **沟通偏好** | tone_preference, length, emoji_usage, taboo | 喜欢温柔短句 / 中等长度 / 多 emoji / 不爱被叫"哥" |
| **宠物依恋** | nicknames, special_dates, ritual_moments | "豆包"、"小笨蛋" / 4-25 是它的"领养纪念日" / 每晚刷牙时一起 |

### 2.3 信号采集（三个来源）

| 来源 | 采集点 | 隐私边界 |
|---|---|---|
| **行为信号** | 登录时间、对话时长、活跃时段、消息长度 | 默认开 |
| **语义信号** | 对话内容情感分析、关键词 | 默认开，可关闭 |
| **主动填写** | "了解我" 问卷、纪念日设置 | 完全可选 |

### 2.4 画像构建流程

```
[OwnerSignal 原始信号] → 每周 Celery 任务 → [LLM 摘要 + 规则提取]
                                              ↓
                                    更新 OwnerProfile（带 confidence_score）
```

`confidence_score` 0–1，反映样本量和一致性。低置信度的字段在分身 prompt 里**不使用**，避免胡说。

### 2.5 数据模型

```python
class OwnerProfile(Base):
    __tablename__ = "owner_profiles"
    user_id (PK)
    daily_rhythm: JSON         # {wake, sleep, peak_hours, weekend_pattern}
    emotional_baseline: JSON   # {dominant_moods[], stress_triggers[], comfort_topics[]}
    relationships: JSON        # {family[], work_role, hobbies[]}
    communication: JSON        # {tone, length, emoji_usage, taboos[]}
    pet_attachment: JSON       # {nicknames[], special_dates[], ritual_moments[]}
    confidence_score: Float    # 0-1
    last_built_at: DateTime
    is_visible_to_avatar: Boolean = True
    updated_at

class OwnerSignal(Base):
    __tablename__ = "owner_signals"
    id, user_id
    signal_type: enum(login / chat_start / chat_end / message / sentiment / explicit_input / app_event)
    payload: JSON
    recorded_at: DateTime  # index
```

### 2.6 用户控制

- "查看 / 编辑 / 删除" 自己的画像（GDPR 风格）
- "暂停学习 7 天" 开关
- 月度画像报告 push（"你的'豆包'本月发现你这些秘密 🐾"）

---

## 3. 支柱三：硬件适配层（Avatar Render Layer）

### 3.1 产品要义

分身不是被困在 App 里的聊天机器人，而是**家庭成员**。它能在：

- 网页 / 手机里 2D Live2D
- 桌面雾屏 / Looking Glass 全息投影
- 桌面机器人 / 投影玩具实体
- AR 滤镜里"看到"

### 3.2 商业模式价值

谁先定标准，谁就掌握 SDK 渠道。我们要先**自己定一个开放协议（ASP, Avatar State Protocol）**，硬件厂可以适配 → 我们的分身就成了它的灵魂。

### 3.3 抽象架构

```
┌──────────────────────────────────────────────────┐
│  pet_avatar_service.chat() / sticker() / event() │
│                       │                          │
│                       ▼                          │
│        ┌─────────────────────────────┐          │
│        │  AvatarRenderOrchestrator   │  ←  根据用户的 device_bindings 决定 fan-out 给谁
│        └────────────┬────────────────┘          │
│                     │                            │
│   ┌──────────┬──────┼─────────┬─────────┐       │
│   ▼          ▼      ▼         ▼         ▼       │
│ Web      Hologram  Desktop   AR       Future    │
│ Driver   Driver    Pet       Driver   Driver    │
│ (WS)     (MQTT)    (BLE)     (WS)     (...)    │
└──────────────────────────────────────────────────┘
```

### 3.4 ASP 协议（v0.1 草案）

每条状态事件都符合统一 schema：

```json
{
  "event_id": "uuid",
  "avatar_id": 123,
  "ts": "2026-04-25T11:30:00Z",
  "type": "speech | emotion | animation | gaze | idle",
  "emotion": "happy | sleepy | curious | loving | sad | angry | neutral",
  "intensity": 0.0,
  "speech": { "text": "...", "audio_url": "...", "duration_ms": 0 },
  "animation": { "name": "wag_tail", "loop": false, "duration_ms": 0 },
  "posture": { "x": 0, "y": 0, "facing": "left" },
  "ttl_ms": 5000
}
```

驱动各自决定如何呈现：Web 驱动转换成 Live2D 动作；全息驱动转换成 3D 体积渲染指令；桌宠驱动转换成 BLE 命令包。

### 3.5 设备绑定

```python
class DeviceBinding(Base):
    __tablename__ = "device_bindings"
    id, user_id, pet_avatar_id
    device_type: enum(web / mobile / hologram / desktop_pet / ar_glasses)
    device_id: String(64)         # 由设备生成或我们颁发
    device_name: String(50)
    capabilities: JSON            # {speech: true, animation: true, emotion: true, ...}
    pairing_code: String(8)       # 用户输入到设备
    last_seen_at: DateTime
    status: enum(pending / online / offline / revoked)
    transport: enum(websocket / mqtt / ble_relay)
    created_at, updated_at
```

绑定流程：
1. 用户在设备上启动 → 设备显示 8 位配对码
2. App 输入配对码 → 后端校验、写入 binding、status=online
3. 后续 ASP 事件通过协商好的 transport 推送

### 3.6 路线图

| 版本 | 范围 |
|---|---|
| **v0.1（本次）** | 协议定义 + Web Driver 完整实现 + Hologram/DesktopPet 占位（mock 推送） |
| v0.2 | DesktopPet Driver 实接 BLE relay（树莓派/ESP32 demo） |
| v0.3 | Hologram Driver 适配 Looking Glass / 投影雾屏 |
| v1.0 | 公开 SDK + 合作硬件认证计划 |

---

## 4. 三支柱的协作

```
用户对主人/宠物说：「今天好累，让豆包陪我聊天」
                          │
                          ▼
            ┌─────────────────────────────┐
            │ pet_avatar_service.chat()   │
            └────────────┬────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
  retrieve_memory   load_owner_profile  build_persona
        │                │                │
        └────────┬───────┴────────┬───────┘
                 ▼                ▼
           组装 LLM Prompt   生成 reply + emotion
                 │                │
                 ▼                ▼
        write_new_memory   AvatarRenderOrchestrator
                                  │
              ┌───────────┬───────┼───────┐
              ▼           ▼       ▼       ▼
            Web        Hologram  桌宠  其它已绑定设备
```

**关键集成点**：
1. 对话前：`memory_service.retrieve()` + `owner_profile_service.load()` 注入 system prompt
2. 对话后：`memory_service.write_from_chat()` 异步写入新记忆
3. 输出时：`render_orchestrator.broadcast(asp_event)` → 所有已绑定设备同步动作

---

## 5. 不在本期范围

明确**不做**的，避免无限蔓延：

- ❌ 真正的向量数据库部署（先 MySQL + LLM 重排）
- ❌ 真正的 BLE / MQTT 通信（先建协议层，driver 走 mock）
- ❌ 全息硬件 SDK（待硬件方确定再展开）
- ❌ 多模态记忆（图片/语音记忆）
- ❌ 跨用户的"分身串门"（社交飞轮 Phase 4）

---

## 6. 风险与对策

| 风险 | 对策 |
|---|---|
| LLM 生成的"记忆"出现幻觉，伤害用户信任 | 所有记忆带 source 标记，用户可"这条不对"一键删除并标记 LLM 不再生成同类 |
| 主人画像越准越像监控，引起反感 | 默认低敏感档位 + 明确开关 + 月度透明报告 |
| 适配层定标准但无人采纳 | 先内部 Web Driver 跑通，再开源协议 + 提供参考实现（树莓派 demo） |
| 性能：每次对话拉一堆记忆 + 画像，延迟高 | 画像缓存到 Redis（TTL 1h），记忆检索 top-K 默认 5 条 |

---

> **本文档是契约**：后续模型、API、服务实现都按此文档对齐；任何偏离需回头更新本文档。

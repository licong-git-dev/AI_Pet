# AI_Pet · PetPal — AI 驱动的宠物社交与电子分身平台

> 让你的猫狗拥有第二条数字生命。
> **目标：比宠物更懂主人。**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)]()
[![Vue](https://img.shields.io/badge/Vue-3.x-42b883.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()

---

## 项目愿景

`AI_Pet` 是一个面向家庭猫狗主人的**社交 + 电子宠物养成**平台。我们相信宠物不只是陪伴，更是有性格、有记忆、有故事的家庭成员。

平台的两大支柱：

1. **宠物社交网络（流量入口）**
   - 宠物主页、动态、社区、健康问诊、宠物商城、积分体系；
   - 主人在分享日常的同时，平台沉淀出宠物的"成长档案"。

2. **AI 电子宠物分身（养成核心）**
   - 基于宠物的**性格、习惯、外貌、健康、互动史**，AI 不断打磨一个数字分身；
   - 分身可与主人聊天、生成专属表情包、模拟脾气与口头禅；
   - **未来形态**：通过全息投影显示在桌面，或加载到桌面机器人/玩具上成为实体陪伴；
   - 分身的最终目标——**比宠物更懂主人**：记得喂食时间、识别情绪、提前提醒、陪伴对话。

类比：参考 OpenPaw / 电子宠物养成 + Replika 数字伙伴 + 宠物版小红书。

---

## 已实现能力

### 后端（FastAPI · 已就绪）

| 模块 | 关键路径 | 说明 |
| --- | --- | --- |
| 认证 | `app/api/auth.py` | JWT access/refresh 双 token、图形验证码、登录日志 |
| 用户 | `app/api/users.py` | 用户资料、设置、会员、积分 |
| 宠物档案 | `app/api/pets.py`, `models/pet.py` | 多宠物管理、品种、健康记录 |
| 健康诊断 | `app/api/diagnosis.py`, `services/qwen_vl_service.py` | 阿里云通义千问 VL 拍照诊断 |
| **电子分身** | `app/api/pet_avatar.py`, `services/pet_avatar_service.py` | **数字分身、性格档案、AI 对话、表情包生成** |
| 社区 | `app/api/posts.py` | 动态发布、评论、点赞、关注 |
| 商城 / 积分 | `app/api/shop.py`, `points.py` | 商品、订单、积分充值与消耗 |
| 即时消息 | `app/api/messages.py`, `websocket/` | 私信、群聊、系统通知 WebSocket |
| 支付 | `app/api/payments.py` | 支付回调与订单状态机 |
| 安全 | `utils/xss_filter.py`, `utils/sql_guard.py`, `middleware/` | XSS / SQL / 速率限制 / CSP |
| 后台 | `app/api/admin/` | 审核、审计、运营面板 |

### 已上线的"电子宠物"原子能力

- **性格档案** (`PersonalityProfile`)：从主人填写 + 互动行为 → 性格画像；
- **数字分身** (`PetAvatar`)：外貌描述、人设、说话风格（cute / sassy / lazy / energetic / gentle）；
- **AI 对话** (`PetAvatarChat`, `PetAvatarMessage`)：分身以宠物视角与主人对话，记忆持续会话；
- **表情包生成** (`PetSticker`)：基于宠物形象生成专属表情包用于社交分发。

---

## 路线图（Roadmap）

> 下面是为了实现"比宠物更懂主人"愿景，已规划但尚未完全落地的方向。

### Phase 1 · 数据沉淀（进行中）
- [x] 宠物多模态档案（照片 + 文字 + 健康记录）
- [x] 性格画像 v1（基于主人输入）
- [ ] 互动事件流（喂食、外出、就医自动记录）
- [ ] 主人侧画像（作息、情绪关键词、关心点）

### Phase 2 · 分身进化
- [x] 文本对话分身
- [ ] 语音分身（TTS / 声纹克隆，需主人授权）
- [ ] 长期记忆模块（Vector DB + 周期性总结）
- [ ] 主动陪伴：分身根据日历/天气/健康主动发起对话

### Phase 3 · 实体化
- [ ] **全息投影 SDK**：分身渲染至桌面雾屏 / Looking Glass / 投影玩具
- [ ] **硬件桌宠适配层**：通用 BLE/MQTT 协议，对接合作硬件
- [ ] AR 滤镜：手机摄像头中"看到"宠物分身

### Phase 4 · 社交飞轮
- [x] 内容社区（基础）
- [ ] 分身互访：朋友的分身可来你家"串门"
- [ ] 宠物社交图谱：基于品种 / 性格 / 地理推荐玩伴

---

## 技术栈

**后端**
- FastAPI 0.109 · SQLAlchemy 2.0 · Alembic · Pydantic v2
- MySQL 8.0 · Redis 7 · Celery（异步任务 + 定时任务）
- 阿里云 DashScope（通义千问 VL）— 多模态宠物诊断与分身生成

**前端**（规划 / 部分代码在另一仓库）
- Vue 3 · TypeScript · Vite · Vant 4（移动端 UI）· Pinia
- 移动优先 · postcss-px-to-viewport 适配

**基础设施**
- Docker Compose · Nginx · 6 容器编排（backend / celery-worker / celery-beat / frontend / mysql / redis）

---

## 快速开始

### 后端

```bash
cd backend

# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp ../.env.docker.example .env    # 修改 JWT_SECRET_KEY / 数据库 / DashScope Key

# 4. 数据库迁移
alembic upgrade head

# 5. 启动开发服务
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 6. (可选) 启动 Celery
celery -A app.celery_app worker --loglevel=info
celery -A app.celery_app beat   --loglevel=info
```

API 文档（开发环境）：

- Swagger: http://localhost:8000/docs
- ReDoc:   http://localhost:8000/redoc

### Docker 一键部署

```bash
docker-compose build
docker-compose up -d
docker-compose exec backend alembic upgrade head
```

参考：[DOCKER_DEPLOY.md](./DOCKER_DEPLOY.md)

---

## 目录结构

```
AI_pet/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/             # 路由（按业务域划分）
│   │   │   ├── pet_avatar.py    # 电子分身 API ⭐
│   │   │   ├── diagnosis.py     # 健康诊断
│   │   │   ├── pets.py / users.py / posts.py / shop.py ...
│   │   │   └── admin/
│   │   ├── models/          # SQLAlchemy ORM
│   │   │   └── avatar.py        # 分身、性格、表情包模型
│   │   ├── schemas/         # Pydantic 请求 / 响应模型
│   │   ├── services/
│   │   │   ├── pet_avatar_service.py    # 分身核心服务 ⭐
│   │   │   ├── qwen_vl_service.py       # 通义千问 VL
│   │   │   └── ai_health.py
│   │   ├── utils/           # XSS / SQL / 文件 / 响应封装
│   │   ├── middleware/      # 速率限制、安全头
│   │   ├── tasks/           # Celery 异步任务
│   │   └── websocket/       # 实时消息
│   ├── alembic/             # 数据库迁移
│   ├── tests/               # pytest 单元测试
│   └── requirements.txt
├── docker/                  # Docker 相关配置
├── docs/                    # 设计 & 测试报告
├── docker-compose.yml
├── DOCKER_DEPLOY.md
└── CLAUDE.md                # AI 协作指引
```

---

## 数据库规范

- 主键：`BIGINT AUTO_INCREMENT`
- 所有表必含：`created_at`、`updated_at`
- 外键：`ON DELETE CASCADE`
- 字符集：`utf8mb4`

---

## API 响应规范

所有接口统一返回：

```json
{
  "code": 0,
  "message": "success",
  "data": { "...": "..." }
}
```

辅助函数位于 `backend/app/utils/response.py`：`success()` / `error()` / `page_response()`。

---

## 开发规范

### 提交信息

```
feat:     新增功能
fix:      修复 bug
docs:     文档更新
refactor: 重构
test:     测试
perf:     性能优化
chore:    构建/配置
```

### 代码风格

- 后端：PEP 8，所有函数必须 Type Hints
- 前端：TypeScript 严格模式，Composition API `<script setup>`

---

## 安全

- JWT 双 token 鉴权 · bcrypt 哈希 · 图形验证码
- XSS 过滤（bleach）· SQL 注入防御 · 文件 MIME 校验
- 速率限制 · CSP · HSTS · X-Frame-Options
- 上传文件白名单 + 病毒级扩展名拦截

---

## License

MIT

---

> **让每只宠物都有一个永远懂主人的数字分身。**

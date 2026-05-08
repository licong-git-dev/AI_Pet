# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

PetPal 是一个 AI 驱动的宠物社交服务平台，提供宠物健康拍照诊断、智能问诊、社区内容分享、宠物商城、积分系统和实时消息等功能。代码库采用 monorepo 结构，包含 Python 后端和 Vue 3 前端。

## 常用命令

### 后端

```bash
cd backend

# 安装依赖
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 启动开发服务器
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 运行全部测试
pytest

# 运行单个测试文件
pytest tests/unit/test_xss_filter.py

# 运行测试并生成覆盖率报告
pytest --cov=app tests/

# 数据库迁移
alembic revision --autogenerate -m "迁移描述"
alembic upgrade head

# Celery 异步任务 worker
celery -A app.celery_app worker --loglevel=info

# Celery 定时任务调度器
celery -A app.celery_app beat --loglevel=info
```

### 前端

```bash
cd frontend

npm install
npm run dev       # 开发服务器 http://localhost:5173
npm run build     # 生产构建
npm run preview   # 预览生产构建
```

### Docker 全栈部署

```bash
docker-compose build
docker-compose up -d
docker-compose exec backend alembic upgrade head
docker-compose logs -f
```

## 架构

### 后端 (`backend/`)

**技术栈**: FastAPI + SQLAlchemy 2.0 + Alembic + Celery + Redis

**分层架构**: API 路由 → Services 业务逻辑 → Models 数据模型 → Database

```
backend/app/
├── main.py            # FastAPI 应用入口、中间件栈、全局异常处理
├── config.py          # 基于 pydantic-settings 的配置（环境变量 / .env）
├── database.py        # SQLAlchemy 引擎和会话管理
├── celery_app.py      # Celery 配置
├── api/               # 路由处理（按业务域划分文件）
│   ├── __init__.py    # 汇总注册所有子路由的 api_router
│   ├── auth.py, users.py, pets.py, posts.py, health.py
│   ├── diagnosis.py, shop.py, points.py, messages.py
│   ├── payments.py, activities.py, upload.py, search.py
│   └── admin/         # 管理后台接口
├── models/            # SQLAlchemy ORM 模型（12 张表）
├── schemas/           # Pydantic 请求/响应模型
├── services/          # 业务逻辑层（ai_health, qwen_vl_service, storage, sms, payment, audit）
├── utils/             # 安全工具（xss_filter, sql_guard, file_validator）、响应工具、依赖注入
├── middleware/         # rate_limit.py, security_headers.py
├── tasks/             # Celery 异步任务（content, health, user, order）
└── websocket/         # WebSocket 处理器和连接管理器
```

**中间件执行顺序**（后添加的先执行）:
1. SecurityHeadersMiddleware（CSP, HSTS, X-Frame-Options）
2. RateLimitMiddleware（速率限制）
3. CORSMiddleware（跨域处理）
4. 请求追踪中间件（耗时统计、请求 ID）

**API 响应格式**: 所有接口统一返回 `{"code": 0, "message": "success", "data": {...}}`。使用 `app/utils/response.py` 中的辅助函数：`success()`、`error()`、`page_response()`。

**认证机制**: JWT access/refresh 双 token。认证依赖通过 `app/utils/deps.py` 注入。除认证接口外，所有路由均需 JWT 鉴权。

**AI 集成**: 通过阿里云 DashScope（通义千问 VL）实现宠物健康拍照诊断，核心逻辑在 `app/services/qwen_vl_service.py` 和 `app/services/ai_health.py`。

**配置管理**: `app/config.py` 基于 `pydantic-settings`，从环境变量和 `.env` 文件加载。详见 `.env.example`。生产环境必须配置 `JWT_SECRET_KEY` 和 `SECRET_KEY`。

### 三大支柱（电子分身核心）

详细 PRD 见 [docs/PRODUCT_DESIGN.md](docs/PRODUCT_DESIGN.md)。代码入口：

| 支柱 | 数据 | 服务 | 接口 / 集成点 |
| --- | --- | --- | --- |
| 长期记忆 | `models/memory.py` (PetMemory + MemoryDigest) | `services/memory_service.py` | `api/memory.py` 9 端点；对话前后由 `services/avatar_chat_pipeline.py` 自动注入与抽取 |
| 主人画像 | `models/owner_profile.py` (OwnerProfile + OwnerSignal) | `services/owner_profile_service.py` | `api/owner_profile.py` 7 端点（含 `/wrapped` 月报）；周期重建在 `tasks/profile_builder.py` |
| 渲染适配层 | `models/device.py` (DeviceBinding) | `services/avatar_render/`（protocol / base / drivers / orchestrator） | `api/devices.py` 6 端点；MQTT publisher 在 `main.py` lifespan 内注入 |

### LLM 网关（`services/llm/`）

为长期记忆抽取 / 周摘要 / 画像构建 / Wrapped 月报创意层提供统一 LLM 接口。

```
LLMRouter (主→次自动 failover)
  ├─ GeminiClient (gemini-flash-latest)
  └─ OpenAIClient (gpt-4o-mini)
```

- 配置：`app/config.py` 的 `LLM_PRIMARY_PROVIDER` / `LLM_FALLBACK_PROVIDER`
- 真实 keys 写在 `backend/.env`（已 gitignored），样例见 `.env.docker.example`
- Celery 任务通过 `services/llm/sync_helpers.py` 调用（`asyncio.run` 桥接）
- 不影响 DashScope 路径，三者并存

### 监控 / Prometheus

后端启动自动挂 `/metrics`。四套业务指标在 `app/utils/metrics.py`：
- `petpal_llm_calls_total{provider,model,outcome}` + `_duration_seconds`
- `petpal_memory_writes_total{memory_type,source}` + 重要度直方图 + 检索耗时 + 抽取决策
- `petpal_wrapped_generated_total{llm_used,outcome}` + cards / secrets 直方图
- `petpal_asp_broadcast_total{event_type,outcome}` + active drivers gauge

Prometheus + Grafana 一键起：`docker compose -f docker/observability/docker-compose.observability.yml up`。
默认仪表盘已 provision（admin / petpal-grafana）。

### 前端 (`frontend/`)

**技术栈**: Vue 3 + TypeScript + Vite + Vant 4（移动端 UI 组件库）+ Pinia

```
frontend/src/
├── views/          # 页面组件（约 40 个页面）
├── components/     # 公共组件
├── composables/    # Vue 3 组合式函数
├── stores/         # Pinia 状态管理（user, pet, cart, diagnosis, notification）
├── router/         # Vue Router 路由配置，含鉴权守卫
├── utils/          # 工具函数和 Axios API 封装
├── types/          # TypeScript 类型定义
└── styles/         # 全局 SCSS 样式
```

**移动端优先**: 使用 `postcss-px-to-viewport` 做响应式适配，基于 Vant 4 组件库。

### 前后端通信

- REST API: 前端调用后端 `/api/v1/*` 接口
- WebSocket: 实时消息推送 `/api/v1/ws/*`
- API 文档（仅开发环境）: Swagger `/docs`，ReDoc `/redoc`

### 基础设施 (Docker)

6 个容器: backend（FastAPI）、celery-worker、celery-beat、frontend（Nginx）、mysql（8.0）、redis（7.0）。在 `docker-compose.yml` 中定义，配有健康检查和数据持久化卷。

## 开发规范

### 新增 API 接口

1. 在 `backend/app/models/` 创建/更新数据模型
2. 在 `backend/app/schemas/` 创建 Pydantic 请求/响应模型
3. 在 `backend/app/api/` 创建路由处理函数
4. 在 `backend/app/api/__init__.py` 注册路由

### 新增前端页面

1. 在 `frontend/src/views/` 创建 Vue 组件
2. 在 `frontend/src/router/index.ts` 添加路由配置
3. 如需状态管理，在 `frontend/src/stores/` 创建 Pinia store

### 数据库规范

- 主键使用 BIGINT AUTO_INCREMENT
- 所有表必须包含 `created_at` 和 `updated_at` 字段
- 外键约束使用 ON DELETE CASCADE
- 字符集使用 UTF8MB4

### Git 提交规范

```
feat: 新增XXX功能
fix: 修复XXX bug
docs: 更新XXX文档
refactor: 重构XXX模块
test: 添加XXX测试
perf: 优化XXX性能
chore: 构建配置变更
```

### 代码风格

- 后端: 遵循 PEP 8，所有函数添加 Type Hints 类型提示
- 前端: TypeScript 严格模式，使用 Vue 3 Composition API `<script setup>` 语法

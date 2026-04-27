"""
PetPal - 主应用入口

集成：
- CORS跨域处理
- 安全响应头 (CSP, HSTS等)
- 速率限制
- 请求追踪
- 全局异常处理
- 静态文件服务
"""
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import time
import uuid

from loguru import logger

from app.config import settings, print_config_status
from app.database import engine, Base
from app.api import api_router
from app.websocket import websocket_router
from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware

# 上传目录配置
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("=" * 50)
    logger.info("[PetPal] API Starting...")
    print_config_status()

    # 创建数据库表（开发环境）
    if settings.debug:
        Base.metadata.create_all(bind=engine)
        logger.info("[PetPal] Database tables created/verified")

    logger.info("[PetPal] WebSocket server enabled")

    # 注入分身渲染编排器的 MQTT 发布器（启用时）
    try:
        from app.services.avatar_render import get_orchestrator
        from app.services.avatar_render.mqtt_publisher import get_publisher
        publisher = get_publisher()
        if publisher is not None:
            get_orchestrator().configure_mqtt_publisher(publisher)
            logger.info("[PetPal] MQTT publisher wired to AvatarRenderOrchestrator")
        else:
            logger.info("[PetPal] MQTT disabled; hologram/desktop_pet drivers will use mock")
    except Exception as e:
        logger.warning(f"[PetPal] MQTT 注入失败（已忽略）: {e}")

    logger.info("=" * 50)

    yield

    # 关闭时
    logger.info("[PetPal] Cleaning up WebSocket connections...")
    logger.info("[PetPal] API Shutdown")
    logger.info("=" * 50)


# 创建FastAPI应用
app = FastAPI(
    title="PetPal API",
    description="AI驱动的宠物社交服务平台API",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan
)


# ==================== 中间件配置 ====================
# 注意：中间件的添加顺序很重要，后添加的先执行

# 1. 安全响应头中间件（最外层）
app.add_middleware(SecurityHeadersMiddleware)

# 2. 速率限制中间件
app.add_middleware(RateLimitMiddleware)

# 3. CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=[
        "X-Process-Time",
        "X-Request-ID",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset"
    ],
)


# ==================== 请求处理中间件 ====================

@app.middleware("http")
async def request_tracking_middleware(request: Request, call_next):
    """请求追踪和耗时统计中间件"""
    # 生成请求ID
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]

    # 记录请求开始时间
    start_time = time.time()

    # 将request_id存储到request.state
    request.state.request_id = request_id

    # 处理请求
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(
            f"Request failed | id={request_id} | "
            f"path={request.url.path} | error={str(e)}"
        )
        raise

    # 计算处理时间
    process_time = time.time() - start_time
    process_time_ms = round(process_time * 1000, 2)

    # 添加响应头
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time_ms}ms"

    # 记录请求日志（排除健康检查）
    if request.url.path not in ["/health", "/", "/favicon.ico"]:
        log_level = "warning" if response.status_code >= 400 else "info"
        getattr(logger, log_level)(
            f"Request | id={request_id} | "
            f"{request.method} {request.url.path} | "
            f"status={response.status_code} | "
            f"time={process_time_ms}ms"
        )

    return response


# ==================== 异常处理 ====================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    request_id = getattr(request.state, "request_id", "unknown")

    # 记录错误日志
    logger.exception(
        f"Unhandled exception | id={request_id} | "
        f"path={request.url.path} | error={str(exc)}"
    )

    # 生产环境不暴露错误详情
    error_message = str(exc) if settings.debug else "服务器内部错误"

    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": error_message,
            "data": None,
            "request_id": request_id
        }
    )


from fastapi import HTTPException

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理"""
    request_id = getattr(request.state, "request_id", "unknown")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail,
            "data": None,
            "request_id": request_id
        },
        headers=exc.headers
    )


# ==================== 路由注册 ====================

# API路由
app.include_router(api_router, prefix="/api/v1")

# WebSocket路由
app.include_router(websocket_router, prefix="/api/v1", tags=["WebSocket"])

# 静态文件服务（上传文件）
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ==================== 基础端点 ====================

@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查端点"""
    return {
        "status": "ok",
        "service": "PetPal API",
        "version": "1.0.0"
    }


@app.get("/", tags=["系统"])
async def root():
    """根路由"""
    return {
        "name": "PetPal API",
        "version": "1.0.0",
        "description": "AI驱动的宠物社交服务平台",
        "docs": "/docs" if settings.debug else "API文档仅在开发环境可用",
        "environment": settings.app_env
    }


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning",
        access_log=settings.debug
    )

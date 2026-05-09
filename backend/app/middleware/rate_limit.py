"""
PetPal - 速率限制中间件

提供API请求频率限制功能，防止滥用和DDoS攻击
支持：
- 全局限流
- 按接口限流
- 按用户限流
- VIP差异化限流
"""
import time
from datetime import datetime, timedelta
from typing import Optional, Callable, Tuple
from functools import wraps

from fastapi import Request, HTTPException, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
from loguru import logger

from app.config import settings


# Redis客户端（懒加载）
_redis_client = None
_memory_store = {}


def _get_redis():
    """获取Redis客户端"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis不可用，使用内存限流: {e}")
        _redis_client = None  # 避免半连通状态被复用
        return None


class SlidingWindowRateLimiter:
    """滑动窗口限流器

    使用Redis的有序集合实现滑动窗口算法
    """

    def __init__(self, key_prefix: str = "rate_limit"):
        self.key_prefix = key_prefix

    def is_allowed(
        self,
        identifier: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, int, int]:
        """检查是否允许请求

        Args:
            identifier: 唯一标识符（如IP、用户ID等）
            max_requests: 窗口内最大请求数
            window_seconds: 时间窗口（秒）

        Returns:
            (是否允许, 剩余请求数, 重置时间戳)
        """
        redis_client = _get_redis()
        key = f"{self.key_prefix}:{identifier}"
        now = time.time()
        window_start = now - window_seconds

        if redis_client:
            return self._redis_sliding_window(
                redis_client, key, max_requests, window_seconds, now, window_start
            )
        else:
            return self._memory_sliding_window(
                key, max_requests, window_seconds, now, window_start
            )

    def _redis_sliding_window(
        self,
        redis_client,
        key: str,
        max_requests: int,
        window_seconds: int,
        now: float,
        window_start: float
    ) -> Tuple[bool, int, int]:
        """Redis滑动窗口实现"""
        pipe = redis_client.pipeline()

        # 移除窗口外的请求记录
        pipe.zremrangebyscore(key, 0, window_start)
        # 获取当前窗口内的请求数
        pipe.zcard(key)
        # 添加当前请求
        pipe.zadd(key, {str(now): now})
        # 设置过期时间
        pipe.expire(key, window_seconds + 1)

        results = pipe.execute()
        current_count = results[1]

        remaining = max(0, max_requests - current_count - 1)
        reset_time = int(now + window_seconds)

        if current_count >= max_requests:
            # 移除刚添加的请求记录（因为已被拒绝）
            redis_client.zrem(key, str(now))
            return False, 0, reset_time

        return True, remaining, reset_time

    def _memory_sliding_window(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        now: float,
        window_start: float
    ) -> Tuple[bool, int, int]:
        """内存滑动窗口实现（用于开发环境）"""
        if key not in _memory_store:
            _memory_store[key] = []

        # 清理过期记录
        _memory_store[key] = [t for t in _memory_store[key] if t > window_start]

        current_count = len(_memory_store[key])
        remaining = max(0, max_requests - current_count - 1)
        reset_time = int(now + window_seconds)

        if current_count >= max_requests:
            return False, 0, reset_time

        _memory_store[key].append(now)
        return True, remaining, reset_time


# 全局限流器实例
rate_limiter = SlidingWindowRateLimiter()


# 限流配置
RATE_LIMIT_CONFIGS = {
    # 全局默认配置
    "default": {"max_requests": 100, "window_seconds": 60},
    # VIP用户配置
    "vip": {"max_requests": 200, "window_seconds": 60},
    # 敏感接口配置
    "/api/v1/auth/send-code": {"max_requests": 5, "window_seconds": 60},
    "/api/v1/auth/login": {"max_requests": 10, "window_seconds": 60},
    "/api/v1/auth/register": {"max_requests": 5, "window_seconds": 60},
    "/api/v1/posts": {"max_requests": 10, "window_seconds": 60},  # POST发帖
    "/api/v1/diagnosis/diagnose": {"max_requests": 10, "window_seconds": 60},
}


def get_rate_limit_config(path: str, is_vip: bool = False) -> dict:
    """获取限流配置

    Args:
        path: 请求路径
        is_vip: 是否为VIP用户

    Returns:
        限流配置
    """
    # 先检查特定路径配置
    for config_path, config in RATE_LIMIT_CONFIGS.items():
        if config_path != "default" and config_path != "vip":
            if path.startswith(config_path):
                # VIP用户翻倍
                if is_vip:
                    return {
                        "max_requests": config["max_requests"] * 2,
                        "window_seconds": config["window_seconds"]
                    }
                return config

    # 返回默认配置
    if is_vip:
        return RATE_LIMIT_CONFIGS["vip"]
    return RATE_LIMIT_CONFIGS["default"]


def get_client_ip(request: Request) -> str:
    """获取客户端IP"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    if request.client:
        return request.client.host

    return "127.0.0.1"


def extract_user_from_token(request: Request) -> Tuple[Optional[int], bool]:
    """从请求的Token中提取用户信息

    Args:
        request: FastAPI请求对象

    Returns:
        (user_id, is_vip) 如果无法提取则返回 (None, False)
    """
    # 获取Authorization头
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, False

    token = auth_header[7:]  # 去掉 "Bearer " 前缀

    try:
        # 解码Token（不验证过期，因为速率限制应该在认证之前）
        # 但我们至少要验证签名
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False}  # 不验证过期，让后续认证处理
        )

        # 提取用户ID
        user_id = payload.get("sub")
        if user_id:
            user_id = int(user_id)
        else:
            return None, False

        # 检查是否为VIP用户（从缓存获取）
        is_vip = _check_user_vip_status(user_id)

        return user_id, is_vip

    except (JWTError, ValueError) as e:
        logger.debug(f"Token解析失败（速率限制）: {e}")
        return None, False


def _check_user_vip_status(user_id: int) -> bool:
    """检查用户VIP状态（使用缓存）

    Args:
        user_id: 用户ID

    Returns:
        是否为VIP用户
    """
    redis_client = _get_redis()
    cache_key = f"user_vip:{user_id}"

    if redis_client:
        try:
            # 从缓存获取VIP状态
            cached = redis_client.get(cache_key)
            if cached is not None:
                return cached == "1"

            # 缓存未命中，查询数据库
            is_vip = _query_user_vip_from_db(user_id)

            # 缓存结果，5分钟过期
            redis_client.setex(cache_key, 300, "1" if is_vip else "0")
            return is_vip

        except Exception as e:
            logger.warning(f"检查VIP状态失败: {e}")
            return False
    else:
        # 无Redis时，使用内存缓存
        cache_entry = _memory_store.get(cache_key)
        if cache_entry and cache_entry.get("expire", 0) > time.time():
            return cache_entry.get("is_vip", False)

        # 查询数据库
        is_vip = _query_user_vip_from_db(user_id)

        # 内存缓存，5分钟过期
        _memory_store[cache_key] = {
            "is_vip": is_vip,
            "expire": time.time() + 300
        }
        return is_vip


def _query_user_vip_from_db(user_id: int) -> bool:
    """从数据库查询用户VIP状态

    Args:
        user_id: 用户ID

    Returns:
        是否为VIP用户
    """
    try:
        # 延迟导入避免循环依赖
        from app.database import SessionLocal
        from app.models.user import User

        db = SessionLocal()
        try:
            user = db.query(User).filter(
                User.id == user_id,
                User.deleted_at.is_(None)
            ).first()

            if not user:
                return False

            # VIP条件：会员等级>0 且 未过期
            if user.member_level > 0:
                if user.member_expire_at is None:
                    return True  # 无过期时间视为永久VIP
                return user.member_expire_at > datetime.now()

            return False
        finally:
            db.close()

    except Exception as e:
        logger.error(f"查询用户VIP状态失败: {e}")
        return False


def invalidate_user_vip_cache(user_id: int):
    """清除用户VIP状态缓存（用于VIP状态变更时调用）

    Args:
        user_id: 用户ID
    """
    redis_client = _get_redis()
    cache_key = f"user_vip:{user_id}"

    if redis_client:
        try:
            redis_client.delete(cache_key)
        except Exception as e:
            logger.warning(f"清除VIP缓存失败: {e}")
    else:
        _memory_store.pop(cache_key, None)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件"""

    async def dispatch(self, request: Request, call_next) -> Response:
        # 跳过健康检查和静态资源
        if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        # 获取客户端标识
        client_ip = get_client_ip(request)

        # 从Token中获取用户ID和VIP状态
        user_id, is_vip = extract_user_from_token(request)

        # 使用用户ID或IP作为标识
        # 登录用户使用user_id，未登录用户使用IP
        identifier = f"user:{user_id}" if user_id else f"ip:{client_ip}"

        # 获取限流配置
        config = get_rate_limit_config(request.url.path, is_vip)

        # 检查是否允许请求
        allowed, remaining, reset_time = rate_limiter.is_allowed(
            identifier,
            config["max_requests"],
            config["window_seconds"]
        )

        if not allowed:
            retry_after = reset_time - int(time.time())
            logger.warning(
                f"Rate limit exceeded: {identifier}, path={request.url.path}, "
                f"is_vip={is_vip}, limit={config['max_requests']}/{config['window_seconds']}s"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "message": "请求过于频繁，请稍后重试",
                    "data": {
                        "retry_after": retry_after
                    }
                },
                headers={
                    "X-RateLimit-Limit": str(config["max_requests"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(retry_after)
                }
            )

        # 执行请求
        response = await call_next(request)

        # 添加限流响应头
        response.headers["X-RateLimit-Limit"] = str(config["max_requests"])
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response


def rate_limit(
    max_requests: int = 60,
    window_seconds: int = 60,
    key_func: Optional[Callable[[Request], str]] = None
):
    """速率限制装饰器

    用于对特定路由进行精细化限流控制

    Args:
        max_requests: 窗口内最大请求数
        window_seconds: 时间窗口（秒）
        key_func: 自定义标识符生成函数

    Example:
        @router.post("/api/sensitive")
        @rate_limit(max_requests=5, window_seconds=60)
        async def sensitive_endpoint():
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从kwargs中获取request
            request = kwargs.get("request") or kwargs.get("req")
            if not request:
                # 尝试从args中找Request对象
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if not request:
                return await func(*args, **kwargs)

            # 生成标识符
            if key_func:
                identifier = key_func(request)
            else:
                identifier = f"route:{func.__name__}:{get_client_ip(request)}"

            # 检查限流
            allowed, remaining, reset_time = rate_limiter.is_allowed(
                identifier, max_requests, window_seconds
            )

            if not allowed:
                retry_after = reset_time - int(time.time())
                raise HTTPException(
                    status_code=429,
                    detail=f"请求过于频繁，请{retry_after}秒后重试",
                    headers={"Retry-After": str(retry_after)}
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator

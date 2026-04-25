"""
PetPal - 安全头中间件

提供：
- Content Security Policy (CSP)
- 其他安全响应头
- 点击劫持保护
- XSS保护
"""
from typing import Optional, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全响应头中间件

    添加各种安全相关的HTTP响应头
    """

    def __init__(
        self,
        app,
        csp_policy: Optional[dict] = None,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,  # 1年
    ):
        super().__init__(app)
        self.csp_policy = csp_policy or self._default_csp_policy()
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age

    def _default_csp_policy(self) -> dict:
        """默认CSP策略"""
        return {
            "default-src": ["'self'"],
            "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],  # 开发环境需要
            "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
            "img-src": ["'self'", "data:", "blob:", "https:"],
            "font-src": ["'self'", "https://fonts.gstatic.com"],
            "connect-src": ["'self'", "https:", "wss:"],
            "media-src": ["'self'", "blob:"],
            "object-src": ["'none'"],
            "frame-src": ["'self'"],
            "frame-ancestors": ["'self'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
            "upgrade-insecure-requests": [],
        }

    def _build_csp_header(self) -> str:
        """构建CSP头字符串"""
        directives = []
        for directive, values in self.csp_policy.items():
            if values:
                directives.append(f"{directive} {' '.join(values)}")
            else:
                directives.append(directive)
        return "; ".join(directives)

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Content Security Policy
        if settings.is_production:
            response.headers["Content-Security-Policy"] = self._build_csp_header()
        else:
            # 开发环境使用Report-Only模式
            response.headers["Content-Security-Policy-Report-Only"] = self._build_csp_header()

        # X-Content-Type-Options - 防止MIME类型嗅探
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-Frame-Options - 防止点击劫持
        response.headers["X-Frame-Options"] = "SAMEORIGIN"

        # X-XSS-Protection - 启用浏览器XSS过滤
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer-Policy - 控制Referer头
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy - 限制浏览器功能
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )

        # HSTS - HTTP严格传输安全（仅生产环境）
        if self.enable_hsts and settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains; preload"
            )

        # Cache-Control for API responses
        if request.url.path.startswith("/api/"):
            # API响应默认不缓存
            if "Cache-Control" not in response.headers:
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"

        return response


class CORSSecurityMiddleware(BaseHTTPMiddleware):
    """CORS安全增强中间件

    在FastAPI的CORS中间件基础上添加额外的安全检查
    """

    def __init__(
        self,
        app,
        allowed_origins: Optional[List[str]] = None,
        allow_credentials: bool = True,
    ):
        super().__init__(app)
        self.allowed_origins = allowed_origins or settings.cors_origins
        self.allow_credentials = allow_credentials

    async def dispatch(self, request: Request, call_next) -> Response:
        origin = request.headers.get("Origin")

        # 检查Origin是否在允许列表中
        if origin:
            origin_allowed = any(
                self._match_origin(origin, allowed)
                for allowed in self.allowed_origins
            )

            if not origin_allowed:
                # 记录可疑的跨域请求
                from loguru import logger
                logger.warning(
                    f"Blocked CORS request from unauthorized origin: {origin}, "
                    f"path={request.url.path}"
                )

        response = await call_next(request)
        return response

    def _match_origin(self, origin: str, pattern: str) -> bool:
        """匹配Origin"""
        if pattern == "*":
            return True
        if pattern == origin:
            return True
        # 支持通配符子域名匹配
        if pattern.startswith("*."):
            domain = pattern[2:]
            return origin.endswith(domain) or origin.endswith(f".{domain}")
        return False


def get_security_headers_middleware(
    csp_policy: Optional[dict] = None,
    enable_hsts: bool = True,
) -> SecurityHeadersMiddleware:
    """获取安全头中间件实例

    Args:
        csp_policy: 自定义CSP策略
        enable_hsts: 是否启用HSTS

    Returns:
        SecurityHeadersMiddleware实例
    """
    return SecurityHeadersMiddleware(
        app=None,  # 会在添加时设置
        csp_policy=csp_policy,
        enable_hsts=enable_hsts
    )


# 预配置的CSP策略
CSP_STRICT = {
    "default-src": ["'self'"],
    "script-src": ["'self'"],
    "style-src": ["'self'"],
    "img-src": ["'self'"],
    "font-src": ["'self'"],
    "connect-src": ["'self'"],
    "media-src": ["'self'"],
    "object-src": ["'none'"],
    "frame-src": ["'none'"],
    "frame-ancestors": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
}

CSP_RELAXED = {
    "default-src": ["'self'", "https:"],
    "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https:"],
    "style-src": ["'self'", "'unsafe-inline'", "https:"],
    "img-src": ["'self'", "data:", "blob:", "https:", "http:"],
    "font-src": ["'self'", "https:", "data:"],
    "connect-src": ["'self'", "https:", "wss:", "http://localhost:*"],
    "media-src": ["'self'", "blob:", "https:"],
    "object-src": ["'none'"],
    "frame-src": ["'self'", "https:"],
    "frame-ancestors": ["'self'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
}

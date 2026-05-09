"""
PetPal - JWT认证工具

提供：
- 密码哈希与验证
- Access Token 生成与验证
- Refresh Token 生成与验证
- Token黑名单管理
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from loguru import logger

from app.config import settings


# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token类型常量
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

# Redis客户端（懒加载）
_redis_client = None
_memory_blacklist = {}  # 内存黑名单（开发环境降级方案）
_memory_refresh_tokens = {}  # 内存刷新令牌存储
_last_cleanup_time = 0  # 上次清理时间
MEMORY_STORE_MAX_SIZE = 10000  # 内存存储最大条目数
CLEANUP_INTERVAL = 300  # 清理间隔（秒）


def _cleanup_memory_stores():
    """清理过期的内存存储数据，防止内存无限增长"""
    global _last_cleanup_time, _memory_blacklist, _memory_refresh_tokens

    current_time = datetime.utcnow().timestamp()

    # 限制清理频率
    if current_time - _last_cleanup_time < CLEANUP_INTERVAL:
        return

    _last_cleanup_time = current_time

    # 清理过期的黑名单
    expired_blacklist = [
        jti for jti, expire in _memory_blacklist.items()
        if expire <= current_time
    ]
    for jti in expired_blacklist:
        del _memory_blacklist[jti]

    # 清理过期的 refresh tokens
    expired_tokens = [
        key for key, data in _memory_refresh_tokens.items()
        if data.get("expire", 0) <= current_time
    ]
    for key in expired_tokens:
        del _memory_refresh_tokens[key]

    # 如果超过最大限制，强制清理最旧的数据
    if len(_memory_blacklist) > MEMORY_STORE_MAX_SIZE:
        sorted_items = sorted(_memory_blacklist.items(), key=lambda x: x[1])
        for jti, _ in sorted_items[:len(_memory_blacklist) - MEMORY_STORE_MAX_SIZE]:
            del _memory_blacklist[jti]

    if len(_memory_refresh_tokens) > MEMORY_STORE_MAX_SIZE:
        sorted_items = sorted(
            _memory_refresh_tokens.items(),
            key=lambda x: x[1].get("expire", 0)
        )
        for key, _ in sorted_items[:len(_memory_refresh_tokens) - MEMORY_STORE_MAX_SIZE]:
            del _memory_refresh_tokens[key]

    if expired_blacklist or expired_tokens:
        logger.debug(f"内存清理: 黑名单={len(expired_blacklist)}, RefreshTokens={len(expired_tokens)}")


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
        logger.warning(f"Redis不可用，Token管理使用内存存储: {e}")
        _redis_client = None  # 避免半连通客户端被复用
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """哈希密码"""
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """创建Access Token

    Args:
        data: 要编码的数据（必须包含sub字段）
        expires_delta: 过期时间增量

    Returns:
        JWT Access Token字符串
    """
    to_encode = data.copy()

    # 设置过期时间
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    # 生成唯一Token ID（用于黑名单）
    jti = str(uuid.uuid4())

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": TOKEN_TYPE_ACCESS,
        "jti": jti,
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def create_refresh_token(
    user_id: int,
    device_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None
) -> Tuple[str, str]:
    """创建Refresh Token

    Args:
        user_id: 用户ID
        device_id: 设备标识（用于多设备管理）
        expires_delta: 过期时间增量

    Returns:
        (Refresh Token字符串, Token ID)
    """
    # 设置过期时间
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)

    # 生成唯一Token ID
    jti = str(uuid.uuid4())

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": TOKEN_TYPE_REFRESH,
        "jti": jti,
        "device_id": device_id or "default",
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    # 存储Refresh Token到Redis（用于单点登出和Token轮换）
    _store_refresh_token(user_id, jti, device_id, expire)

    return encoded_jwt, jti


def _store_refresh_token(
    user_id: int,
    jti: str,
    device_id: Optional[str],
    expire: datetime
):
    """存储Refresh Token信息"""
    redis_client = _get_redis()
    key = f"refresh_token:{user_id}:{device_id or 'default'}"
    ttl = int((expire - datetime.utcnow()).total_seconds())

    if redis_client:
        redis_client.setex(key, ttl, jti)
    else:
        _memory_refresh_tokens[key] = {
            "jti": jti,
            "expire": expire.timestamp()
        }


def verify_token(token: str) -> Optional[dict]:
    """验证JWT Token

    Args:
        token: JWT Token字符串

    Returns:
        解码后的数据，验证失败返回None
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        # 检查是否在黑名单中
        jti = payload.get("jti")
        if jti and is_token_blacklisted(jti):
            logger.warning(f"Token已被吊销: jti={jti}")
            return None

        return payload
    except JWTError as e:
        logger.debug(f"Token验证失败: {e}")
        return None


def verify_access_token(token: str) -> Optional[dict]:
    """验证Access Token

    Args:
        token: JWT Token字符串

    Returns:
        解码后的数据，验证失败返回None
    """
    payload = verify_token(token)
    if payload and payload.get("type") == TOKEN_TYPE_ACCESS:
        return payload
    return None


def verify_refresh_token(token: str) -> Optional[dict]:
    """验证Refresh Token

    Args:
        token: JWT Token字符串

    Returns:
        解码后的数据，验证失败返回None
    """
    payload = verify_token(token)
    if not payload or payload.get("type") != TOKEN_TYPE_REFRESH:
        return None

    # 验证Token是否是当前有效的Refresh Token
    user_id = payload.get("sub")
    device_id = payload.get("device_id", "default")
    jti = payload.get("jti")

    if not _verify_stored_refresh_token(user_id, device_id, jti):
        logger.warning(f"Refresh Token已被轮换或吊销: user_id={user_id}, jti={jti}")
        return None

    return payload


def _verify_stored_refresh_token(
    user_id: str,
    device_id: str,
    jti: str
) -> bool:
    """验证存储的Refresh Token"""
    redis_client = _get_redis()
    key = f"refresh_token:{user_id}:{device_id}"

    if redis_client:
        stored_jti = redis_client.get(key)
        return stored_jti == jti
    else:
        stored = _memory_refresh_tokens.get(key)
        if stored and stored["expire"] > datetime.utcnow().timestamp():
            return stored["jti"] == jti
        return False


def refresh_tokens(
    refresh_token: str,
    device_id: Optional[str] = None
) -> Optional[Dict[str, str]]:
    """使用Refresh Token刷新令牌对

    实现Token轮换：每次刷新都生成新的Refresh Token

    Args:
        refresh_token: 当前的Refresh Token
        device_id: 设备标识

    Returns:
        {
            "access_token": "新的Access Token",
            "refresh_token": "新的Refresh Token"
        }
        刷新失败返回None
    """
    # 验证Refresh Token
    payload = verify_refresh_token(refresh_token)
    if not payload:
        return None

    user_id = int(payload.get("sub"))
    old_jti = payload.get("jti")
    device_id = device_id or payload.get("device_id", "default")

    # 生成新的Token对
    new_access_token = create_access_token(data={"sub": str(user_id)})
    new_refresh_token, new_jti = create_refresh_token(
        user_id=user_id,
        device_id=device_id
    )

    # 将旧的Refresh Token加入黑名单（Token轮换安全措施）
    blacklist_token(old_jti, ttl=86400)  # 保留24小时

    logger.info(f"Token刷新成功: user_id={user_id}, device_id={device_id}")

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token
    }


def blacklist_token(jti: str, ttl: int = 86400):
    """将Token加入黑名单

    Args:
        jti: Token唯一标识
        ttl: 黑名单保留时间（秒），默认24小时
    """
    redis_client = _get_redis()
    key = f"token_blacklist:{jti}"

    if redis_client:
        redis_client.setex(key, ttl, "1")
    else:
        # 定期清理内存存储，防止OOM
        _cleanup_memory_stores()
        _memory_blacklist[jti] = datetime.utcnow().timestamp() + ttl


def is_token_blacklisted(jti: str) -> bool:
    """检查Token是否在黑名单中

    Args:
        jti: Token唯一标识

    Returns:
        是否在黑名单中
    """
    redis_client = _get_redis()
    key = f"token_blacklist:{jti}"

    if redis_client:
        return redis_client.exists(key) > 0
    else:
        # 定期清理内存存储，防止OOM
        _cleanup_memory_stores()
        expire = _memory_blacklist.get(jti)
        if expire and expire > datetime.utcnow().timestamp():
            return True
        elif expire:
            # 清理过期的黑名单项
            del _memory_blacklist[jti]
        return False


def revoke_user_tokens(user_id: int, device_id: Optional[str] = None):
    """吊销用户的所有Token（用于登出/密码修改）

    Args:
        user_id: 用户ID
        device_id: 设备标识（为空则吊销所有设备）
    """
    redis_client = _get_redis()

    if redis_client:
        if device_id:
            # 吊销特定设备
            key = f"refresh_token:{user_id}:{device_id}"
            redis_client.delete(key)
        else:
            # 吊销所有设备
            pattern = f"refresh_token:{user_id}:*"
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)
    else:
        # 内存存储
        keys_to_delete = []
        prefix = f"refresh_token:{user_id}:"
        for key in _memory_refresh_tokens.keys():
            if key.startswith(prefix):
                if device_id is None or key == f"{prefix}{device_id}":
                    keys_to_delete.append(key)
        for key in keys_to_delete:
            del _memory_refresh_tokens[key]

    logger.info(f"用户Token已吊销: user_id={user_id}, device_id={device_id or 'all'}")


def get_user_active_sessions(user_id: int) -> list:
    """获取用户的活跃会话列表

    Args:
        user_id: 用户ID

    Returns:
        活跃会话列表
    """
    redis_client = _get_redis()
    sessions = []

    if redis_client:
        pattern = f"refresh_token:{user_id}:*"
        keys = redis_client.keys(pattern)
        for key in keys:
            device_id = key.split(":")[-1]
            ttl = redis_client.ttl(key)
            if ttl > 0:
                sessions.append({
                    "device_id": device_id,
                    "expires_in": ttl
                })
    else:
        prefix = f"refresh_token:{user_id}:"
        now = datetime.utcnow().timestamp()
        for key, value in _memory_refresh_tokens.items():
            if key.startswith(prefix) and value["expire"] > now:
                device_id = key.replace(prefix, "")
                sessions.append({
                    "device_id": device_id,
                    "expires_in": int(value["expire"] - now)
                })

    return sessions


def decode_token_without_verification(token: str) -> Optional[dict]:
    """解码Token但不验证（用于日志和调试）

    Args:
        token: JWT Token字符串

    Returns:
        解码后的数据
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False}
        )
    except JWTError:
        return None

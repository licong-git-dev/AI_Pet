"""
PetPal - 短信服务模块

提供短信验证码发送功能，集成阿里云短信服务
包含频率限制、IP限制、重试机制、日志记录等功能
"""
import random
import json
from datetime import datetime, timedelta
from typing import Optional, Tuple
from loguru import logger

from app.config import settings

# 阿里云短信SDK (懒加载)
_sms_client = None


def _get_sms_client():
    """获取阿里云短信客户端 (懒加载)"""
    global _sms_client
    if _sms_client is not None:
        return _sms_client

    if not settings.sms_enabled:
        logger.warning("短信服务未配置，将使用模拟模式")
        return None

    try:
        from alibabacloud_dysmsapi20170525.client import Client as Dysmsapi20170525Client
        from alibabacloud_tea_openapi import models as open_api_models

        config = open_api_models.Config(
            access_key_id=settings.aliyun_sms_access_key_id,
            access_key_secret=settings.aliyun_sms_access_key_secret
        )
        config.endpoint = 'dysmsapi.aliyuncs.com'
        _sms_client = Dysmsapi20170525Client(config)
        logger.info("阿里云短信客户端初始化成功")
        return _sms_client
    except Exception as e:
        logger.error(f"阿里云短信客户端初始化失败: {e}")
        return None


# Redis客户端（带备用内存存储）
_memory_store = {}  # 开发环境备用存储
_redis_client = None


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
        logger.warning(f"Redis不可用，使用内存存储: {e}")
        _redis_client = None
        return None


def _cache_get(key: str) -> Optional[str]:
    """从缓存获取值"""
    redis_client = _get_redis()
    if redis_client:
        return redis_client.get(key)
    else:
        item = _memory_store.get(key)
        if item and item['expire'] > datetime.now():
            return item['value']
        return None


def _cache_set(key: str, value: str, ttl: int):
    """设置缓存值"""
    redis_client = _get_redis()
    if redis_client:
        redis_client.setex(key, ttl, value)
    else:
        _memory_store[key] = {
            'value': value,
            'expire': datetime.now() + timedelta(seconds=ttl)
        }


def _cache_exists(key: str) -> bool:
    """检查缓存key是否存在"""
    redis_client = _get_redis()
    if redis_client:
        return redis_client.exists(key) > 0
    else:
        item = _memory_store.get(key)
        return item is not None and item['expire'] > datetime.now()


def _cache_delete(key: str):
    """删除缓存key"""
    redis_client = _get_redis()
    if redis_client:
        redis_client.delete(key)
    else:
        _memory_store.pop(key, None)


def _cache_incr(key: str, ttl: int = 3600) -> int:
    """增加计数器"""
    redis_client = _get_redis()
    if redis_client:
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, ttl)
        return count
    else:
        item = _memory_store.get(key)
        if item and item['expire'] > datetime.now():
            item['value'] = str(int(item['value']) + 1)
            return int(item['value'])
        else:
            _memory_store[key] = {
                'value': '1',
                'expire': datetime.now() + timedelta(seconds=ttl)
            }
            return 1


def generate_code(length: int = 6) -> str:
    """生成随机验证码

    Args:
        length: 验证码长度，默认6位

    Returns:
        验证码字符串
    """
    return "".join([str(random.randint(0, 9)) for _ in range(length)])


def check_phone_rate_limit(phone: str) -> Tuple[bool, str]:
    """检查手机号发送频率限制

    同一手机号60秒内只能发送一次

    Args:
        phone: 手机号

    Returns:
        (是否允许发送, 错误信息)
    """
    rate_key = f"sms_rate:{phone}"
    if _cache_exists(rate_key):
        return False, "发送过于频繁，请60秒后重试"
    return True, ""


def check_ip_rate_limit(ip: str) -> Tuple[bool, str]:
    """检查IP发送频率限制

    同一IP每小时最多发送10次

    Args:
        ip: IP地址

    Returns:
        (是否允许发送, 错误信息)
    """
    ip_key = f"sms_ip_rate:{ip}"
    count = int(_cache_get(ip_key) or 0)
    if count >= 10:
        return False, "该IP发送次数过多，请稍后再试"
    return True, ""


def check_phone_daily_limit(phone: str) -> Tuple[bool, str]:
    """检查手机号每日发送限制

    同一手机号每天最多发送10次

    Args:
        phone: 手机号

    Returns:
        (是否允许发送, 错误信息)
    """
    daily_key = f"sms_daily:{phone}:{datetime.now().strftime('%Y%m%d')}"
    count = int(_cache_get(daily_key) or 0)
    if count >= 10:
        return False, "今日发送次数已达上限，请明天再试"
    return True, ""


async def send_sms_code(
    phone: str,
    ip: str = "127.0.0.1",
    max_retries: int = 3
) -> Tuple[bool, str, Optional[str]]:
    """发送短信验证码

    包含频率限制、IP限制、重试机制

    Args:
        phone: 手机号
        ip: 请求IP地址
        max_retries: 最大重试次数

    Returns:
        (是否成功, 消息, 验证码[仅开发环境返回])
    """
    # 1. 频率限制检查
    allowed, error = check_phone_rate_limit(phone)
    if not allowed:
        logger.warning(f"短信发送被拒绝(频率限制): phone={phone}")
        return False, error, None

    # 2. IP限制检查
    allowed, error = check_ip_rate_limit(ip)
    if not allowed:
        logger.warning(f"短信发送被拒绝(IP限制): phone={phone}, ip={ip}")
        return False, error, None

    # 3. 每日限制检查
    allowed, error = check_phone_daily_limit(phone)
    if not allowed:
        logger.warning(f"短信发送被拒绝(每日限制): phone={phone}")
        return False, error, None

    # 4. 生成验证码
    code = generate_code()

    # 5. 发送短信（带重试）
    sms_client = _get_sms_client()
    send_success = False
    last_error = None

    if sms_client:
        from alibabacloud_dysmsapi20170525 import models as sms_models

        for attempt in range(max_retries):
            try:
                request = sms_models.SendSmsRequest(
                    phone_numbers=phone,
                    sign_name=settings.aliyun_sms_sign_name,
                    template_code=settings.aliyun_sms_template_code,
                    template_param=json.dumps({"code": code})
                )
                response = sms_client.send_sms(request)

                if response.body.code == "OK":
                    send_success = True
                    logger.info(f"短信发送成功: phone={phone}, attempt={attempt + 1}")
                    break
                else:
                    last_error = response.body.message
                    logger.warning(f"短信发送失败: phone={phone}, error={last_error}, attempt={attempt + 1}")

            except Exception as e:
                last_error = str(e)
                logger.error(f"短信发送异常: phone={phone}, error={e}, attempt={attempt + 1}")

            # 重试前等待
            if attempt < max_retries - 1:
                import asyncio
                await asyncio.sleep(1)
    else:
        # 模拟模式（开发环境）
        send_success = True
        logger.info(f"短信发送(模拟模式): phone={phone}, code={code}")

    if not send_success:
        return False, f"短信发送失败: {last_error}", None

    # 6. 存储验证码（5分钟有效）
    code_key = f"sms_code:{phone}"
    _cache_set(code_key, code, 300)

    # 7. 设置频率限制（60秒）
    rate_key = f"sms_rate:{phone}"
    _cache_set(rate_key, "1", 60)

    # 8. 增加IP计数
    ip_key = f"sms_ip_rate:{ip}"
    _cache_incr(ip_key, 3600)

    # 9. 增加每日计数
    daily_key = f"sms_daily:{phone}:{datetime.now().strftime('%Y%m%d')}"
    _cache_incr(daily_key, 86400)

    # 10. 记录发送日志（不记录验证码以确保安全）
    await log_sms_send(phone, ip, send_success)

    return True, "验证码已发送", None


def verify_sms_code(phone: str, code: str) -> Tuple[bool, str]:
    """验证短信验证码

    Args:
        phone: 手机号
        code: 用户输入的验证码

    Returns:
        (是否验证通过, 错误信息)
    """
    code_key = f"sms_code:{phone}"
    stored_code = _cache_get(code_key)

    if not stored_code:
        return False, "验证码已过期"

    if stored_code != code:
        # 记录错误次数
        error_key = f"sms_error:{phone}"
        error_count = _cache_incr(error_key, 300)

        if error_count >= 5:
            # 错误次数过多，删除验证码
            _cache_delete(code_key)
            return False, "验证码错误次数过多，请重新获取"

        return False, "验证码错误"

    # 验证成功，删除验证码和错误计数
    _cache_delete(code_key)
    _cache_delete(f"sms_error:{phone}")

    return True, ""


async def log_sms_send(
    phone: str,
    ip: str,
    success: bool
):
    """记录短信发送日志

    Args:
        phone: 手机号（脱敏）
        ip: IP地址
        success: 是否发送成功
    """
    # 手机号脱敏处理
    masked_phone = f"{phone[:3]}****{phone[-4:]}" if len(phone) >= 7 else "***"

    # 这里可以扩展为写入数据库
    log_data = {
        "phone": masked_phone,
        "ip": ip,
        "success": success,
        "time": datetime.now().isoformat()
    }

    logger.info(f"SMS Log: {json.dumps(log_data)}")


def get_code_ttl(phone: str) -> int:
    """获取验证码剩余有效时间（秒）

    Args:
        phone: 手机号

    Returns:
        剩余有效时间（秒），如果已过期返回0
    """
    redis_client = _get_redis()
    if redis_client:
        code_key = f"sms_code:{phone}"
        ttl = redis_client.ttl(code_key)
        return max(0, ttl)
    return 0


def get_rate_limit_ttl(phone: str) -> int:
    """获取频率限制剩余时间（秒）

    Args:
        phone: 手机号

    Returns:
        剩余等待时间（秒），如果无限制返回0
    """
    redis_client = _get_redis()
    if redis_client:
        rate_key = f"sms_rate:{phone}"
        ttl = redis_client.ttl(rate_key)
        return max(0, ttl)
    return 0

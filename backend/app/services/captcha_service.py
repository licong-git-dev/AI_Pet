"""
PetPal - 图形验证码服务

提供图形验证码生成和验证功能，用于：
- 登录失败次数过多时的人机验证
- 注册时的防刷验证
- 敏感操作的二次验证
"""
import io
import uuid
import random
import string
from datetime import datetime, timedelta
from typing import Optional, Tuple

from loguru import logger

from app.config import settings


# Redis客户端（懒加载）
_redis_client = None
_memory_store = {}  # 内存存储（开发环境降级方案）


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
        logger.warning(f"Redis不可用，验证码使用内存存储: {e}")
        _redis_client = None  # 显式置空，避免半连通状态被复用
        return None


# 验证码配置
CAPTCHA_LENGTH = 4
CAPTCHA_EXPIRE_SECONDS = 300  # 5分钟
CAPTCHA_WIDTH = 160
CAPTCHA_HEIGHT = 60


def generate_captcha_code(length: int = CAPTCHA_LENGTH) -> str:
    """生成随机验证码字符串

    Args:
        length: 验证码长度

    Returns:
        验证码字符串
    """
    # 使用容易区分的字符，排除 0/O, 1/I/l 等易混淆字符
    chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(random.choices(chars, k=length))


def generate_captcha_image(code: str) -> bytes:
    """生成验证码图片

    Args:
        code: 验证码字符串

    Returns:
        PNG图片的bytes数据
    """
    try:
        from captcha.image import ImageCaptcha

        # 创建验证码图片生成器
        image_captcha = ImageCaptcha(
            width=CAPTCHA_WIDTH,
            height=CAPTCHA_HEIGHT,
            font_sizes=(36, 40, 44)
        )

        # 生成图片
        image = image_captcha.generate(code)
        return image.read()

    except ImportError:
        # 如果captcha库不可用，使用PIL简单实现
        return _generate_simple_captcha_image(code)


def _generate_simple_captcha_image(code: str) -> bytes:
    """简单的验证码图片生成（降级方案）"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        # 创建图片
        width, height = CAPTCHA_WIDTH, CAPTCHA_HEIGHT
        image = Image.new("RGB", (width, height), _random_color(200, 255))

        draw = ImageDraw.Draw(image)

        # 尝试使用系统字体
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except Exception:
            font = ImageFont.load_default()

        # 绘制文字
        char_width = width // (len(code) + 1)
        for i, char in enumerate(code):
            x = char_width * (i + 0.5)
            y = random.randint(5, height - 45)
            color = _random_color(0, 150)
            draw.text((x, y), char, font=font, fill=color)

        # 添加干扰线
        for _ in range(5):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            draw.line([(x1, y1), (x2, y2)], fill=_random_color(100, 200))

        # 添加干扰点
        for _ in range(100):
            x = random.randint(0, width)
            y = random.randint(0, height)
            draw.point((x, y), fill=_random_color(100, 200))

        # 保存为bytes
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    except ImportError:
        logger.error("PIL库未安装，无法生成验证码图片")
        raise RuntimeError("验证码服务不可用")


def _random_color(min_val: int, max_val: int) -> Tuple[int, int, int]:
    """生成随机颜色"""
    return (
        random.randint(min_val, max_val),
        random.randint(min_val, max_val),
        random.randint(min_val, max_val)
    )


def create_captcha() -> Tuple[str, str, bytes]:
    """创建验证码

    Returns:
        (captcha_id, captcha_code, captcha_image_bytes)
    """
    # 生成唯一ID
    captcha_id = str(uuid.uuid4())

    # 生成验证码
    code = generate_captcha_code()

    # 生成图片
    image_bytes = generate_captcha_image(code)

    # 存储验证码（不区分大小写）
    _store_captcha(captcha_id, code.upper())

    logger.debug(f"生成验证码: id={captcha_id}, code={code}")

    return captcha_id, code, image_bytes


def _store_captcha(captcha_id: str, code: str):
    """存储验证码"""
    redis_client = _get_redis()
    key = f"captcha:{captcha_id}"

    if redis_client:
        redis_client.setex(key, CAPTCHA_EXPIRE_SECONDS, code)
    else:
        _memory_store[key] = {
            "code": code,
            "expire": datetime.now().timestamp() + CAPTCHA_EXPIRE_SECONDS
        }


def verify_captcha(captcha_id: str, code: str) -> Tuple[bool, str]:
    """验证验证码

    Args:
        captcha_id: 验证码ID
        code: 用户输入的验证码

    Returns:
        (是否验证通过, 错误信息)
    """
    if not captcha_id or not code:
        return False, "验证码不能为空"

    redis_client = _get_redis()
    key = f"captcha:{captcha_id}"

    # 获取存储的验证码
    stored_code = None

    if redis_client:
        stored_code = redis_client.get(key)
        # 验证后删除（一次性使用）
        if stored_code:
            redis_client.delete(key)
    else:
        stored = _memory_store.get(key)
        if stored and stored["expire"] > datetime.now().timestamp():
            stored_code = stored["code"]
        # 删除
        if key in _memory_store:
            del _memory_store[key]

    if not stored_code:
        return False, "验证码已过期或不存在"

    # 不区分大小写比较
    if stored_code.upper() != code.upper():
        return False, "验证码错误"

    return True, "验证通过"


def get_captcha_ttl(captcha_id: str) -> int:
    """获取验证码剩余有效时间

    Args:
        captcha_id: 验证码ID

    Returns:
        剩余秒数，-1表示不存在或已过期
    """
    redis_client = _get_redis()
    key = f"captcha:{captcha_id}"

    if redis_client:
        ttl = redis_client.ttl(key)
        return max(ttl, -1)
    else:
        stored = _memory_store.get(key)
        if stored:
            remaining = int(stored["expire"] - datetime.now().timestamp())
            return max(remaining, -1)
        return -1


class CaptchaService:
    """验证码服务类"""

    @staticmethod
    def create() -> Tuple[str, str, bytes]:
        """创建验证码"""
        return create_captcha()

    @staticmethod
    def verify(captcha_id: str, code: str) -> Tuple[bool, str]:
        """验证验证码"""
        return verify_captcha(captcha_id, code)

    @staticmethod
    def get_ttl(captcha_id: str) -> int:
        """获取验证码剩余时间"""
        return get_captcha_ttl(captcha_id)


# 全局服务实例
captcha_service = CaptchaService()

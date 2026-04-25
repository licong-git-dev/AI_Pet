"""
PetPal - 图形验证码服务单元测试
"""
import pytest
from app.services.captcha_service import (
    generate_captcha_code, generate_captcha_image,
    create_captcha, verify_captcha, get_captcha_ttl,
    CaptchaService, captcha_service,
    CAPTCHA_LENGTH, CAPTCHA_EXPIRE_SECONDS
)


class TestGenerateCaptchaCode:
    """测试验证码生成"""

    def test_default_length(self):
        """测试默认长度"""
        code = generate_captcha_code()
        assert len(code) == CAPTCHA_LENGTH

    def test_custom_length(self):
        """测试自定义长度"""
        code = generate_captcha_code(length=6)
        assert len(code) == 6

    def test_uppercase_letters(self):
        """测试包含大写字母"""
        code = generate_captcha_code()
        assert any(c.isupper() for c in code)

    def test_no_confusing_chars(self):
        """测试不包含易混淆字符"""
        # 生成多个验证码检查
        for _ in range(100):
            code = generate_captcha_code()
            # 不应包含0, O, 1, I, l
            assert '0' not in code
            assert 'O' not in code
            assert '1' not in code
            assert 'I' not in code
            assert 'l' not in code

    def test_randomness(self):
        """测试随机性"""
        codes = [generate_captcha_code() for _ in range(10)]
        # 10个验证码应该大部分不同
        unique_codes = set(codes)
        assert len(unique_codes) > 5


class TestGenerateCaptchaImage:
    """测试验证码图片生成"""

    def test_returns_bytes(self):
        """测试返回字节数据"""
        image_bytes = generate_captcha_image('ABCD')
        assert isinstance(image_bytes, bytes)
        assert len(image_bytes) > 0

    def test_png_format(self):
        """测试PNG格式"""
        image_bytes = generate_captcha_image('TEST')
        # PNG文件头
        assert image_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    def test_different_codes_different_images(self):
        """测试不同验证码生成不同图片"""
        image1 = generate_captcha_image('AAAA')
        image2 = generate_captcha_image('BBBB')
        assert image1 != image2


class TestCreateCaptcha:
    """测试创建验证码"""

    def test_returns_tuple(self):
        """测试返回元组"""
        result = create_captcha()
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_captcha_id_format(self):
        """测试验证码ID格式"""
        captcha_id, code, image = create_captcha()
        # UUID格式
        assert len(captcha_id) == 36
        assert '-' in captcha_id

    def test_code_format(self):
        """测试验证码格式"""
        captcha_id, code, image = create_captcha()
        assert len(code) == CAPTCHA_LENGTH
        assert code.isalnum()

    def test_image_data(self):
        """测试图片数据"""
        captcha_id, code, image = create_captcha()
        assert isinstance(image, bytes)
        assert len(image) > 0


class TestVerifyCaptcha:
    """测试验证码验证"""

    def test_verify_correct_code(self):
        """测试正确验证码"""
        captcha_id, code, image = create_captcha()
        valid, msg = verify_captcha(captcha_id, code)
        assert valid
        assert '通过' in msg

    def test_verify_case_insensitive(self):
        """测试大小写不敏感"""
        captcha_id, code, image = create_captcha()
        # 尝试小写
        valid, msg = verify_captcha(captcha_id, code.lower())
        assert valid

    def test_verify_wrong_code(self):
        """测试错误验证码"""
        captcha_id, code, image = create_captcha()
        valid, msg = verify_captcha(captcha_id, 'WRONG')
        assert not valid
        assert '错误' in msg

    def test_verify_expired_or_nonexistent(self):
        """测试过期或不存在的验证码"""
        valid, msg = verify_captcha('nonexistent-id', 'CODE')
        assert not valid
        assert '过期' in msg or '不存在' in msg

    def test_verify_empty_code(self):
        """测试空验证码"""
        captcha_id, code, image = create_captcha()
        valid, msg = verify_captcha(captcha_id, '')
        assert not valid

    def test_verify_empty_id(self):
        """测试空验证码ID"""
        valid, msg = verify_captcha('', 'CODE')
        assert not valid

    def test_one_time_use(self):
        """测试一次性使用"""
        captcha_id, code, image = create_captcha()
        # 第一次验证
        valid1, msg1 = verify_captcha(captcha_id, code)
        assert valid1
        # 第二次验证应该失败
        valid2, msg2 = verify_captcha(captcha_id, code)
        assert not valid2


class TestGetCaptchaTtl:
    """测试获取验证码剩余时间"""

    def test_fresh_captcha_ttl(self):
        """测试新创建验证码的TTL"""
        captcha_id, code, image = create_captcha()
        ttl = get_captcha_ttl(captcha_id)
        # 应该接近过期时间
        assert ttl > 0
        assert ttl <= CAPTCHA_EXPIRE_SECONDS

    def test_nonexistent_captcha_ttl(self):
        """测试不存在验证码的TTL"""
        ttl = get_captcha_ttl('nonexistent-id')
        assert ttl == -1

    def test_used_captcha_ttl(self):
        """测试已使用验证码的TTL"""
        captcha_id, code, image = create_captcha()
        verify_captcha(captcha_id, code)  # 使用验证码
        ttl = get_captcha_ttl(captcha_id)
        assert ttl == -1


class TestCaptchaService:
    """测试CaptchaService类"""

    def test_create_method(self):
        """测试create方法"""
        result = CaptchaService.create()
        assert len(result) == 3

    def test_verify_method(self):
        """测试verify方法"""
        captcha_id, code, image = CaptchaService.create()
        valid, msg = CaptchaService.verify(captcha_id, code)
        assert valid

    def test_get_ttl_method(self):
        """测试get_ttl方法"""
        captcha_id, code, image = CaptchaService.create()
        ttl = CaptchaService.get_ttl(captcha_id)
        assert ttl > 0


class TestCaptchaServiceInstance:
    """测试captcha_service实例"""

    def test_instance_exists(self):
        """测试实例存在"""
        assert captcha_service is not None
        assert isinstance(captcha_service, CaptchaService)

    def test_instance_methods(self):
        """测试实例方法"""
        # 创建
        captcha_id, code, image = captcha_service.create()
        assert captcha_id
        assert code
        assert image

        # 获取TTL
        ttl = captcha_service.get_ttl(captcha_id)
        assert ttl > 0

        # 验证
        valid, msg = captcha_service.verify(captcha_id, code)
        assert valid


class TestCaptchaConfig:
    """测试验证码配置"""

    def test_captcha_length(self):
        """测试验证码长度配置"""
        assert CAPTCHA_LENGTH == 4

    def test_captcha_expire_seconds(self):
        """测试过期时间配置"""
        assert CAPTCHA_EXPIRE_SECONDS == 300  # 5分钟

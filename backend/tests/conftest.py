"""
PetPal - 测试配置文件

包含pytest fixtures和公共测试工具
"""
import os
import sys
import pytest
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def sample_image_bytes():
    """生成测试用的PNG图片字节"""
    # 最小的有效PNG图片（1x1像素透明）
    return bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
        0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
        0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
        0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,  # IEND chunk
        0x42, 0x60, 0x82
    ])


@pytest.fixture
def sample_jpeg_bytes():
    """生成测试用的JPEG图片字节"""
    # JPEG文件头
    return bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46,
        0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
        0x00, 0x01, 0x00, 0x00
    ])


@pytest.fixture
def malicious_file_bytes():
    """生成包含可疑内容的文件字节"""
    return b'<script>alert("XSS")</script>'


@pytest.fixture
def sql_injection_samples():
    """SQL注入测试样本"""
    return [
        "'; DROP TABLE users; --",
        "1' OR '1'='1",
        "admin'--",
        "1; SELECT * FROM users",
        "' UNION SELECT * FROM passwords --",
        "1' AND 1=1 --",
        "'; EXEC xp_cmdshell('dir'); --",
        "1 OR 1=1",
        "' OR ''='",
    ]


@pytest.fixture
def xss_samples():
    """XSS攻击测试样本"""
    return [
        '<script>alert("XSS")</script>',
        '<img src="x" onerror="alert(1)">',
        '<svg onload="alert(1)">',
        'javascript:alert(1)',
        '<a href="javascript:alert(1)">Click</a>',
        '<div onclick="alert(1)">Test</div>',
        '"><script>alert(1)</script>',
        '<iframe src="javascript:alert(1)">',
    ]


@pytest.fixture
def safe_text_samples():
    """安全文本测试样本"""
    return [
        "Hello World",
        "这是一段中文文本",
        "User's input with apostrophe",
        "Email: test@example.com",
        "Price: $19.99",
        "100% satisfaction guaranteed",
    ]

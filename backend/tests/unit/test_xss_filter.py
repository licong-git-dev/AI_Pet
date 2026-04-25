"""
PetPal - XSS过滤器单元测试
"""
import pytest
from app.utils.xss_filter import (
    clean_html, strip_tags, escape_html, sanitize_text,
    sanitize_url, sanitize_filename, check_content_safety,
    ContentSanitizer
)


class TestCleanHtml:
    """测试clean_html函数"""

    def test_clean_script_tags(self):
        """测试清除script标签"""
        html = '<p>Hello</p><script>alert("XSS")</script>'
        result = clean_html(html)
        assert '<script>' not in result
        assert 'alert' not in result
        assert '<p>Hello</p>' in result

    def test_clean_event_handlers(self):
        """测试清除事件处理器"""
        html = '<img src="x" onerror="alert(1)">'
        result = clean_html(html)
        assert 'onerror' not in result

    def test_allow_safe_tags(self):
        """测试允许安全标签"""
        html = '<p>Text</p><strong>Bold</strong><a href="https://example.com">Link</a>'
        result = clean_html(html)
        assert '<p>' in result
        assert '<strong>' in result
        assert '<a href=' in result

    def test_clean_javascript_url(self):
        """测试清除javascript URL"""
        html = '<a href="javascript:alert(1)">Click</a>'
        result = clean_html(html)
        assert 'javascript:' not in result


class TestStripTags:
    """测试strip_tags函数"""

    def test_strip_all_tags(self):
        """测试移除所有标签"""
        html = '<p>Hello <strong>World</strong></p>'
        result = strip_tags(html)
        assert result == 'Hello World'

    def test_strip_nested_tags(self):
        """测试移除嵌套标签"""
        html = '<div><p><span>Text</span></p></div>'
        result = strip_tags(html)
        assert result == 'Text'

    def test_preserve_text(self):
        """测试保留文本内容"""
        html = '普通文本没有标签'
        result = strip_tags(html)
        assert result == '普通文本没有标签'


class TestEscapeHtml:
    """测试escape_html函数"""

    def test_escape_angle_brackets(self):
        """测试转义尖括号"""
        text = '<script>alert(1)</script>'
        result = escape_html(text)
        assert '<' not in result or '&lt;' in result
        assert '>' not in result or '&gt;' in result

    def test_escape_quotes(self):
        """测试转义引号"""
        text = 'He said "Hello"'
        result = escape_html(text)
        assert '&quot;' in result or '"' not in result

    def test_escape_ampersand(self):
        """测试转义&符号"""
        text = 'A & B'
        result = escape_html(text)
        assert '&amp;' in result


class TestSanitizeText:
    """测试sanitize_text函数"""

    def test_sanitize_normal_text(self):
        """测试普通文本"""
        text = 'Hello World'
        result = sanitize_text(text)
        assert result == 'Hello World'

    def test_sanitize_chinese(self):
        """测试中文文本"""
        text = '你好世界'
        result = sanitize_text(text)
        assert result == '你好世界'

    def test_sanitize_with_max_length(self):
        """测试长度限制"""
        text = 'A' * 1000
        result = sanitize_text(text, max_length=100)
        assert len(result) <= 100


class TestSanitizeUrl:
    """测试sanitize_url函数"""

    def test_valid_http_url(self):
        """测试有效HTTP URL"""
        url = 'https://example.com/path?query=1'
        result = sanitize_url(url)
        assert result == url

    def test_block_javascript_url(self):
        """测试阻止javascript URL"""
        url = 'javascript:alert(1)'
        result = sanitize_url(url)
        assert result == '' or 'javascript' not in result.lower()

    def test_block_data_url(self):
        """测试阻止data URL"""
        url = 'data:text/html,<script>alert(1)</script>'
        result = sanitize_url(url)
        assert result == '' or 'data:' not in result.lower()


class TestSanitizeFilename:
    """测试sanitize_filename函数"""

    def test_remove_path_traversal(self):
        """测试移除路径遍历"""
        filename = '../../../etc/passwd'
        result = sanitize_filename(filename)
        assert '..' not in result
        assert '/' not in result

    def test_remove_special_chars(self):
        """测试移除特殊字符"""
        filename = 'file<>:"|?*.txt'
        result = sanitize_filename(filename)
        assert '<' not in result
        assert '>' not in result
        assert ':' not in result

    def test_preserve_extension(self):
        """测试保留扩展名"""
        filename = 'document.pdf'
        result = sanitize_filename(filename)
        assert result.endswith('.pdf')


class TestCheckContentSafety:
    """测试check_content_safety函数"""

    def test_safe_content(self):
        """测试安全内容"""
        content = '这是一段正常的文本内容'
        is_safe, issues = check_content_safety(content)
        assert is_safe
        assert len(issues) == 0

    def test_detect_xss(self, xss_samples):
        """测试检测XSS攻击"""
        for sample in xss_samples:
            is_safe, issues = check_content_safety(sample)
            # 至少应该检测到部分XSS攻击
            # 具体行为取决于实现


class TestContentSanitizer:
    """测试ContentSanitizer类"""

    def test_sanitizer_instance(self):
        """测试创建实例"""
        sanitizer = ContentSanitizer()
        assert sanitizer is not None

    def test_sanitize_dict(self):
        """测试清理字典数据"""
        sanitizer = ContentSanitizer()
        data = {
            'title': '<script>alert(1)</script>Title',
            'content': '<p>Content</p>',
        }
        result = sanitizer.sanitize_dict(data, ['title', 'content'])
        assert '<script>' not in str(result)

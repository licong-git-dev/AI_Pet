"""
PetPal - XSS过滤与内容安全工具

提供XSS攻击防护和内容安全过滤功能
"""
import re
from typing import Optional, List, Set
from html import escape as html_escape

# 尝试导入bleach库，如果不存在则使用简单的HTML转义
try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False


# 允许的HTML标签（用于富文本内容）
ALLOWED_TAGS: List[str] = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'br', 'code',
    'em', 'i', 'li', 'ol', 'p', 'pre', 'strong', 'ul',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr',
    'span', 'div', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
]

# 允许的HTML属性
ALLOWED_ATTRIBUTES: dict = {
    '*': ['class', 'id', 'style'],
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'table': ['border', 'cellpadding', 'cellspacing'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan'],
}

# 允许的CSS属性（用于style属性过滤）
ALLOWED_STYLES: List[str] = [
    'color', 'background-color', 'font-size', 'font-weight',
    'text-align', 'text-decoration', 'margin', 'padding',
    'border', 'width', 'height',
]

# 允许的URL协议
ALLOWED_PROTOCOLS: List[str] = ['http', 'https', 'mailto']

# 危险字符/模式
DANGEROUS_PATTERNS = [
    r'javascript:',
    r'vbscript:',
    r'data:',
    r'on\w+\s*=',  # onclick, onload等事件处理器
    r'<script',
    r'</script',
    r'<iframe',
    r'</iframe',
    r'<object',
    r'</object',
    r'<embed',
    r'</embed',
    r'expression\s*\(',
    r'url\s*\(',
]


def clean_html(
    html: Optional[str],
    allowed_tags: Optional[List[str]] = None,
    allowed_attributes: Optional[dict] = None,
    strip: bool = True
) -> Optional[str]:
    """清理HTML内容，移除危险标签和属性

    Args:
        html: 要清理的HTML内容
        allowed_tags: 允许的标签列表
        allowed_attributes: 允许的属性字典
        strip: 是否移除不允许的标签（True）或转义（False）

    Returns:
        清理后的HTML
    """
    if not html:
        return html

    tags = allowed_tags or ALLOWED_TAGS
    attrs = allowed_attributes or ALLOWED_ATTRIBUTES

    if BLEACH_AVAILABLE:
        return bleach.clean(
            html,
            tags=tags,
            attributes=attrs,
            protocols=ALLOWED_PROTOCOLS,
            strip=strip
        )
    else:
        # 简单实现：移除所有HTML标签
        return strip_tags(html)


def strip_tags(text: Optional[str]) -> Optional[str]:
    """移除所有HTML标签

    Args:
        text: 包含HTML标签的文本

    Returns:
        纯文本
    """
    if not text:
        return text

    # 移除HTML标签
    clean = re.sub(r'<[^>]+>', '', text)
    # 解码HTML实体
    clean = clean.replace('&nbsp;', ' ')
    clean = clean.replace('&lt;', '<')
    clean = clean.replace('&gt;', '>')
    clean = clean.replace('&amp;', '&')
    clean = clean.replace('&quot;', '"')
    return clean.strip()


def escape_html(text: Optional[str]) -> Optional[str]:
    """转义HTML特殊字符

    Args:
        text: 要转义的文本

    Returns:
        转义后的文本
    """
    if not text:
        return text
    return html_escape(text, quote=True)


def sanitize_text(text: Optional[str]) -> Optional[str]:
    """清理纯文本内容

    用于用户昵称、宠物名称等不应包含HTML的字段

    Args:
        text: 要清理的文本

    Returns:
        清理后的文本
    """
    if not text:
        return text

    # 移除HTML标签
    text = strip_tags(text)

    # 移除危险字符
    for pattern in DANGEROUS_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # 移除控制字符（保留换行和制表符）
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    return text.strip()


def sanitize_url(url: Optional[str]) -> Optional[str]:
    """清理URL，防止XSS攻击

    Args:
        url: 要清理的URL

    Returns:
        清理后的URL，如果不安全则返回None
    """
    if not url:
        return url

    url = url.strip()

    # 检查协议
    url_lower = url.lower()
    if url_lower.startswith('javascript:'):
        return None
    if url_lower.startswith('vbscript:'):
        return None
    if url_lower.startswith('data:') and not url_lower.startswith('data:image/'):
        return None

    # 检查危险模式
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return None

    return url


def sanitize_filename(filename: Optional[str]) -> Optional[str]:
    """清理文件名，防止目录遍历攻击

    Args:
        filename: 文件名

    Returns:
        安全的文件名
    """
    if not filename:
        return filename

    # 移除路径分隔符
    filename = filename.replace('/', '_').replace('\\', '_')
    # 移除 ..
    filename = filename.replace('..', '_')
    # 移除特殊字符
    filename = re.sub(r'[<>:"|?*]', '_', filename)
    # 移除控制字符
    filename = re.sub(r'[\x00-\x1f]', '', filename)

    return filename.strip('._')


def check_content_safety(content: Optional[str]) -> dict:
    """检查内容安全性

    Args:
        content: 要检查的内容

    Returns:
        安全检查结果
    """
    result = {
        "is_safe": True,
        "warnings": [],
        "dangerous_patterns": []
    }

    if not content:
        return result

    content_lower = content.lower()

    # 检查危险模式
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            result["is_safe"] = False
            result["dangerous_patterns"].append(pattern)

    # 检查可疑关键词
    suspicious_words = ['<script', 'javascript:', 'onclick', 'onerror', 'eval(']
    for word in suspicious_words:
        if word in content_lower:
            result["warnings"].append(f"发现可疑内容: {word}")

    return result


class ContentSanitizer:
    """内容清理器

    提供统一的内容清理接口
    """

    @staticmethod
    def sanitize_post_content(content: Optional[str]) -> Optional[str]:
        """清理帖子内容（允许部分HTML）"""
        return clean_html(content)

    @staticmethod
    def sanitize_comment(content: Optional[str]) -> Optional[str]:
        """清理评论内容（只允许基本格式）"""
        basic_tags = ['b', 'i', 'em', 'strong', 'br', 'a']
        basic_attrs = {'a': ['href']}
        return clean_html(content, allowed_tags=basic_tags, allowed_attributes=basic_attrs)

    @staticmethod
    def sanitize_nickname(name: Optional[str]) -> Optional[str]:
        """清理昵称"""
        return sanitize_text(name)

    @staticmethod
    def sanitize_bio(bio: Optional[str]) -> Optional[str]:
        """清理个人简介"""
        return sanitize_text(bio)

    @staticmethod
    def sanitize_pet_name(name: Optional[str]) -> Optional[str]:
        """清理宠物名称"""
        return sanitize_text(name)

    @staticmethod
    def sanitize_search_query(query: Optional[str]) -> Optional[str]:
        """清理搜索查询"""
        if not query:
            return query
        # 移除特殊字符
        query = re.sub(r'[<>"\';\\]', '', query)
        return query.strip()[:100]  # 限制长度

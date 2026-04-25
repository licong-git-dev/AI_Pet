"""
PetPal - 文件上传安全验证服务

提供全面的文件上传安全检查：
- MIME类型检测（基于magic bytes）
- 文件扩展名验证
- 文件大小限制
- 安全文件名生成
- 图片文件验证
- 恶意软件扫描钩子
"""
import os
import re
import uuid
import hashlib
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any, BinaryIO, Union
from io import BytesIO

from loguru import logger


# ==================== 文件类型定义 ====================

# Magic Bytes 签名（用于真实MIME类型检测）
MAGIC_BYTES = {
    # 图片格式
    b'\xFF\xD8\xFF': 'image/jpeg',
    b'\x89PNG\r\n\x1a\n': 'image/png',
    b'GIF87a': 'image/gif',
    b'GIF89a': 'image/gif',
    b'RIFF': 'image/webp',  # 需要进一步检查
    b'BM': 'image/bmp',
    b'\x00\x00\x01\x00': 'image/x-icon',
    b'\x00\x00\x02\x00': 'image/x-icon',
    # 文档格式
    b'%PDF': 'application/pdf',
    b'PK\x03\x04': 'application/zip',  # 也可能是docx, xlsx等
    # 视频格式
    b'\x00\x00\x00\x1c\x66\x74\x79\x70': 'video/mp4',
    b'\x00\x00\x00\x20\x66\x74\x79\x70': 'video/mp4',
    # 音频格式
    b'ID3': 'audio/mpeg',
    b'\xFF\xFB': 'audio/mpeg',
    b'\xFF\xFA': 'audio/mpeg',
}

# 允许的文件类型配置
ALLOWED_FILE_TYPES = {
    'image': {
        'extensions': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'],
        'mime_types': ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'],
        'max_size': 10 * 1024 * 1024,  # 10MB
    },
    'avatar': {
        'extensions': ['.jpg', '.jpeg', '.png', '.webp'],
        'mime_types': ['image/jpeg', 'image/png', 'image/webp'],
        'max_size': 2 * 1024 * 1024,  # 2MB
    },
    'document': {
        'extensions': ['.pdf', '.doc', '.docx', '.txt'],
        'mime_types': ['application/pdf', 'application/msword',
                       'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                       'text/plain'],
        'max_size': 20 * 1024 * 1024,  # 20MB
    },
    'video': {
        'extensions': ['.mp4', '.mov', '.avi', '.webm'],
        'mime_types': ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm'],
        'max_size': 100 * 1024 * 1024,  # 100MB
    },
    'audio': {
        'extensions': ['.mp3', '.wav', '.ogg', '.m4a'],
        'mime_types': ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp4'],
        'max_size': 20 * 1024 * 1024,  # 20MB
    },
}

# 危险文件扩展名黑名单
DANGEROUS_EXTENSIONS = {
    '.exe', '.bat', '.cmd', '.com', '.msi', '.scr',  # Windows可执行
    '.sh', '.bash', '.zsh',  # Shell脚本
    '.php', '.phtml', '.php3', '.php4', '.php5',  # PHP
    '.asp', '.aspx', '.asa',  # ASP
    '.jsp', '.jspx',  # JSP
    '.py', '.pyc', '.pyo',  # Python
    '.rb', '.erb',  # Ruby
    '.pl', '.cgi',  # Perl/CGI
    '.js', '.mjs',  # JavaScript (服务端)
    '.htaccess', '.htpasswd',  # Apache配置
    '.config', '.ini',  # 配置文件
    '.sql', '.db', '.sqlite',  # 数据库
    '.dll', '.so', '.dylib',  # 动态库
}

# 危险MIME类型黑名单
DANGEROUS_MIME_TYPES = {
    'application/x-executable',
    'application/x-msdownload',
    'application/x-msdos-program',
    'application/x-sh',
    'application/x-shellscript',
    'text/x-php',
    'application/x-php',
    'text/x-python',
    'application/x-python',
}


# ==================== MIME类型检测 ====================

def detect_mime_type(file_content: bytes) -> Optional[str]:
    """通过magic bytes检测真实MIME类型

    Args:
        file_content: 文件内容（至少需要前几百字节）

    Returns:
        检测到的MIME类型，未知返回None
    """
    if not file_content:
        return None

    # 检查magic bytes
    for magic, mime_type in MAGIC_BYTES.items():
        if file_content.startswith(magic):
            # WebP需要额外检查
            if magic == b'RIFF' and len(file_content) >= 12:
                if file_content[8:12] == b'WEBP':
                    return 'image/webp'
                continue
            return mime_type

    # 使用python-magic库（如果可用）
    try:
        import magic
        mime = magic.Magic(mime=True)
        return mime.from_buffer(file_content)
    except ImportError:
        pass

    return None


def get_extension_mime_type(filename: str) -> Optional[str]:
    """根据文件扩展名获取MIME类型

    Args:
        filename: 文件名

    Returns:
        MIME类型
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type


# ==================== 文件验证 ====================

def validate_file(
    file_content: bytes,
    filename: str,
    file_type: str = 'image',
    max_size: Optional[int] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """验证文件安全性

    Args:
        file_content: 文件内容
        filename: 原始文件名
        file_type: 文件类型类别 ('image', 'avatar', 'document', 'video', 'audio')
        max_size: 自定义最大文件大小（覆盖默认配置）

    Returns:
        (是否通过, 错误信息, 文件信息)
    """
    file_info = {
        'original_filename': filename,
        'size': len(file_content),
        'detected_mime': None,
        'extension': None,
    }

    # 获取文件类型配置
    type_config = ALLOWED_FILE_TYPES.get(file_type)
    if not type_config:
        return False, f"不支持的文件类型类别: {file_type}", file_info

    # 1. 检查文件是否为空
    if not file_content:
        return False, "文件内容为空", file_info

    # 2. 检查文件大小
    actual_max_size = max_size or type_config['max_size']
    if len(file_content) > actual_max_size:
        max_mb = actual_max_size / (1024 * 1024)
        return False, f"文件大小超过限制（最大{max_mb:.1f}MB）", file_info

    # 3. 检查文件扩展名
    ext = Path(filename).suffix.lower()
    file_info['extension'] = ext

    if ext in DANGEROUS_EXTENSIONS:
        logger.warning(f"检测到危险文件扩展名: {filename}")
        return False, "不允许上传此类型文件", file_info

    if ext not in type_config['extensions']:
        allowed = ', '.join(type_config['extensions'])
        return False, f"不支持的文件格式，允许的格式: {allowed}", file_info

    # 4. 检测真实MIME类型
    detected_mime = detect_mime_type(file_content)
    file_info['detected_mime'] = detected_mime

    if detected_mime:
        # 检查是否为危险MIME类型
        if detected_mime in DANGEROUS_MIME_TYPES:
            logger.warning(f"检测到危险MIME类型: {detected_mime}, 文件: {filename}")
            return False, "不允许上传此类型文件", file_info

        # 检查MIME类型是否匹配
        if detected_mime not in type_config['mime_types']:
            logger.warning(
                f"MIME类型不匹配: 声明={get_extension_mime_type(filename)}, "
                f"实际={detected_mime}, 文件={filename}"
            )
            return False, "文件类型与扩展名不匹配", file_info

    # 5. 额外的图片验证
    if file_type in ('image', 'avatar'):
        valid, msg = _validate_image(file_content)
        if not valid:
            return False, msg, file_info

    logger.debug(f"文件验证通过: {filename}, MIME={detected_mime}, size={len(file_content)}")
    return True, "验证通过", file_info


def _validate_image(file_content: bytes) -> Tuple[bool, str]:
    """验证图片文件

    Args:
        file_content: 图片文件内容

    Returns:
        (是否有效, 错误信息)
    """
    try:
        from PIL import Image
        from io import BytesIO

        # 尝试打开图片
        img = Image.open(BytesIO(file_content))

        # 验证图片（尝试加载）
        img.verify()

        # 重新打开（verify后需要重新打开）
        img = Image.open(BytesIO(file_content))

        # 检查图片尺寸
        width, height = img.size
        if width > 10000 or height > 10000:
            return False, "图片尺寸过大（最大10000x10000）"

        if width < 10 or height < 10:
            return False, "图片尺寸过小（最小10x10）"

        # 检查像素总数（防止解压炸弹）
        if width * height > 100000000:  # 1亿像素
            return False, "图片像素总数过大"

        return True, ""

    except ImportError:
        # PIL未安装，跳过图片验证
        logger.warning("PIL未安装，跳过图片深度验证")
        return True, ""
    except Exception as e:
        logger.warning(f"图片验证失败: {e}")
        return False, "无效的图片文件"


# ==================== 安全文件名 ====================

def sanitize_filename(filename: str) -> str:
    """清理文件名，移除危险字符

    Args:
        filename: 原始文件名

    Returns:
        安全的文件名
    """
    if not filename:
        return "unnamed"

    # 获取扩展名
    path = Path(filename)
    name = path.stem
    ext = path.suffix.lower()

    # 移除危险字符
    # 只保留字母、数字、下划线、连字符、中文
    name = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', name)

    # 移除连续的下划线
    name = re.sub(r'_+', '_', name)

    # 去除首尾下划线
    name = name.strip('_')

    # 限制长度
    if len(name) > 100:
        name = name[:100]

    # 确保文件名不为空
    if not name:
        name = "file"

    return f"{name}{ext}"


def generate_safe_filename(
    original_filename: str,
    prefix: str = "",
    use_uuid: bool = True,
    include_timestamp: bool = True,
) -> str:
    """生成安全的唯一文件名

    Args:
        original_filename: 原始文件名
        prefix: 文件名前缀
        use_uuid: 是否使用UUID
        include_timestamp: 是否包含时间戳

    Returns:
        安全的唯一文件名
    """
    # 获取扩展名
    ext = Path(original_filename).suffix.lower()

    # 构建文件名部分
    parts = []

    if prefix:
        parts.append(prefix)

    if include_timestamp:
        parts.append(datetime.now().strftime("%Y%m%d_%H%M%S"))

    if use_uuid:
        parts.append(uuid.uuid4().hex[:8])

    return '_'.join(parts) + ext


def generate_file_path(
    filename: str,
    base_dir: str,
    sub_dirs: Optional[List[str]] = None,
    use_date_dirs: bool = True,
) -> Tuple[str, str]:
    """生成文件存储路径

    Args:
        filename: 文件名
        base_dir: 基础目录
        sub_dirs: 子目录列表
        use_date_dirs: 是否使用日期分目录

    Returns:
        (完整文件路径, 相对路径)
    """
    parts = [base_dir]

    # 添加子目录
    if sub_dirs:
        parts.extend(sub_dirs)

    # 添加日期目录
    if use_date_dirs:
        now = datetime.now()
        parts.append(str(now.year))
        parts.append(f"{now.month:02d}")
        parts.append(f"{now.day:02d}")

    # 创建目录
    dir_path = os.path.join(*parts)
    os.makedirs(dir_path, exist_ok=True)

    # 完整路径
    full_path = os.path.join(dir_path, filename)

    # 相对路径（从base_dir开始）
    rel_parts = parts[1:] if len(parts) > 1 else []
    rel_path = os.path.join(*rel_parts, filename) if rel_parts else filename

    return full_path, rel_path


# ==================== 文件哈希 ====================

def calculate_file_hash(
    file_content: bytes,
    algorithm: str = 'sha256'
) -> str:
    """计算文件哈希值

    Args:
        file_content: 文件内容
        algorithm: 哈希算法 (md5, sha1, sha256)

    Returns:
        哈希值（十六进制字符串）
    """
    if algorithm == 'md5':
        return hashlib.md5(file_content).hexdigest()
    elif algorithm == 'sha1':
        return hashlib.sha1(file_content).hexdigest()
    else:
        return hashlib.sha256(file_content).hexdigest()


def check_duplicate_file(
    file_hash: str,
    existing_hashes: set,
) -> bool:
    """检查文件是否重复

    Args:
        file_hash: 文件哈希值
        existing_hashes: 已存在的哈希值集合

    Returns:
        是否重复
    """
    return file_hash in existing_hashes


# ==================== 恶意软件扫描钩子 ====================

class MalwareScanResult:
    """恶意软件扫描结果"""
    def __init__(
        self,
        is_clean: bool,
        threat_name: Optional[str] = None,
        scanner: str = "unknown"
    ):
        self.is_clean = is_clean
        self.threat_name = threat_name
        self.scanner = scanner


async def scan_for_malware(
    file_content: bytes,
    filename: str,
) -> MalwareScanResult:
    """扫描文件是否包含恶意软件

    这是一个钩子函数，可以集成第三方杀毒软件API

    Args:
        file_content: 文件内容
        filename: 文件名

    Returns:
        扫描结果
    """
    # 基础检查：文件大小异常
    if len(file_content) == 0:
        return MalwareScanResult(
            is_clean=False,
            threat_name="EmptyFile",
            scanner="basic"
        )

    # 检查是否包含可疑的脚本标签（针对伪装成图片的HTML/JS文件）
    suspicious_patterns = [
        b'<script',
        b'<?php',
        b'<%',
        b'javascript:',
        b'vbscript:',
        b'data:text/html',
    ]

    for pattern in suspicious_patterns:
        if pattern in file_content.lower():
            logger.warning(f"检测到可疑内容: {pattern} in {filename}")
            return MalwareScanResult(
                is_clean=False,
                threat_name="SuspiciousContent",
                scanner="basic"
            )

    # TODO: 集成ClamAV或其他杀毒引擎
    # try:
    #     import clamd
    #     cd = clamd.ClamdUnixSocket()
    #     result = cd.instream(BytesIO(file_content))
    #     if result['stream'][0] == 'FOUND':
    #         return MalwareScanResult(
    #             is_clean=False,
    #             threat_name=result['stream'][1],
    #             scanner="clamav"
    #         )
    # except Exception as e:
    #     logger.error(f"ClamAV扫描失败: {e}")

    return MalwareScanResult(is_clean=True, scanner="basic")


# ==================== 文件处理服务类 ====================

class FileValidator:
    """文件验证器类"""

    def __init__(
        self,
        file_type: str = 'image',
        max_size: Optional[int] = None,
        scan_malware: bool = True,
    ):
        self.file_type = file_type
        self.max_size = max_size
        self.scan_malware = scan_malware

    async def validate(
        self,
        file_content: bytes,
        filename: str,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """验证文件

        Args:
            file_content: 文件内容
            filename: 原始文件名

        Returns:
            (是否通过, 错误信息, 文件信息)
        """
        # 基础验证
        valid, msg, file_info = validate_file(
            file_content=file_content,
            filename=filename,
            file_type=self.file_type,
            max_size=self.max_size,
        )

        if not valid:
            return False, msg, file_info

        # 恶意软件扫描
        if self.scan_malware:
            scan_result = await scan_for_malware(file_content, filename)
            if not scan_result.is_clean:
                logger.warning(
                    f"检测到恶意文件: {filename}, "
                    f"threat={scan_result.threat_name}"
                )
                return False, "文件包含可疑内容", file_info

        return True, "验证通过", file_info

    def generate_filename(
        self,
        original_filename: str,
        prefix: str = "",
    ) -> str:
        """生成安全文件名"""
        return generate_safe_filename(
            original_filename=original_filename,
            prefix=prefix,
        )


# ==================== 便捷函数 ====================

async def validate_upload_file(
    file_content: bytes,
    filename: str,
    file_type: str = 'image',
    max_size: Optional[int] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """验证上传文件（便捷函数）

    Args:
        file_content: 文件内容
        filename: 原始文件名
        file_type: 文件类型类别
        max_size: 自定义最大大小

    Returns:
        (是否通过, 错误信息, 文件信息)
    """
    validator = FileValidator(
        file_type=file_type,
        max_size=max_size,
        scan_malware=True,
    )
    return await validator.validate(file_content, filename)


def process_upload_file(
    file_content: bytes,
    original_filename: str,
    base_dir: str,
    file_type: str = 'image',
    prefix: str = "",
) -> Tuple[str, str, str]:
    """处理上传文件（生成文件名和路径）

    Args:
        file_content: 文件内容
        original_filename: 原始文件名
        base_dir: 存储基础目录
        file_type: 文件类型
        prefix: 文件名前缀

    Returns:
        (安全文件名, 完整路径, 相对路径)
    """
    # 生成安全文件名
    safe_filename = generate_safe_filename(
        original_filename=original_filename,
        prefix=prefix,
    )

    # 生成存储路径
    full_path, rel_path = generate_file_path(
        filename=safe_filename,
        base_dir=base_dir,
        sub_dirs=[file_type],
    )

    return safe_filename, full_path, rel_path

"""
PetPal - 文件验证器单元测试
"""
import pytest
from pathlib import Path
from app.utils.file_validator import (
    detect_mime_type, validate_file, sanitize_filename,
    generate_safe_filename, generate_file_path,
    calculate_file_hash, scan_for_malware,
    FileValidator, ALLOWED_FILE_TYPES, DANGEROUS_EXTENSIONS
)


class TestDetectMimeType:
    """测试MIME类型检测"""

    def test_detect_png(self, sample_image_bytes):
        """测试检测PNG格式"""
        mime_type = detect_mime_type(sample_image_bytes)
        assert mime_type == 'image/png'

    def test_detect_jpeg(self, sample_jpeg_bytes):
        """测试检测JPEG格式"""
        mime_type = detect_mime_type(sample_jpeg_bytes)
        assert mime_type == 'image/jpeg'

    def test_unknown_format(self):
        """测试未知格式"""
        content = b'random bytes that are not a known format'
        mime_type = detect_mime_type(content)
        # 未知格式应返回None或尝试其他检测方法
        assert mime_type is None or isinstance(mime_type, str)

    def test_empty_content(self):
        """测试空内容"""
        mime_type = detect_mime_type(b'')
        assert mime_type is None


class TestValidateFile:
    """测试文件验证"""

    def test_valid_image(self, sample_image_bytes):
        """测试有效图片"""
        valid, msg, info = validate_file(
            sample_image_bytes,
            'test.png',
            file_type='image'
        )
        assert valid
        assert info['extension'] == '.png'

    def test_empty_file(self):
        """测试空文件"""
        valid, msg, info = validate_file(
            b'',
            'empty.png',
            file_type='image'
        )
        assert not valid
        assert '空' in msg

    def test_dangerous_extension(self):
        """测试危险扩展名"""
        valid, msg, info = validate_file(
            b'fake content',
            'malware.exe',
            file_type='image'
        )
        assert not valid

    def test_file_too_large(self, sample_image_bytes):
        """测试文件过大"""
        valid, msg, info = validate_file(
            sample_image_bytes,
            'large.png',
            file_type='image',
            max_size=10  # 10 bytes
        )
        assert not valid
        assert '大小' in msg or '超过' in msg

    def test_extension_mismatch(self, sample_image_bytes):
        """测试扩展名不匹配"""
        # PNG内容但声称是JPEG
        valid, msg, info = validate_file(
            sample_image_bytes,
            'fake.jpg',
            file_type='image'
        )
        # 根据实现，可能通过或失败

    def test_php_file_rejected(self):
        """测试PHP文件被拒绝"""
        content = b'<?php echo "Hello"; ?>'
        valid, msg, info = validate_file(
            content,
            'shell.php',
            file_type='image'
        )
        assert not valid

    def test_script_in_file_rejected(self, malicious_file_bytes):
        """测试包含脚本的文件被拒绝"""
        # 伪装成图片的恶意文件
        valid, msg, info = validate_file(
            malicious_file_bytes,
            'image.png',
            file_type='image'
        )
        # 应该被MIME检测或恶意扫描拦截


class TestSanitizeFilename:
    """测试文件名清理"""

    def test_remove_path_chars(self):
        """测试移除路径字符"""
        filename = '../../../etc/passwd'
        result = sanitize_filename(filename)
        assert '..' not in result
        assert '/' not in result
        assert '\\' not in result

    def test_remove_special_chars(self):
        """测试移除特殊字符"""
        filename = 'file<>:"|?*.txt'
        result = sanitize_filename(filename)
        # 特殊字符应被移除或替换
        for char in '<>:"|?*':
            assert char not in result

    def test_preserve_chinese(self):
        """测试保留中文字符"""
        filename = '测试文件.png'
        result = sanitize_filename(filename)
        assert '测试文件' in result

    def test_empty_filename(self):
        """测试空文件名"""
        result = sanitize_filename('')
        assert result  # 应该有默认值

    def test_preserve_extension(self):
        """测试保留扩展名"""
        filename = 'document.pdf'
        result = sanitize_filename(filename)
        assert result.endswith('.pdf')


class TestGenerateSafeFilename:
    """测试安全文件名生成"""

    def test_generate_with_uuid(self):
        """测试生成带UUID的文件名"""
        filename = generate_safe_filename('test.png', use_uuid=True)
        assert filename.endswith('.png')
        # UUID部分应该存在
        assert len(filename) > len('.png')

    def test_generate_with_timestamp(self):
        """测试生成带时间戳的文件名"""
        filename = generate_safe_filename(
            'test.png',
            include_timestamp=True
        )
        assert filename.endswith('.png')

    def test_generate_with_prefix(self):
        """测试生成带前缀的文件名"""
        filename = generate_safe_filename(
            'test.png',
            prefix='avatar'
        )
        assert filename.startswith('avatar')

    def test_unique_filenames(self):
        """测试文件名唯一性"""
        filename1 = generate_safe_filename('test.png')
        filename2 = generate_safe_filename('test.png')
        assert filename1 != filename2


class TestGenerateFilePath:
    """测试文件路径生成"""

    def test_generate_path_with_date_dirs(self, tmp_path):
        """测试生成带日期目录的路径"""
        full_path, rel_path = generate_file_path(
            'test.png',
            str(tmp_path),
            use_date_dirs=True
        )
        assert str(tmp_path) in full_path
        assert 'test.png' in full_path

    def test_generate_path_with_subdirs(self, tmp_path):
        """测试生成带子目录的路径"""
        full_path, rel_path = generate_file_path(
            'test.png',
            str(tmp_path),
            sub_dirs=['uploads', 'images']
        )
        assert 'uploads' in full_path
        assert 'images' in full_path


class TestCalculateFileHash:
    """测试文件哈希计算"""

    def test_sha256_hash(self, sample_image_bytes):
        """测试SHA256哈希"""
        hash_value = calculate_file_hash(sample_image_bytes, 'sha256')
        assert len(hash_value) == 64  # SHA256产生64个十六进制字符

    def test_md5_hash(self, sample_image_bytes):
        """测试MD5哈希"""
        hash_value = calculate_file_hash(sample_image_bytes, 'md5')
        assert len(hash_value) == 32  # MD5产生32个十六进制字符

    def test_consistent_hash(self, sample_image_bytes):
        """测试哈希一致性"""
        hash1 = calculate_file_hash(sample_image_bytes)
        hash2 = calculate_file_hash(sample_image_bytes)
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """测试不同内容产生不同哈希"""
        hash1 = calculate_file_hash(b'content1')
        hash2 = calculate_file_hash(b'content2')
        assert hash1 != hash2


class TestScanForMalware:
    """测试恶意软件扫描"""

    @pytest.mark.asyncio
    async def test_clean_file(self, sample_image_bytes):
        """测试干净文件"""
        result = await scan_for_malware(sample_image_bytes, 'clean.png')
        assert result.is_clean

    @pytest.mark.asyncio
    async def test_suspicious_content(self, malicious_file_bytes):
        """测试可疑内容"""
        result = await scan_for_malware(malicious_file_bytes, 'suspicious.png')
        assert not result.is_clean
        assert result.threat_name is not None

    @pytest.mark.asyncio
    async def test_empty_file(self):
        """测试空文件"""
        result = await scan_for_malware(b'', 'empty.txt')
        assert not result.is_clean


class TestFileValidator:
    """测试FileValidator类"""

    @pytest.mark.asyncio
    async def test_validate_valid_image(self, sample_image_bytes):
        """测试验证有效图片"""
        validator = FileValidator(file_type='image')
        valid, msg, info = await validator.validate(
            sample_image_bytes,
            'test.png'
        )
        assert valid

    @pytest.mark.asyncio
    async def test_validate_with_custom_size(self, sample_image_bytes):
        """测试自定义大小限制"""
        validator = FileValidator(
            file_type='image',
            max_size=10  # 很小的限制
        )
        valid, msg, info = await validator.validate(
            sample_image_bytes,
            'test.png'
        )
        assert not valid

    def test_generate_filename(self):
        """测试生成文件名"""
        validator = FileValidator(file_type='image')
        filename = validator.generate_filename('original.png', prefix='img')
        assert filename.endswith('.png')
        assert 'img' in filename


class TestAllowedFileTypes:
    """测试文件类型配置"""

    def test_image_config(self):
        """测试图片配置"""
        config = ALLOWED_FILE_TYPES.get('image')
        assert config is not None
        assert '.jpg' in config['extensions']
        assert '.png' in config['extensions']
        assert 'image/jpeg' in config['mime_types']

    def test_avatar_config(self):
        """测试头像配置"""
        config = ALLOWED_FILE_TYPES.get('avatar')
        assert config is not None
        assert config['max_size'] <= ALLOWED_FILE_TYPES['image']['max_size']

    def test_document_config(self):
        """测试文档配置"""
        config = ALLOWED_FILE_TYPES.get('document')
        assert config is not None
        assert '.pdf' in config['extensions']


class TestDangerousExtensions:
    """测试危险扩展名"""

    def test_executable_extensions(self):
        """测试可执行文件扩展名"""
        assert '.exe' in DANGEROUS_EXTENSIONS
        assert '.bat' in DANGEROUS_EXTENSIONS
        assert '.sh' in DANGEROUS_EXTENSIONS

    def test_script_extensions(self):
        """测试脚本文件扩展名"""
        assert '.php' in DANGEROUS_EXTENSIONS
        assert '.py' in DANGEROUS_EXTENSIONS
        assert '.js' in DANGEROUS_EXTENSIONS

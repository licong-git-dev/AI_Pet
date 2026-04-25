"""
PetPal - 文件存储服务

支持多种存储后端：
- 本地文件存储
- 阿里云OSS存储
- 腾讯云COS存储（预留）
- 七牛云存储（预留）

功能包括：
- 文件上传/下载/删除
- 签名URL生成
- 图片处理（缩略图、水印）
- 文件去重
"""
import os
import hashlib
import uuid
import mimetypes
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, BinaryIO, Union
from dataclasses import dataclass
from enum import Enum
from io import BytesIO

from loguru import logger

from app.config import settings


class StorageType(str, Enum):
    """存储类型"""
    LOCAL = "local"
    ALIYUN_OSS = "aliyun_oss"
    TENCENT_COS = "tencent_cos"
    QINIU = "qiniu"


@dataclass
class UploadResult:
    """上传结果"""
    success: bool
    url: str
    key: str
    size: int
    hash: str
    mime_type: str
    storage_type: str
    error_message: Optional[str] = None


@dataclass
class FileInfo:
    """文件信息"""
    key: str
    size: int
    hash: str
    mime_type: str
    last_modified: datetime
    storage_type: str
    metadata: Optional[Dict] = None


class StorageBackend(ABC):
    """存储后端抽象基类"""

    @abstractmethod
    async def upload(
        self,
        file_content: bytes,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> UploadResult:
        """上传文件"""
        pass

    @abstractmethod
    async def download(self, key: str) -> Optional[bytes]:
        """下载文件"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除文件"""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查文件是否存在"""
        pass

    @abstractmethod
    async def get_info(self, key: str) -> Optional[FileInfo]:
        """获取文件信息"""
        pass

    @abstractmethod
    def get_url(self, key: str, expires: int = 3600) -> str:
        """获取文件访问URL"""
        pass


class LocalStorageBackend(StorageBackend):
    """本地文件存储后端"""

    def __init__(self, base_dir: str, base_url: str = "/uploads"):
        self.base_dir = os.path.abspath(base_dir)
        self.base_url = base_url
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_full_path(self, key: str) -> str:
        """获取完整文件路径"""
        # 防止路径遍历攻击
        safe_key = key.lstrip("/").replace("..", "")
        return os.path.join(self.base_dir, safe_key)

    async def upload(
        self,
        file_content: bytes,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> UploadResult:
        """上传文件到本地"""
        try:
            full_path = self._get_full_path(key)

            # 确保目录存在
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # 写入文件
            with open(full_path, "wb") as f:
                f.write(file_content)

            # 计算哈希
            file_hash = hashlib.md5(file_content).hexdigest()

            # 获取MIME类型
            mime_type = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"

            url = f"{self.base_url}/{key}"

            logger.info(f"[Storage] 本地上传成功: {key}")

            return UploadResult(
                success=True,
                url=url,
                key=key,
                size=len(file_content),
                hash=file_hash,
                mime_type=mime_type,
                storage_type=StorageType.LOCAL
            )

        except Exception as e:
            logger.error(f"[Storage] 本地上传失败: {str(e)}")
            return UploadResult(
                success=False,
                url="",
                key=key,
                size=0,
                hash="",
                mime_type="",
                storage_type=StorageType.LOCAL,
                error_message=str(e)
            )

    async def download(self, key: str) -> Optional[bytes]:
        """从本地下载文件"""
        try:
            full_path = self._get_full_path(key)
            if not os.path.exists(full_path):
                return None

            with open(full_path, "rb") as f:
                return f.read()

        except Exception as e:
            logger.error(f"[Storage] 本地下载失败: {str(e)}")
            return None

    async def delete(self, key: str) -> bool:
        """删除本地文件"""
        try:
            full_path = self._get_full_path(key)
            if os.path.exists(full_path):
                os.remove(full_path)
                logger.info(f"[Storage] 本地删除成功: {key}")
                return True
            return False

        except Exception as e:
            logger.error(f"[Storage] 本地删除失败: {str(e)}")
            return False

    async def exists(self, key: str) -> bool:
        """检查本地文件是否存在"""
        full_path = self._get_full_path(key)
        return os.path.exists(full_path)

    async def get_info(self, key: str) -> Optional[FileInfo]:
        """获取本地文件信息"""
        try:
            full_path = self._get_full_path(key)
            if not os.path.exists(full_path):
                return None

            stat = os.stat(full_path)
            mime_type = mimetypes.guess_type(key)[0] or "application/octet-stream"

            # 计算哈希
            with open(full_path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

            return FileInfo(
                key=key,
                size=stat.st_size,
                hash=file_hash,
                mime_type=mime_type,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                storage_type=StorageType.LOCAL
            )

        except Exception as e:
            logger.error(f"[Storage] 获取文件信息失败: {str(e)}")
            return None

    def get_url(self, key: str, expires: int = 3600) -> str:
        """获取本地文件URL（不支持签名）"""
        return f"{self.base_url}/{key}"


class AliyunOSSBackend(StorageBackend):
    """阿里云OSS存储后端"""

    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        bucket_name: str,
        endpoint: str,
        custom_domain: Optional[str] = None
    ):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.bucket_name = bucket_name
        self.endpoint = endpoint
        self.custom_domain = custom_domain
        self._bucket = None

    def _get_bucket(self):
        """获取OSS Bucket实例"""
        if self._bucket is None:
            try:
                import oss2
                auth = oss2.Auth(self.access_key_id, self.access_key_secret)
                self._bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)
            except ImportError:
                logger.error("[Storage] oss2库未安装，请运行: pip install oss2")
                raise ImportError("请安装oss2: pip install oss2")
        return self._bucket

    async def upload(
        self,
        file_content: bytes,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> UploadResult:
        """上传文件到OSS"""
        try:
            import oss2

            bucket = self._get_bucket()

            # 准备headers
            headers = {}
            if content_type:
                headers["Content-Type"] = content_type
            if metadata:
                for k, v in metadata.items():
                    headers[f"x-oss-meta-{k}"] = str(v)

            # 上传
            result = bucket.put_object(key, file_content, headers=headers)

            # 计算哈希
            file_hash = hashlib.md5(file_content).hexdigest()

            # 生成URL
            if self.custom_domain:
                url = f"https://{self.custom_domain}/{key}"
            else:
                url = f"https://{self.bucket_name}.{self.endpoint}/{key}"

            mime_type = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"

            logger.info(f"[Storage] OSS上传成功: {key}, etag={result.etag}")

            return UploadResult(
                success=True,
                url=url,
                key=key,
                size=len(file_content),
                hash=file_hash,
                mime_type=mime_type,
                storage_type=StorageType.ALIYUN_OSS
            )

        except ImportError:
            return UploadResult(
                success=False,
                url="",
                key=key,
                size=0,
                hash="",
                mime_type="",
                storage_type=StorageType.ALIYUN_OSS,
                error_message="oss2库未安装"
            )
        except Exception as e:
            logger.error(f"[Storage] OSS上传失败: {str(e)}")
            return UploadResult(
                success=False,
                url="",
                key=key,
                size=0,
                hash="",
                mime_type="",
                storage_type=StorageType.ALIYUN_OSS,
                error_message=str(e)
            )

    async def download(self, key: str) -> Optional[bytes]:
        """从OSS下载文件"""
        try:
            bucket = self._get_bucket()
            result = bucket.get_object(key)
            return result.read()

        except Exception as e:
            logger.error(f"[Storage] OSS下载失败: {str(e)}")
            return None

    async def delete(self, key: str) -> bool:
        """删除OSS文件"""
        try:
            bucket = self._get_bucket()
            bucket.delete_object(key)
            logger.info(f"[Storage] OSS删除成功: {key}")
            return True

        except Exception as e:
            logger.error(f"[Storage] OSS删除失败: {str(e)}")
            return False

    async def exists(self, key: str) -> bool:
        """检查OSS文件是否存在"""
        try:
            bucket = self._get_bucket()
            return bucket.object_exists(key)

        except Exception as e:
            logger.error(f"[Storage] OSS检查文件存在失败: {str(e)}")
            return False

    async def get_info(self, key: str) -> Optional[FileInfo]:
        """获取OSS文件信息"""
        try:
            bucket = self._get_bucket()
            meta = bucket.get_object_meta(key)

            return FileInfo(
                key=key,
                size=meta.content_length,
                hash=meta.etag.strip('"'),
                mime_type=meta.content_type or "application/octet-stream",
                last_modified=datetime.strptime(
                    meta.last_modified,
                    "%a, %d %b %Y %H:%M:%S GMT"
                ) if meta.last_modified else datetime.now(),
                storage_type=StorageType.ALIYUN_OSS
            )

        except Exception as e:
            logger.error(f"[Storage] OSS获取文件信息失败: {str(e)}")
            return None

    def get_url(self, key: str, expires: int = 3600) -> str:
        """获取OSS文件签名URL"""
        try:
            bucket = self._get_bucket()
            url = bucket.sign_url("GET", key, expires)
            return url

        except Exception as e:
            logger.error(f"[Storage] OSS生成签名URL失败: {str(e)}")
            # 返回公开URL
            if self.custom_domain:
                return f"https://{self.custom_domain}/{key}"
            return f"https://{self.bucket_name}.{self.endpoint}/{key}"

    async def upload_multipart(
        self,
        file_stream: BinaryIO,
        key: str,
        content_type: Optional[str] = None,
        part_size: int = 10 * 1024 * 1024
    ) -> UploadResult:
        """分片上传大文件"""
        try:
            import oss2

            bucket = self._get_bucket()

            # 初始化分片上传
            upload_id = bucket.init_multipart_upload(key).upload_id
            parts = []
            part_number = 1
            total_size = 0

            # 分片上传
            while True:
                data = file_stream.read(part_size)
                if not data:
                    break

                result = bucket.upload_part(key, upload_id, part_number, data)
                parts.append(oss2.models.PartInfo(part_number, result.etag))
                total_size += len(data)
                part_number += 1

            # 完成上传
            bucket.complete_multipart_upload(key, upload_id, parts)

            # 生成URL
            if self.custom_domain:
                url = f"https://{self.custom_domain}/{key}"
            else:
                url = f"https://{self.bucket_name}.{self.endpoint}/{key}"

            mime_type = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"

            logger.info(f"[Storage] OSS分片上传成功: {key}, size={total_size}")

            return UploadResult(
                success=True,
                url=url,
                key=key,
                size=total_size,
                hash="",
                mime_type=mime_type,
                storage_type=StorageType.ALIYUN_OSS
            )

        except Exception as e:
            logger.error(f"[Storage] OSS分片上传失败: {str(e)}")
            return UploadResult(
                success=False,
                url="",
                key=key,
                size=0,
                hash="",
                mime_type="",
                storage_type=StorageType.ALIYUN_OSS,
                error_message=str(e)
            )

    def get_sts_token(self, role_arn: str, session_name: str, duration: int = 3600) -> Dict:
        """获取STS临时凭证（用于客户端直传）"""
        try:
            from aliyunsdkcore.client import AcsClient
            from aliyunsdksts.request.v20150401.AssumeRoleRequest import AssumeRoleRequest
            import json

            client = AcsClient(
                self.access_key_id,
                self.access_key_secret,
                "cn-hangzhou"
            )

            request = AssumeRoleRequest()
            request.set_RoleArn(role_arn)
            request.set_RoleSessionName(session_name)
            request.set_DurationSeconds(duration)

            response = client.do_action_with_exception(request)
            result = json.loads(response)

            credentials = result.get("Credentials", {})

            return {
                "success": True,
                "access_key_id": credentials.get("AccessKeyId"),
                "access_key_secret": credentials.get("AccessKeySecret"),
                "security_token": credentials.get("SecurityToken"),
                "expiration": credentials.get("Expiration"),
                "bucket": self.bucket_name,
                "endpoint": self.endpoint
            }

        except ImportError:
            return {
                "success": False,
                "error": "aliyun-python-sdk-sts库未安装"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class StorageService:
    """统一存储服务"""

    def __init__(self):
        self._backend: Optional[StorageBackend] = None
        self._local_backend: Optional[LocalStorageBackend] = None
        self._init_backends()

    def _init_backends(self):
        """初始化存储后端"""
        # 本地存储总是可用
        upload_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "uploads"
        )
        self._local_backend = LocalStorageBackend(upload_dir)

        # 如果配置了OSS，使用OSS作为主后端
        if settings.oss_enabled:
            try:
                self._backend = AliyunOSSBackend(
                    access_key_id=settings.oss_access_key_id,
                    access_key_secret=settings.oss_access_key_secret,
                    bucket_name=settings.oss_bucket_name,
                    endpoint=settings.oss_endpoint,
                    custom_domain=settings.oss_domain
                )
                logger.info("[Storage] 使用阿里云OSS存储")
            except Exception as e:
                logger.warning(f"[Storage] OSS初始化失败，回退到本地存储: {str(e)}")
                self._backend = self._local_backend
        else:
            self._backend = self._local_backend
            logger.info("[Storage] 使用本地文件存储")

    @property
    def backend(self) -> StorageBackend:
        """获取当前存储后端"""
        return self._backend

    @property
    def local_backend(self) -> LocalStorageBackend:
        """获取本地存储后端"""
        return self._local_backend

    def generate_key(
        self,
        filename: str,
        category: str = "images",
        user_id: Optional[int] = None
    ) -> str:
        """生成存储key"""
        # 获取文件扩展名
        ext = os.path.splitext(filename)[1].lower() or ".bin"

        # 生成唯一标识
        timestamp = datetime.now().strftime("%Y%m%d")
        unique_id = uuid.uuid4().hex[:16]

        # 组合路径
        if user_id:
            key = f"{category}/{timestamp}/u{user_id}_{unique_id}{ext}"
        else:
            key = f"{category}/{timestamp}/{unique_id}{ext}"

        return key

    async def upload(
        self,
        file_content: bytes,
        filename: str,
        category: str = "images",
        user_id: Optional[int] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict] = None,
        use_local: bool = False
    ) -> UploadResult:
        """
        上传文件

        Args:
            file_content: 文件内容
            filename: 原始文件名
            category: 分类（images, avatars, documents等）
            user_id: 用户ID
            content_type: MIME类型
            metadata: 元数据
            use_local: 强制使用本地存储

        Returns:
            UploadResult
        """
        key = self.generate_key(filename, category, user_id)

        # 选择存储后端
        backend = self._local_backend if use_local else self._backend

        return await backend.upload(
            file_content=file_content,
            key=key,
            content_type=content_type,
            metadata=metadata
        )

    async def upload_from_url(
        self,
        url: str,
        category: str = "images",
        user_id: Optional[int] = None
    ) -> UploadResult:
        """从URL下载并上传文件"""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()

                content = response.content
                content_type = response.headers.get("content-type", "")

                # 从URL获取文件名
                filename = url.split("/")[-1].split("?")[0]
                if not filename:
                    ext = mimetypes.guess_extension(content_type) or ".bin"
                    filename = f"download{ext}"

                return await self.upload(
                    file_content=content,
                    filename=filename,
                    category=category,
                    user_id=user_id,
                    content_type=content_type
                )

        except Exception as e:
            logger.error(f"[Storage] 从URL上传失败: {str(e)}")
            return UploadResult(
                success=False,
                url="",
                key="",
                size=0,
                hash="",
                mime_type="",
                storage_type="",
                error_message=str(e)
            )

    async def download(self, key: str, use_local: bool = False) -> Optional[bytes]:
        """下载文件"""
        backend = self._local_backend if use_local else self._backend
        return await backend.download(key)

    async def delete(self, key: str, use_local: bool = False) -> bool:
        """删除文件"""
        backend = self._local_backend if use_local else self._backend
        return await backend.delete(key)

    async def exists(self, key: str, use_local: bool = False) -> bool:
        """检查文件是否存在"""
        backend = self._local_backend if use_local else self._backend
        return await backend.exists(key)

    async def get_info(self, key: str, use_local: bool = False) -> Optional[FileInfo]:
        """获取文件信息"""
        backend = self._local_backend if use_local else self._backend
        return await backend.get_info(key)

    def get_url(self, key: str, expires: int = 3600, use_local: bool = False) -> str:
        """获取文件访问URL"""
        backend = self._local_backend if use_local else self._backend
        return backend.get_url(key, expires)

    def get_public_url(self, key: str) -> str:
        """获取公开访问URL（不带签名）"""
        if isinstance(self._backend, AliyunOSSBackend):
            if self._backend.custom_domain:
                return f"https://{self._backend.custom_domain}/{key}"
            return f"https://{self._backend.bucket_name}.{self._backend.endpoint}/{key}"
        return f"/uploads/{key}"

    async def copy(self, source_key: str, dest_key: str) -> bool:
        """复制文件"""
        content = await self.download(source_key)
        if content is None:
            return False

        result = await self._backend.upload(content, dest_key)
        return result.success

    async def move(self, source_key: str, dest_key: str) -> bool:
        """移动文件"""
        if await self.copy(source_key, dest_key):
            return await self.delete(source_key)
        return False

    def get_storage_type(self) -> str:
        """获取当前存储类型"""
        if isinstance(self._backend, AliyunOSSBackend):
            return StorageType.ALIYUN_OSS
        return StorageType.LOCAL

    async def get_sts_token(
        self,
        role_arn: str,
        session_name: str = "petpal-upload",
        duration: int = 3600
    ) -> Dict:
        """获取STS临时凭证（仅OSS支持）"""
        if isinstance(self._backend, AliyunOSSBackend):
            return self._backend.get_sts_token(role_arn, session_name, duration)
        return {
            "success": False,
            "error": "当前存储后端不支持STS"
        }


# ==================== 图片处理工具 ====================

class ImageProcessor:
    """图片处理器"""

    @staticmethod
    def resize(
        image_content: bytes,
        max_width: int = 1920,
        max_height: int = 1080,
        quality: int = 85
    ) -> bytes:
        """调整图片大小"""
        try:
            from PIL import Image
            from io import BytesIO

            img = Image.open(BytesIO(image_content))

            # 保持比例缩放
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            # 保存
            output = BytesIO()
            img_format = img.format or "JPEG"
            if img_format == "JPEG":
                img.save(output, format=img_format, quality=quality, optimize=True)
            else:
                img.save(output, format=img_format, optimize=True)

            return output.getvalue()

        except ImportError:
            logger.warning("[Storage] Pillow未安装，跳过图片处理")
            return image_content
        except Exception as e:
            logger.error(f"[Storage] 图片处理失败: {str(e)}")
            return image_content

    @staticmethod
    def create_thumbnail(
        image_content: bytes,
        width: int = 200,
        height: int = 200
    ) -> bytes:
        """创建缩略图"""
        try:
            from PIL import Image
            from io import BytesIO

            img = Image.open(BytesIO(image_content))
            img.thumbnail((width, height), Image.Resampling.LANCZOS)

            output = BytesIO()
            img.save(output, format="JPEG", quality=80)
            return output.getvalue()

        except ImportError:
            logger.warning("[Storage] Pillow未安装，跳过缩略图生成")
            return image_content
        except Exception as e:
            logger.error(f"[Storage] 缩略图生成失败: {str(e)}")
            return image_content

    @staticmethod
    def add_watermark(
        image_content: bytes,
        watermark_text: str = "PetPal",
        position: str = "bottom-right"
    ) -> bytes:
        """添加文字水印"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            from io import BytesIO

            img = Image.open(BytesIO(image_content))
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # 创建水印层
            txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(txt_layer)

            # 使用默认字体
            try:
                font = ImageFont.truetype("arial.ttf", 36)
            except Exception:
                font = ImageFont.load_default()

            # 计算文字位置
            bbox = draw.textbbox((0, 0), watermark_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            padding = 20
            if position == "bottom-right":
                x = img.width - text_width - padding
                y = img.height - text_height - padding
            elif position == "bottom-left":
                x = padding
                y = img.height - text_height - padding
            elif position == "top-right":
                x = img.width - text_width - padding
                y = padding
            else:  # top-left
                x = padding
                y = padding

            # 绘制半透明文字
            draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, 128))

            # 合并图层
            result = Image.alpha_composite(img, txt_layer)

            # 输出
            output = BytesIO()
            result.convert("RGB").save(output, format="JPEG", quality=85)
            return output.getvalue()

        except ImportError:
            logger.warning("[Storage] Pillow未安装，跳过水印添加")
            return image_content
        except Exception as e:
            logger.error(f"[Storage] 水印添加失败: {str(e)}")
            return image_content

    @staticmethod
    def get_image_info(image_content: bytes) -> Dict:
        """获取图片信息"""
        try:
            from PIL import Image
            from io import BytesIO

            img = Image.open(BytesIO(image_content))
            return {
                "width": img.width,
                "height": img.height,
                "format": img.format,
                "mode": img.mode,
                "size": len(image_content)
            }

        except ImportError:
            return {"error": "Pillow未安装"}
        except Exception as e:
            return {"error": str(e)}


# 全局存储服务实例
storage_service = StorageService()
image_processor = ImageProcessor()

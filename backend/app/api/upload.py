"""
PetPal - 文件上传API

提供安全的文件上传功能：
- 图片上传（头像、宠物照片、帖子图片）
- 文件验证（类型、大小、恶意内容检测）
- 本地存储和云存储支持（阿里云OSS）
"""
import os
import asyncio
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.config import settings
from app.utils.deps import get_current_user
from app.utils.response import success
from app.utils.file_validator import (
    validate_upload_file, process_upload_file, calculate_file_hash,
    FileValidator, ALLOWED_FILE_TYPES
)
from app.services.storage_service import storage_service, image_processor

router = APIRouter()

# 上传配置
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
MAX_FILES_PER_REQUEST = 9


def ensure_upload_dir():
    """确保上传目录存在"""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # 创建子目录
    for subdir in ["images", "avatars", "documents"]:
        os.makedirs(os.path.join(UPLOAD_DIR, subdir), exist_ok=True)


@router.post("/image", summary="上传图片")
async def upload_image(
    file: UploadFile = File(..., description="图片文件"),
    category: str = Form("images", description="分类: images avatars pet_photos"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    上传单个图片文件

    - 支持格式: JPG, PNG, GIF, WebP
    - 最大大小: 10MB
    - 返回图片URL
    """
    ensure_upload_dir()

    # 读取文件内容
    content = await file.read()

    # 确定文件类型
    file_type = "avatar" if category == "avatars" else "image"

    # 验证文件
    valid, msg, file_info = await validate_upload_file(
        file_content=content,
        filename=file.filename,
        file_type=file_type
    )

    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    # 生成文件路径
    safe_filename, full_path, rel_path = process_upload_file(
        file_content=content,
        original_filename=file.filename,
        base_dir=UPLOAD_DIR,
        file_type=category,
        prefix=f"u{current_user.id}"
    )

    # 保存文件
    with open(full_path, "wb") as f:
        f.write(content)

    # 生成访问URL
    file_url = f"/uploads/{rel_path.replace(os.sep, '/')}"

    # 计算文件哈希（用于去重）
    file_hash = calculate_file_hash(content)

    return success(data={
        "url": file_url,
        "filename": safe_filename,
        "size": len(content),
        "mime_type": file_info.get("detected_mime"),
        "hash": file_hash
    }, message="上传成功")


@router.post("/images", summary="批量上传图片")
async def upload_images(
    files: List[UploadFile] = File(..., description="图片文件列表"),
    category: str = Form("images", description="分类"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    批量上传图片文件

    - 最多同时上传9张图片
    - 支持格式: JPG, PNG, GIF, WebP
    - 返回所有图片的URL列表
    """
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"最多同时上传{MAX_FILES_PER_REQUEST}个文件"
        )

    ensure_upload_dir()

    results = []
    errors = []

    for idx, file in enumerate(files):
        try:
            content = await file.read()

            # 验证文件
            valid, msg, file_info = await validate_upload_file(
                file_content=content,
                filename=file.filename,
                file_type="image"
            )

            if not valid:
                errors.append({
                    "index": idx,
                    "filename": file.filename,
                    "error": msg
                })
                continue

            # 生成文件路径
            safe_filename, full_path, rel_path = process_upload_file(
                file_content=content,
                original_filename=file.filename,
                base_dir=UPLOAD_DIR,
                file_type=category,
                prefix=f"u{current_user.id}"
            )

            # 保存文件
            with open(full_path, "wb") as f:
                f.write(content)

            file_url = f"/uploads/{rel_path.replace(os.sep, '/')}"

            results.append({
                "index": idx,
                "url": file_url,
                "filename": safe_filename,
                "size": len(content),
                "mime_type": file_info.get("detected_mime")
            })

        except Exception as e:
            errors.append({
                "index": idx,
                "filename": file.filename if file else "unknown",
                "error": str(e)
            })

    return success(data={
        "uploaded": results,
        "errors": errors,
        "total": len(files),
        "success_count": len(results),
        "error_count": len(errors)
    }, message=f"成功上传{len(results)}个文件")


@router.post("/avatar", summary="上传头像")
async def upload_avatar(
    file: UploadFile = File(..., description="头像图片"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    上传用户头像

    - 支持格式: JPG, PNG, WebP
    - 最大大小: 2MB
    - 会自动更新用户头像
    """
    ensure_upload_dir()

    content = await file.read()

    # 验证文件（使用更严格的avatar类型）
    valid, msg, file_info = await validate_upload_file(
        file_content=content,
        filename=file.filename,
        file_type="avatar"
    )

    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    # 生成文件路径
    safe_filename, full_path, rel_path = process_upload_file(
        file_content=content,
        original_filename=file.filename,
        base_dir=UPLOAD_DIR,
        file_type="avatars",
        prefix=f"avatar_{current_user.id}"
    )

    # 保存文件
    with open(full_path, "wb") as f:
        f.write(content)

    file_url = f"/uploads/{rel_path.replace(os.sep, '/')}"

    # 更新用户头像
    current_user.avatar_url = file_url
    db.commit()

    return success(data={
        "url": file_url,
        "filename": safe_filename
    }, message="头像更新成功")


@router.post("/document", summary="上传文档")
async def upload_document(
    file: UploadFile = File(..., description="文档文件"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    上传文档文件

    - 支持格式: PDF, DOC, DOCX, TXT
    - 最大大小: 20MB
    """
    ensure_upload_dir()

    content = await file.read()

    # 验证文件
    valid, msg, file_info = await validate_upload_file(
        file_content=content,
        filename=file.filename,
        file_type="document"
    )

    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    # 生成文件路径
    safe_filename, full_path, rel_path = process_upload_file(
        file_content=content,
        original_filename=file.filename,
        base_dir=UPLOAD_DIR,
        file_type="documents",
        prefix=f"doc_{current_user.id}"
    )

    # 保存文件
    with open(full_path, "wb") as f:
        f.write(content)

    file_url = f"/uploads/{rel_path.replace(os.sep, '/')}"

    return success(data={
        "url": file_url,
        "filename": safe_filename,
        "size": len(content),
        "mime_type": file_info.get("detected_mime")
    }, message="文档上传成功")


@router.get("/config", summary="获取上传配置")
async def get_upload_config():
    """获取文件上传配置信息"""
    return success(data={
        "allowed_types": {
            "image": {
                "extensions": ALLOWED_FILE_TYPES["image"]["extensions"],
                "max_size_mb": ALLOWED_FILE_TYPES["image"]["max_size"] / (1024 * 1024)
            },
            "avatar": {
                "extensions": ALLOWED_FILE_TYPES["avatar"]["extensions"],
                "max_size_mb": ALLOWED_FILE_TYPES["avatar"]["max_size"] / (1024 * 1024)
            },
            "document": {
                "extensions": ALLOWED_FILE_TYPES["document"]["extensions"],
                "max_size_mb": ALLOWED_FILE_TYPES["document"]["max_size"] / (1024 * 1024)
            }
        },
        "max_files_per_request": MAX_FILES_PER_REQUEST
    })


@router.delete("", summary="删除文件")
async def delete_file(
    url: str = Query(..., description="文件URL"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    删除已上传的文件

    - 只能删除自己上传的文件
    - 需要提供完整的文件URL
    """
    # 验证URL格式
    if not url.startswith("/uploads/"):
        raise HTTPException(status_code=400, detail="无效的文件URL")

    # 从URL中提取用户ID进行权限验证
    # 文件名格式: u{user_id}_timestamp_uuid.ext 或 avatar_{user_id}_timestamp_uuid.ext
    filename = os.path.basename(url)

    # 简单的权限检查（通过文件名前缀）
    user_prefix = f"u{current_user.id}_"
    avatar_prefix = f"avatar_{current_user.id}_"
    doc_prefix = f"doc_{current_user.id}_"

    if not (filename.startswith(user_prefix) or
            filename.startswith(avatar_prefix) or
            filename.startswith(doc_prefix)):
        raise HTTPException(status_code=403, detail="无权删除此文件")

    # 构建完整路径
    rel_path = url.replace("/uploads/", "").replace("/", os.sep)
    full_path = os.path.join(UPLOAD_DIR, rel_path)

    # 检查文件是否存在
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    # 删除文件
    os.remove(full_path)

    return success(message="文件删除成功")


# ==================== 云存储增强接口 ====================

@router.post("/cloud/image", summary="上传图片到云存储")
async def upload_image_to_cloud(
    file: UploadFile = File(..., description="图片文件"),
    category: str = Form("images", description="分类: images avatars pet_photos"),
    resize: bool = Form(False, description="是否自动调整大小"),
    watermark: bool = Form(False, description="是否添加水印"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    上传图片到云存储（如果配置了OSS则使用OSS，否则使用本地存储）

    - 支持格式: JPG, PNG, GIF, WebP
    - 最大大小: 10MB
    - 可选：自动调整大小、添加水印
    """
    content = await file.read()

    # 验证文件
    file_type = "avatar" if category == "avatars" else "image"
    valid, msg, file_info = await validate_upload_file(
        file_content=content,
        filename=file.filename,
        file_type=file_type
    )

    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    # 图片处理
    if resize:
        content = image_processor.resize(content, max_width=1920, max_height=1080)

    if watermark:
        content = image_processor.add_watermark(content, "PetPal")

    # 上传到存储服务
    result = await storage_service.upload(
        file_content=content,
        filename=file.filename,
        category=category,
        user_id=current_user.id,
        content_type=file_info.get("detected_mime")
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error_message or "上传失败")

    # 获取图片信息
    img_info = image_processor.get_image_info(content)

    return success(data={
        "url": result.url,
        "key": result.key,
        "size": result.size,
        "mime_type": result.mime_type,
        "hash": result.hash,
        "storage_type": result.storage_type,
        "image_info": img_info
    }, message="上传成功")


@router.post("/cloud/images", summary="批量上传图片到云存储")
async def upload_images_to_cloud(
    files: List[UploadFile] = File(..., description="图片文件列表"),
    category: str = Form("images", description="分类"),
    resize: bool = Form(False, description="是否自动调整大小"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    批量上传图片到云存储

    - 最多同时上传9张图片
    """
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"最多同时上传{MAX_FILES_PER_REQUEST}个文件"
        )

    results = []
    errors = []

    for idx, file in enumerate(files):
        try:
            content = await file.read()

            # 验证文件
            valid, msg, file_info = await validate_upload_file(
                file_content=content,
                filename=file.filename,
                file_type="image"
            )

            if not valid:
                errors.append({
                    "index": idx,
                    "filename": file.filename,
                    "error": msg
                })
                continue

            # 图片处理
            if resize:
                content = image_processor.resize(content)

            # 上传
            result = await storage_service.upload(
                file_content=content,
                filename=file.filename,
                category=category,
                user_id=current_user.id,
                content_type=file_info.get("detected_mime")
            )

            if result.success:
                results.append({
                    "index": idx,
                    "url": result.url,
                    "key": result.key,
                    "size": result.size,
                    "mime_type": result.mime_type
                })
            else:
                errors.append({
                    "index": idx,
                    "filename": file.filename,
                    "error": result.error_message
                })

        except Exception as e:
            errors.append({
                "index": idx,
                "filename": file.filename if file else "unknown",
                "error": str(e)
            })

    return success(data={
        "uploaded": results,
        "errors": errors,
        "total": len(files),
        "success_count": len(results),
        "error_count": len(errors),
        "storage_type": storage_service.get_storage_type()
    }, message=f"成功上传{len(results)}个文件")


@router.get("/cloud/sts", summary="获取云存储临时凭证")
async def get_sts_token(
    current_user: User = Depends(get_current_user)
):
    """
    获取OSS临时上传凭证（用于客户端直传）

    返回STS临时凭证，客户端可以用此凭证直接上传到OSS
    """
    if not settings.oss_enabled:
        raise HTTPException(status_code=400, detail="云存储未启用")

    # 需要配置RAM角色ARN
    role_arn = getattr(settings, 'oss_role_arn', None)
    if not role_arn:
        raise HTTPException(status_code=400, detail="STS未配置")

    result = await storage_service.get_sts_token(
        role_arn=role_arn,
        session_name=f"petpal-user-{current_user.id}"
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "获取凭证失败"))

    return success(data=result, message="获取成功")


@router.get("/cloud/url/{key:path}", summary="获取文件签名URL")
async def get_signed_url(
    key: str,
    expires: int = Query(3600, description="过期时间(秒)"),
    current_user: User = Depends(get_current_user)
):
    """
    获取文件的签名访问URL

    - 用于访问私有文件
    - 默认1小时有效
    """
    url = storage_service.get_url(key, expires=expires)
    return success(data={"url": url, "expires_in": expires})


@router.delete("/cloud/{key:path}", summary="删除云存储文件")
async def delete_cloud_file(
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    删除云存储文件

    - 只能删除自己上传的文件（通过key中的用户ID判断）
    """
    # 权限检查：key中应包含用户ID
    user_marker = f"u{current_user.id}_"
    if user_marker not in key:
        raise HTTPException(status_code=403, detail="无权删除此文件")

    deleted = await storage_service.delete(key)
    if not deleted:
        raise HTTPException(status_code=404, detail="文件不存在或删除失败")

    return success(message="文件删除成功")


@router.get("/cloud/info/{key:path}", summary="获取文件信息")
async def get_file_info(
    key: str,
    current_user: User = Depends(get_current_user)
):
    """
    获取云存储文件信息

    返回文件大小、类型、修改时间等
    """
    info = await storage_service.get_info(key)
    if not info:
        raise HTTPException(status_code=404, detail="文件不存在")

    return success(data={
        "key": info.key,
        "size": info.size,
        "hash": info.hash,
        "mime_type": info.mime_type,
        "last_modified": info.last_modified.isoformat(),
        "storage_type": info.storage_type
    })


@router.get("/storage/status", summary="获取存储服务状态")
async def get_storage_status():
    """获取当前存储服务状态"""
    return success(data={
        "storage_type": storage_service.get_storage_type(),
        "oss_enabled": settings.oss_enabled,
        "oss_bucket": settings.oss_bucket_name if settings.oss_enabled else None,
        "oss_endpoint": settings.oss_endpoint if settings.oss_enabled else None,
        "local_upload_dir": UPLOAD_DIR
    })

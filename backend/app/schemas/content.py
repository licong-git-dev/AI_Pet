"""
PetPal - 内容相关Schema

包含：
- 帖子管理
- 评论管理
- 话题管理
- 收藏管理
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import json


# ==================== 帖子相关 ====================

class CreatePostRequest(BaseModel):
    """创建帖子请求"""
    content_type: str = Field("image", pattern="^(image|video|article)$")
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = Field(None, max_length=10000)
    media_urls: Optional[List[str]] = Field(None, max_length=9)
    cover_url: Optional[str] = Field(None, max_length=500)
    video_duration: Optional[int] = Field(None, ge=0)
    pet_id: Optional[int] = None
    tags: Optional[List[str]] = Field(None, max_length=10)
    topics: Optional[List[str]] = Field(None, max_length=5)
    product_ids: Optional[List[int]] = None
    location: Optional[str] = Field(None, max_length=200)
    latitude: Optional[str] = Field(None, max_length=20)
    longitude: Optional[str] = Field(None, max_length=20)
    is_original: bool = True

    @field_validator('media_urls')
    @classmethod
    def validate_media(cls, v, info):
        if v is not None:
            content_type = info.data.get('content_type', 'image')
            if content_type == 'image' and len(v) > 9:
                raise ValueError('图片最多9张')
            if content_type == 'video' and len(v) > 1:
                raise ValueError('视频只能上传1个')
        return v

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        if v is not None:
            v = [tag.strip()[:20] for tag in v if tag.strip()]
            if len(v) > 10:
                raise ValueError('标签最多10个')
        return v


class UpdatePostRequest(BaseModel):
    """更新帖子请求"""
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = Field(None, max_length=10000)
    tags: Optional[List[str]] = Field(None, max_length=10)
    topics: Optional[List[str]] = Field(None, max_length=5)
    location: Optional[str] = Field(None, max_length=200)


class PostAuthor(BaseModel):
    """帖子作者信息"""
    id: int
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    is_following: bool = False


class PostResponse(BaseModel):
    """帖子响应"""
    id: int
    content_type: str
    title: Optional[str] = None
    content: Optional[str] = None
    media_urls: Optional[List[str]] = None
    cover_url: Optional[str] = None
    tags: Optional[List[str]] = None
    topics: Optional[List[str]] = None
    location: Optional[str] = None
    views_count: int = 0
    likes_count: int = 0
    comments_count: int = 0
    shares_count: int = 0
    collects_count: int = 0
    is_top: bool = False
    is_hot: bool = False
    is_liked: bool = False
    is_collected: bool = False
    author: Optional[PostAuthor] = None
    pet: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


# ==================== 评论相关 ====================

class CreateCommentRequest(BaseModel):
    """创建评论请求"""
    post_id: int = Field(..., gt=0)
    content: str = Field(..., min_length=1, max_length=1000)
    parent_id: Optional[int] = Field(None, gt=0)
    reply_to_user_id: Optional[int] = Field(None, gt=0)
    image_url: Optional[str] = Field(None, max_length=500)

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('评论内容不能为空')
        return v


class CommentUser(BaseModel):
    """评论用户信息"""
    id: int
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None


class CommentResponse(BaseModel):
    """评论响应"""
    id: int
    post_id: int
    parent_id: Optional[int] = None
    content: str
    image_url: Optional[str] = None
    likes_count: int = 0
    replies_count: int = 0
    is_liked: bool = False
    user: Optional[CommentUser] = None
    reply_to_user: Optional[CommentUser] = None
    replies: Optional[List['CommentResponse']] = None
    created_at: Optional[datetime] = None


# ==================== 话题相关 ====================

class TopicCreate(BaseModel):
    """创建话题（管理员）"""
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    cover_image: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=50)
    is_official: bool = False


class TopicResponse(BaseModel):
    """话题响应"""
    id: int
    name: str
    description: Optional[str] = None
    cover_image: Optional[str] = None
    category: Optional[str] = None
    posts_count: int = 0
    followers_count: int = 0
    is_hot: bool = False
    is_official: bool = False
    is_following: bool = False


class TopicSearchRequest(BaseModel):
    """搜索话题请求"""
    keyword: str = Field(..., min_length=1, max_length=50)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


# ==================== 收藏相关 ====================

class CollectPostRequest(BaseModel):
    """收藏帖子请求"""
    post_id: int = Field(..., gt=0)
    folder_id: Optional[int] = Field(None, gt=0)


class CreateFolderRequest(BaseModel):
    """创建收藏夹请求"""
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    is_private: bool = False


class UpdateFolderRequest(BaseModel):
    """更新收藏夹请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    is_private: Optional[bool] = None


class FolderResponse(BaseModel):
    """收藏夹响应"""
    id: int
    name: str
    description: Optional[str] = None
    cover_image: Optional[str] = None
    is_private: bool = False
    posts_count: int = 0
    created_at: Optional[datetime] = None


# ==================== 分享相关 ====================

class SharePostRequest(BaseModel):
    """分享帖子请求"""
    post_id: int = Field(..., gt=0)
    platform: str = Field(..., pattern="^(wechat|weibo|qq|internal)$")


# ==================== 搜索相关 ====================

class SearchPostsRequest(BaseModel):
    """搜索帖子请求"""
    keyword: str = Field(..., min_length=1, max_length=100)
    content_type: Optional[str] = Field(None, pattern="^(image|video|article)$")
    pet_type: Optional[str] = None
    sort_by: str = Field("relevance", pattern="^(relevance|time|hot)$")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class SearchResult(BaseModel):
    """搜索结果"""
    posts: List[PostResponse] = []
    topics: List[TopicResponse] = []
    users: List[Dict[str, Any]] = []
    total_posts: int = 0
    total_topics: int = 0
    total_users: int = 0

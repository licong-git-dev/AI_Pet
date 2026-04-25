"""
PetPal - 内容模型 (帖子、评论、点赞、收藏、话题)
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Topic(Base):
    """话题表"""
    __tablename__ = "topics"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="话题ID")
    name = Column(String(50), unique=True, nullable=False, comment="话题名称")
    description = Column(String(500), nullable=True, comment="话题描述")
    cover_image = Column(String(500), nullable=True, comment="封面图")
    category = Column(String(50), nullable=True, comment="分类")

    posts_count = Column(Integer, default=0, comment="帖子数")
    followers_count = Column(Integer, default=0, comment="关注数")
    views_count = Column(Integer, default=0, comment="浏览数")

    is_hot = Column(Integer, default=0, comment="是否热门")
    is_official = Column(Integer, default=0, comment="是否官方话题")
    sort_order = Column(Integer, default=0, comment="排序")
    status = Column(Integer, default=1, comment="状态: 0禁用 1正常")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "cover_image": self.cover_image,
            "category": self.category,
            "posts_count": self.posts_count,
            "followers_count": self.followers_count,
            "is_hot": bool(self.is_hot),
            "is_official": bool(self.is_official)
        }


class TopicFollow(Base):
    """话题关注表"""
    __tablename__ = "topic_follows"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(BigInteger, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('user_id', 'topic_id', name='uk_user_topic'),
    )


class Post(Base):
    """帖子/内容表"""
    __tablename__ = "posts"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="帖子ID")
    author_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="作者ID")
    pet_id = Column(BigInteger, ForeignKey("pets.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联宠物ID")

    # 内容
    content_type = Column(String(20), default="image", comment="内容类型: image图片 video视频 article文章")
    title = Column(String(200), nullable=True, comment="标题")
    content = Column(Text, nullable=True, comment="文字内容")
    media_urls = Column(Text, nullable=True, comment="媒体URL列表(JSON)")
    cover_url = Column(String(500), nullable=True, comment="封面图URL")
    video_duration = Column(Integer, nullable=True, comment="视频时长(秒)")

    # 标签和话题
    tags = Column(Text, nullable=True, comment="标签列表(JSON)")
    topics = Column(Text, nullable=True, comment="话题列表(JSON)")

    # 商品关联
    product_ids = Column(Text, nullable=True, comment="关联商品ID列表(JSON)")

    # 位置信息
    location = Column(String(200), nullable=True, comment="位置名称")
    latitude = Column(String(20), nullable=True, comment="纬度")
    longitude = Column(String(20), nullable=True, comment="经度")

    # 统计
    views_count = Column(Integer, default=0, comment="浏览数")
    likes_count = Column(Integer, default=0, comment="点赞数")
    comments_count = Column(Integer, default=0, comment="评论数")
    shares_count = Column(Integer, default=0, comment="分享数")
    collects_count = Column(Integer, default=0, comment="收藏数")

    # 状态
    status = Column(Integer, default=1, comment="状态: 0审核中 1已发布 2已下架 3已删除")
    is_top = Column(Integer, default=0, comment="是否置顶")
    is_hot = Column(Integer, default=0, comment="是否热门")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    deleted_at = Column(DateTime, nullable=True, comment="删除时间")

    # 关系
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", lazy="dynamic")

    def to_dict(self, include_author=True):
        """转换为字典"""
        data = {
            "id": self.id,
            "content_type": self.content_type,
            "title": self.title,
            "content": self.content,
            "media_urls": self.media_urls,
            "cover_url": self.cover_url,
            "tags": self.tags,
            "topics": self.topics,
            "location": self.location,
            "views_count": self.views_count,
            "likes_count": self.likes_count,
            "comments_count": self.comments_count,
            "shares_count": self.shares_count,
            "collects_count": self.collects_count,
            "is_top": self.is_top,
            "is_hot": self.is_hot,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        if include_author and self.author:
            data["author"] = {
                "id": self.author.id,
                "nickname": self.author.nickname,
                "avatar_url": self.author.avatar_url
            }
        return data


class Comment(Base):
    """评论表"""
    __tablename__ = "comments"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="评论ID")
    post_id = Column(BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True, comment="帖子ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    parent_id = Column(BigInteger, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True, comment="父评论ID")
    reply_to_user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="回复用户ID")

    content = Column(Text, nullable=False, comment="评论内容")
    image_url = Column(String(500), nullable=True, comment="图片URL")

    likes_count = Column(Integer, default=0, comment="点赞数")
    replies_count = Column(Integer, default=0, comment="回复数")

    status = Column(Integer, default=1, comment="状态: 0审核中 1正常 2已删除")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    post = relationship("Post", back_populates="comments")
    user = relationship("User", foreign_keys=[user_id])
    reply_to_user = relationship("User", foreign_keys=[reply_to_user_id])

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "post_id": self.post_id,
            "parent_id": self.parent_id,
            "content": self.content,
            "image_url": self.image_url,
            "likes_count": self.likes_count,
            "replies_count": self.replies_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "user": {
                "id": self.user.id,
                "nickname": self.user.nickname,
                "avatar_url": self.user.avatar_url
            } if self.user else None
        }


class Like(Base):
    """点赞表"""
    __tablename__ = "likes"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="点赞ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    target_type = Column(String(20), nullable=False, comment="目标类型: post帖子 comment评论")
    target_id = Column(BigInteger, nullable=False, index=True, comment="目标ID")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        # 用户只能对同一目标点赞一次
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )


class Collection(Base):
    """收藏表"""
    __tablename__ = "collections"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="收藏ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    post_id = Column(BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True, comment="帖子ID")
    folder_id = Column(BigInteger, nullable=True, comment="收藏夹ID")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        UniqueConstraint('user_id', 'post_id', name='uk_user_post_collect'),
    )


class CollectionFolder(Base):
    """收藏夹表"""
    __tablename__ = "collection_folders"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="收藏夹ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    name = Column(String(50), nullable=False, comment="收藏夹名称")
    description = Column(String(200), nullable=True, comment="描述")
    cover_image = Column(String(500), nullable=True, comment="封面图")
    is_private = Column(Integer, default=0, comment="是否私密")
    posts_count = Column(Integer, default=0, comment="帖子数")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "cover_image": self.cover_image,
            "is_private": bool(self.is_private),
            "posts_count": self.posts_count,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Share(Base):
    """分享记录表"""
    __tablename__ = "shares"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="分享ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    post_id = Column(BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True, comment="帖子ID")
    platform = Column(String(50), nullable=False, comment="分享平台: wechat微信 weibo微博 qq内部")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

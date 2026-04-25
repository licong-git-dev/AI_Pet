"""
PetPal - 内容API (帖子、评论、点赞、收藏、话题)

提供完整的内容社区功能：
- 帖子发布与管理
- 评论系统
- 点赞/收藏/分享
- 话题管理
- 内容搜索
"""
import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, func

from app.database import get_db
from app.models.user import User
from app.models.pet import Pet
from app.models.content import (
    Post, Comment, Like, Topic, TopicFollow,
    Collection, CollectionFolder, Share
)
from app.models.social import Follow
from app.models.user_settings import UserBlacklist
from app.schemas.content import (
    CreatePostRequest, UpdatePostRequest, CreateCommentRequest,
    CollectPostRequest, CreateFolderRequest, UpdateFolderRequest,
    SharePostRequest
)
from app.utils.deps import get_current_user, get_current_user_optional
from app.utils.response import success, page_response

router = APIRouter()


# ==================== 帖子信息流 ====================

@router.get("", summary="获取帖子列表")
async def get_posts(
    tab: str = Query("recommend", description="标签: recommend推荐 follow关注 hot热门 latest最新"),
    pet_type: str = Query(None, description="宠物类型筛选"),
    topic: str = Query(None, description="话题筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取帖子信息流"""
    query = db.query(Post).filter(Post.status == 1, Post.deleted_at.is_(None))

    # 排除被拉黑用户的帖子
    if current_user:
        blocked_ids = db.query(UserBlacklist.blocked_user_id).filter(
            UserBlacklist.user_id == current_user.id
        ).subquery()
        query = query.filter(~Post.author_id.in_(blocked_ids))

    if tab == "follow" and current_user:
        # 关注的人的帖子
        following_ids = db.query(Follow.following_id).filter(
            Follow.follower_id == current_user.id
        ).subquery()
        query = query.filter(Post.author_id.in_(following_ids))
    elif tab == "hot":
        # 热门帖子
        query = query.filter(Post.is_hot == 1)

    if pet_type:
        # 根据宠物类型筛选
        pet_ids = db.query(Pet.id).filter(Pet.pet_type == pet_type).subquery()
        query = query.filter(Post.pet_id.in_(pet_ids))

    if topic:
        query = query.filter(Post.topics.contains(topic))

    # 排序
    if tab == "recommend":
        query = query.order_by(desc(Post.is_top), desc(Post.created_at))
    elif tab == "hot":
        query = query.order_by(desc(Post.likes_count), desc(Post.created_at))
    elif tab == "latest":
        query = query.order_by(desc(Post.created_at))
    else:
        query = query.order_by(desc(Post.created_at))

    total = query.count()
    posts = query.offset((page - 1) * page_size).limit(page_size).all()

    # 批量获取点赞和收藏状态
    post_ids = [p.id for p in posts]
    liked_ids = set()
    collected_ids = set()

    if current_user and post_ids:
        likes = db.query(Like.target_id).filter(
            Like.user_id == current_user.id,
            Like.target_type == "post",
            Like.target_id.in_(post_ids)
        ).all()
        liked_ids = {l[0] for l in likes}

        collections = db.query(Collection.post_id).filter(
            Collection.user_id == current_user.id,
            Collection.post_id.in_(post_ids)
        ).all()
        collected_ids = {c[0] for c in collections}

    # 处理帖子数据
    posts_data = []
    for post in posts:
        post_dict = _format_post(post, current_user, liked_ids, collected_ids)
        posts_data.append(post_dict)

    return page_response(data=posts_data, page=page, page_size=page_size, total=total)


def _format_post(post: Post, current_user: User, liked_ids: set = None, collected_ids: set = None) -> dict:
    """格式化帖子数据"""
    post_dict = {
        "id": post.id,
        "content_type": post.content_type,
        "title": post.title,
        "content": post.content,
        "cover_url": post.cover_url,
        "location": post.location,
        "views_count": post.views_count,
        "likes_count": post.likes_count,
        "comments_count": post.comments_count,
        "shares_count": post.shares_count,
        "collects_count": post.collects_count,
        "is_top": bool(post.is_top),
        "is_hot": bool(post.is_hot),
        "created_at": post.created_at.isoformat() if post.created_at else None
    }

    # 解析JSON字段
    try:
        post_dict["media_urls"] = json.loads(post.media_urls) if post.media_urls else []
    except (json.JSONDecodeError, ValueError):
        post_dict["media_urls"] = []

    try:
        post_dict["tags"] = json.loads(post.tags) if post.tags else []
    except (json.JSONDecodeError, ValueError):
        post_dict["tags"] = []

    try:
        post_dict["topics"] = json.loads(post.topics) if post.topics else []
    except (json.JSONDecodeError, ValueError):
        post_dict["topics"] = []

    # 作者信息
    if post.author:
        post_dict["author"] = {
            "id": post.author.id,
            "nickname": post.author.nickname,
            "avatar_url": post.author.avatar_url
        }

    # 点赞/收藏状态
    if liked_ids is not None:
        post_dict["is_liked"] = post.id in liked_ids
    else:
        post_dict["is_liked"] = False

    if collected_ids is not None:
        post_dict["is_collected"] = post.id in collected_ids
    else:
        post_dict["is_collected"] = False

    return post_dict


# ==================== 帖子CRUD ====================

@router.post("", summary="发布帖子")
async def create_post(
    request: CreatePostRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """发布新帖子"""
    # 验证宠物归属
    if request.pet_id:
        pet = db.query(Pet).filter(
            Pet.id == request.pet_id,
            Pet.owner_id == current_user.id,
            Pet.deleted_at.is_(None)
        ).first()
        if not pet:
            raise HTTPException(status_code=400, detail="宠物不存在或不属于您")

    post = Post(
        author_id=current_user.id,
        pet_id=request.pet_id,
        content_type=request.content_type,
        title=request.title,
        content=request.content,
        media_urls=json.dumps(request.media_urls) if request.media_urls else None,
        cover_url=request.cover_url or (request.media_urls[0] if request.media_urls else None),
        video_duration=request.video_duration,
        tags=json.dumps(request.tags) if request.tags else None,
        topics=json.dumps(request.topics) if request.topics else None,
        product_ids=json.dumps(request.product_ids) if request.product_ids else None,
        location=request.location,
        latitude=request.latitude,
        longitude=request.longitude,
        status=1
    )
    db.add(post)

    # 更新用户发帖数
    current_user.posts_count += 1

    # 增加积分
    from app.models.points import PointsRecord
    points_record = PointsRecord(
        user_id=current_user.id,
        points=3,
        balance=current_user.points + 3,
        source_type="post",
        description="发布内容奖励"
    )
    current_user.points += 3
    db.add(points_record)

    # 更新话题帖子数
    if request.topics:
        for topic_name in request.topics:
            topic = db.query(Topic).filter(Topic.name == topic_name).first()
            if topic:
                topic.posts_count += 1

    db.commit()
    db.refresh(post)

    return success(data=_format_post(post, current_user, set(), set()), message="发布成功")


@router.get("/{post_id}", summary="获取帖子详情")
async def get_post(
    post_id: int,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取帖子详情"""
    post = db.query(Post).filter(Post.id == post_id, Post.deleted_at.is_(None)).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    # 检查是否被作者拉黑
    if current_user:
        is_blocked = db.query(UserBlacklist).filter(
            UserBlacklist.user_id == post.author_id,
            UserBlacklist.blocked_user_id == current_user.id
        ).first()
        if is_blocked:
            raise HTTPException(status_code=403, detail="无法查看该内容")

    # 增加浏览数
    post.views_count += 1
    db.commit()

    # 获取点赞和收藏状态
    liked_ids = set()
    collected_ids = set()

    if current_user:
        if db.query(Like).filter(
            Like.user_id == current_user.id,
            Like.target_type == "post",
            Like.target_id == post_id
        ).first():
            liked_ids.add(post_id)

        if db.query(Collection).filter(
            Collection.user_id == current_user.id,
            Collection.post_id == post_id
        ).first():
            collected_ids.add(post_id)

    post_dict = _format_post(post, current_user, liked_ids, collected_ids)

    # 添加宠物信息
    if post.pet_id:
        pet = db.query(Pet).filter(Pet.id == post.pet_id).first()
        if pet:
            post_dict["pet"] = {
                "id": pet.id,
                "name": pet.name,
                "pet_type": pet.pet_type,
                "avatar_url": pet.avatar_url
            }

    return success(data=post_dict)


@router.put("/{post_id}", summary="更新帖子")
async def update_post(
    post_id: int,
    request: UpdatePostRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新帖子"""
    post = db.query(Post).filter(
        Post.id == post_id,
        Post.author_id == current_user.id,
        Post.deleted_at.is_(None)
    ).first()

    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    update_data = request.model_dump(exclude_unset=True)

    # 处理JSON字段
    if "tags" in update_data and update_data["tags"] is not None:
        update_data["tags"] = json.dumps(update_data["tags"])
    if "topics" in update_data and update_data["topics"] is not None:
        update_data["topics"] = json.dumps(update_data["topics"])

    for key, value in update_data.items():
        setattr(post, key, value)

    db.commit()
    db.refresh(post)

    return success(data=_format_post(post, current_user), message="更新成功")


@router.delete("/{post_id}", summary="删除帖子")
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除帖子"""
    post = db.query(Post).filter(
        Post.id == post_id,
        Post.author_id == current_user.id,
        Post.deleted_at.is_(None)
    ).first()

    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    post.deleted_at = datetime.now()
    post.status = 3
    current_user.posts_count = max(0, current_user.posts_count - 1)

    db.commit()

    return success(message="删除成功")


# ==================== 点赞功能 ====================

@router.post("/{post_id}/like", summary="点赞帖子")
async def like_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """点赞帖子"""
    post = db.query(Post).filter(Post.id == post_id, Post.deleted_at.is_(None)).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    # 检查是否已点赞
    existing = db.query(Like).filter(
        Like.user_id == current_user.id,
        Like.target_type == "post",
        Like.target_id == post_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="已点赞")

    # 创建点赞记录
    like = Like(user_id=current_user.id, target_type="post", target_id=post_id)
    db.add(like)

    # 更新计数
    post.likes_count += 1

    # 给作者增加获赞数和积分
    author = db.query(User).filter(User.id == post.author_id).first()
    if author and author.id != current_user.id:
        author.likes_count += 1
        from app.models.points import PointsRecord
        points_record = PointsRecord(
            user_id=author.id,
            points=1,
            balance=author.points + 1,
            source_type="like",
            source_id=post_id,
            description="获得点赞奖励"
        )
        author.points += 1
        db.add(points_record)

    db.commit()

    return success(data={"likes_count": post.likes_count}, message="点赞成功")


@router.delete("/{post_id}/like", summary="取消点赞")
async def unlike_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消点赞"""
    like = db.query(Like).filter(
        Like.user_id == current_user.id,
        Like.target_type == "post",
        Like.target_id == post_id
    ).first()

    if not like:
        raise HTTPException(status_code=400, detail="未点赞")

    db.delete(like)

    # 更新计数
    post = db.query(Post).filter(Post.id == post_id).first()
    if post:
        post.likes_count = max(0, post.likes_count - 1)

    db.commit()

    return success(data={"likes_count": post.likes_count if post else 0}, message="取消点赞成功")


# ==================== 收藏功能 ====================

@router.post("/{post_id}/collect", summary="收藏帖子")
async def collect_post(
    post_id: int,
    folder_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """收藏帖子"""
    post = db.query(Post).filter(Post.id == post_id, Post.deleted_at.is_(None)).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    # 检查是否已收藏
    existing = db.query(Collection).filter(
        Collection.user_id == current_user.id,
        Collection.post_id == post_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="已收藏")

    # 验证收藏夹
    if folder_id:
        folder = db.query(CollectionFolder).filter(
            CollectionFolder.id == folder_id,
            CollectionFolder.user_id == current_user.id
        ).first()
        if not folder:
            raise HTTPException(status_code=400, detail="收藏夹不存在")

    # 创建收藏
    collection = Collection(
        user_id=current_user.id,
        post_id=post_id,
        folder_id=folder_id
    )
    db.add(collection)

    # 更新帖子收藏数
    post.collects_count += 1

    # 更新收藏夹帖子数
    if folder_id:
        folder.posts_count += 1

    db.commit()

    return success(data={"collects_count": post.collects_count}, message="收藏成功")


@router.delete("/{post_id}/collect", summary="取消收藏")
async def uncollect_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消收藏"""
    collection = db.query(Collection).filter(
        Collection.user_id == current_user.id,
        Collection.post_id == post_id
    ).first()

    if not collection:
        raise HTTPException(status_code=400, detail="未收藏")

    folder_id = collection.folder_id
    db.delete(collection)

    # 更新帖子收藏数
    post = db.query(Post).filter(Post.id == post_id).first()
    if post:
        post.collects_count = max(0, post.collects_count - 1)

    # 更新收藏夹帖子数
    if folder_id:
        folder = db.query(CollectionFolder).filter(CollectionFolder.id == folder_id).first()
        if folder:
            folder.posts_count = max(0, folder.posts_count - 1)

    db.commit()

    return success(data={"collects_count": post.collects_count if post else 0}, message="取消收藏成功")


@router.get("/collections/list", summary="获取收藏列表")
async def get_collections(
    folder_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我的收藏列表"""
    query = db.query(Post).join(Collection, Collection.post_id == Post.id).filter(
        Collection.user_id == current_user.id,
        Post.deleted_at.is_(None)
    )

    if folder_id:
        query = query.filter(Collection.folder_id == folder_id)

    query = query.order_by(desc(Collection.created_at))

    total = query.count()
    posts = query.offset((page - 1) * page_size).limit(page_size).all()

    posts_data = [_format_post(p, current_user, set(), {p.id}) for p in posts]

    return page_response(data=posts_data, page=page, page_size=page_size, total=total)


# ==================== 收藏夹管理 ====================

@router.get("/folders", summary="获取收藏夹列表")
async def get_folders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我的收藏夹列表"""
    folders = db.query(CollectionFolder).filter(
        CollectionFolder.user_id == current_user.id
    ).order_by(CollectionFolder.created_at.desc()).all()

    return success(data=[f.to_dict() for f in folders])


@router.post("/folders", summary="创建收藏夹")
async def create_folder(
    request: CreateFolderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建收藏夹"""
    # 检查收藏夹数量
    count = db.query(CollectionFolder).filter(
        CollectionFolder.user_id == current_user.id
    ).count()
    if count >= 50:
        raise HTTPException(status_code=400, detail="收藏夹数量已达上限")

    folder = CollectionFolder(
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        is_private=1 if request.is_private else 0
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)

    return success(data=folder.to_dict(), message="创建成功")


@router.delete("/folders/{folder_id}", summary="删除收藏夹")
async def delete_folder(
    folder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除收藏夹"""
    folder = db.query(CollectionFolder).filter(
        CollectionFolder.id == folder_id,
        CollectionFolder.user_id == current_user.id
    ).first()

    if not folder:
        raise HTTPException(status_code=404, detail="收藏夹不存在")

    # 将该收藏夹中的收藏移到默认
    db.query(Collection).filter(
        Collection.folder_id == folder_id
    ).update({"folder_id": None})

    db.delete(folder)
    db.commit()

    return success(message="删除成功")


# ==================== 分享功能 ====================

@router.post("/{post_id}/share", summary="分享帖子")
async def share_post(
    post_id: int,
    platform: str = Query("internal", description="平台: wechat weibo qq internal"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """记录分享"""
    post = db.query(Post).filter(Post.id == post_id, Post.deleted_at.is_(None)).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    # 记录分享
    share = Share(
        user_id=current_user.id,
        post_id=post_id,
        platform=platform
    )
    db.add(share)

    # 更新分享数
    post.shares_count += 1

    # 给作者增加积分
    author = db.query(User).filter(User.id == post.author_id).first()
    if author and author.id != current_user.id:
        from app.models.points import PointsRecord
        points_record = PointsRecord(
            user_id=author.id,
            points=1,
            balance=author.points + 1,
            source_type="share",
            source_id=post_id,
            description="内容被分享奖励"
        )
        author.points += 1
        db.add(points_record)

    db.commit()

    return success(data={"shares_count": post.shares_count}, message="分享成功")


# ==================== 评论功能 ====================

@router.get("/{post_id}/comments", summary="获取评论列表")
async def get_comments(
    post_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取帖子评论列表"""
    query = db.query(Comment).filter(
        Comment.post_id == post_id,
        Comment.parent_id.is_(None),
        Comment.status == 1
    ).order_by(desc(Comment.likes_count), desc(Comment.created_at))

    total = query.count()
    comments = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取点赞状态
    comment_ids = [c.id for c in comments]
    liked_ids = set()
    if current_user and comment_ids:
        likes = db.query(Like.target_id).filter(
            Like.user_id == current_user.id,
            Like.target_type == "comment",
            Like.target_id.in_(comment_ids)
        ).all()
        liked_ids = {l[0] for l in likes}

    result = []
    for comment in comments:
        comment_dict = _format_comment(comment, liked_ids)

        # 获取子评论（最多3条）
        replies = db.query(Comment).filter(
            Comment.parent_id == comment.id,
            Comment.status == 1
        ).order_by(Comment.created_at).limit(3).all()

        if replies:
            comment_dict["replies"] = [_format_comment(r, liked_ids) for r in replies]

        result.append(comment_dict)

    return page_response(data=result, page=page, page_size=page_size, total=total)


def _format_comment(comment: Comment, liked_ids: set = None) -> dict:
    """格式化评论数据"""
    return {
        "id": comment.id,
        "post_id": comment.post_id,
        "parent_id": comment.parent_id,
        "content": comment.content,
        "image_url": comment.image_url,
        "likes_count": comment.likes_count,
        "replies_count": comment.replies_count,
        "is_liked": comment.id in (liked_ids or set()),
        "user": {
            "id": comment.user.id,
            "nickname": comment.user.nickname,
            "avatar_url": comment.user.avatar_url
        } if comment.user else None,
        "reply_to_user": {
            "id": comment.reply_to_user.id,
            "nickname": comment.reply_to_user.nickname
        } if comment.reply_to_user else None,
        "created_at": comment.created_at.isoformat() if comment.created_at else None
    }


@router.get("/{post_id}/comments/{comment_id}/replies", summary="获取评论回复")
async def get_comment_replies(
    post_id: int,
    comment_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取评论的回复列表"""
    query = db.query(Comment).filter(
        Comment.parent_id == comment_id,
        Comment.status == 1
    ).order_by(Comment.created_at)

    total = query.count()
    replies = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取点赞状态
    reply_ids = [r.id for r in replies]
    liked_ids = set()
    if current_user and reply_ids:
        likes = db.query(Like.target_id).filter(
            Like.user_id == current_user.id,
            Like.target_type == "comment",
            Like.target_id.in_(reply_ids)
        ).all()
        liked_ids = {l[0] for l in likes}

    result = [_format_comment(r, liked_ids) for r in replies]

    return page_response(data=result, page=page, page_size=page_size, total=total)


@router.post("/comments", summary="发表评论")
async def create_comment(
    request: CreateCommentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """发表评论"""
    post = db.query(Post).filter(Post.id == request.post_id, Post.deleted_at.is_(None)).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    # 验证父评论
    if request.parent_id:
        parent = db.query(Comment).filter(
            Comment.id == request.parent_id,
            Comment.post_id == request.post_id,
            Comment.status == 1
        ).first()
        if not parent:
            raise HTTPException(status_code=400, detail="父评论不存在")

    comment = Comment(
        post_id=request.post_id,
        user_id=current_user.id,
        content=request.content,
        parent_id=request.parent_id,
        reply_to_user_id=request.reply_to_user_id,
        image_url=request.image_url
    )
    db.add(comment)

    # 更新帖子评论数
    post.comments_count += 1

    # 更新父评论回复数
    if request.parent_id:
        parent.replies_count += 1

    # 增加积分
    from app.models.points import PointsRecord
    points_record = PointsRecord(
        user_id=current_user.id,
        points=1,
        balance=current_user.points + 1,
        source_type="comment",
        description="发表评论奖励"
    )
    current_user.points += 1
    db.add(points_record)

    db.commit()
    db.refresh(comment)

    return success(data=_format_comment(comment), message="评论成功")


@router.post("/comments/{comment_id}/like", summary="点赞评论")
async def like_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """点赞评论"""
    comment = db.query(Comment).filter(Comment.id == comment_id, Comment.status == 1).first()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    existing = db.query(Like).filter(
        Like.user_id == current_user.id,
        Like.target_type == "comment",
        Like.target_id == comment_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="已点赞")

    like = Like(user_id=current_user.id, target_type="comment", target_id=comment_id)
    db.add(like)
    comment.likes_count += 1

    db.commit()

    return success(data={"likes_count": comment.likes_count}, message="点赞成功")


@router.delete("/comments/{comment_id}/like", summary="取消评论点赞")
async def unlike_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消评论点赞"""
    like = db.query(Like).filter(
        Like.user_id == current_user.id,
        Like.target_type == "comment",
        Like.target_id == comment_id
    ).first()

    if not like:
        raise HTTPException(status_code=400, detail="未点赞")

    db.delete(like)

    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if comment:
        comment.likes_count = max(0, comment.likes_count - 1)

    db.commit()

    return success(data={"likes_count": comment.likes_count if comment else 0}, message="取消点赞成功")


@router.delete("/comments/{comment_id}", summary="删除评论")
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除评论（只能删除自己的）"""
    comment = db.query(Comment).filter(
        Comment.id == comment_id,
        Comment.user_id == current_user.id,
        Comment.status == 1
    ).first()

    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    comment.status = 2  # 标记为已删除
    comment.deleted_at = datetime.now()

    # 更新帖子评论数
    post = db.query(Post).filter(Post.id == comment.post_id).first()
    if post:
        post.comments_count = max(0, post.comments_count - 1)

    # 更新父评论回复数
    if comment.parent_id:
        parent = db.query(Comment).filter(Comment.id == comment.parent_id).first()
        if parent:
            parent.replies_count = max(0, parent.replies_count - 1)

    db.commit()

    return success(message="删除成功")


# ==================== 话题功能 ====================

@router.get("/topics/hot", summary="获取热门话题")
async def get_hot_topics(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """获取热门话题"""
    topics = db.query(Topic).filter(
        Topic.status == 1
    ).order_by(desc(Topic.is_hot), desc(Topic.posts_count)).limit(limit).all()

    return success(data=[t.to_dict() for t in topics])


@router.get("/topics/search", summary="搜索话题")
async def search_topics(
    keyword: str = Query(..., min_length=1, max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """搜索话题"""
    query = db.query(Topic).filter(
        Topic.status == 1,
        Topic.name.ilike(f"%{keyword}%")
    ).order_by(desc(Topic.posts_count))

    total = query.count()
    topics = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取关注状态
    following_ids = set()
    if current_user:
        follows = db.query(TopicFollow.topic_id).filter(
            TopicFollow.user_id == current_user.id
        ).all()
        following_ids = {f[0] for f in follows}

    result = []
    for topic in topics:
        topic_dict = topic.to_dict()
        topic_dict["is_following"] = topic.id in following_ids
        result.append(topic_dict)

    return page_response(data=result, page=page, page_size=page_size, total=total)


@router.get("/topics/{topic_id}", summary="获取话题详情")
async def get_topic(
    topic_id: int,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取话题详情"""
    topic = db.query(Topic).filter(Topic.id == topic_id, Topic.status == 1).first()
    if not topic:
        raise HTTPException(status_code=404, detail="话题不存在")

    topic.views_count += 1
    db.commit()

    topic_dict = topic.to_dict()

    if current_user:
        is_following = db.query(TopicFollow).filter(
            TopicFollow.user_id == current_user.id,
            TopicFollow.topic_id == topic_id
        ).first() is not None
        topic_dict["is_following"] = is_following

    return success(data=topic_dict)


@router.post("/topics/{topic_id}/follow", summary="关注话题")
async def follow_topic(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """关注话题"""
    topic = db.query(Topic).filter(Topic.id == topic_id, Topic.status == 1).first()
    if not topic:
        raise HTTPException(status_code=404, detail="话题不存在")

    existing = db.query(TopicFollow).filter(
        TopicFollow.user_id == current_user.id,
        TopicFollow.topic_id == topic_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="已关注该话题")

    follow = TopicFollow(user_id=current_user.id, topic_id=topic_id)
    db.add(follow)
    topic.followers_count += 1

    db.commit()

    return success(message="关注成功")


@router.delete("/topics/{topic_id}/follow", summary="取消关注话题")
async def unfollow_topic(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消关注话题"""
    follow = db.query(TopicFollow).filter(
        TopicFollow.user_id == current_user.id,
        TopicFollow.topic_id == topic_id
    ).first()

    if not follow:
        raise HTTPException(status_code=400, detail="未关注该话题")

    db.delete(follow)

    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if topic:
        topic.followers_count = max(0, topic.followers_count - 1)

    db.commit()

    return success(message="取消关注成功")


# ==================== 用户帖子 ====================

@router.get("/user/{user_id}/posts", summary="获取用户帖子")
async def get_user_posts(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取用户发布的帖子"""
    query = db.query(Post).filter(
        Post.author_id == user_id,
        Post.status == 1,
        Post.deleted_at.is_(None)
    ).order_by(desc(Post.created_at))

    total = query.count()
    posts = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取点赞和收藏状态
    post_ids = [p.id for p in posts]
    liked_ids = set()
    collected_ids = set()

    if current_user and post_ids:
        likes = db.query(Like.target_id).filter(
            Like.user_id == current_user.id,
            Like.target_type == "post",
            Like.target_id.in_(post_ids)
        ).all()
        liked_ids = {l[0] for l in likes}

        collections = db.query(Collection.post_id).filter(
            Collection.user_id == current_user.id,
            Collection.post_id.in_(post_ids)
        ).all()
        collected_ids = {c[0] for c in collections}

    posts_data = [_format_post(p, current_user, liked_ids, collected_ids) for p in posts]

    return page_response(data=posts_data, page=page, page_size=page_size, total=total)


# ==================== 搜索功能 ====================

@router.get("/search", summary="搜索内容")
async def search_content(
    keyword: str = Query(..., min_length=1, max_length=100),
    content_type: Optional[str] = Query(None, description="内容类型"),
    sort_by: str = Query("relevance", description="排序: relevance time hot"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """搜索帖子"""
    query = db.query(Post).filter(
        Post.status == 1,
        Post.deleted_at.is_(None),
        or_(
            Post.title.ilike(f"%{keyword}%"),
            Post.content.ilike(f"%{keyword}%"),
            Post.tags.ilike(f"%{keyword}%")
        )
    )

    if content_type:
        query = query.filter(Post.content_type == content_type)

    # 排序
    if sort_by == "time":
        query = query.order_by(desc(Post.created_at))
    elif sort_by == "hot":
        query = query.order_by(desc(Post.likes_count), desc(Post.created_at))
    else:
        # relevance - 按匹配度（简单实现）
        query = query.order_by(desc(Post.views_count), desc(Post.created_at))

    total = query.count()
    posts = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取点赞和收藏状态
    post_ids = [p.id for p in posts]
    liked_ids = set()
    collected_ids = set()

    if current_user and post_ids:
        likes = db.query(Like.target_id).filter(
            Like.user_id == current_user.id,
            Like.target_type == "post",
            Like.target_id.in_(post_ids)
        ).all()
        liked_ids = {l[0] for l in likes}

        collections = db.query(Collection.post_id).filter(
            Collection.user_id == current_user.id,
            Collection.post_id.in_(post_ids)
        ).all()
        collected_ids = {c[0] for c in collections}

    posts_data = [_format_post(p, current_user, liked_ids, collected_ids) for p in posts]

    return page_response(data=posts_data, page=page, page_size=page_size, total=total)

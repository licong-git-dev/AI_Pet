"""
PetPal - 搜索API
提供全局搜索功能，支持搜索帖子、用户、商品、宠物
"""
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from app.database import get_db
from app.models.user import User
from app.models.pet import Pet
from app.models.content import Post
from app.models.shop import Product
from app.models.social import Follow
from app.utils.response import success
from app.utils.deps import get_current_user_optional
from app.config import settings
from typing import Optional, List
from datetime import datetime
from loguru import logger
import json

router = APIRouter()

# Redis客户端（懒加载）
_redis_client = None
_memory_store = {}  # 内存存储（开发环境降级方案）

# 搜索历史配置
SEARCH_HISTORY_KEY_PREFIX = "search_history:"
SEARCH_HISTORY_MAX_SIZE = 20  # 最多保存20条历史
SEARCH_HISTORY_EXPIRE_DAYS = 30  # 历史保留30天

POST_STATUS_PUBLISHED = 1
PRODUCT_STATUS_ON_SALE = 1


def _get_redis():
    """获取Redis客户端"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis不可用，搜索历史使用内存存储: {e}")
        _redis_client = None
        return None


def _save_search_history(user_id: int, keyword: str):
    """保存用户搜索历史"""
    if not keyword or not keyword.strip():
        return

    keyword = keyword.strip()[:50]  # 限制长度
    redis_client = _get_redis()
    key = f"{SEARCH_HISTORY_KEY_PREFIX}{user_id}"

    if redis_client:
        try:
            # 先移除已存在的相同关键词（避免重复）
            redis_client.lrem(key, 0, keyword)
            # 添加到列表头部
            redis_client.lpush(key, keyword)
            # 裁剪列表，保持最大长度
            redis_client.ltrim(key, 0, SEARCH_HISTORY_MAX_SIZE - 1)
            # 设置过期时间
            redis_client.expire(key, SEARCH_HISTORY_EXPIRE_DAYS * 24 * 3600)
        except Exception as e:
            logger.error(f"保存搜索历史到Redis失败: {e}")
    else:
        # 使用内存存储
        if key not in _memory_store:
            _memory_store[key] = []
        history = _memory_store[key]
        # 移除重复项
        if keyword in history:
            history.remove(keyword)
        # 添加到头部
        history.insert(0, keyword)
        # 保持最大长度
        _memory_store[key] = history[:SEARCH_HISTORY_MAX_SIZE]


def _get_search_history(user_id: int) -> List[str]:
    """获取用户搜索历史"""
    redis_client = _get_redis()
    key = f"{SEARCH_HISTORY_KEY_PREFIX}{user_id}"

    if redis_client:
        try:
            return redis_client.lrange(key, 0, SEARCH_HISTORY_MAX_SIZE - 1)
        except Exception as e:
            logger.error(f"从Redis获取搜索历史失败: {e}")
            return []
    else:
        return _memory_store.get(key, [])


def _clear_search_history(user_id: int):
    """清空用户搜索历史"""
    redis_client = _get_redis()
    key = f"{SEARCH_HISTORY_KEY_PREFIX}{user_id}"

    if redis_client:
        try:
            redis_client.delete(key)
        except Exception as e:
            logger.error(f"从Redis清空搜索历史失败: {e}")
    else:
        if key in _memory_store:
            del _memory_store[key]


@router.get("/global", summary="全局搜索")
async def global_search(
    keyword: str = Query(..., min_length=1, max_length=50, description="搜索关键词"),
    search_type: str = Query("all", description="搜索类型: all/post/user/product/pet"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    全局搜索接口

    支持搜索类型:
    - all: 搜索所有内容
    - post: 仅搜索帖子
    - user: 仅搜索用户
    - product: 仅搜索商品
    - pet: 仅搜索宠物
    """
    # 保存搜索历史（仅登录用户）
    if current_user:
        _save_search_history(current_user.id, keyword)

    results = {
        "keyword": keyword,
        "posts": [],
        "users": [],
        "products": [],
        "pets": []
    }

    offset = (page - 1) * page_size

    # 搜索帖子
    if search_type in ["all", "post"]:
        post_query = db.query(Post).filter(
            Post.deleted_at.is_(None),
            Post.status == POST_STATUS_PUBLISHED,
            or_(
                Post.content.ilike(f"%{keyword}%"),
                Post.title.ilike(f"%{keyword}%")
            )
        ).order_by(desc(Post.created_at))

        if search_type == "post":
            posts = post_query.offset(offset).limit(page_size).all()
        else:
            posts = post_query.limit(5).all()

        # 批量获取作者信息，避免N+1查询
        author_ids = list(set(p.author_id for p in posts if p.author_id))
        authors_map = {}
        if author_ids:
            authors = db.query(User).filter(User.id.in_(author_ids)).all()
            authors_map = {a.id: a for a in authors}

        for post in posts:
            author = authors_map.get(post.author_id)
            post_dict = {
                "id": post.id,
                "content": post.content[:100] if post.content else "",
                "title": post.title,
                "cover_url": None,
                "likes_count": post.likes_count,
                "comments_count": post.comments_count,
                "created_at": post.created_at.isoformat() if post.created_at else None,
                "author": {
                    "id": author.id,
                    "nickname": author.nickname,
                    "avatar_url": author.avatar_url
                } if author else None
            }
            # 解析媒体URL获取封面
            try:
                if post.media_urls:
                    urls = json.loads(post.media_urls) if isinstance(post.media_urls, str) else post.media_urls
                    if urls:
                        post_dict["cover_url"] = urls[0]
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Post {post.id} media_urls JSON解析失败: {str(e)}")
            results["posts"].append(post_dict)

    # 搜索用户
    if search_type in ["all", "user"]:
        user_query = db.query(User).filter(
            User.deleted_at.is_(None),
            or_(
                User.nickname.ilike(f"%{keyword}%"),
                User.bio.ilike(f"%{keyword}%")
            )
        ).order_by(desc(User.followers_count))

        if search_type == "user":
            users = user_query.offset(offset).limit(page_size).all()
        else:
            users = user_query.limit(5).all()

        # 获取当前用户的关注列表
        following_ids = set()
        if current_user and users:
            user_ids = [u.id for u in users]
            follows = db.query(Follow.following_id).filter(
                Follow.follower_id == current_user.id,
                Follow.following_id.in_(user_ids)
            ).all()
            following_ids = {f[0] for f in follows}

        for user in users:
            results["users"].append({
                "id": user.id,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
                "bio": user.bio[:50] if user.bio else None,
                "followers_count": user.followers_count,
                "is_following": user.id in following_ids
            })

    # 搜索商品
    if search_type in ["all", "product"]:
        product_query = db.query(Product).filter(
            Product.deleted_at.is_(None),
            Product.status == PRODUCT_STATUS_ON_SALE,
            or_(
                Product.name.ilike(f"%{keyword}%"),
                Product.description.ilike(f"%{keyword}%")
            )
        ).order_by(desc(Product.sales_count))

        if search_type == "product":
            products = product_query.offset(offset).limit(page_size).all()
        else:
            products = product_query.limit(5).all()

        for product in products:
            results["products"].append({
                "id": product.id,
                "name": product.name,
                "cover_image": product.cover_image,
                "price": float(product.price) if product.price else 0,
                "original_price": float(product.original_price) if product.original_price else None,
                "sales_count": product.sales_count
            })

    # 搜索宠物
    if search_type in ["all", "pet"]:
        pet_query = db.query(Pet).filter(
            Pet.deleted_at.is_(None),
            or_(
                Pet.name.ilike(f"%{keyword}%"),
                Pet.breed_name.ilike(f"%{keyword}%")
            )
        ).order_by(desc(Pet.created_at))

        if search_type == "pet":
            pets = pet_query.offset(offset).limit(page_size).all()
        else:
            pets = pet_query.limit(5).all()

        for pet in pets:
            owner = db.query(User).filter(User.id == pet.owner_id).first()
            results["pets"].append({
                "id": pet.id,
                "name": pet.name,
                "pet_type": pet.pet_type,
                "breed_name": pet.breed_name,
                "avatar_url": pet.avatar_url,
                "owner": {
                    "id": owner.id,
                    "nickname": owner.nickname
                } if owner else None
            })

    return success(data=results)


@router.get("/hot", summary="热门搜索")
async def get_hot_searches(
    db: Session = Depends(get_db)
):
    """获取热门搜索词"""
    # 这里可以从Redis获取热门搜索，暂时返回固定数据
    hot_keywords = [
        "猫粮推荐",
        "狗狗皮肤病",
        "宠物美容",
        "猫咪绝育",
        "狗粮排行",
        "宠物疫苗",
        "布偶猫",
        "柯基犬"
    ]
    return success(data={"keywords": hot_keywords})


@router.get("/history", summary="搜索历史")
async def get_search_history(
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取用户搜索历史"""
    if not current_user:
        return success(data={"history": []})

    history = _get_search_history(current_user.id)
    return success(data={"history": history})


@router.delete("/history", summary="清空搜索历史")
async def clear_search_history(
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """清空用户搜索历史"""
    if current_user:
        _clear_search_history(current_user.id)
    return success(message="搜索历史已清空")


@router.get("/suggest", summary="搜索建议")
async def get_search_suggestions(
    keyword: str = Query(..., min_length=1, max_length=50),
    db: Session = Depends(get_db)
):
    """根据输入获取搜索建议"""
    suggestions = []

    # 从帖子标题获取建议
    posts = db.query(Post.title).filter(
        Post.deleted_at.is_(None),
        Post.title.ilike(f"%{keyword}%")
    ).distinct().limit(3).all()
    suggestions.extend([p.title for p in posts if p.title])

    # 从商品名称获取建议
    products = db.query(Product.name).filter(
        Product.deleted_at.is_(None),
        Product.name.ilike(f"%{keyword}%")
    ).distinct().limit(3).all()
    suggestions.extend([p.name for p in products])

    # 从用户昵称获取建议
    users = db.query(User.nickname).filter(
        User.deleted_at.is_(None),
        User.nickname.ilike(f"%{keyword}%")
    ).distinct().limit(2).all()
    suggestions.extend([u.nickname for u in users])

    return success(data={"suggestions": suggestions[:8]})

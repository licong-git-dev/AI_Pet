"""
PetPal - 商城API

提供完整的电商功能：
- 商品浏览与搜索
- 分类管理
- 购物车
- 订单管理
- 优惠券系统
- 商品评价
- 商品收藏
- 退款申请
"""
import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, func

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.shop import (
    Product, ProductCategory, Order, OrderItem,
    Coupon, UserCoupon, ProductReview, ProductFavorite, RefundRequest
)
from app.models.points import PointsRecord
from app.models.user_settings import UserAddress
from app.schemas.shop import (
    CartItemAdd, CartItemUpdate, CartItemSelect, CreateOrderRequest, OrderPreviewRequest, PayOrderRequest,
    CreateReviewRequest, AppendReviewRequest, CreateRefundRequest, RefundShipRequest,
    ReceiveCouponRequest
)
from app.utils.deps import get_current_user, get_current_user_optional
from app.utils.response import success, page_response

router = APIRouter()
PAYMENT_EXPIRE_MINUTES = 30


def _cart_item_key(product_id: int, sku_id: Optional[int]) -> str:
    return f"{product_id}:{sku_id or 0}"


def _parse_cart_item_key(cart_key: str) -> tuple[int, Optional[int]]:
    product_id_text, _, sku_id_text = cart_key.partition(":")
    product_id = int(product_id_text)
    sku_id = int(sku_id_text) if sku_id_text and sku_id_text != "0" else None
    return product_id, sku_id


def _build_sku_info(specs: dict[str, str]) -> str:
    return " / ".join(f"{key}:{value}" for key, value in specs.items())


def _merge_order_items(items: list) -> list:
    merged: dict[tuple[int, Optional[int]], dict] = {}
    for item in items:
        key = (item.product_id, item.sku_id)
        if key not in merged:
            merged[key] = {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "sku_id": item.sku_id,
                "sku_info": item.sku_info,
            }
        else:
            merged[key]["quantity"] += item.quantity
            if not merged[key]["sku_info"] and item.sku_info:
                merged[key]["sku_info"] = item.sku_info
    return list(merged.values())


def _update_product_sku_stock(product: Product, sku_id: Optional[int], quantity_delta: int) -> None:
    product.stock = max(0, int(product.stock or 0) + quantity_delta)
    if sku_id is None:
        return

    sku_data = _resolve_product_sku(product, sku_id, allow_missing=False)
    matched_sku = sku_data["matched_sku"]
    if matched_sku is None:
        return
    matched_sku["stock"] = max(0, int(matched_sku.get("stock", 0)) + quantity_delta)
    product.skus = json.dumps(sku_data["skus"], ensure_ascii=False)


def _resolve_product_sku(product: Product, sku_id: Optional[int], fallback_sku_info: Optional[str] = None, *, allow_missing: bool = False) -> dict:
    price = float(product.price)
    stock = int(product.stock)
    sku_info = fallback_sku_info or ""

    try:
        skus = json.loads(product.skus) if product.skus else []
    except (json.JSONDecodeError, ValueError, TypeError):
        skus = []

    has_skus = len(skus) > 0
    if sku_id is None:
        if has_skus and not allow_missing:
            raise HTTPException(status_code=400, detail=f"商品{product.id}必须选择规格")
        return {
            "sku_id": None,
            "price": price,
            "stock": stock,
            "sku_info": sku_info,
            "matched_sku": None,
            "skus": skus,
        }

    try:
        skus = json.loads(product.skus) if product.skus else []
    except (json.JSONDecodeError, ValueError, TypeError):
        skus = []

    matched_sku = next((sku for sku in skus if int(sku.get("id", 0)) == sku_id), None)
    if not matched_sku:
        if allow_missing:
            return {
                "sku_id": sku_id,
                "price": price,
                "stock": 0,
                "sku_info": sku_info,
                "matched_sku": None,
                "skus": skus,
            }
        raise HTTPException(status_code=400, detail=f"商品{product.id}规格不存在")

    sku_price = matched_sku.get("price", price)
    sku_stock = matched_sku.get("stock", stock)
    sku_specs = matched_sku.get("specs") if isinstance(matched_sku.get("specs"), dict) else {}
    resolved_sku_info = fallback_sku_info or _build_sku_info(sku_specs)

    return {
        "sku_id": sku_id,
        "price": float(sku_price),
        "stock": int(sku_stock),
        "sku_info": resolved_sku_info,
        "matched_sku": matched_sku,
        "skus": skus,
    }


def _is_local_development() -> bool:
    return settings.debug and settings.app_env == "development" and settings.app_base_url.startswith("http://localhost")


def _is_payment_expired(order: Order) -> bool:
    if not order.created_at:
        return False
    return datetime.now() > order.created_at + timedelta(minutes=PAYMENT_EXPIRE_MINUTES)


def _rollback_pending_order(order: Order, user: User, db: Session) -> None:
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            _update_product_sku_stock(product, item.sku_id, item.quantity)

    if order.points_used > 0:
        points_record = PointsRecord(
            user_id=user.id,
            points=order.points_used,
            balance=user.points + order.points_used,
            source_type="order_refund",
            source_id=order.id,
            description="订单取消退还积分"
        )
        user.points += order.points_used
        db.add(points_record)

    user_coupon = db.query(UserCoupon).filter(UserCoupon.order_id == order.id).first()
    if user_coupon:
        user_coupon.status = "unused"
        user_coupon.used_at = None
        user_coupon.order_id = None

    order.status = "cancelled"


# ==================== 商品分类 ====================

@router.get("/categories", summary="获取商品分类")
async def get_categories(
    parent_id: Optional[int] = Query(None, description="父分类ID，不传获取全部"),
    db: Session = Depends(get_db)
):
    """获取商品分类列表（支持树形结构）"""
    if parent_id is not None:
        categories = db.query(ProductCategory).filter(
            ProductCategory.parent_id == parent_id,
            ProductCategory.is_show == 1
        ).order_by(ProductCategory.sort_order).all()
        return success(data=[c.to_dict() for c in categories])

    # 获取所有一级分类
    root_categories = db.query(ProductCategory).filter(
        ProductCategory.parent_id.is_(None),
        ProductCategory.is_show == 1
    ).order_by(ProductCategory.sort_order).all()

    result = []
    for cat in root_categories:
        cat_dict = cat.to_dict()
        # 获取子分类
        children = db.query(ProductCategory).filter(
            ProductCategory.parent_id == cat.id,
            ProductCategory.is_show == 1
        ).order_by(ProductCategory.sort_order).all()
        cat_dict["children"] = [c.to_dict() for c in children]
        result.append(cat_dict)

    return success(data=result)


# ==================== 商品列表与搜索 ====================

@router.get("/products", summary="获取商品列表")
async def get_products(
    category_id: Optional[int] = Query(None, description="分类ID"),
    category: Optional[str] = Query(None, description="分类标识"),
    pet_type: Optional[str] = Query(None, description="适用宠物类型"),
    brand: Optional[str] = Query(None, description="品牌"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    min_price: Optional[float] = Query(None, ge=0, description="最低价格"),
    max_price: Optional[float] = Query(None, ge=0, description="最高价格"),
    is_new: Optional[int] = Query(None, description="是否新品"),
    is_hot: Optional[int] = Query(None, description="是否热销"),
    sort: str = Query("recommend", description="排序方式"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取商品列表，支持多条件筛选和排序"""
    query = db.query(Product).filter(
        Product.status == 1,
        Product.deleted_at.is_(None)
    )

    # 分类筛选
    if category_id:
        # 包含子分类
        child_ids = db.query(ProductCategory.id).filter(
            ProductCategory.parent_id == category_id
        ).all()
        all_cat_ids = [category_id] + [c[0] for c in child_ids]
        # 获取所有分类的名称用于筛选
        cat_names = db.query(ProductCategory.name).filter(
            ProductCategory.id.in_(all_cat_ids)
        ).all()
        cat_name_list = [c[0] for c in cat_names]
        if cat_name_list:
            query = query.filter(Product.category.in_(cat_name_list))

    if category:
        query = query.filter(Product.category == category)

    if pet_type:
        query = query.filter(
            or_(Product.pet_type == pet_type, Product.pet_type == "all", Product.pet_type.is_(None))
        )

    if brand:
        query = query.filter(Product.brand == brand)

    if keyword:
        keyword_filter = f"%{keyword}%"
        query = query.filter(
            or_(
                Product.name.ilike(keyword_filter),
                Product.subtitle.ilike(keyword_filter),
                Product.description.ilike(keyword_filter)
            )
        )

    if min_price is not None:
        query = query.filter(Product.price >= min_price)

    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    if is_new is not None:
        query = query.filter(Product.is_new == is_new)

    if is_hot is not None:
        query = query.filter(Product.is_hot == is_hot)

    # 排序
    if sort == "sales":
        query = query.order_by(desc(Product.sales_count))
    elif sort == "price_asc":
        query = query.order_by(Product.price)
    elif sort == "price_desc":
        query = query.order_by(desc(Product.price))
    elif sort == "rating":
        query = query.order_by(desc(Product.rating))
    elif sort == "new":
        query = query.order_by(desc(Product.created_at))
    else:  # recommend
        query = query.order_by(desc(Product.is_recommended), desc(Product.is_hot), desc(Product.created_at))

    total = query.count()
    products = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取收藏状态
    product_ids = [p.id for p in products]
    favorited_ids = set()
    if current_user and product_ids:
        favs = db.query(ProductFavorite.product_id).filter(
            ProductFavorite.user_id == current_user.id,
            ProductFavorite.product_id.in_(product_ids)
        ).all()
        favorited_ids = {f[0] for f in favs}

    products_data = []
    for p in products:
        p_dict = p.to_dict()
        p_dict["is_favorited"] = p.id in favorited_ids
        products_data.append(p_dict)

    return page_response(data=products_data, page=page, page_size=page_size, total=total)


@router.get("/products/{product_id}", summary="获取商品详情")
async def get_product(
    product_id: int,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取商品详细信息"""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.status == 1,
        Product.deleted_at.is_(None)
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    # 增加浏览量
    product.views_count += 1
    db.commit()

    product_dict = product.to_dict()

    # 解析JSON字段
    try:
        product_dict["images"] = json.loads(product.images) if product.images else []
    except (json.JSONDecodeError, ValueError):
        product_dict["images"] = []

    try:
        product_dict["specs"] = json.loads(product.specs) if product.specs else []
    except (json.JSONDecodeError, ValueError):
        product_dict["specs"] = []

    try:
        product_dict["skus"] = json.loads(product.skus) if product.skus else []
    except (json.JSONDecodeError, ValueError):
        product_dict["skus"] = []

    product_dict["description"] = product.description
    product_dict["video_url"] = product.video_url

    # 收藏状态
    if current_user:
        is_favorited = db.query(ProductFavorite).filter(
            ProductFavorite.user_id == current_user.id,
            ProductFavorite.product_id == product_id
        ).first() is not None
        product_dict["is_favorited"] = is_favorited
    else:
        product_dict["is_favorited"] = False

    # 评价统计
    review_stats = db.query(
        func.count(ProductReview.id).label('count'),
        func.avg(ProductReview.rating).label('avg_rating')
    ).filter(
        ProductReview.product_id == product_id,
        ProductReview.status == 1
    ).first()

    product_dict["review_count"] = review_stats.count or 0
    product_dict["rating"] = round(float(review_stats.avg_rating or 5.0), 1)

    return success(data=product_dict)


# ==================== 购物车 ====================

def _get_redis_client():
    """获取Redis客户端"""
    import redis
    from app.config import settings
    return redis.from_url(settings.redis_url, decode_responses=True)


@router.get("/cart", summary="获取购物车")
async def get_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取购物车商品列表"""
    redis_client = _get_redis_client()
    cart_key = f"cart:{current_user.id}"
    select_key = f"cart_select:{current_user.id}"

    cart_items = redis_client.hgetall(cart_key)
    selected_items = redis_client.smembers(select_key)

    if not cart_items:
        return success(data={
            "items": [],
            "total_count": 0,
            "selected_count": 0,
            "total_amount": 0,
            "selected_amount": 0
        })

    items_data = []
    total_amount = 0
    selected_amount = 0
    selected_count = 0

    for item_key, item_json in cart_items.items():
        try:
            item_data = json.loads(item_json)
        except (json.JSONDecodeError, ValueError):
            item_data = {"quantity": int(item_json)}

        product_id, parsed_sku_id = _parse_cart_item_key(item_key)
        quantity = item_data.get("quantity", 1)
        sku_id = item_data.get("sku_id", parsed_sku_id)
        sku_info = item_data.get("sku_info", "")

        product = db.query(Product).filter(Product.id == product_id).first()

        if product:
            sku_data = _resolve_product_sku(product, sku_id, sku_info, allow_missing=True)
            price = sku_data["price"]
            stock = sku_data["stock"]
            resolved_sku_info = sku_data["sku_info"]
            is_valid = product.status == 1 and stock > 0 and not (product.skus and sku_id is None) and (sku_id is None or sku_data["matched_sku"] is not None)
        else:
            price = 0
            stock = 0
            resolved_sku_info = sku_info
            is_valid = False

        is_selected = item_key in selected_items
        item_amount = price * quantity
        total_amount += item_amount

        if is_selected:
            selected_amount += item_amount
            selected_count += quantity

        items_data.append({
            "cart_key": item_key,
            "product_id": product_id,
            "product_name": product.name if product else "商品已下架",
            "product_image": product.cover_image if product else None,
            "sku_id": sku_id,
            "sku_info": resolved_sku_info,
            "price": float(price),
            "quantity": quantity,
            "amount": float(item_amount),
            "stock": stock,
            "selected": is_selected,
            "is_valid": is_valid
        })

    return success(data={
        "items": items_data,
        "total_count": sum(item.get("quantity", 0) for item in items_data),
        "selected_count": selected_count,
        "total_amount": float(total_amount),
        "selected_amount": float(selected_amount)
    })


@router.post("/cart", summary="添加到购物车")
async def add_to_cart(
    request: CartItemAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加商品到购物车"""
    product = db.query(Product).filter(
        Product.id == request.product_id,
        Product.status == 1,
        Product.deleted_at.is_(None)
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    if product.stock < request.quantity:
        raise HTTPException(status_code=400, detail="库存不足")

    sku_data = _resolve_product_sku(product, request.sku_id, request.sku_info)

    redis_client = _get_redis_client()
    cart_key = f"cart:{current_user.id}"
    select_key = f"cart_select:{current_user.id}"
    item_key = _cart_item_key(request.product_id, request.sku_id)

    # 获取现有数量
    existing = redis_client.hget(cart_key, item_key)
    if existing:
        try:
            existing_data = json.loads(existing)
            current_qty = existing_data.get("quantity", 0)
        except (json.JSONDecodeError, ValueError):
            current_qty = int(existing)
    else:
        current_qty = 0

    new_qty = current_qty + request.quantity

    if new_qty > sku_data["stock"]:
        raise HTTPException(status_code=400, detail="超出库存数量")

    if new_qty > 99:
        raise HTTPException(status_code=400, detail="单商品最多99件")

    # 保存购物车数据
    item_data = {
        "quantity": new_qty,
        "sku_id": sku_data["sku_id"],
        "sku_info": sku_data["sku_info"]
    }
    redis_client.hset(cart_key, item_key, json.dumps(item_data))
    redis_client.sadd(select_key, item_key)  # 默认选中
    redis_client.expire(cart_key, 30 * 24 * 3600)  # 30天过期
    redis_client.expire(select_key, 30 * 24 * 3600)

    return success(message="已添加到购物车")


@router.put("/cart/{product_id}", summary="更新购物车商品数量")
async def update_cart_item(
    product_id: int,
    request: CartItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新购物车商品数量"""
    if not request.cart_key:
        raise HTTPException(status_code=400, detail="缺少购物车项标识")

    key_product_id, sku_id = _parse_cart_item_key(request.cart_key)
    if key_product_id != product_id:
        raise HTTPException(status_code=400, detail="购物车项标识无效")

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    sku_data = _resolve_product_sku(product, sku_id)
    if request.quantity > sku_data["stock"]:
        raise HTTPException(status_code=400, detail="超出库存数量")

    redis_client = _get_redis_client()
    cart_key = f"cart:{current_user.id}"

    existing = redis_client.hget(cart_key, request.cart_key)
    if not existing:
        raise HTTPException(status_code=404, detail="商品不在购物车中")

    try:
        item_data = json.loads(existing)
        item_data["quantity"] = request.quantity
    except (json.JSONDecodeError, ValueError):
        item_data = {"quantity": request.quantity, "sku_id": sku_id, "sku_info": sku_data["sku_info"]}

    redis_client.hset(cart_key, request.cart_key, json.dumps(item_data))

    return success(message="更新成功")


@router.delete("/cart/{product_id}", summary="从购物车移除")
async def remove_from_cart(
    product_id: int,
    cart_key: str = Query(..., description="购物车项标识"),
    current_user: User = Depends(get_current_user)
):
    """从购物车移除商品"""
    key_product_id, _ = _parse_cart_item_key(cart_key)
    if key_product_id != product_id:
        raise HTTPException(status_code=400, detail="购物车项标识无效")

    redis_client = _get_redis_client()
    user_cart_key = f"cart:{current_user.id}"
    select_key = f"cart_select:{current_user.id}"

    redis_client.hdel(user_cart_key, cart_key)
    redis_client.srem(select_key, cart_key)

    return success(message="已从购物车移除")


@router.post("/cart/select", summary="选中/取消选中商品")
async def select_cart_items(
    request: CartItemSelect,
    current_user: User = Depends(get_current_user)
):
    """批量选中/取消选中购物车商品"""
    redis_client = _get_redis_client()
    select_key = f"cart_select:{current_user.id}"

    if request.selected:
        if request.cart_keys:
            redis_client.sadd(select_key, *request.cart_keys)
    else:
        if request.cart_keys:
            redis_client.srem(select_key, *request.cart_keys)

    return success(message="更新成功")


@router.post("/cart/select-all", summary="全选/取消全选")
async def select_all_cart(
    selected: bool = Body(True, embed=True),
    current_user: User = Depends(get_current_user)
):
    """全选/取消全选购物车"""
    redis_client = _get_redis_client()
    cart_key = f"cart:{current_user.id}"
    select_key = f"cart_select:{current_user.id}"

    cart_items = redis_client.hkeys(cart_key)

    if selected:
        if cart_items:
            redis_client.sadd(select_key, *cart_items)
    else:
        redis_client.delete(select_key)

    return success(message="更新成功")


@router.delete("/cart/clear", summary="清空购物车")
async def clear_cart(
    only_selected: bool = Query(False, description="是否只清空选中的"),
    current_user: User = Depends(get_current_user)
):
    """清空购物车"""
    redis_client = _get_redis_client()
    cart_key = f"cart:{current_user.id}"
    select_key = f"cart_select:{current_user.id}"

    if only_selected:
        selected = redis_client.smembers(select_key)
        if selected:
            redis_client.hdel(cart_key, *selected)
            redis_client.delete(select_key)
    else:
        redis_client.delete(cart_key)
        redis_client.delete(select_key)

    return success(message="清空成功")


# ==================== 订单管理 ====================

@router.post("/orders/preview", summary="订单预览")
async def preview_order(
    request: OrderPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """下单前预览订单信息"""
    if not request.items:
        raise HTTPException(status_code=400, detail="请选择商品")

    # 计算商品金额
    items_data = []
    total_amount = 0
    merged_items = _merge_order_items(request.items)

    for item in merged_items:
        product = db.query(Product).filter(
            Product.id == item["product_id"],
            Product.status == 1
        ).first()

        if not product:
            raise HTTPException(status_code=400, detail=f"商品{item['product_id']}不存在或已下架")

        sku_data = _resolve_product_sku(product, item["sku_id"], item["sku_info"])
        quantity = item["quantity"]
        if sku_data["stock"] < quantity:
            raise HTTPException(status_code=400, detail=f"商品{product.name}库存不足")

        item_amount = sku_data["price"] * quantity
        total_amount += item_amount

        items_data.append({
            "product_id": product.id,
            "product_name": product.name,
            "product_image": product.cover_image,
            "sku_id": sku_data["sku_id"],
            "sku_info": sku_data["sku_info"],
            "price": sku_data["price"],
            "quantity": quantity,
            "amount": float(item_amount)
        })

    # 运费（简单逻辑：满99免运费）
    freight_amount = 0 if total_amount >= 99 else 10

    # 优惠券
    discount_amount = 0
    if request.coupon_id:
        user_coupon = db.query(UserCoupon).filter(
            UserCoupon.id == request.coupon_id,
            UserCoupon.user_id == current_user.id,
            UserCoupon.status == "unused"
        ).first()

        if user_coupon and user_coupon.coupon:
            coupon = user_coupon.coupon
            if total_amount >= coupon.min_amount:
                if coupon.coupon_type == "amount":
                    discount_amount = coupon.discount_amount
                elif coupon.coupon_type == "percent":
                    discount_amount = total_amount * coupon.discount_percent / 100
                    if coupon.max_discount > 0:
                        discount_amount = min(discount_amount, coupon.max_discount)
                elif coupon.coupon_type == "shipping":
                    discount_amount = freight_amount

    # 积分抵扣（100积分=1元）
    max_points_use = min(current_user.points, int(total_amount * 10))  # 最多抵扣10%
    points_use = min(request.points_use, max_points_use)
    points_amount = points_use / 100

    # 实付金额
    pay_amount = max(0.01, total_amount + freight_amount - discount_amount - points_amount)

    # 获取可用优惠券
    available_coupons = []
    user_coupons = db.query(UserCoupon).filter(
        UserCoupon.user_id == current_user.id,
        UserCoupon.status == "unused"
    ).all()

    for uc in user_coupons:
        if uc.coupon and total_amount >= uc.coupon.min_amount:
            available_coupons.append(uc.to_dict())

    return success(data={
        "items": items_data,
        "total_amount": float(total_amount),
        "discount_amount": float(discount_amount),
        "points_amount": float(points_amount),
        "freight_amount": float(freight_amount),
        "pay_amount": float(pay_amount),
        "available_coupons": available_coupons,
        "max_points_use": max_points_use,
        "points_use": points_use
    })


@router.post("/orders", summary="创建订单")
async def create_order(
    request: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建订单"""
    if not request.items:
        raise HTTPException(status_code=400, detail="订单不能为空")

    # 验证地址
    address = db.query(UserAddress).filter(
        UserAddress.id == request.address_id,
        UserAddress.user_id == current_user.id
    ).first()

    if not address:
        raise HTTPException(status_code=400, detail="收货地址不存在")

    # 计算订单金额
    total_amount = 0
    order_items = []
    merged_items = _merge_order_items(request.items)

    for item in merged_items:
        product = db.query(Product).filter(
            Product.id == item["product_id"],
            Product.status == 1
        ).first()

        if not product:
            raise HTTPException(status_code=400, detail=f"商品{item['product_id']}不存在或已下架")

        sku_data = _resolve_product_sku(product, item["sku_id"], item["sku_info"])
        if sku_data["stock"] < item["quantity"]:
            raise HTTPException(status_code=400, detail=f"商品{product.name}库存不足")

        item_amount = sku_data["price"] * item["quantity"]
        total_amount += item_amount

        order_items.append({
            "product": product,
            "quantity": item["quantity"],
            "price": sku_data["price"],
            "amount": item_amount,
            "sku_id": sku_data["sku_id"],
            "sku_info": sku_data["sku_info"]
        })

    # 运费
    freight_amount = 0 if total_amount >= 99 else 10

    # 优惠券
    discount_amount = 0
    user_coupon = None
    if request.coupon_id:
        user_coupon = db.query(UserCoupon).filter(
            UserCoupon.id == request.coupon_id,
            UserCoupon.user_id == current_user.id,
            UserCoupon.status == "unused"
        ).first()

        if user_coupon and user_coupon.coupon:
            coupon = user_coupon.coupon
            if total_amount >= coupon.min_amount:
                if coupon.coupon_type == "amount":
                    discount_amount = coupon.discount_amount
                elif coupon.coupon_type == "percent":
                    discount_amount = total_amount * coupon.discount_percent / 100
                    if coupon.max_discount > 0:
                        discount_amount = min(discount_amount, coupon.max_discount)
                elif coupon.coupon_type == "shipping":
                    discount_amount = freight_amount

    # 积分抵扣
    max_points_use = min(current_user.points, int(total_amount * 10))
    points_use = min(request.points_use, max_points_use)
    points_amount = points_use / 100

    # 实付金额
    pay_amount = max(0.01, total_amount + freight_amount - discount_amount - points_amount)

    # 生成订单号
    order_no = f"PET{int(time.time() * 1000)}{current_user.id}"

    # 创建订单
    order = Order(
        order_no=order_no,
        user_id=current_user.id,
        total_amount=total_amount,
        discount_amount=discount_amount,
        points_amount=points_amount,
        freight_amount=freight_amount,
        pay_amount=pay_amount,
        points_used=points_use,
        receiver_name=address.receiver_name,
        receiver_phone=address.receiver_phone,
        receiver_address=f"{address.province}{address.city}{address.district}{address.detail_address}",
        remark=request.remark,
        status="pending"
    )
    db.add(order)
    db.flush()

    # 创建订单项并扣减库存
    for item_data in order_items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item_data["product"].id,
            sku_id=item_data["sku_id"],
            product_name=item_data["product"].name,
            product_image=item_data["product"].cover_image,
            sku_info=item_data["sku_info"],
            price=item_data["price"],
            quantity=item_data["quantity"],
            total_amount=item_data["amount"]
        )
        db.add(order_item)
        _update_product_sku_stock(item_data["product"], item_data["sku_id"], -item_data["quantity"])

    # 使用优惠券
    if user_coupon:
        user_coupon.status = "used"
        user_coupon.used_at = datetime.now()
        user_coupon.order_id = order.id

    # 扣除积分
    if points_use > 0:
        points_record = PointsRecord(
            user_id=current_user.id,
            points=-points_use,
            balance=current_user.points - points_use,
            source_type="order_use",
            source_id=order.id,
            description=f"订单抵扣"
        )
        current_user.points -= points_use
        db.add(points_record)

    # 从购物车移除
    if request.from_cart:
        redis_client = _get_redis_client()
        cart_key = f"cart:{current_user.id}"
        select_key = f"cart_select:{current_user.id}"
        for item in request.items:
            item_key = _cart_item_key(item.product_id, item.sku_id)
            legacy_key = str(item.product_id)
            redis_client.hdel(cart_key, item_key)
            redis_client.hdel(cart_key, legacy_key)
            redis_client.srem(select_key, item_key)
            redis_client.srem(select_key, legacy_key)

    db.commit()
    db.refresh(order)

    return success(data={
        "order_id": order.id,
        "order_no": order.order_no,
        "pay_amount": float(pay_amount)
    }, message="订单创建成功")


@router.get("/orders", summary="获取订单列表")
async def get_orders(
    status: Optional[str] = Query(None, description="订单状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户订单列表"""
    query = db.query(Order).filter(Order.user_id == current_user.id)

    if status:
        query = query.filter(Order.status == status)

    query = query.order_by(desc(Order.created_at))

    total = query.count()
    orders = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[o.to_dict() for o in orders],
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/orders/{order_id}", summary="获取订单详情")
async def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取订单详情"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == current_user.id
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    order_dict = order.to_dict()

    # 检查是否已评价
    for item in order_dict.get("items", []):
        reviewed = db.query(ProductReview).filter(
            ProductReview.order_id == order_id,
            ProductReview.product_id == item["product_id"]
        ).first()
        item["is_reviewed"] = reviewed is not None

    return success(data=order_dict)


@router.post("/orders/{order_id}/pay", summary="支付订单")
async def pay_order(
    order_id: int,
    request: PayOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """支付订单"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == current_user.id,
        Order.status == "pending"
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="订单不存在或状态异常")

    if _is_payment_expired(order):
        _rollback_pending_order(order, current_user, db)
        db.commit()
        raise HTTPException(status_code=400, detail="订单支付已超时，请重新下单")

    payment_result = None
    if request.pay_type == "balance":
        required_points = int(Decimal(str(order.pay_amount)) * 100)
        if current_user.points < required_points:
            raise HTTPException(status_code=400, detail="积分余额不足")

        current_user.points -= required_points
        order.pay_method = request.pay_type
        order.status = "paid"
        order.paid_at = datetime.now()
        order.trade_no = f"BAL{int(time.time())}{current_user.id}"
    else:
        # 调用支付服务创建支付
        from app.services.payment_service import payment_service

        client_type = "h5"
        payment_result = await payment_service.create_payment(
            order_no=order.order_no,
            amount=Decimal(str(order.pay_amount)),
            subject=f"PetPal订单-{order.order_no}",
            payment_method=request.pay_type,
            client_type=client_type,
            user_id=current_user.id,
            extra_data={"order_id": order.id}
        )

        if not payment_result.success:
            raise HTTPException(status_code=400, detail=payment_result.error_message or "创建支付失败")

        order.pay_method = request.pay_type

        is_mock_payment = request.pay_type in {"alipay", "wechat"} and _is_local_development()
        if is_mock_payment:
            order.status = "paid"
            order.paid_at = datetime.now()
            order.trade_no = f"MOCK{int(time.time())}{current_user.id}"

    db.commit()

    return success(data={
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status,
        "pay_amount": float(order.pay_amount),
        "pay_type": request.pay_type,
        "pay_data": payment_result.pay_data if payment_result else None,
        "trade_no": order.trade_no or (payment_result.trade_no if payment_result else ""),
        "is_mock_payment": request.pay_type in {"alipay", "wechat"} and _is_local_development()
    }, message="支付成功" if order.status == "paid" else "请完成支付")


@router.post("/orders/{order_id}/cancel", summary="取消订单")
async def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消订单"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == current_user.id,
        Order.status == "pending"
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="订单不存在或无法取消")

    _rollback_pending_order(order, current_user, db)

    db.commit()

    return success(message="订单已取消")


@router.post("/orders/{order_id}/confirm", summary="确认收货")
async def confirm_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """确认收货"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == current_user.id,
        Order.status == "shipped"
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="订单不存在或状态异常")

    order.status = "received"
    order.receive_time = datetime.now()

    db.commit()

    return success(message="确认收货成功")


# ==================== 优惠券 ====================

@router.get("/coupons", summary="获取可领取优惠券")
async def get_available_coupons(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取可领取的优惠券列表"""
    now = datetime.now()

    query = db.query(Coupon).filter(
        Coupon.status == 1,
        or_(Coupon.start_time.is_(None), Coupon.start_time <= now),
        or_(Coupon.end_time.is_(None), Coupon.end_time > now),
        or_(Coupon.total_count == 0, Coupon.used_count < Coupon.total_count)
    )

    total = query.count()
    coupons = query.offset((page - 1) * page_size).limit(page_size).all()

    # 检查用户是否已领取
    received_ids = set()
    if current_user:
        received = db.query(UserCoupon.coupon_id).filter(
            UserCoupon.user_id == current_user.id
        ).all()
        received_ids = {r[0] for r in received}

    result = []
    for coupon in coupons:
        coupon_dict = coupon.to_dict()
        coupon_dict["is_received"] = coupon.id in received_ids
        result.append(coupon_dict)

    return page_response(data=result, page=page, page_size=page_size, total=total)


@router.post("/coupons/receive", summary="领取优惠券")
async def receive_coupon(
    request: ReceiveCouponRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """领取优惠券"""
    coupon = db.query(Coupon).filter(
        Coupon.id == request.coupon_id,
        Coupon.status == 1
    ).first()

    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")

    now = datetime.now()

    if coupon.start_time and coupon.start_time > now:
        raise HTTPException(status_code=400, detail="优惠券未开始")

    if coupon.end_time and coupon.end_time < now:
        raise HTTPException(status_code=400, detail="优惠券已过期")

    if coupon.total_count > 0 and coupon.used_count >= coupon.total_count:
        raise HTTPException(status_code=400, detail="优惠券已领完")

    # 检查领取限制
    user_count = db.query(UserCoupon).filter(
        UserCoupon.user_id == current_user.id,
        UserCoupon.coupon_id == coupon.id
    ).count()

    if user_count >= coupon.per_user_limit:
        raise HTTPException(status_code=400, detail="已达领取上限")

    # 领取
    user_coupon = UserCoupon(
        user_id=current_user.id,
        coupon_id=coupon.id,
        expire_at=coupon.end_time
    )
    db.add(user_coupon)
    coupon.used_count += 1

    db.commit()

    return success(message="领取成功")


@router.get("/coupons/my", summary="我的优惠券")
async def get_my_coupons(
    status: str = Query("unused", description="状态: unused/used/expired"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我的优惠券列表"""
    query = db.query(UserCoupon).filter(
        UserCoupon.user_id == current_user.id,
        UserCoupon.status == status
    )

    query = query.order_by(desc(UserCoupon.created_at))

    total = query.count()
    coupons = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[c.to_dict() for c in coupons],
        page=page,
        page_size=page_size,
        total=total
    )


# ==================== 商品评价 ====================

@router.get("/products/{product_id}/reviews", summary="获取商品评价")
async def get_product_reviews(
    product_id: int,
    rating: Optional[int] = Query(None, ge=1, le=5, description="评分筛选"),
    has_image: Optional[bool] = Query(None, description="是否有图"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取商品评价列表"""
    query = db.query(ProductReview).filter(
        ProductReview.product_id == product_id,
        ProductReview.status == 1
    )

    if rating:
        query = query.filter(ProductReview.rating == rating)

    if has_image:
        query = query.filter(ProductReview.images.isnot(None))

    query = query.order_by(desc(ProductReview.likes_count), desc(ProductReview.created_at))

    total = query.count()
    reviews = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取点赞状态
    review_ids = [r.id for r in reviews]
    liked_ids = set()
    # 这里可以添加点赞表查询

    result = []
    for review in reviews:
        review_dict = review.to_dict()
        review_dict["is_liked"] = review.id in liked_ids
        result.append(review_dict)

    # 评分统计
    stats = db.query(
        ProductReview.rating,
        func.count(ProductReview.id)
    ).filter(
        ProductReview.product_id == product_id,
        ProductReview.status == 1
    ).group_by(ProductReview.rating).all()

    rating_stats = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r, c in stats:
        rating_stats[r] = c

    return success(data={
        "list": result,
        "total": total,
        "page": page,
        "page_size": page_size,
        "rating_stats": rating_stats
    })


@router.post("/reviews", summary="发表评价")
async def create_review(
    request: CreateReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """发表商品评价"""
    # 验证订单
    order = db.query(Order).filter(
        Order.id == request.order_id,
        Order.user_id == current_user.id,
        Order.status.in_(["received", "completed"])
    ).first()

    if not order:
        raise HTTPException(status_code=400, detail="订单不存在或无法评价")

    # 检查是否已评价
    existing = db.query(ProductReview).filter(
        ProductReview.order_id == request.order_id,
        ProductReview.product_id == request.product_id,
        ProductReview.user_id == current_user.id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="已评价过该商品")

    # 验证商品在订单中
    order_item = db.query(OrderItem).filter(
        OrderItem.order_id == request.order_id,
        OrderItem.product_id == request.product_id
    ).first()

    if not order_item:
        raise HTTPException(status_code=400, detail="商品不在订单中")

    # 创建评价
    review = ProductReview(
        user_id=current_user.id,
        product_id=request.product_id,
        order_id=request.order_id,
        order_item_id=request.order_item_id,
        rating=request.rating,
        content=request.content,
        images=json.dumps(request.images) if request.images else None,
        is_anonymous=1 if request.is_anonymous else 0
    )
    db.add(review)

    # 更新商品评分
    product = db.query(Product).filter(Product.id == request.product_id).first()
    if product:
        product.review_count += 1
        # 重新计算平均评分
        avg = db.query(func.avg(ProductReview.rating)).filter(
            ProductReview.product_id == request.product_id,
            ProductReview.status == 1
        ).scalar()
        product.rating = round(float(avg or 5.0), 1)

    # 奖励积分
    points_earned = 10 if request.images else 5
    points_record = PointsRecord(
        user_id=current_user.id,
        points=points_earned,
        balance=current_user.points + points_earned,
        source_type="review",
        description="评价商品奖励"
    )
    current_user.points += points_earned
    db.add(points_record)

    db.commit()
    db.refresh(review)

    return success(data=review.to_dict(), message=f"评价成功，获得{points_earned}积分")


@router.post("/reviews/{review_id}/append", summary="追评")
async def append_review(
    review_id: int,
    request: AppendReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """追加评价"""
    review = db.query(ProductReview).filter(
        ProductReview.id == review_id,
        ProductReview.user_id == current_user.id,
        ProductReview.append_content.is_(None)
    ).first()

    if not review:
        raise HTTPException(status_code=404, detail="评价不存在或已追评")

    review.append_content = request.content
    review.append_images = json.dumps(request.images) if request.images else None
    review.append_at = datetime.now()

    db.commit()

    return success(message="追评成功")


# ==================== 商品收藏 ====================

@router.get("/favorites", summary="获取收藏列表")
async def get_favorites(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取商品收藏列表"""
    query = db.query(Product).join(
        ProductFavorite,
        ProductFavorite.product_id == Product.id
    ).filter(
        ProductFavorite.user_id == current_user.id,
        Product.deleted_at.is_(None)
    ).order_by(desc(ProductFavorite.created_at))

    total = query.count()
    products = query.offset((page - 1) * page_size).limit(page_size).all()

    products_data = []
    for p in products:
        p_dict = p.to_dict()
        p_dict["is_favorited"] = True
        products_data.append(p_dict)

    return page_response(data=products_data, page=page, page_size=page_size, total=total)


@router.post("/favorites/{product_id}", summary="收藏商品")
async def add_favorite(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """收藏商品"""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.deleted_at.is_(None)
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    existing = db.query(ProductFavorite).filter(
        ProductFavorite.user_id == current_user.id,
        ProductFavorite.product_id == product_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="已收藏")

    favorite = ProductFavorite(
        user_id=current_user.id,
        product_id=product_id
    )
    db.add(favorite)
    product.favorites_count += 1

    db.commit()

    return success(message="收藏成功")


@router.delete("/favorites/{product_id}", summary="取消收藏")
async def remove_favorite(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消收藏商品"""
    favorite = db.query(ProductFavorite).filter(
        ProductFavorite.user_id == current_user.id,
        ProductFavorite.product_id == product_id
    ).first()

    if not favorite:
        raise HTTPException(status_code=400, detail="未收藏")

    db.delete(favorite)

    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        product.favorites_count = max(0, product.favorites_count - 1)

    db.commit()

    return success(message="取消收藏成功")


# ==================== 退款申请 ====================

@router.post("/refunds", summary="申请退款")
async def create_refund(
    request: CreateRefundRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """申请退款"""
    order = db.query(Order).filter(
        Order.id == request.order_id,
        Order.user_id == current_user.id,
        Order.status.in_(["paid", "shipped", "received"])
    ).first()

    if not order:
        raise HTTPException(status_code=400, detail="订单不存在或无法退款")

    # 检查是否已有退款申请
    existing = db.query(RefundRequest).filter(
        RefundRequest.order_id == request.order_id,
        RefundRequest.status.notin_(["rejected", "cancelled", "completed"])
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="已有退款申请进行中")

    if request.refund_amount > order.pay_amount:
        raise HTTPException(status_code=400, detail="退款金额不能超过实付金额")

    # 生成退款单号
    refund_no = f"REF{int(time.time() * 1000)}{current_user.id}"

    refund = RefundRequest(
        refund_no=refund_no,
        order_id=request.order_id,
        user_id=current_user.id,
        refund_type=request.refund_type,
        reason=request.reason,
        description=request.description,
        images=json.dumps(request.images) if request.images else None,
        refund_amount=request.refund_amount
    )
    db.add(refund)

    # 更新订单状态
    order.status = "refunding"

    db.commit()
    db.refresh(refund)

    return success(data=refund.to_dict(), message="退款申请已提交")


@router.get("/refunds", summary="获取退款列表")
async def get_refunds(
    status: Optional[str] = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取退款申请列表"""
    query = db.query(RefundRequest).filter(
        RefundRequest.user_id == current_user.id
    )

    if status:
        query = query.filter(RefundRequest.status == status)

    query = query.order_by(desc(RefundRequest.created_at))

    total = query.count()
    refunds = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[r.to_dict() for r in refunds],
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/refunds/{refund_id}", summary="获取退款详情")
async def get_refund(
    refund_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取退款申请详情"""
    refund = db.query(RefundRequest).filter(
        RefundRequest.id == refund_id,
        RefundRequest.user_id == current_user.id
    ).first()

    if not refund:
        raise HTTPException(status_code=404, detail="退款申请不存在")

    return success(data=refund.to_dict())


@router.post("/refunds/{refund_id}/ship", summary="填写退货物流")
async def ship_refund(
    refund_id: int,
    request: RefundShipRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """填写退货物流信息"""
    refund = db.query(RefundRequest).filter(
        RefundRequest.id == refund_id,
        RefundRequest.user_id == current_user.id,
        RefundRequest.status == "approved",
        RefundRequest.refund_type == "return"
    ).first()

    if not refund:
        raise HTTPException(status_code=404, detail="退款申请不存在或状态异常")

    refund.return_ship_company = request.ship_company
    refund.return_ship_no = request.ship_no
    refund.return_ship_time = datetime.now()
    refund.status = "shipping"

    db.commit()

    return success(message="物流信息已提交")


@router.post("/refunds/{refund_id}/cancel", summary="取消退款申请")
async def cancel_refund(
    refund_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消退款申请"""
    refund = db.query(RefundRequest).filter(
        RefundRequest.id == refund_id,
        RefundRequest.user_id == current_user.id,
        RefundRequest.status.in_(["pending", "approved"])
    ).first()

    if not refund:
        raise HTTPException(status_code=404, detail="退款申请不存在或无法取消")

    refund.status = "cancelled"

    # 恢复订单状态
    order = db.query(Order).filter(Order.id == refund.order_id).first()
    if order:
        # 根据之前的状态恢复
        if order.ship_no:
            order.status = "shipped" if not order.receive_time else "received"
        else:
            order.status = "paid"

    db.commit()

    return success(message="退款申请已取消")

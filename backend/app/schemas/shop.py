"""
PetPal - 商城相关Schema

包含：
- 商品管理
- 购物车
- 订单管理
- 优惠券
- 商品评价
- 退款申请
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# ==================== 商品相关 ====================

class ProductQuery(BaseModel):
    """商品查询参数"""
    category_id: Optional[int] = None
    category: Optional[str] = None
    pet_type: Optional[str] = None
    brand: Optional[str] = None
    keyword: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    sort: str = Field("recommend", pattern="^(recommend|sales|price_asc|price_desc|rating|new)$")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class ProductResponse(BaseModel):
    """商品响应"""
    id: int
    name: str
    subtitle: Optional[str] = None
    cover_image: Optional[str] = None
    images: Optional[List[str]] = None
    category: Optional[str] = None
    category_name: Optional[str] = None
    brand: Optional[str] = None
    original_price: float
    price: float
    points_price: int = 0
    stock: int = 0
    sales_count: int = 0
    rating: float = 5.0
    review_count: int = 0
    is_recommended: bool = False
    is_hot: bool = False
    is_new: bool = False
    is_favorited: bool = False


# ==================== 购物车相关 ====================

class CartItemAdd(BaseModel):
    """添加购物车请求"""
    product_id: int = Field(..., gt=0)
    quantity: int = Field(1, ge=1, le=99)
    sku_id: Optional[int] = None
    sku_info: Optional[str] = None


class CartItemUpdate(BaseModel):
    """更新购物车商品数量"""
    quantity: int = Field(..., ge=1, le=99)
    cart_key: Optional[str] = None


class CartItemSelect(BaseModel):
    """选中/取消选中购物车商品"""
    selected: bool = True
    cart_keys: List[str] = Field(default_factory=list)


class CartItem(BaseModel):
    """购物车商品"""
    cart_key: str
    product_id: int
    product_name: str
    product_image: Optional[str] = None
    sku_id: Optional[int] = None
    sku_info: Optional[str] = None
    price: float
    quantity: int
    amount: float
    stock: int
    selected: bool = True
    is_valid: bool = True


class CartResponse(BaseModel):
    """购物车响应"""
    items: List[CartItem] = []
    total_count: int = 0
    selected_count: int = 0
    total_amount: float = 0
    selected_amount: float = 0


# ==================== 订单相关 ====================

class OrderItemCreate(BaseModel):
    """创建订单商品"""
    product_id: int = Field(..., gt=0)
    quantity: int = Field(..., ge=1)
    sku_id: Optional[int] = None
    sku_info: Optional[str] = None


class CreateOrderRequest(BaseModel):
    """创建订单请求"""
    items: List[OrderItemCreate] = Field(..., min_length=1)
    address_id: int = Field(..., gt=0)
    coupon_id: Optional[int] = None
    points_use: int = Field(0, ge=0)
    remark: Optional[str] = Field(None, max_length=500)
    from_cart: bool = False


class OrderPreviewRequest(BaseModel):
    """订单预览请求"""
    items: List[OrderItemCreate] = Field(..., min_length=1)
    address_id: Optional[int] = None
    coupon_id: Optional[int] = None
    points_use: int = Field(0, ge=0)


class OrderPreviewResponse(BaseModel):
    """订单预览响应"""
    items: List[dict] = []
    total_amount: float = 0
    discount_amount: float = 0
    points_amount: float = 0
    freight_amount: float = 0
    pay_amount: float = 0
    available_coupons: List[dict] = []
    max_points_use: int = 0


class PayOrderRequest(BaseModel):
    """支付订单请求"""
    pay_type: str = Field("wechat", pattern="^(wechat|alipay|balance)$")


class ShipOrderRequest(BaseModel):
    """发货请求（商家）"""
    ship_company: str = Field(..., min_length=1, max_length=50)
    ship_no: str = Field(..., min_length=1, max_length=50)


class OrderItemResponse(BaseModel):
    """订单商品响应"""
    id: int
    product_id: Optional[int] = None
    sku_id: Optional[int] = None
    product_name: str
    product_image: Optional[str] = None
    sku_info: Optional[str] = None
    price: float
    quantity: int
    total_amount: float
    is_reviewed: bool = False


class OrderResponse(BaseModel):
    """订单响应"""
    id: int
    order_no: str
    total_amount: float
    discount_amount: float = 0
    points_amount: float = 0
    freight_amount: float = 0
    pay_amount: float
    status: str
    receiver_name: Optional[str] = None
    receiver_phone: Optional[str] = None
    receiver_address: Optional[str] = None
    ship_company: Optional[str] = None
    ship_no: Optional[str] = None
    remark: Optional[str] = None
    pay_time: Optional[datetime] = None
    ship_time: Optional[datetime] = None
    receive_time: Optional[datetime] = None
    items: List[OrderItemResponse] = []
    created_at: Optional[datetime] = None


# ==================== 优惠券相关 ====================

class CouponResponse(BaseModel):
    """优惠券响应"""
    id: int
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    coupon_type: str
    discount_amount: float = 0
    discount_percent: float = 0
    min_amount: float = 0
    max_discount: float = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: int = 1


class UserCouponResponse(BaseModel):
    """用户优惠券响应"""
    id: int
    coupon: CouponResponse
    status: str
    used_at: Optional[datetime] = None
    expire_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ReceiveCouponRequest(BaseModel):
    """领取优惠券请求"""
    coupon_id: int = Field(..., gt=0)


class UseCouponRequest(BaseModel):
    """使用优惠券请求（通过码）"""
    code: str = Field(..., min_length=1, max_length=50)


# ==================== 商品评价相关 ====================

class CreateReviewRequest(BaseModel):
    """创建评价请求"""
    order_id: int = Field(..., gt=0)
    product_id: int = Field(..., gt=0)
    order_item_id: Optional[int] = None
    rating: int = Field(5, ge=1, le=5)
    content: Optional[str] = Field(None, max_length=1000)
    images: Optional[List[str]] = Field(None, max_length=9)
    is_anonymous: bool = False

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        if v:
            v = v.strip()
        return v


class AppendReviewRequest(BaseModel):
    """追评请求"""
    content: str = Field(..., min_length=1, max_length=500)
    images: Optional[List[str]] = Field(None, max_length=3)


class ReplyReviewRequest(BaseModel):
    """商家回复评价请求"""
    content: str = Field(..., min_length=1, max_length=500)


class ReviewResponse(BaseModel):
    """评价响应"""
    id: int
    rating: int
    content: Optional[str] = None
    images: List[str] = []
    append_content: Optional[str] = None
    append_images: List[str] = []
    append_at: Optional[datetime] = None
    reply_content: Optional[str] = None
    reply_at: Optional[datetime] = None
    likes_count: int = 0
    is_anonymous: bool = False
    is_liked: bool = False
    user: Optional[dict] = None
    created_at: Optional[datetime] = None


# ==================== 商品收藏相关 ====================

class FavoriteProductRequest(BaseModel):
    """收藏商品请求"""
    product_id: int = Field(..., gt=0)


# ==================== 退款相关 ====================

class CreateRefundRequest(BaseModel):
    """创建退款申请"""
    order_id: int = Field(..., gt=0)
    refund_type: str = Field("refund", pattern="^(refund|return)$")
    reason: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    images: Optional[List[str]] = Field(None, max_length=9)
    refund_amount: float = Field(..., gt=0)


class RefundShipRequest(BaseModel):
    """退货物流信息"""
    ship_company: str = Field(..., min_length=1, max_length=50)
    ship_no: str = Field(..., min_length=1, max_length=50)


class HandleRefundRequest(BaseModel):
    """处理退款请求（商家）"""
    action: str = Field(..., pattern="^(approve|reject|receive|complete)$")
    reject_reason: Optional[str] = Field(None, max_length=500)
    actual_refund: Optional[float] = None


class RefundResponse(BaseModel):
    """退款响应"""
    id: int
    refund_no: str
    order_id: int
    refund_type: str
    reason: str
    description: Optional[str] = None
    images: List[str] = []
    refund_amount: float
    actual_refund: float = 0
    return_ship_company: Optional[str] = None
    return_ship_no: Optional[str] = None
    status: str
    reject_reason: Optional[str] = None
    created_at: Optional[datetime] = None


# ==================== 分类相关 ====================

class CategoryResponse(BaseModel):
    """分类响应"""
    id: int
    parent_id: Optional[int] = None
    name: str
    icon: Optional[str] = None
    image: Optional[str] = None
    children: List['CategoryResponse'] = []

"""
PetPal - 商城模型 (商品、订单、优惠券、评价)
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, ForeignKey, Float, func, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class ProductCategory(Base):
    """商品分类表"""
    __tablename__ = "product_categories"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    parent_id = Column(BigInteger, nullable=True, comment="父分类ID")
    name = Column(String(100), nullable=False, comment="分类名称")
    icon = Column(String(200), nullable=True, comment="分类图标")
    image = Column(String(500), nullable=True, comment="分类图片")
    sort_order = Column(Integer, default=0, comment="排序")
    is_show = Column(Integer, default=1, comment="是否显示")

    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "name": self.name,
            "icon": self.icon,
            "image": self.image
        }


class Product(Base):
    """商品表"""
    __tablename__ = "products"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="商品ID")
    merchant_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="商家ID")

    # 基本信息
    name = Column(String(200), nullable=False, comment="商品名称")
    subtitle = Column(String(500), nullable=True, comment="副标题")
    description = Column(Text, nullable=True, comment="商品描述")
    images = Column(Text, nullable=True, comment="商品图片列表(JSON)")
    video_url = Column(String(500), nullable=True, comment="商品视频")

    # 分类
    category = Column(String(100), nullable=True, index=True, comment="分类")
    category_name = Column(String(100), nullable=True, comment="分类名称")
    cover_image = Column(String(500), nullable=True, comment="封面图片")
    pet_type = Column(String(50), nullable=True, comment="适用宠物类型")
    brand = Column(String(100), nullable=True, comment="品牌")

    # 价格
    original_price = Column(Float, nullable=False, comment="原价")
    price = Column(Float, nullable=False, comment="售价")
    points_price = Column(Integer, default=0, comment="积分价格(可用积分抵扣)")

    # 库存
    stock = Column(Integer, default=0, comment="库存")
    sales_count = Column(Integer, default=0, comment="销量")

    # SKU
    specs = Column(Text, nullable=True, comment="规格选项(JSON)")
    skus = Column(Text, nullable=True, comment="SKU列表(JSON)")

    # 统计
    views_count = Column(Integer, default=0, comment="浏览数")
    favorites_count = Column(Integer, default=0, comment="收藏数")
    rating = Column(Float, default=5.0, comment="评分")
    review_count = Column(Integer, default=0, comment="评价数")

    # 状态
    status = Column(Integer, default=1, comment="状态: 0下架 1上架 2售罄")
    is_recommended = Column(Integer, default=0, comment="是否推荐")
    is_hot = Column(Integer, default=0, comment="是否热销")
    is_new = Column(Integer, default=0, comment="是否新品")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    deleted_at = Column(DateTime, nullable=True, comment="删除时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "subtitle": self.subtitle,
            "images": self.images,
            "cover_image": self.cover_image,
            "category": self.category,
            "category_name": self.category_name,
            "brand": self.brand,
            "original_price": self.original_price,
            "price": self.price,
            "points_price": self.points_price,
            "stock": self.stock,
            "sales_count": self.sales_count,
            "rating": self.rating,
            "review_count": self.review_count,
            "is_recommended": self.is_recommended,
            "is_hot": self.is_hot,
            "is_new": self.is_new
        }


class Order(Base):
    """订单表"""
    __tablename__ = "orders"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="订单ID")
    order_no = Column(String(50), unique=True, nullable=False, index=True, comment="订单号")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")

    # 金额
    total_amount = Column(Float, nullable=False, comment="商品总额")
    discount_amount = Column(Float, default=0, comment="优惠金额")
    points_amount = Column(Float, default=0, comment="积分抵扣金额")
    freight_amount = Column(Float, default=0, comment="运费")
    pay_amount = Column(Float, nullable=False, comment="实付金额")

    # 积分
    points_used = Column(Integer, default=0, comment="使用积分")
    points_earned = Column(Integer, default=0, comment="获得积分")

    # 收货信息
    receiver_name = Column(String(50), nullable=True, comment="收货人")
    receiver_phone = Column(String(20), nullable=True, comment="收货电话")
    receiver_address = Column(String(500), nullable=True, comment="收货地址")

    # 支付信息
    pay_type = Column(String(20), nullable=True, comment="支付方式: wechat微信 alipay支付宝")
    pay_time = Column(DateTime, nullable=True, comment="支付时间")
    pay_trade_no = Column(String(100), nullable=True, comment="支付流水号")

    # 物流信息
    ship_company = Column(String(50), nullable=True, comment="快递公司")
    ship_no = Column(String(50), nullable=True, comment="快递单号")
    ship_time = Column(DateTime, nullable=True, comment="发货时间")
    receive_time = Column(DateTime, nullable=True, comment="收货时间")

    # 状态
    status = Column(String(20), default="pending", comment="状态: pending待支付 paid已支付 shipped已发货 received已收货 completed已完成 cancelled已取消 refunding退款中 refunded已退款")

    remark = Column(String(500), nullable=True, comment="备注")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    items = relationship("OrderItem", back_populates="order", lazy="joined")

    @property
    def pay_method(self):
        return self.pay_type

    @pay_method.setter
    def pay_method(self, value):
        self.pay_type = value

    @property
    def trade_no(self):
        return self.pay_trade_no

    @trade_no.setter
    def trade_no(self, value):
        self.pay_trade_no = value

    @property
    def paid_at(self):
        return self.pay_time

    @paid_at.setter
    def paid_at(self, value):
        self.pay_time = value

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "order_no": self.order_no,
            "total_amount": self.total_amount,
            "discount_amount": self.discount_amount,
            "points_amount": self.points_amount,
            "freight_amount": self.freight_amount,
            "pay_amount": self.pay_amount,
            "status": self.status,
            "receiver_name": self.receiver_name,
            "receiver_phone": self.receiver_phone,
            "receiver_address": self.receiver_address,
            "ship_company": self.ship_company,
            "ship_no": self.ship_no,
            "pay_type": self.pay_type,
            "pay_time": self.pay_time.isoformat() if self.pay_time else None,
            "pay_trade_no": self.pay_trade_no,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [item.to_dict() for item in self.items] if self.items else []
        }


class OrderItem(Base):
    """订单项表"""
    __tablename__ = "order_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="订单项ID")
    order_id = Column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True, comment="订单ID")
    product_id = Column(BigInteger, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, comment="商品ID")
    sku_id = Column(BigInteger, nullable=True, comment="SKU ID")

    product_name = Column(String(200), nullable=False, comment="商品名称")
    product_image = Column(String(500), nullable=True, comment="商品图片")
    sku_info = Column(String(500), nullable=True, comment="SKU信息")
    price = Column(Float, nullable=False, comment="单价")
    quantity = Column(Integer, nullable=False, comment="数量")
    total_amount = Column(Float, nullable=False, comment="小计")

    # 关系
    order = relationship("Order", back_populates="items")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "product_image": self.product_image,
            "sku_id": self.sku_id,
            "sku_info": self.sku_info,
            "price": self.price,
            "quantity": self.quantity,
            "total_amount": self.total_amount
        }


class Coupon(Base):
    """优惠券表"""
    __tablename__ = "coupons"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="优惠券ID")
    name = Column(String(100), nullable=False, comment="优惠券名称")
    code = Column(String(50), unique=True, nullable=True, index=True, comment="优惠码")
    description = Column(String(500), nullable=True, comment="描述")

    # 优惠类型
    coupon_type = Column(String(20), default="amount", comment="类型: amount满减 percent折扣 shipping免运费")
    discount_amount = Column(Float, default=0, comment="优惠金额")
    discount_percent = Column(Float, default=0, comment="折扣比例(0-100)")
    min_amount = Column(Float, default=0, comment="最低消费金额")
    max_discount = Column(Float, default=0, comment="最大优惠金额(折扣券)")

    # 使用限制
    category_ids = Column(Text, nullable=True, comment="适用分类ID(JSON)")
    product_ids = Column(Text, nullable=True, comment="适用商品ID(JSON)")
    exclude_product_ids = Column(Text, nullable=True, comment="排除商品ID(JSON)")

    # 数量和时间
    total_count = Column(Integer, default=0, comment="发放总量(0无限)")
    used_count = Column(Integer, default=0, comment="已使用数量")
    per_user_limit = Column(Integer, default=1, comment="每人限领")
    start_time = Column(DateTime, nullable=True, comment="生效时间")
    end_time = Column(DateTime, nullable=True, comment="失效时间")

    status = Column(Integer, default=1, comment="状态: 0禁用 1启用")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "coupon_type": self.coupon_type,
            "discount_amount": self.discount_amount,
            "discount_percent": self.discount_percent,
            "min_amount": self.min_amount,
            "max_discount": self.max_discount,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status
        }


class UserCoupon(Base):
    """用户优惠券表"""
    __tablename__ = "user_coupons"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    coupon_id = Column(BigInteger, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True, comment="优惠券ID")
    order_id = Column(BigInteger, nullable=True, comment="使用的订单ID")

    status = Column(String(20), default="unused", comment="状态: unused未使用 used已使用 expired已过期")
    used_at = Column(DateTime, nullable=True, comment="使用时间")
    expire_at = Column(DateTime, nullable=True, comment="过期时间")

    created_at = Column(DateTime, server_default=func.now(), comment="领取时间")

    # 关系
    coupon = relationship("Coupon")

    __table_args__ = (
        UniqueConstraint('user_id', 'coupon_id', name='uk_user_coupon'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "coupon": self.coupon.to_dict() if self.coupon else None,
            "status": self.status,
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "expire_at": self.expire_at.isoformat() if self.expire_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ProductReview(Base):
    """商品评价表"""
    __tablename__ = "product_reviews"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="评价ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    product_id = Column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True, comment="商品ID")
    order_id = Column(BigInteger, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, comment="订单ID")
    order_item_id = Column(BigInteger, nullable=True, comment="订单项ID")

    # 评分
    rating = Column(Integer, default=5, comment="评分1-5")
    content = Column(Text, nullable=True, comment="评价内容")
    images = Column(Text, nullable=True, comment="评价图片(JSON)")

    # 追评
    append_content = Column(Text, nullable=True, comment="追评内容")
    append_images = Column(Text, nullable=True, comment="追评图片(JSON)")
    append_at = Column(DateTime, nullable=True, comment="追评时间")

    # 商家回复
    reply_content = Column(Text, nullable=True, comment="商家回复")
    reply_at = Column(DateTime, nullable=True, comment="回复时间")

    # 统计
    likes_count = Column(Integer, default=0, comment="点赞数")
    is_anonymous = Column(Integer, default=0, comment="是否匿名")

    status = Column(Integer, default=1, comment="状态: 0隐藏 1显示")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    user = relationship("User")
    product = relationship("Product")

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "rating": self.rating,
            "content": self.content,
            "images": json.loads(self.images) if self.images else [],
            "append_content": self.append_content,
            "append_images": json.loads(self.append_images) if self.append_images else [],
            "append_at": self.append_at.isoformat() if self.append_at else None,
            "reply_content": self.reply_content,
            "reply_at": self.reply_at.isoformat() if self.reply_at else None,
            "likes_count": self.likes_count,
            "is_anonymous": bool(self.is_anonymous),
            "user": {
                "id": self.user.id if not self.is_anonymous else 0,
                "nickname": self.user.nickname if not self.is_anonymous else "匿名用户",
                "avatar_url": self.user.avatar_url if not self.is_anonymous else None
            } if self.user else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ProductFavorite(Base):
    """商品收藏表"""
    __tablename__ = "product_favorites"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    product_id = Column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True, comment="商品ID")

    created_at = Column(DateTime, server_default=func.now(), comment="收藏时间")

    # 关系
    product = relationship("Product")

    __table_args__ = (
        UniqueConstraint('user_id', 'product_id', name='uk_user_product_fav'),
    )


class RefundRequest(Base):
    """退款申请表"""
    __tablename__ = "refund_requests"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="退款ID")
    refund_no = Column(String(50), unique=True, nullable=False, index=True, comment="退款单号")
    order_id = Column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True, comment="订单ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")

    # 退款类型
    refund_type = Column(String(20), default="refund", comment="类型: refund仅退款 return退货退款")
    reason = Column(String(200), nullable=False, comment="退款原因")
    description = Column(Text, nullable=True, comment="详细描述")
    images = Column(Text, nullable=True, comment="凭证图片(JSON)")

    # 金额
    refund_amount = Column(Float, nullable=False, comment="退款金额")
    actual_refund = Column(Float, default=0, comment="实际退款金额")

    # 退货物流
    return_ship_company = Column(String(50), nullable=True, comment="退货快递公司")
    return_ship_no = Column(String(50), nullable=True, comment="退货快递单号")
    return_ship_time = Column(DateTime, nullable=True, comment="退货时间")

    # 处理
    status = Column(String(20), default="pending", comment="状态: pending待处理 approved已同意 rejected已拒绝 shipping退货中 received已收货 completed已完成 cancelled已取消")
    reject_reason = Column(String(500), nullable=True, comment="拒绝原因")
    handled_at = Column(DateTime, nullable=True, comment="处理时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    order = relationship("Order")

    @property
    def trade_no(self):
        return None

    @trade_no.setter
    def trade_no(self, value):
        pass

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "refund_no": self.refund_no,
            "order_id": self.order_id,
            "refund_type": self.refund_type,
            "reason": self.reason,
            "description": self.description,
            "images": json.loads(self.images) if self.images else [],
            "refund_amount": self.refund_amount,
            "actual_refund": self.actual_refund,
            "return_ship_company": self.return_ship_company,
            "return_ship_no": self.return_ship_no,
            "status": self.status,
            "reject_reason": self.reject_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

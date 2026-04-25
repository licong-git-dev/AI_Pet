"""
PetPal - 积分模型 (积分记录、积分商品)
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, ForeignKey, Float, func
from sqlalchemy.orm import relationship
from app.database import Base


class PointsRecord(Base):
    """积分记录表"""
    __tablename__ = "points_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记录ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")

    points = Column(Integer, nullable=False, comment="积分变动(正数为获得,负数为消耗)")
    balance = Column(Integer, nullable=False, comment="变动后余额")

    source_type = Column(String(50), nullable=False, comment="来源类型: sign_in签到 post发帖 like点赞 comment评论 share分享 invite邀请 purchase购物 exchange兑换 expire过期 admin管理员操作")
    source_id = Column(BigInteger, nullable=True, comment="来源ID")
    description = Column(String(500), nullable=True, comment="描述")

    # 过期信息
    expire_at = Column(DateTime, nullable=True, comment="过期时间")
    is_expired = Column(Integer, default=0, comment="是否已过期: 0否 1是")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "points": self.points,
            "balance": self.balance,
            "source_type": self.source_type,
            "description": self.description,
            "expire_at": self.expire_at.isoformat() if self.expire_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class PointsProduct(Base):
    """积分商品表"""
    __tablename__ = "points_products"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="商品ID")

    name = Column(String(200), nullable=False, comment="商品名称")
    description = Column(Text, nullable=True, comment="商品描述")
    image = Column(String(500), nullable=True, comment="商品图片")
    category = Column(String(50), nullable=True, comment="商品分类: coupon优惠券 physical实物 virtual虚拟")

    # 积分价格
    points_price = Column(Integer, nullable=False, comment="所需积分")
    original_value = Column(Float, nullable=True, comment="原价值(元)")

    # 类型
    product_type = Column(String(50), nullable=False, comment="商品类型: physical实物 coupon优惠券 virtual虚拟商品")
    coupon_value = Column(Float, nullable=True, comment="优惠券面额")
    coupon_min_amount = Column(Float, nullable=True, comment="优惠券最低消费")

    # 库存与限制
    stock = Column(Integer, default=0, comment="库存")
    exchange_count = Column(Integer, default=0, comment="兑换数量")
    limit_per_user = Column(Integer, default=0, comment="每人限兑(0为不限)")
    exchange_limit = Column(Integer, default=0, comment="兑换次数上限(0为不限)")
    member_level_required = Column(Integer, default=0, comment="所需会员等级")

    # 状态
    status = Column(Integer, default=1, comment="状态: 0下架 1上架")
    is_hot = Column(Integer, default=0, comment="是否热门")

    start_time = Column(DateTime, nullable=True, comment="开始时间")
    end_time = Column(DateTime, nullable=True, comment="结束时间")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "image": self.image,
            "category": self.category,
            "points_price": self.points_price,
            "original_value": self.original_value,
            "product_type": self.product_type,
            "stock": self.stock,
            "exchange_count": self.exchange_count,
            "limit_per_user": self.limit_per_user,
            "exchange_limit": self.exchange_limit,
            "member_level_required": self.member_level_required,
            "is_hot": self.is_hot
        }


class PointsExchange(Base):
    """积分兑换记录表"""
    __tablename__ = "points_exchanges"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="兑换ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    product_id = Column(BigInteger, ForeignKey("points_products.id", ondelete="SET NULL"), nullable=True, comment="商品ID")
    address_id = Column(BigInteger, ForeignKey("user_addresses.id", ondelete="SET NULL"), nullable=True, comment="收货地址ID")

    product_name = Column(String(200), nullable=False, comment="商品名称")
    points_cost = Column(Integer, nullable=False, comment="消耗积分")
    quantity = Column(Integer, default=1, comment="兑换数量")

    # 收货信息(实物)
    receiver_name = Column(String(50), nullable=True, comment="收货人")
    receiver_phone = Column(String(20), nullable=True, comment="收货电话")
    receiver_address = Column(String(500), nullable=True, comment="收货地址")

    # 优惠券信息
    coupon_code = Column(String(50), nullable=True, comment="优惠券码")
    coupon_expire_at = Column(DateTime, nullable=True, comment="优惠券过期时间")

    # 状态
    status = Column(String(20), default="pending", comment="状态: pending待处理 shipped已发货 completed已完成 cancelled已取消")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "product_id": self.product_id,
            "address_id": self.address_id,
            "product_name": self.product_name,
            "points_cost": self.points_cost,
            "quantity": self.quantity,
            "receiver_name": self.receiver_name,
            "receiver_phone": self.receiver_phone,
            "receiver_address": self.receiver_address,
            "coupon_code": self.coupon_code,
            "coupon_expire_at": self.coupon_expire_at.isoformat() if self.coupon_expire_at else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class PointsRechargeOrder(Base):
    """积分充值订单表"""
    __tablename__ = "points_recharge_orders"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="充值订单ID")
    order_no = Column(String(50), unique=True, nullable=False, index=True, comment="充值订单号")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")

    package_code = Column(String(50), nullable=False, comment="套餐编码")
    package_name = Column(String(100), nullable=False, comment="套餐名称")
    points = Column(Integer, nullable=False, comment="充值积分")
    bonus_points = Column(Integer, default=0, comment="赠送积分")
    amount = Column(Float, nullable=False, comment="支付金额")

    pay_type = Column(String(20), nullable=True, comment="支付方式: wechat微信 alipay支付宝 balance余额")
    pay_time = Column(DateTime, nullable=True, comment="支付时间")
    pay_trade_no = Column(String(100), nullable=True, comment="支付流水号")

    status = Column(String(20), default="pending", comment="状态: pending待支付 paid已支付 cancelled已取消")
    credited_at = Column(DateTime, nullable=True, comment="积分到账时间")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    user = relationship("User")

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

    @property
    def pay_amount(self):
        return self.amount

    def to_dict(self):
        total_points = self.points + self.bonus_points
        return {
            "id": self.id,
            "order_no": self.order_no,
            "package_code": self.package_code,
            "package_name": self.package_name,
            "points": self.points,
            "bonus_points": self.bonus_points,
            "total_points": total_points,
            "amount": self.amount,
            "status": self.status,
            "pay_type": self.pay_type,
            "pay_time": self.pay_time.isoformat() if self.pay_time else None,
            "pay_trade_no": self.pay_trade_no,
            "credited_at": self.credited_at.isoformat() if self.credited_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

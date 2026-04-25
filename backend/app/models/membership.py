"""
PetPal - 会员订单模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Float, ForeignKey, func
from sqlalchemy.orm import relationship

from app.database import Base


class MembershipOrder(Base):
    """会员购买订单表"""
    __tablename__ = "membership_orders"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="会员订单ID")
    order_no = Column(String(50), unique=True, nullable=False, index=True, comment="会员订单号")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")

    plan_code = Column(String(50), nullable=False, comment="会员套餐编码")
    plan_name = Column(String(100), nullable=False, comment="会员套餐名称")
    member_level = Column(Integer, nullable=False, comment="会员等级")
    duration_days = Column(Integer, nullable=False, comment="会员时长(天)")
    amount = Column(Float, nullable=False, comment="支付金额")

    pay_type = Column(String(20), nullable=True, comment="支付方式: wechat微信 alipay支付宝 balance余额")
    pay_time = Column(DateTime, nullable=True, comment="支付时间")
    pay_trade_no = Column(String(100), nullable=True, comment="支付流水号")

    status = Column(String(20), default="pending", comment="状态: pending待支付 paid已支付 cancelled已取消")
    fulfilled_at = Column(DateTime, nullable=True, comment="会员生效时间")

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
        return {
            "id": self.id,
            "order_no": self.order_no,
            "plan_code": self.plan_code,
            "plan_name": self.plan_name,
            "member_level": self.member_level,
            "duration_days": self.duration_days,
            "amount": self.amount,
            "status": self.status,
            "pay_type": self.pay_type,
            "pay_time": self.pay_time.isoformat() if self.pay_time else None,
            "pay_trade_no": self.pay_trade_no,
            "fulfilled_at": self.fulfilled_at.isoformat() if self.fulfilled_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

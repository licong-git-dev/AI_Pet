"""
PetPal - 支付服务模块

支持多种支付方式：
- 支付宝（App支付、网页支付）
- 微信支付（App支付、JSAPI支付、H5支付）
- 余额支付

功能包括：
- 统一下单
- 支付回调处理
- 退款
- 订单查询
"""
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass

import httpx
from loguru import logger

from app.config import settings


class PaymentMethod(str, Enum):
    """支付方式"""
    ALIPAY = "alipay"
    WECHAT = "wechat"
    BALANCE = "balance"


class PaymentStatus(str, Enum):
    """支付状态"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDING = "refunding"
    REFUNDED = "refunded"


@dataclass
class PaymentResult:
    """支付结果"""
    success: bool
    payment_method: str
    trade_no: str
    out_trade_no: str
    pay_data: Optional[Dict] = None
    error_message: Optional[str] = None


@dataclass
class RefundResult:
    """退款结果"""
    success: bool
    refund_no: str
    out_refund_no: str
    refund_amount: Decimal
    error_message: Optional[str] = None


class PaymentService:
    """统一支付服务"""

    def __init__(self):
        self.alipay = AlipayService()
        self.wechat = WechatPayService()

    async def create_payment(
        self,
        order_no: str,
        amount: Decimal,
        subject: str,
        payment_method: str,
        client_type: str = "app",
        user_id: int = None,
        extra_data: Dict = None
    ) -> PaymentResult:
        """
        创建支付订单

        Args:
            order_no: 订单号
            amount: 支付金额
            subject: 商品标题
            payment_method: 支付方式
            client_type: 客户端类型 (app/h5/web/mini)
            user_id: 用户ID（余额支付需要）
            extra_data: 额外参数

        Returns:
            PaymentResult
        """
        try:
            if payment_method == PaymentMethod.ALIPAY:
                return await self.alipay.create_order(
                    order_no=order_no,
                    amount=amount,
                    subject=subject,
                    client_type=client_type,
                    extra_data=extra_data
                )
            elif payment_method == PaymentMethod.WECHAT:
                return await self.wechat.create_order(
                    order_no=order_no,
                    amount=amount,
                    subject=subject,
                    client_type=client_type,
                    extra_data=extra_data
                )
            elif payment_method == PaymentMethod.BALANCE:
                return await self._pay_with_balance(
                    order_no=order_no,
                    amount=amount,
                    user_id=user_id
                )
            else:
                return PaymentResult(
                    success=False,
                    payment_method=payment_method,
                    trade_no="",
                    out_trade_no=order_no,
                    error_message=f"不支持的支付方式: {payment_method}"
                )
        except Exception as e:
            logger.error(f"创建支付失败: {str(e)}")
            return PaymentResult(
                success=False,
                payment_method=payment_method,
                trade_no="",
                out_trade_no=order_no,
                error_message=str(e)
            )

    async def _pay_with_balance(
        self,
        order_no: str,
        amount: Decimal,
        user_id: int
    ) -> PaymentResult:
        """余额支付"""
        from app.database import SessionLocal
        from app.models.user import User
        from app.models.shop import Order

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return PaymentResult(
                    success=False,
                    payment_method="balance",
                    trade_no="",
                    out_trade_no=order_no,
                    error_message="用户不存在"
                )

            # 检查余额（假设用积分兑换余额，1积分=0.01元）
            required_points = int(amount * 100)
            if user.points < required_points:
                return PaymentResult(
                    success=False,
                    payment_method="balance",
                    trade_no="",
                    out_trade_no=order_no,
                    error_message="积分余额不足"
                )

            # 扣除积分
            user.points -= required_points

            # 更新订单状态
            order = db.query(Order).filter(Order.order_no == order_no).first()
            if order:
                order.status = "paid"
                order.pay_method = "balance"
                order.paid_at = datetime.now()
                order.trade_no = f"BAL{int(time.time())}{user_id}"

            db.commit()

            return PaymentResult(
                success=True,
                payment_method="balance",
                trade_no=order.trade_no if order else "",
                out_trade_no=order_no
            )
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    async def query_payment(
        self,
        order_no: str,
        payment_method: str
    ) -> Dict:
        """查询支付状态"""
        if payment_method == PaymentMethod.ALIPAY:
            return await self.alipay.query_order(order_no)
        elif payment_method == PaymentMethod.WECHAT:
            return await self.wechat.query_order(order_no)
        else:
            return {"status": "unknown", "error": "不支持的支付方式"}

    async def refund(
        self,
        order_no: str,
        refund_no: str,
        refund_amount: Decimal,
        total_amount: Decimal,
        payment_method: str,
        reason: str = ""
    ) -> RefundResult:
        """申请退款"""
        try:
            if payment_method == PaymentMethod.ALIPAY:
                return await self.alipay.refund(
                    order_no=order_no,
                    refund_no=refund_no,
                    refund_amount=refund_amount,
                    reason=reason
                )
            elif payment_method == PaymentMethod.WECHAT:
                return await self.wechat.refund(
                    order_no=order_no,
                    refund_no=refund_no,
                    refund_amount=refund_amount,
                    total_amount=total_amount,
                    reason=reason
                )
            else:
                return RefundResult(
                    success=False,
                    refund_no=refund_no,
                    out_refund_no=refund_no,
                    refund_amount=refund_amount,
                    error_message="不支持的支付方式"
                )
        except Exception as e:
            logger.error(f"退款失败: {str(e)}")
            return RefundResult(
                success=False,
                refund_no=refund_no,
                out_refund_no=refund_no,
                refund_amount=refund_amount,
                error_message=str(e)
            )


class AlipayService:
    """支付宝支付服务"""

    def __init__(self):
        self.app_id = settings.alipay_app_id
        self.private_key = settings.alipay_private_key
        self.public_key = settings.alipay_public_key
        self.gateway = "https://openapi.alipay.com/gateway.do"
        self.sandbox_gateway = "https://openapi.alipaydev.com/gateway.do"
        self.notify_url = f"{settings.app_base_url}/api/v1/payments/alipay/notify"
        self.return_url = f"{settings.app_base_url}/payment/result"

    async def create_order(
        self,
        order_no: str,
        amount: Decimal,
        subject: str,
        client_type: str = "app",
        extra_data: Dict = None
    ) -> PaymentResult:
        """创建支付宝订单"""
        try:
            # 构建业务参数
            biz_content = {
                "out_trade_no": order_no,
                "total_amount": str(amount),
                "subject": subject,
                "product_code": self._get_product_code(client_type)
            }

            if extra_data:
                biz_content.update(extra_data)

            # 构建请求参数
            params = self._build_params(
                method=self._get_method(client_type),
                biz_content=biz_content
            )

            # 签名
            params["sign"] = self._sign(params)

            # 根据客户端类型返回不同格式
            if client_type == "app":
                # App支付返回签名后的字符串
                pay_data = self._build_order_string(params)
            elif client_type == "h5":
                # H5支付返回支付URL
                pay_data = f"{self._get_gateway()}?{self._build_order_string(params)}"
            else:
                # 网页支付返回表单
                pay_data = self._build_form(params)

            return PaymentResult(
                success=True,
                payment_method="alipay",
                trade_no="",
                out_trade_no=order_no,
                pay_data={"pay_info": pay_data, "client_type": client_type}
            )

        except Exception as e:
            logger.error(f"支付宝下单失败: {str(e)}")
            return PaymentResult(
                success=False,
                payment_method="alipay",
                trade_no="",
                out_trade_no=order_no,
                error_message=str(e)
            )

    async def query_order(self, order_no: str) -> Dict:
        """查询订单状态"""
        try:
            biz_content = {"out_trade_no": order_no}
            params = self._build_params(
                method="alipay.trade.query",
                biz_content=biz_content
            )
            params["sign"] = self._sign(params)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._get_gateway(),
                    data=params,
                    timeout=30.0
                )

                result = response.json()
                trade_response = result.get("alipay_trade_query_response", {})

                if trade_response.get("code") == "10000":
                    return {
                        "success": True,
                        "trade_no": trade_response.get("trade_no"),
                        "status": trade_response.get("trade_status"),
                        "amount": trade_response.get("total_amount")
                    }
                else:
                    return {
                        "success": False,
                        "error": trade_response.get("sub_msg", "查询失败")
                    }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def refund(
        self,
        order_no: str,
        refund_no: str,
        refund_amount: Decimal,
        reason: str = ""
    ) -> RefundResult:
        """申请退款"""
        try:
            biz_content = {
                "out_trade_no": order_no,
                "out_request_no": refund_no,
                "refund_amount": str(refund_amount),
                "refund_reason": reason or "用户申请退款"
            }

            params = self._build_params(
                method="alipay.trade.refund",
                biz_content=biz_content
            )
            params["sign"] = self._sign(params)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._get_gateway(),
                    data=params,
                    timeout=30.0
                )

                result = response.json()
                refund_response = result.get("alipay_trade_refund_response", {})

                if refund_response.get("code") == "10000":
                    return RefundResult(
                        success=True,
                        refund_no=refund_response.get("trade_no", ""),
                        out_refund_no=refund_no,
                        refund_amount=refund_amount
                    )
                else:
                    return RefundResult(
                        success=False,
                        refund_no="",
                        out_refund_no=refund_no,
                        refund_amount=refund_amount,
                        error_message=refund_response.get("sub_msg", "退款失败")
                    )

        except Exception as e:
            return RefundResult(
                success=False,
                refund_no="",
                out_refund_no=refund_no,
                refund_amount=refund_amount,
                error_message=str(e)
            )

    def verify_notify(self, params: Dict) -> bool:
        """验证异步通知签名"""
        try:
            sign = params.pop("sign", "")
            sign_type = params.pop("sign_type", "RSA2")

            # 按字母顺序排序并拼接
            sorted_params = sorted(params.items())
            sign_content = "&".join(f"{k}={v}" for k, v in sorted_params if v)

            # 使用公钥验证签名
            return self._verify_sign(sign_content, sign)
        except Exception as e:
            logger.error(f"验签失败: {str(e)}")
            return False

    def _get_gateway(self) -> str:
        """获取网关地址"""
        return self.sandbox_gateway if settings.debug else self.gateway

    def _get_method(self, client_type: str) -> str:
        """根据客户端类型获取接口方法"""
        methods = {
            "app": "alipay.trade.app.pay",
            "h5": "alipay.trade.wap.pay",
            "web": "alipay.trade.page.pay"
        }
        return methods.get(client_type, "alipay.trade.app.pay")

    def _get_product_code(self, client_type: str) -> str:
        """根据客户端类型获取产品码"""
        codes = {
            "app": "QUICK_MSECURITY_PAY",
            "h5": "QUICK_WAP_WAY",
            "web": "FAST_INSTANT_TRADE_PAY"
        }
        return codes.get(client_type, "QUICK_MSECURITY_PAY")

    def _build_params(self, method: str, biz_content: Dict) -> Dict:
        """构建公共请求参数"""
        return {
            "app_id": self.app_id,
            "method": method,
            "format": "JSON",
            "charset": "utf-8",
            "sign_type": "RSA2",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "notify_url": self.notify_url,
            "biz_content": json.dumps(biz_content, ensure_ascii=False)
        }

    def _sign(self, params: Dict) -> str:
        """RSA2签名"""
        try:
            from Crypto.PublicKey import RSA
            from Crypto.Signature import PKCS1_v1_5
            from Crypto.Hash import SHA256
            import base64

            sorted_params = sorted(params.items())
            sign_content = "&".join(f"{k}={v}" for k, v in sorted_params if v)

            key = RSA.import_key(self.private_key)
            signer = PKCS1_v1_5.new(key)
            digest = SHA256.new(sign_content.encode("utf-8"))
            signature = signer.sign(digest)

            return base64.b64encode(signature).decode("utf-8")
        except ImportError:
            logger.warning("PyCryptodome未安装，使用模拟签名")
            return "mock_signature"
        except Exception as e:
            logger.error(f"签名失败: {str(e)}")
            return ""

    def _verify_sign(self, content: str, sign: str) -> bool:
        """验证签名"""
        try:
            from Crypto.PublicKey import RSA
            from Crypto.Signature import PKCS1_v1_5
            from Crypto.Hash import SHA256
            import base64

            key = RSA.import_key(self.public_key)
            verifier = PKCS1_v1_5.new(key)
            digest = SHA256.new(content.encode("utf-8"))
            return verifier.verify(digest, base64.b64decode(sign))
        except Exception:
            return False

    def _build_order_string(self, params: Dict) -> str:
        """构建订单字符串"""
        from urllib.parse import urlencode
        return urlencode(params)

    def _build_form(self, params: Dict) -> str:
        """构建自动提交表单"""
        inputs = "".join(
            f'<input type="hidden" name="{k}" value="{v}"/>'
            for k, v in params.items()
        )
        return f'''
        <form id="alipay_form" action="{self._get_gateway()}" method="POST">
            {inputs}
        </form>
        <script>document.getElementById("alipay_form").submit();</script>
        '''


class WechatPayService:
    """微信支付服务"""

    def __init__(self):
        self.app_id = settings.wechat_app_id
        self.mch_id = settings.wechat_mch_id
        self.api_key = settings.wechat_api_key
        self.api_v3_key = getattr(settings, 'wechat_api_v3_key', '')
        self.cert_path = getattr(settings, 'wechat_cert_path', '')
        self.key_path = getattr(settings, 'wechat_key_path', '')
        self.notify_url = f"{settings.app_base_url}/api/v1/payments/wechat/notify"

    async def create_order(
        self,
        order_no: str,
        amount: Decimal,
        subject: str,
        client_type: str = "app",
        extra_data: Dict = None
    ) -> PaymentResult:
        """创建微信支付订单"""
        try:
            # 金额转换为分
            total_fee = int(amount * 100)

            # 构建请求参数
            params = {
                "appid": self.app_id,
                "mch_id": self.mch_id,
                "nonce_str": self._generate_nonce(),
                "body": subject[:128],  # 商品描述限128字符
                "out_trade_no": order_no,
                "total_fee": total_fee,
                "spbill_create_ip": extra_data.get("client_ip", "127.0.0.1") if extra_data else "127.0.0.1",
                "notify_url": self.notify_url,
                "trade_type": self._get_trade_type(client_type)
            }

            # 小程序/JSAPI需要openid
            if client_type in ["mini", "jsapi"] and extra_data:
                params["openid"] = extra_data.get("openid", "")

            # 签名
            params["sign"] = self._sign(params)

            # 调用统一下单接口
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.mch.weixin.qq.com/pay/unifiedorder",
                    content=self._dict_to_xml(params),
                    headers={"Content-Type": "application/xml"},
                    timeout=30.0
                )

                result = self._xml_to_dict(response.text)

                if result.get("return_code") == "SUCCESS" and result.get("result_code") == "SUCCESS":
                    pay_data = self._build_pay_data(result, client_type)
                    return PaymentResult(
                        success=True,
                        payment_method="wechat",
                        trade_no=result.get("prepay_id", ""),
                        out_trade_no=order_no,
                        pay_data=pay_data
                    )
                else:
                    error_msg = result.get("err_code_des") or result.get("return_msg", "下单失败")
                    return PaymentResult(
                        success=False,
                        payment_method="wechat",
                        trade_no="",
                        out_trade_no=order_no,
                        error_message=error_msg
                    )

        except Exception as e:
            logger.error(f"微信支付下单失败: {str(e)}")
            return PaymentResult(
                success=False,
                payment_method="wechat",
                trade_no="",
                out_trade_no=order_no,
                error_message=str(e)
            )

    async def query_order(self, order_no: str) -> Dict:
        """查询订单状态"""
        try:
            params = {
                "appid": self.app_id,
                "mch_id": self.mch_id,
                "out_trade_no": order_no,
                "nonce_str": self._generate_nonce()
            }
            params["sign"] = self._sign(params)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.mch.weixin.qq.com/pay/orderquery",
                    content=self._dict_to_xml(params),
                    headers={"Content-Type": "application/xml"},
                    timeout=30.0
                )

                result = self._xml_to_dict(response.text)

                if result.get("return_code") == "SUCCESS" and result.get("result_code") == "SUCCESS":
                    return {
                        "success": True,
                        "trade_no": result.get("transaction_id"),
                        "status": result.get("trade_state"),
                        "amount": int(result.get("total_fee", 0)) / 100
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("err_code_des", "查询失败")
                    }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def refund(
        self,
        order_no: str,
        refund_no: str,
        refund_amount: Decimal,
        total_amount: Decimal,
        reason: str = ""
    ) -> RefundResult:
        """申请退款"""
        try:
            params = {
                "appid": self.app_id,
                "mch_id": self.mch_id,
                "nonce_str": self._generate_nonce(),
                "out_trade_no": order_no,
                "out_refund_no": refund_no,
                "total_fee": int(total_amount * 100),
                "refund_fee": int(refund_amount * 100),
                "refund_desc": reason or "用户申请退款"
            }
            params["sign"] = self._sign(params)

            # 退款接口需要双向证书
            async with httpx.AsyncClient(
                cert=(self.cert_path, self.key_path) if self.cert_path else None
            ) as client:
                response = await client.post(
                    "https://api.mch.weixin.qq.com/secapi/pay/refund",
                    content=self._dict_to_xml(params),
                    headers={"Content-Type": "application/xml"},
                    timeout=30.0
                )

                result = self._xml_to_dict(response.text)

                if result.get("return_code") == "SUCCESS" and result.get("result_code") == "SUCCESS":
                    return RefundResult(
                        success=True,
                        refund_no=result.get("refund_id", ""),
                        out_refund_no=refund_no,
                        refund_amount=refund_amount
                    )
                else:
                    return RefundResult(
                        success=False,
                        refund_no="",
                        out_refund_no=refund_no,
                        refund_amount=refund_amount,
                        error_message=result.get("err_code_des", "退款失败")
                    )

        except Exception as e:
            return RefundResult(
                success=False,
                refund_no="",
                out_refund_no=refund_no,
                refund_amount=refund_amount,
                error_message=str(e)
            )

    def verify_notify(self, xml_data: str) -> tuple:
        """验证异步通知"""
        try:
            data = self._xml_to_dict(xml_data)
            sign = data.pop("sign", "")

            # 验证签名
            if self._sign(data) != sign:
                return False, data

            return True, data
        except Exception as e:
            logger.error(f"微信支付验签失败: {str(e)}")
            return False, {}

    def _get_trade_type(self, client_type: str) -> str:
        """获取交易类型"""
        types = {
            "app": "APP",
            "h5": "MWEB",
            "mini": "JSAPI",
            "jsapi": "JSAPI",
            "native": "NATIVE"
        }
        return types.get(client_type, "APP")

    def _generate_nonce(self) -> str:
        """生成随机字符串"""
        return uuid.uuid4().hex[:32]

    def _sign(self, params: Dict) -> str:
        """MD5签名"""
        sorted_params = sorted(params.items())
        sign_str = "&".join(f"{k}={v}" for k, v in sorted_params if v)
        sign_str += f"&key={self.api_key}"
        return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()

    def _build_pay_data(self, result: Dict, client_type: str) -> Dict:
        """构建客户端支付数据"""
        prepay_id = result.get("prepay_id", "")
        timestamp = str(int(time.time()))
        nonce_str = self._generate_nonce()

        if client_type == "app":
            # App支付
            pay_data = {
                "appid": self.app_id,
                "partnerid": self.mch_id,
                "prepayid": prepay_id,
                "package": "Sign=WXPay",
                "noncestr": nonce_str,
                "timestamp": timestamp
            }
            pay_data["sign"] = self._sign(pay_data)
            return pay_data

        elif client_type in ["mini", "jsapi"]:
            # 小程序/JSAPI支付
            pay_data = {
                "appId": self.app_id,
                "timeStamp": timestamp,
                "nonceStr": nonce_str,
                "package": f"prepay_id={prepay_id}",
                "signType": "MD5"
            }
            sign_data = {
                "appId": self.app_id,
                "timeStamp": timestamp,
                "nonceStr": nonce_str,
                "package": f"prepay_id={prepay_id}",
                "signType": "MD5"
            }
            pay_data["paySign"] = self._sign(sign_data)
            return pay_data

        elif client_type == "h5":
            # H5支付
            return {"mweb_url": result.get("mweb_url", "")}

        elif client_type == "native":
            # Native支付（二维码）
            return {"code_url": result.get("code_url", "")}

        return {"prepay_id": prepay_id}

    def _dict_to_xml(self, data: Dict) -> str:
        """字典转XML"""
        xml_parts = ["<xml>"]
        for key, value in data.items():
            if isinstance(value, str):
                xml_parts.append(f"<{key}><![CDATA[{value}]]></{key}>")
            else:
                xml_parts.append(f"<{key}>{value}</{key}>")
        xml_parts.append("</xml>")
        return "".join(xml_parts)

    def _xml_to_dict(self, xml_str: str) -> Dict:
        """XML转字典"""
        import re
        result = {}
        pattern = r"<(\w+)>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</\1>"
        matches = re.findall(pattern, xml_str, re.DOTALL)
        for key, value in matches:
            result[key] = value.strip()
        return result


# 全局支付服务实例
payment_service = PaymentService()

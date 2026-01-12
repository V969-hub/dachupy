"""
支付服务模块

实现微信支付下单和支付回调验证功能。

Requirements:
- 8.1: 创建微信支付订单
- 8.2: 支付回调验证
- 8.3: 支付成功更新订单状态
- 8.4: 支付失败保持订单状态
"""
import hashlib
import hmac
import time
import uuid
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
import logging

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.order import Order
from app.models.tip import Tip
from app.models.notification import Notification


logger = logging.getLogger(__name__)


class PaymentServiceError(Exception):
    """支付服务异常"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


def generate_nonce_str(length: int = 32) -> str:
    """生成随机字符串"""
    return uuid.uuid4().hex[:length]


def generate_sign(params: Dict[str, Any], api_key: str) -> str:
    """
    生成微信支付签名
    
    使用MD5签名方式
    """
    # 按字典序排序参数
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    
    # 拼接字符串
    string_a = "&".join([f"{k}={v}" for k, v in sorted_params if v])
    string_sign_temp = f"{string_a}&key={api_key}"
    
    # MD5签名
    sign = hashlib.md5(string_sign_temp.encode("utf-8")).hexdigest().upper()
    
    return sign


def dict_to_xml(data: Dict[str, Any]) -> str:
    """将字典转换为XML字符串"""
    xml_parts = ["<xml>"]
    for key, value in data.items():
        if value is not None:
            xml_parts.append(f"<{key}><![CDATA[{value}]]></{key}>")
    xml_parts.append("</xml>")
    return "".join(xml_parts)


def xml_to_dict(xml_str: str) -> Dict[str, str]:
    """将XML字符串转换为字典"""
    result = {}
    try:
        root = ET.fromstring(xml_str)
        for child in root:
            result[child.tag] = child.text or ""
    except ET.ParseError as e:
        logger.error(f"XML解析错误: {e}")
        raise PaymentServiceError("XML解析错误", code=400)
    return result


def verify_sign(params: Dict[str, Any], sign: str, api_key: str) -> bool:
    """
    验证微信支付签名
    
    Requirements: 8.2
    """
    # 移除sign字段
    params_copy = {k: v for k, v in params.items() if k != "sign"}
    
    # 计算签名
    calculated_sign = generate_sign(params_copy, api_key)
    
    return calculated_sign == sign


class PaymentService:
    """支付服务类"""
    
    # 微信支付统一下单接口
    UNIFIED_ORDER_URL = "https://api.mch.weixin.qq.com/pay/unifiedorder"
    
    def __init__(self, db: Session):
        self.db = db
        self.app_id = settings.WECHAT_APP_ID
        self.mch_id = settings.WECHAT_MCH_ID
        self.api_key = settings.WECHAT_API_KEY
    
    # ==================== 订单支付 ====================
    
    async def create_order_payment(
        self,
        order_id: str,
        openid: str,
        notify_url: str,
        client_ip: str = "127.0.0.1"
    ) -> Dict[str, Any]:
        """
        创建订单支付
        
        Args:
            order_id: 订单ID
            openid: 用户微信openid
            notify_url: 支付回调通知URL
            client_ip: 客户端IP
            
        Returns:
            微信支付参数（用于小程序调起支付）
            
        Requirements: 8.1
        """
        # 获取订单
        order = self.db.query(Order).filter(
            Order.id == order_id,
            Order.is_deleted == False
        ).first()
        
        if not order:
            raise PaymentServiceError("订单不存在", code=404)
        
        if order.status != "unpaid":
            raise PaymentServiceError("订单状态不正确，无法支付", code=400)
        
        # 调用微信统一下单接口
        prepay_result = await self._unified_order(
            out_trade_no=order.order_no,
            total_fee=int(order.total_price * 100),  # 转换为分
            body=f"私厨预订-订单{order.order_no}",
            openid=openid,
            notify_url=notify_url,
            client_ip=client_ip
        )
        
        if not prepay_result.get("prepay_id"):
            raise PaymentServiceError(
                prepay_result.get("err_msg", "创建支付订单失败"),
                code=500
            )
        
        # 生成小程序支付参数
        payment_params = self._generate_payment_params(prepay_result["prepay_id"])
        
        return {
            "order_id": order.id,
            "order_no": order.order_no,
            "total_price": float(order.total_price),
            "payment_params": payment_params
        }
    
    async def _unified_order(
        self,
        out_trade_no: str,
        total_fee: int,
        body: str,
        openid: str,
        notify_url: str,
        client_ip: str
    ) -> Dict[str, Any]:
        """
        调用微信统一下单接口
        
        Args:
            out_trade_no: 商户订单号
            total_fee: 金额（分）
            body: 商品描述
            openid: 用户openid
            notify_url: 回调地址
            client_ip: 客户端IP
            
        Returns:
            微信返回结果
        """
        # 构建请求参数
        params = {
            "appid": self.app_id,
            "mch_id": self.mch_id,
            "nonce_str": generate_nonce_str(),
            "body": body,
            "out_trade_no": out_trade_no,
            "total_fee": str(total_fee),
            "spbill_create_ip": client_ip,
            "notify_url": notify_url,
            "trade_type": "JSAPI",
            "openid": openid
        }
        
        # 生成签名
        params["sign"] = generate_sign(params, self.api_key)
        
        # 转换为XML
        xml_data = dict_to_xml(params)
        
        # 发送请求
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.UNIFIED_ORDER_URL,
                    content=xml_data,
                    headers={"Content-Type": "application/xml"}
                )
                response.raise_for_status()
                
                # 解析响应
                result = xml_to_dict(response.text)
                
                if result.get("return_code") != "SUCCESS":
                    logger.error(f"微信统一下单失败: {result.get('return_msg')}")
                    return {"err_msg": result.get("return_msg", "统一下单失败")}
                
                if result.get("result_code") != "SUCCESS":
                    logger.error(f"微信统一下单业务失败: {result.get('err_code_des')}")
                    return {"err_msg": result.get("err_code_des", "统一下单业务失败")}
                
                return result
                
        except httpx.HTTPError as e:
            logger.error(f"微信支付请求失败: {e}")
            return {"err_msg": f"支付请求失败: {str(e)}"}
    
    def _generate_payment_params(self, prepay_id: str) -> Dict[str, str]:
        """
        生成小程序支付参数
        
        Args:
            prepay_id: 预支付交易会话标识
            
        Returns:
            小程序调起支付所需参数
        """
        timestamp = str(int(time.time()))
        nonce_str = generate_nonce_str()
        package = f"prepay_id={prepay_id}"
        
        # 构建签名参数
        sign_params = {
            "appId": self.app_id,
            "timeStamp": timestamp,
            "nonceStr": nonce_str,
            "package": package,
            "signType": "MD5"
        }
        
        # 生成签名
        pay_sign = generate_sign(sign_params, self.api_key)
        
        return {
            "timeStamp": timestamp,
            "nonceStr": nonce_str,
            "package": package,
            "signType": "MD5",
            "paySign": pay_sign
        }
    
    # ==================== 支付回调处理 ====================
    
    def handle_payment_notify(self, xml_data: str) -> Tuple[bool, str, Optional[str]]:
        """
        处理微信支付回调通知
        
        Args:
            xml_data: 微信回调的XML数据
            
        Returns:
            Tuple[bool, str, Optional[str]]: (是否成功, 消息, 订单号)
            
        Requirements: 8.2, 8.3, 8.4
        """
        try:
            # 解析XML
            notify_data = xml_to_dict(xml_data)
            
            # 验证返回状态
            if notify_data.get("return_code") != "SUCCESS":
                logger.error(f"支付回调返回失败: {notify_data.get('return_msg')}")
                return False, notify_data.get("return_msg", "回调失败"), None
            
            # 验证签名 (Requirements: 8.2)
            sign = notify_data.get("sign")
            if not sign or not verify_sign(notify_data, sign, self.api_key):
                logger.error("支付回调签名验证失败")
                return False, "签名验证失败", None
            
            # 获取订单号
            out_trade_no = notify_data.get("out_trade_no")
            if not out_trade_no:
                logger.error("支付回调缺少订单号")
                return False, "缺少订单号", None
            
            # 获取支付结果
            result_code = notify_data.get("result_code")
            transaction_id = notify_data.get("transaction_id")
            
            # 查找订单
            order = self.db.query(Order).filter(
                Order.order_no == out_trade_no
            ).first()
            
            if not order:
                logger.error(f"支付回调订单不存在: {out_trade_no}")
                return False, "订单不存在", out_trade_no
            
            # 检查订单状态，避免重复处理
            if order.status != "unpaid":
                logger.info(f"订单已处理: {out_trade_no}, 状态: {order.status}")
                return True, "订单已处理", out_trade_no
            
            if result_code == "SUCCESS":
                # 支付成功，更新订单状态 (Requirements: 8.3)
                order.status = "pending"
                order.payment_id = transaction_id
                
                # 创建通知给大厨
                notification = Notification(
                    user_id=order.chef_id,
                    type="new_order",
                    title="新订单",
                    content=f"您有一个新订单，订单号: {order.order_no}",
                    data={
                        "order_id": order.id,
                        "order_no": order.order_no,
                        "status": "pending"
                    }
                )
                self.db.add(notification)
                
                self.db.commit()
                logger.info(f"订单支付成功: {out_trade_no}")
                return True, "支付成功", out_trade_no
            else:
                # 支付失败，保持订单状态 (Requirements: 8.4)
                logger.warning(f"订单支付失败: {out_trade_no}, 错误: {notify_data.get('err_code_des')}")
                return False, notify_data.get("err_code_des", "支付失败"), out_trade_no
                
        except Exception as e:
            logger.error(f"处理支付回调异常: {e}", exc_info=True)
            return False, str(e), None
    
    # ==================== 打赏支付 ====================
    
    async def create_tip_payment(
        self,
        tip_id: str,
        openid: str,
        notify_url: str,
        client_ip: str = "127.0.0.1"
    ) -> Dict[str, Any]:
        """
        创建打赏支付
        
        Args:
            tip_id: 打赏记录ID
            openid: 用户微信openid
            notify_url: 支付回调通知URL
            client_ip: 客户端IP
            
        Returns:
            微信支付参数
        """
        # 获取打赏记录
        tip = self.db.query(Tip).filter(Tip.id == tip_id).first()
        
        if not tip:
            raise PaymentServiceError("打赏记录不存在", code=404)
        
        if tip.status != "pending":
            raise PaymentServiceError("打赏状态不正确", code=400)
        
        # 生成打赏订单号
        tip_order_no = f"TIP{generate_nonce_str(20)}"
        
        # 调用微信统一下单接口
        prepay_result = await self._unified_order(
            out_trade_no=tip_order_no,
            total_fee=int(tip.amount * 100),
            body=f"私厨打赏-{tip.message or '感谢大厨'}",
            openid=openid,
            notify_url=notify_url,
            client_ip=client_ip
        )
        
        if not prepay_result.get("prepay_id"):
            raise PaymentServiceError(
                prepay_result.get("err_msg", "创建打赏支付失败"),
                code=500
            )
        
        # 保存支付订单号到打赏记录
        tip.payment_id = tip_order_no
        self.db.commit()
        
        # 生成小程序支付参数
        payment_params = self._generate_payment_params(prepay_result["prepay_id"])
        
        return {
            "tip_id": tip.id,
            "amount": float(tip.amount),
            "payment_params": payment_params
        }
    
    def handle_tip_payment_notify(self, xml_data: str) -> Tuple[bool, str, Optional[str]]:
        """
        处理打赏支付回调通知
        
        Args:
            xml_data: 微信回调的XML数据
            
        Returns:
            Tuple[bool, str, Optional[str]]: (是否成功, 消息, 打赏订单号)
        """
        try:
            # 解析XML
            notify_data = xml_to_dict(xml_data)
            
            # 验证返回状态
            if notify_data.get("return_code") != "SUCCESS":
                return False, notify_data.get("return_msg", "回调失败"), None
            
            # 验证签名
            sign = notify_data.get("sign")
            if not sign or not verify_sign(notify_data, sign, self.api_key):
                return False, "签名验证失败", None
            
            # 获取订单号
            out_trade_no = notify_data.get("out_trade_no")
            if not out_trade_no:
                return False, "缺少订单号", None
            
            # 获取支付结果
            result_code = notify_data.get("result_code")
            transaction_id = notify_data.get("transaction_id")
            
            # 查找打赏记录
            tip = self.db.query(Tip).filter(
                Tip.payment_id == out_trade_no
            ).first()
            
            if not tip:
                logger.error(f"打赏回调记录不存在: {out_trade_no}")
                return False, "打赏记录不存在", out_trade_no
            
            # 检查状态，避免重复处理
            if tip.status != "pending":
                return True, "打赏已处理", out_trade_no
            
            if result_code == "SUCCESS":
                # 支付成功
                tip.status = "paid"
                tip.payment_id = transaction_id
                
                # 创建通知给大厨
                notification = Notification(
                    user_id=tip.chef_id,
                    type="tip",
                    title="收到打赏",
                    content=f"您收到一笔 ¥{tip.amount} 的打赏",
                    data={
                        "tip_id": tip.id,
                        "amount": float(tip.amount),
                        "message": tip.message
                    }
                )
                self.db.add(notification)
                
                self.db.commit()
                return True, "打赏成功", out_trade_no
            else:
                # 支付失败
                tip.status = "failed"
                self.db.commit()
                return False, notify_data.get("err_code_des", "支付失败"), out_trade_no
                
        except Exception as e:
            logger.error(f"处理打赏回调异常: {e}", exc_info=True)
            return False, str(e), None
    
    # ==================== 辅助方法 ====================
    
    def generate_notify_response(self, success: bool, message: str = "") -> str:
        """
        生成微信支付回调响应
        
        Args:
            success: 是否成功
            message: 消息
            
        Returns:
            XML格式响应
        """
        if success:
            return dict_to_xml({
                "return_code": "SUCCESS",
                "return_msg": "OK"
            })
        else:
            return dict_to_xml({
                "return_code": "FAIL",
                "return_msg": message
            })


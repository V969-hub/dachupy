"""
支付API路由模块

实现支付回调接口。

Requirements:
- 8.2: 支付回调验证
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.services.payment_service import PaymentService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment", tags=["Payment"])


@router.post("/notify")
async def payment_notify(request: Request, db: Session = Depends(get_db)):
    """
    微信支付回调通知接口
    
    接收微信支付结果通知，验证签名并更新订单状态。
    
    Requirements: 8.2
    
    注意：此接口由微信服务器调用，不需要JWT认证
    """
    # 读取原始XML数据
    xml_data = await request.body()
    xml_str = xml_data.decode("utf-8")
    
    logger.info(f"收到支付回调: {xml_str[:200]}...")
    
    # 处理支付回调
    payment_service = PaymentService(db)
    success, message, order_no = payment_service.handle_payment_notify(xml_str)
    
    if success:
        logger.info(f"支付回调处理成功: {order_no}")
    else:
        logger.error(f"支付回调处理失败: {order_no}, {message}")
    
    # 返回XML响应给微信
    response_xml = payment_service.generate_notify_response(success, message)
    
    return Response(
        content=response_xml,
        media_type="application/xml"
    )


@router.post("/tip/notify")
async def tip_payment_notify(request: Request, db: Session = Depends(get_db)):
    """
    打赏支付回调通知接口
    
    接收微信支付结果通知，验证签名并更新打赏状态。
    
    注意：此接口由微信服务器调用，不需要JWT认证
    """
    # 读取原始XML数据
    xml_data = await request.body()
    xml_str = xml_data.decode("utf-8")
    
    logger.info(f"收到打赏支付回调: {xml_str[:200]}...")
    
    # 处理打赏支付回调
    payment_service = PaymentService(db)
    success, message, tip_order_no = payment_service.handle_tip_payment_notify(xml_str)
    
    if success:
        logger.info(f"打赏支付回调处理成功: {tip_order_no}")
    else:
        logger.error(f"打赏支付回调处理失败: {tip_order_no}, {message}")
    
    # 返回XML响应给微信
    response_xml = payment_service.generate_notify_response(success, message)
    
    return Response(
        content=response_xml,
        media_type="application/xml"
    )


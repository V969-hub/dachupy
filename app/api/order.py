"""
订单API路由

实现吃货端和大厨端的订单相关接口

Requirements:
- 6.1-6.6: 订单管理接口（吃货端）
- 7.1-7.6: 订单状态管理接口
"""
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_chef, require_foodie
from app.models.user import User
from app.services.order_service import OrderService, OrderServiceError
from app.services.payment_service import PaymentService, PaymentServiceError
from app.schemas.order import (
    OrderCreate,
    OrderCancel,
    OrderReject,
    OrderCreateResponse,
    OrderPayRequest,
)
from app.schemas.common import success_response, error_response, paginated_response
from app.services.wallet_service import (
    PAYMENT_METHOD_VIRTUAL_COIN,
    PAYMENT_METHOD_WECHAT,
    build_wallet_payload,
)


router = APIRouter(tags=["订单"])


# ==================== 吃货端接口 ====================

@router.post("/orders")
async def create_order(
    http_request: Request,
    request: OrderCreate,
    current_user: User = Depends(require_foodie),
    db: Session = Depends(get_db)
):
    """
    创建订单（吃货端）
    
    创建订单后返回订单信息和微信支付参数
    
    Requirements: 6.1, 6.2, 6.3, 6.4
    """
    order_service = OrderService(db)
    
    try:
        # 转换订单项格式
        items = [
            {"dish_id": item.dish_id, "quantity": item.quantity}
            for item in request.items
        ]
        
        order = order_service.create_order(
            foodie_id=current_user.id,
            items=items,
            delivery_time=request.delivery_time,
            address_id=request.address_id,
            remarks=request.remarks,
            payment_method=request.payment_method,
        )

        payment_params = None
        if float(order.total_price) > 0 and order.status == "unpaid" and order.payment_method == PAYMENT_METHOD_WECHAT:
            if not current_user.open_id:
                return error_response(400, "当前账号缺少微信 open_id，无法发起支付")

            payment_service = PaymentService(db)
            base_url = str(http_request.base_url).rstrip("/")
            notify_url = f"{base_url}/api/payment/notify"
            client_ip = http_request.client.host if http_request.client else "127.0.0.1"
            payment_result = await payment_service.create_order_payment(
                order_id=order.id,
                openid=current_user.open_id,
                notify_url=notify_url,
                client_ip=client_ip
            )
            payment_params = payment_result.get("payment_params")

        # 构建响应数据
        response_data = {
            "order_id": order.id,
            "order_no": order.order_no,
            "total_price": float(order.total_price),
            "order_status": order.status,
            "payment_method": order.payment_method,
            "wallet_balance": build_wallet_payload(current_user)["balance"],
            "payment_params": payment_params
        }
        
        return success_response(data=response_data, message="订单创建成功")
        
    except OrderServiceError as e:
        if e.code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=e.message
            )
        elif e.code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=e.message
            )
        return error_response(e.code, e.message)
    except PaymentServiceError as e:
        if e.code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=e.message
            )
        return error_response(e.code, e.message)


@router.post("/orders/{order_id}/pay")
async def pay_order(
    order_id: str,
    http_request: Request,
    request: Optional[OrderPayRequest] = Body(default=None),
    current_user: User = Depends(require_foodie),
    db: Session = Depends(get_db)
):
    """
    为未支付订单重新获取支付参数（吃货端）。
    """
    order_service = OrderService(db)

    order = order_service.get_order_by_id(order_id)
    if not order or order.foodie_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在或无权查看"
        )

    if order.status != "unpaid":
        return error_response(400, "当前订单不需要继续支付")

    payment_method = (request.payment_method if request else PAYMENT_METHOD_WECHAT).strip().lower()

    if payment_method == PAYMENT_METHOD_VIRTUAL_COIN:
        try:
            updated_order = order_service.pay_order_with_virtual_coin(order_id=order.id, foodie_id=current_user.id)
            return success_response(
                data={
                    "order_id": updated_order.id,
                    "order_no": updated_order.order_no,
                    "total_price": float(updated_order.total_price),
                    "order_status": updated_order.status,
                    "payment_method": updated_order.payment_method,
                    "wallet_balance": build_wallet_payload(current_user)["balance"],
                    "payment_params": None,
                },
                message="虚拟币支付成功"
            )
        except OrderServiceError as e:
            if e.code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=e.message
                )
            return error_response(e.code, e.message)

    if not current_user.open_id:
        return error_response(400, "当前账号缺少微信 open_id，无法发起支付")

    payment_service = PaymentService(db)
    base_url = str(http_request.base_url).rstrip("/")
    notify_url = f"{base_url}/api/payment/notify"
    client_ip = http_request.client.host if http_request.client else "127.0.0.1"

    try:
        payment_result = await payment_service.create_order_payment(
            order_id=order.id,
            openid=current_user.open_id,
            notify_url=notify_url,
            client_ip=client_ip
        )
        return success_response(
            data={
                "order_id": order.id,
                "order_no": order.order_no,
                "total_price": float(order.total_price),
                "order_status": order.status,
                "payment_method": order.payment_method,
                "wallet_balance": build_wallet_payload(current_user)["balance"],
                "payment_params": payment_result.get("payment_params")
            },
            message="支付参数获取成功"
        )
    except PaymentServiceError as e:
        if e.code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=e.message
            )
        return error_response(e.code, e.message)


@router.get("/orders")
async def get_orders(
    status_filter: Optional[str] = Query(None, alias="status", description="状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取订单列表
    
    吃货获取自己的订单，大厨获取自己的订单
    
    Requirements: 6.5
    """
    order_service = OrderService(db)
    
    if current_user.role == "foodie":
        orders, total = order_service.get_foodie_orders(
            foodie_id=current_user.id,
            status=status_filter,
            page=page,
            page_size=page_size
        )
    else:
        orders, total = order_service.get_chef_orders(
            chef_id=current_user.id,
            status=status_filter,
            page=page,
            page_size=page_size
        )
    
    # 构建响应数据
    orders_data = [
        order_service.build_order_list_item(order)
        for order in orders
    ]
    
    return paginated_response(
        data=orders_data,
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/orders/{order_id}")
async def get_order_detail(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取订单详情
    
    Requirements: 6.6
    """
    order_service = OrderService(db)
    order_data = order_service.get_order_detail(
        order_id=order_id,
        user_id=current_user.id
    )
    
    if not order_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在或无权查看"
        )
    
    return success_response(data=order_data)


@router.put("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    request: OrderCancel,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    取消订单
    
    吃货或大厨都可以取消订单（在允许的状态下）
    
    Requirements: 7.1
    """
    order_service = OrderService(db)
    
    try:
        order = order_service.cancel_order(
            order_id=order_id,
            user_id=current_user.id,
            reason=request.reason
        )

        response_data = {"order_id": order.id, "status": order.status}
        if current_user.id == order.foodie_id:
            response_data["wallet_balance"] = build_wallet_payload(current_user)["balance"]

        return success_response(
            data=response_data,
            message="订单已取消"
        )
        
    except OrderServiceError as e:
        if e.code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=e.message
            )
        elif e.code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=e.message
            )
        return error_response(e.code, e.message)


@router.put("/orders/{order_id}/confirm")
async def confirm_receipt(
    order_id: str,
    current_user: User = Depends(require_foodie),
    db: Session = Depends(get_db)
):
    """
    确认收货（吃货端）
    
    Requirements: 7.5
    """
    order_service = OrderService(db)
    
    try:
        order = order_service.confirm_receipt(
            order_id=order_id,
            foodie_id=current_user.id
        )
        
        return success_response(
            data={"order_id": order.id, "status": order.status},
            message="已确认收货"
        )
        
    except OrderServiceError as e:
        if e.code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=e.message
            )
        elif e.code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=e.message
            )
        return error_response(e.code, e.message)



# ==================== 大厨端接口 ====================

@router.get("/chef/orders")
async def get_chef_orders(
    status_filter: Optional[str] = Query(None, alias="status", description="状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    current_user: User = Depends(require_chef),
    db: Session = Depends(get_db)
):
    """
    获取大厨订单列表（大厨端）
    
    Requirements: 7.2
    """
    order_service = OrderService(db)
    
    orders, total = order_service.get_chef_orders(
        chef_id=current_user.id,
        status=status_filter,
        page=page,
        page_size=page_size
    )
    
    # 构建响应数据
    orders_data = [
        order_service.build_order_list_item(order)
        for order in orders
    ]
    
    return paginated_response(
        data=orders_data,
        page=page,
        page_size=page_size,
        total=total
    )


@router.put("/chef/orders/{order_id}/accept")
async def accept_order(
    order_id: str,
    current_user: User = Depends(require_chef),
    db: Session = Depends(get_db)
):
    """
    接受订单（大厨端）
    
    Requirements: 7.2
    """
    order_service = OrderService(db)
    
    try:
        order = order_service.accept_order(
            order_id=order_id,
            chef_id=current_user.id
        )
        
        return success_response(
            data={"order_id": order.id, "status": order.status},
            message="订单已接受"
        )
        
    except OrderServiceError as e:
        if e.code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=e.message
            )
        elif e.code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=e.message
            )
        return error_response(e.code, e.message)


@router.put("/chef/orders/{order_id}/reject")
async def reject_order(
    order_id: str,
    request: OrderReject,
    current_user: User = Depends(require_chef),
    db: Session = Depends(get_db)
):
    """
    拒绝订单（大厨端）
    
    Requirements: 7.3
    """
    order_service = OrderService(db)
    
    try:
        order = order_service.reject_order(
            order_id=order_id,
            chef_id=current_user.id,
            reason=request.reason
        )
        
        return success_response(
            data={"order_id": order.id, "status": order.status},
            message="订单已拒绝"
        )
        
    except OrderServiceError as e:
        if e.code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=e.message
            )
        elif e.code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=e.message
            )
        return error_response(e.code, e.message)


@router.put("/chef/orders/{order_id}/cooking-done")
async def cooking_done(
    order_id: str,
    current_user: User = Depends(require_chef),
    db: Session = Depends(get_db)
):
    """
    烹饪完成，开始配送（大厨端）
    
    Requirements: 7.4
    """
    order_service = OrderService(db)
    
    try:
        order = order_service.cooking_done(
            order_id=order_id,
            chef_id=current_user.id
        )
        
        return success_response(
            data={"order_id": order.id, "status": order.status},
            message="已开始配送"
        )
        
    except OrderServiceError as e:
        if e.code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=e.message
            )
        elif e.code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=e.message
            )
        return error_response(e.code, e.message)


@router.put("/chef/orders/{order_id}/delivering")
async def start_delivering(
    order_id: str,
    current_user: User = Depends(require_chef),
    db: Session = Depends(get_db)
):
    """
    开始配送（大厨端）
    
    Requirements: 7.4
    """
    order_service = OrderService(db)
    
    try:
        order = order_service.start_delivering(
            order_id=order_id,
            chef_id=current_user.id
        )
        
        return success_response(
            data={"order_id": order.id, "status": order.status},
            message="配送中"
        )
        
    except OrderServiceError as e:
        if e.code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=e.message
            )
        elif e.code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=e.message
            )
        return error_response(e.code, e.message)


@router.put("/chef/orders/{order_id}/cooking")
async def start_cooking(
    order_id: str,
    current_user: User = Depends(require_chef),
    db: Session = Depends(get_db)
):
    """
    开始烹饪（大厨端）
    
    Requirements: 7.4
    """
    order_service = OrderService(db)
    
    try:
        order = order_service.start_cooking(
            order_id=order_id,
            chef_id=current_user.id
        )
        
        return success_response(
            data={"order_id": order.id, "status": order.status},
            message="开始烹饪"
        )
        
    except OrderServiceError as e:
        if e.code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=e.message
            )
        elif e.code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=e.message
            )
        return error_response(e.code, e.message)

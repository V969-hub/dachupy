"""
打赏API接口

实现打赏创建和查询功能。

Requirements:
- 10.1: POST /tips 创建打赏
- 10.3: GET /tips 打赏记录
"""
from typing import Optional
from decimal import Decimal
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.tip_service import TipService, TipServiceError
from app.services.payment_service import PaymentService, PaymentServiceError
from app.schemas.common import success_response, error_response, paginated_response


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tips", tags=["Tips"])


# ==================== 请求/响应模型 ====================

class CreateTipRequest(BaseModel):
    """创建打赏请求"""
    chef_id: str = Field(..., description="大厨ID")
    amount: Decimal = Field(..., gt=0, description="打赏金额")
    message: Optional[str] = Field(None, max_length=256, description="留言")
    order_id: Optional[str] = Field(None, description="关联订单ID")


class TipResponse(BaseModel):
    """打赏响应"""
    id: str
    chef_id: str
    chef_nickname: Optional[str] = None
    chef_avatar: Optional[str] = None
    amount: float
    message: Optional[str] = None
    order_id: Optional[str] = None
    status: str
    created_at: str


# ==================== API接口 ====================

@router.post("")
async def create_tip(
    request: Request,
    tip_data: CreateTipRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建打赏
    
    创建打赏记录并发起微信支付。
    
    Requirements: 10.1
    """
    try:
        tip_service = TipService(db)
        
        # 创建打赏记录
        tip = tip_service.create_tip(
            foodie_id=current_user["user_id"],
            chef_id=tip_data.chef_id,
            amount=tip_data.amount,
            message=tip_data.message,
            order_id=tip_data.order_id
        )
        
        # 获取用户openid用于支付
        from app.models.user import User
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        # 创建支付
        payment_service = PaymentService(db)
        
        # 构建回调URL
        base_url = str(request.base_url).rstrip("/")
        notify_url = f"{base_url}/api/payment/tip-notify"
        
        # 获取客户端IP
        client_ip = request.client.host if request.client else "127.0.0.1"
        
        payment_result = await payment_service.create_tip_payment(
            tip_id=tip.id,
            openid=user.open_id,
            notify_url=notify_url,
            client_ip=client_ip
        )
        
        return success_response(
            data={
                "tip_id": tip.id,
                "amount": float(tip.amount),
                "payment_params": payment_result.get("payment_params")
            },
            message="打赏创建成功"
        )
        
    except TipServiceError as e:
        logger.error(f"创建打赏失败: {e.message}")
        return error_response(code=e.code, message=e.message)
    except PaymentServiceError as e:
        logger.error(f"创建打赏支付失败: {e.message}")
        return error_response(code=e.code, message=e.message)
    except Exception as e:
        logger.error(f"创建打赏异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="创建打赏失败")


@router.get("")
async def get_tips(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选: pending/paid/failed"),
    role: Optional[str] = Query(None, description="角色视角: foodie/chef"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取打赏记录
    
    根据用户角色返回打赏记录列表。
    - 吃货：返回自己发出的打赏
    - 大厨：返回自己收到的打赏
    
    Requirements: 10.3
    """
    try:
        tip_service = TipService(db)
        user_role = current_user.role
        
        # 根据角色或指定视角查询
        query_role = role if role else user_role
        
        if query_role == "chef":
            tips, total = tip_service.get_tips_by_chef(
                chef_id=current_user.id,
                page=page,
                page_size=page_size,
                status=status
            )
        else:
            tips, total = tip_service.get_tips_by_foodie(
                foodie_id=current_user.id,
                page=page,
                page_size=page_size,
                status=status
            )
        
        # 构建响应数据
        tip_list = []
        for tip in tips:
            tip_data = {
                "id": tip.id,
                "chef_id": tip.chef_id,
                "foodie_id": tip.foodie_id,
                "amount": float(tip.amount),
                "message": tip.message,
                "order_id": tip.order_id,
                "status": tip.status,
                "created_at": tip.created_at.isoformat() if tip.created_at else None
            }
            
            # 添加大厨信息
            if tip.chef:
                tip_data["chef_nickname"] = tip.chef.nickname
                tip_data["chef_avatar"] = tip.chef.avatar
            
            # 添加吃货信息
            if tip.foodie:
                tip_data["foodie_nickname"] = tip.foodie.nickname
                tip_data["foodie_avatar"] = tip.foodie.avatar
            
            tip_list.append(tip_data)
        
        return paginated_response(
            data=tip_list,
            page=page,
            page_size=page_size,
            total=total
        )
        
    except Exception as e:
        logger.error(f"获取打赏记录异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取打赏记录失败")


@router.get("/statistics")
async def get_tip_statistics(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取打赏统计（大厨端）
    
    返回大厨收到的打赏统计数据。
    """
    try:
        # 验证是大厨角色
        if current_user.get("role") != "chef":
            return error_response(code=403, message="仅大厨可查看打赏统计")
        
        tip_service = TipService(db)
        statistics = tip_service.get_chef_tip_statistics(current_user["user_id"])
        
        return success_response(data=statistics)
        
    except Exception as e:
        logger.error(f"获取打赏统计异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取打赏统计失败")


@router.get("/{tip_id}")
async def get_tip_detail(
    tip_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取打赏详情
    
    返回指定打赏记录的详细信息。
    """
    try:
        tip_service = TipService(db)
        tip = tip_service.get_tip_by_id(tip_id)
        
        if not tip:
            return error_response(code=404, message="打赏记录不存在")
        
        # 验证权限：只有打赏者或被打赏者可以查看
        if tip.foodie_id != current_user["user_id"] and tip.chef_id != current_user["user_id"]:
            return error_response(code=403, message="无权查看此打赏记录")
        
        tip_data = {
            "id": tip.id,
            "chef_id": tip.chef_id,
            "foodie_id": tip.foodie_id,
            "amount": float(tip.amount),
            "message": tip.message,
            "order_id": tip.order_id,
            "status": tip.status,
            "payment_id": tip.payment_id,
            "created_at": tip.created_at.isoformat() if tip.created_at else None
        }
        
        # 添加大厨信息
        if tip.chef:
            tip_data["chef"] = {
                "id": tip.chef.id,
                "nickname": tip.chef.nickname,
                "avatar": tip.chef.avatar
            }
        
        # 添加吃货信息
        if tip.foodie:
            tip_data["foodie"] = {
                "id": tip.foodie.id,
                "nickname": tip.foodie.nickname,
                "avatar": tip.foodie.avatar
            }
        
        return success_response(data=tip_data)
        
    except Exception as e:
        logger.error(f"获取打赏详情异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取打赏详情失败")

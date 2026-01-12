"""
收益管理API接口。

为大厨提供收益统计、图表数据和收益明细查询功能。

Requirements:
- 14.1: 收益汇总（总收益、订单收益、打赏收益）
- 14.2: 收益图表（周/月聚合数据）
- 14.3: 收益明细（分页交易列表）
"""
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.common import success_response, error_response, paginated_response
from app.middleware.auth import get_current_user, require_chef
from app.services.earnings_service import EarningsService, EarningsServiceError


router = APIRouter(prefix="/chef/earnings", tags=["收益管理"])


# ============ API接口 ============

@router.get("/summary")
async def get_earnings_summary(
    current_user: User = Depends(require_chef),
    db: Session = Depends(get_db)
):
    """
    获取大厨收益汇总。
    
    返回大厨的收益统计数据，包括：
    - total_earnings: 总收益
    - order_earnings: 订单收益
    - tip_earnings: 打赏收益
    - this_month: 本月收益
    - this_week: 本周收益
    
    Requirements: 14.1
    """
    try:
        service = EarningsService(db)
        summary = service.get_earnings_summary(current_user.id)
        return success_response(data=summary)
    except EarningsServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"获取收益汇总失败: {str(e)}")


@router.get("/chart")
async def get_earnings_chart(
    type: str = Query("weekly", description="图表类型: weekly(最近7天) 或 monthly(最近30天)"),
    current_user: User = Depends(require_chef),
    db: Session = Depends(get_db)
):
    """
    获取收益图表数据。
    
    返回按日期聚合的收益数据，用于前端图表展示。
    
    Query Parameters:
    - type: 图表类型
      - weekly: 最近7天的每日收益
      - monthly: 最近30天的每日收益
    
    返回数据格式：
    - type: 图表类型
    - labels: 日期标签数组
    - datasets: 数据集
      - order: 订单收益数组
      - tip: 打赏收益数组
      - total: 总收益数组
    
    Requirements: 14.2
    """
    try:
        service = EarningsService(db)
        chart_data = service.get_earnings_chart(current_user.id, type)
        return success_response(data=chart_data)
    except EarningsServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"获取收益图表失败: {str(e)}")


@router.get("/detail")
async def get_earnings_detail(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    start_date: Optional[date] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    type: Optional[str] = Query(None, description="交易类型筛选: order(订单) 或 tip(打赏)"),
    current_user: User = Depends(require_chef),
    db: Session = Depends(get_db)
):
    """
    获取收益明细列表。
    
    返回分页的交易记录列表，包括订单收入和打赏收入。
    
    Query Parameters:
    - page: 页码，默认1
    - page_size: 每页数量，默认10，最大100
    - start_date: 开始日期筛选（可选）
    - end_date: 结束日期筛选（可选）
    - type: 交易类型筛选（可选）：order(订单收入) 或 tip(打赏收入)
    
    返回数据格式（每条记录）：
    - id: 记录ID
    - type: 类型 (order/tip)
    - amount: 金额
    - description: 描述
    - created_at: 创建时间
    - order_no: 订单号（订单类型）
    - message: 留言（打赏类型）
    - foodie: 吃货信息
    
    Requirements: 14.3
    """
    try:
        service = EarningsService(db)
        records, total = service.get_earnings_detail(
            chef_id=current_user.id,
            page=page,
            page_size=page_size,
            start_date=start_date,
            end_date=end_date,
            transaction_type=type
        )
        
        return paginated_response(
            data=records,
            page=page,
            page_size=page_size,
            total=total
        )
    except EarningsServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"获取收益明细失败: {str(e)}")

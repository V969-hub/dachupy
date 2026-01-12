"""
通知管理API接口。

Requirements:
- 13.4: 返回分页通知列表，按时间排序
- 13.5: 标记通知为已读
- 13.6: 返回未读通知数量
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.common import success_response, error_response, paginated_response
from app.middleware.auth import get_current_user
from app.services.notification_service import (
    get_user_notifications,
    get_notification_by_id,
    get_unread_count,
    mark_as_read,
    mark_all_as_read,
    notification_to_dict,
    NotificationServiceError
)


router = APIRouter(prefix="/notifications", tags=["通知"])


# ============ API接口 ============

@router.get("")
async def list_notifications(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    type: Optional[str] = Query(None, description="通知类型筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取当前用户的通知列表。
    
    返回分页的通知列表，按创建时间倒序排列。
    
    Query Parameters:
    - page: 页码，默认1
    - page_size: 每页数量，默认20，最大100
    - type: 通知类型筛选（可选）：new_order, order_status, binding, tip, system
    
    Requirements: 13.4
    """
    try:
        notifications, total = get_user_notifications(
            db=db,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            notification_type=type
        )
        
        notification_list = [notification_to_dict(n) for n in notifications]
        
        return paginated_response(
            data=notification_list,
            page=page,
            page_size=page_size,
            total=total
        )
    except Exception as e:
        return error_response(500, f"获取通知列表失败: {str(e)}")


@router.get("/unread-count")
async def get_unread_notification_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取当前用户的未读通知数量。
    
    Requirements: 13.6
    """
    try:
        count = get_unread_count(db, current_user.id)
        return success_response(data={"unread_count": count})
    except Exception as e:
        return error_response(500, f"获取未读数量失败: {str(e)}")


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    标记指定通知为已读。
    
    只能标记自己的通知。
    
    Requirements: 13.5
    """
    # 获取通知
    notification = get_notification_by_id(db, notification_id)
    if not notification:
        return error_response(404, "通知不存在")
    
    try:
        updated_notification = mark_as_read(db, notification, current_user.id)
        return success_response(
            data=notification_to_dict(updated_notification),
            message="已标记为已读"
        )
    except NotificationServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"标记已读失败: {str(e)}")


@router.put("/read-all")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    标记当前用户所有通知为已读。
    
    Requirements: 13.5
    """
    try:
        updated_count = mark_all_as_read(db, current_user.id)
        return success_response(
            data={"updated_count": updated_count},
            message=f"已将{updated_count}条通知标记为已读"
        )
    except Exception as e:
        return error_response(500, f"标记全部已读失败: {str(e)}")

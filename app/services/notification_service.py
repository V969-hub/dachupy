"""
通知服务模块 - 处理系统通知的创建、查询和管理。

Requirements:
- 13.1: 订单创建时为大厨创建通知
- 13.2: 订单状态变更时为相关用户创建通知
- 13.3: 绑定发生时为双方创建通知
- 13.4: 返回分页通知列表，按时间排序
- 13.5: 标记通知为已读
- 13.6: 返回未读通知数量
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.notification import Notification


class NotificationServiceError(Exception):
    """通知服务异常"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


def get_notification_by_id(db: Session, notification_id: str) -> Optional[Notification]:
    """
    根据ID获取通知。
    
    Args:
        db: 数据库会话
        notification_id: 通知ID
        
    Returns:
        通知对象，如果不存在则返回None
    """
    return db.query(Notification).filter(
        Notification.id == notification_id
    ).first()


def get_user_notifications(
    db: Session,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    notification_type: Optional[str] = None
) -> tuple[List[Notification], int]:
    """
    获取用户的通知列表，按时间倒序排列。
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        page: 页码（从1开始）
        page_size: 每页数量
        notification_type: 通知类型筛选（可选）
        
    Returns:
        (通知列表, 总数量)
        
    Requirements: 13.4
    """
    query = db.query(Notification).filter(Notification.user_id == user_id)
    
    # 按类型筛选
    if notification_type:
        query = query.filter(Notification.type == notification_type)
    
    # 获取总数
    total = query.count()
    
    # 分页查询，按创建时间倒序
    notifications = query.order_by(
        desc(Notification.created_at)
    ).offset((page - 1) * page_size).limit(page_size).all()
    
    return notifications, total


def get_unread_count(db: Session, user_id: str) -> int:
    """
    获取用户未读通知数量。
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        未读通知数量
        
    Requirements: 13.6
    """
    return db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False
    ).count()


def mark_as_read(db: Session, notification: Notification, user_id: str) -> Notification:
    """
    标记通知为已读。
    
    Args:
        db: 数据库会话
        notification: 通知对象
        user_id: 当前用户ID（用于验证所有权）
        
    Returns:
        更新后的通知对象
        
    Raises:
        NotificationServiceError: 如果无权限
        
    Requirements: 13.5
    """
    # 验证所有权
    if notification.user_id != user_id:
        raise NotificationServiceError("无权操作此通知", code=403)
    
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    
    return notification



def mark_all_as_read(db: Session, user_id: str) -> int:
    """
    标记用户所有通知为已读。
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        更新的通知数量
        
    Requirements: 13.5
    """
    result = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False
    ).update({"is_read": True})
    
    db.commit()
    
    return result


def create_notification(
    db: Session,
    user_id: str,
    notification_type: str,
    title: str,
    content: str,
    data: Optional[Dict[str, Any]] = None
) -> Notification:
    """
    创建新通知。
    
    Args:
        db: 数据库会话
        user_id: 接收通知的用户ID
        notification_type: 通知类型 (new_order, order_status, binding, tip, system)
        title: 通知标题
        content: 通知内容
        data: 附加数据（可选）
        
    Returns:
        创建的通知对象
        
    Requirements: 13.1, 13.2, 13.3
    """
    # 验证通知类型
    valid_types = ["new_order", "order_status", "binding", "tip", "system"]
    if notification_type not in valid_types:
        raise NotificationServiceError(f"无效的通知类型: {notification_type}")
    
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        content=content,
        data=data
    )
    
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
    return notification


def create_order_notification(
    db: Session,
    user_id: str,
    order_no: str,
    order_id: str,
    title: str,
    content: str,
    is_new_order: bool = False
) -> Notification:
    """
    创建订单相关通知。
    
    Args:
        db: 数据库会话
        user_id: 接收通知的用户ID
        order_no: 订单号
        order_id: 订单ID
        title: 通知标题
        content: 通知内容
        is_new_order: 是否是新订单通知
        
    Returns:
        创建的通知对象
        
    Requirements: 13.1, 13.2
    """
    notification_type = "new_order" if is_new_order else "order_status"
    data = {
        "order_id": order_id,
        "order_no": order_no
    }
    
    return create_notification(
        db=db,
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        content=content,
        data=data
    )


def create_binding_notification(
    db: Session,
    user_id: str,
    binding_id: str,
    title: str,
    content: str
) -> Notification:
    """
    创建绑定相关通知。
    
    Args:
        db: 数据库会话
        user_id: 接收通知的用户ID
        binding_id: 绑定关系ID
        title: 通知标题
        content: 通知内容
        
    Returns:
        创建的通知对象
        
    Requirements: 13.3
    """
    data = {"binding_id": binding_id}
    
    return create_notification(
        db=db,
        user_id=user_id,
        notification_type="binding",
        title=title,
        content=content,
        data=data
    )


def create_tip_notification(
    db: Session,
    user_id: str,
    tip_id: str,
    amount: float,
    title: str,
    content: str
) -> Notification:
    """
    创建打赏相关通知。
    
    Args:
        db: 数据库会话
        user_id: 接收通知的用户ID（大厨）
        tip_id: 打赏ID
        amount: 打赏金额
        title: 通知标题
        content: 通知内容
        
    Returns:
        创建的通知对象
    """
    data = {
        "tip_id": tip_id,
        "amount": float(amount)
    }
    
    return create_notification(
        db=db,
        user_id=user_id,
        notification_type="tip",
        title=title,
        content=content,
        data=data
    )


def notification_to_dict(notification: Notification) -> dict:
    """
    将通知对象转换为字典。
    
    Args:
        notification: 通知对象
        
    Returns:
        通知信息字典
    """
    return {
        "id": notification.id,
        "type": notification.type,
        "title": notification.title,
        "content": notification.content,
        "data": notification.data,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat() if notification.created_at else None
    }

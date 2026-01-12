"""
Notification model for the private chef booking system.
Handles system notifications for users.
"""
from sqlalchemy import Column, String, Enum, JSON, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Notification(Base):
    """
    Notification table storing user notifications.
    
    Requirements:
    - 13.1: Notification creation for order events
    """
    __tablename__ = "notifications"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    type = Column(
        Enum("new_order", "order_status", "binding", "tip", "system", name="notification_type"),
        nullable=False,
        comment="通知类型"
    )
    title = Column(String(64), nullable=False, comment="标题")
    content = Column(String(256), nullable=False, comment="内容")
    data = Column(JSON, nullable=True, comment="附加数据")
    is_read = Column(Boolean, default=False, comment="是否已读")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # Relationships
    user = relationship("User", backref="notifications")
    
    def __repr__(self):
        return f"<Notification(id={self.id}, type={self.type}, is_read={self.is_read})>"

"""
Admin console specific models.
"""
import uuid

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.database import Base


class AdminBroadcast(Base):
    """
    Broadcast record for system-wide admin notifications.
    """
    __tablename__ = "admin_broadcasts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(64), nullable=False, comment="广播标题")
    content = Column(String(256), nullable=False, comment="广播内容")
    target_role = Column(String(16), nullable=True, comment="目标角色")
    recipient_count = Column(Integer, default=0, comment="接收人数")
    created_by = Column(String(64), nullable=False, comment="创建人")
    filters = Column(JSON, nullable=True, comment="筛选条件快照")
    note = Column(Text, nullable=True, comment="补充说明")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    def __repr__(self):
        return f"<AdminBroadcast(id={self.id}, recipient_count={self.recipient_count})>"

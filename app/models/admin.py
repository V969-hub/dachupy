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


class AdminOperationLog(Base):
    """
    Admin operation audit log.
    """
    __tablename__ = "admin_operation_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    operator_username = Column(String(64), nullable=False, comment="操作账号")
    operator_name = Column(String(64), nullable=False, comment="操作人名称")
    action_type = Column(String(64), nullable=False, comment="操作类型")
    target_type = Column(String(32), nullable=False, comment="目标类型")
    target_id = Column(String(64), nullable=True, comment="目标ID")
    summary = Column(String(255), nullable=False, comment="操作摘要")
    detail = Column(JSON, nullable=True, comment="操作详情")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    def __repr__(self):
        return (
            f"<AdminOperationLog(id={self.id}, action_type={self.action_type}, "
            f"target_type={self.target_type})>"
        )

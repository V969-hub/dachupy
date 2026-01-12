"""
Tip model for the private chef booking system.
Handles tips from foodies to chefs.
"""
from sqlalchemy import Column, String, Enum, DECIMAL, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Tip(Base):
    """
    Tip table storing tip records.
    
    Requirements:
    - 10.1: Tip creation with WeChat payment
    """
    __tablename__ = "tips"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    foodie_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="吃货ID")
    chef_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="大厨ID")
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=True, comment="关联订单ID")
    amount = Column(DECIMAL(10, 2), nullable=False, comment="打赏金额")
    message = Column(String(256), nullable=True, comment="留言")
    payment_id = Column(String(64), nullable=True, comment="微信支付订单号")
    status = Column(
        Enum("pending", "paid", "failed", name="tip_status"),
        default="pending",
        comment="支付状态"
    )
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # Relationships
    foodie = relationship("User", foreign_keys=[foodie_id], backref="tips_given")
    chef = relationship("User", foreign_keys=[chef_id], backref="tips_received")
    order = relationship("Order", backref="tips")
    
    def __repr__(self):
        return f"<Tip(id={self.id}, amount={self.amount}, status={self.status})>"

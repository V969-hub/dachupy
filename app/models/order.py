"""
Order model for the private chef booking system.
Handles order information and order items.
"""
from sqlalchemy import Column, String, Enum, Text, JSON, DECIMAL, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Order(Base):
    """
    Order table storing booking orders.
    
    Requirements:
    - 6.1: Order creation with dish availability and quantity validation
    - 6.2: Unique order number generation
    """
    __tablename__ = "orders"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_no = Column(String(32), unique=True, nullable=False, comment="订单号")
    foodie_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="吃货ID")
    chef_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="大厨ID")
    status = Column(
        Enum("unpaid", "pending", "accepted", "cooking", "delivering", "completed", "cancelled", 
             name="order_status"),
        default="unpaid",
        comment="订单状态"
    )
    total_price = Column(DECIMAL(10, 2), nullable=False, comment="总价")
    delivery_time = Column(DateTime, nullable=False, comment="配送时间")
    address_snapshot = Column(JSON, nullable=False, comment="地址快照")
    remarks = Column(Text, nullable=True, comment="备注")
    cancel_reason = Column(String(256), nullable=True, comment="取消原因")
    is_reviewed = Column(Boolean, default=False, comment="是否已评价")
    payment_id = Column(String(64), nullable=True, comment="微信支付订单号")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    
    # Relationships
    foodie = relationship("User", foreign_keys=[foodie_id], backref="orders_as_foodie")
    chef = relationship("User", foreign_keys=[chef_id], backref="orders_as_chef")
    items = relationship("OrderItem", backref="order", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Order(id={self.id}, order_no={self.order_no}, status={self.status})>"


class OrderItem(Base):
    """
    Order item table storing individual items in an order.
    Stores snapshot of dish information at time of order.
    """
    __tablename__ = "order_items"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, comment="订单ID")
    dish_id = Column(String(36), nullable=False, comment="菜品ID")
    dish_name = Column(String(128), nullable=False, comment="菜品名称快照")
    dish_image = Column(String(512), nullable=True, comment="菜品图片快照")
    price = Column(DECIMAL(10, 2), nullable=False, comment="单价快照")
    quantity = Column(Integer, default=1, comment="数量")
    
    def __repr__(self):
        return f"<OrderItem(id={self.id}, dish_name={self.dish_name}, quantity={self.quantity})>"

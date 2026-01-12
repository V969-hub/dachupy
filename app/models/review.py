"""
Review model for the private chef booking system.
Handles order reviews and ratings.
"""
from sqlalchemy import Column, String, Text, JSON, Boolean, DateTime, ForeignKey, SmallInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Review(Base):
    """
    Review table storing order reviews.
    
    Requirements:
    - 9.1: Review submission for completed orders
    """
    __tablename__ = "reviews"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False, comment="订单ID")
    foodie_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="吃货ID")
    chef_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="大厨ID")
    dish_id = Column(String(36), ForeignKey("dishes.id"), nullable=False, comment="菜品ID")
    rating = Column(SmallInteger, nullable=False, comment="评分1-5")
    content = Column(Text, nullable=True, comment="评价内容")
    images = Column(JSON, nullable=True, comment="评价图片")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # Relationships
    order = relationship("Order", backref="reviews")
    foodie = relationship("User", foreign_keys=[foodie_id], backref="reviews_given")
    chef = relationship("User", foreign_keys=[chef_id], backref="reviews_received")
    dish = relationship("Dish", backref="reviews")
    
    def __repr__(self):
        return f"<Review(id={self.id}, rating={self.rating})>"

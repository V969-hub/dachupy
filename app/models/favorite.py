"""
Favorite model for the private chef booking system.
Handles user dish favorites.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Favorite(Base):
    """
    Favorite table storing user dish favorites.
    
    Requirements:
    - 15.1: Favorite creation for dishes
    """
    __tablename__ = "favorites"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    dish_id = Column(String(36), ForeignKey("dishes.id"), nullable=False, comment="菜品ID")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # Unique constraint for user-dish combination
    __table_args__ = (
        UniqueConstraint('user_id', 'dish_id', name='uk_user_dish'),
    )
    
    # Relationships
    user = relationship("User", backref="favorites")
    dish = relationship("Dish", backref="favorited_by")
    
    def __repr__(self):
        return f"<Favorite(id={self.id}, user_id={self.user_id}, dish_id={self.dish_id})>"

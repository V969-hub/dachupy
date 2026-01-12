"""
Dish model for the private chef booking system.
Handles dish information and daily quantity tracking.
"""
from sqlalchemy import Column, String, Text, JSON, DECIMAL, Integer, Boolean, DateTime, Date, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Dish(Base):
    """
    Dish table storing chef's menu items.
    
    Requirements:
    - 4.1: Dish creation with required fields (name, price, images, ingredients)
    - 4.2: Dish saved with chef's ID
    """
    __tablename__ = "dishes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chef_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="大厨ID")
    name = Column(String(128), nullable=False, comment="菜品名称")
    price = Column(DECIMAL(10, 2), nullable=False, comment="价格")
    images = Column(JSON, nullable=False, comment="图片URL列表")
    description = Column(Text, nullable=True, comment="描述")
    ingredients = Column(JSON, nullable=True, comment="食材列表")
    tags = Column(JSON, nullable=True, comment="口味标签")
    category = Column(String(32), nullable=True, comment="菜系分类")
    available_dates = Column(JSON, nullable=True, comment="可预订日期")
    max_quantity = Column(Integer, default=10, comment="每日最大份数")
    rating = Column(DECIMAL(2, 1), default=5.0, comment="评分")
    review_count = Column(Integer, default=0, comment="评价数")
    is_on_shelf = Column(Boolean, default=True, comment="是否上架")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # Relationships
    chef = relationship("User", backref="dishes")
    
    def __repr__(self):
        return f"<Dish(id={self.id}, name={self.name}, price={self.price})>"


class DailyDishQuantity(Base):
    """
    Daily dish quantity tracking table.
    Tracks booked quantities per dish per date.
    """
    __tablename__ = "daily_dish_quantities"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dish_id = Column(String(36), ForeignKey("dishes.id"), nullable=False, comment="菜品ID")
    date = Column(Date, nullable=False, comment="日期")
    booked_quantity = Column(Integer, default=0, comment="已预订数量")
    
    # Relationships
    dish = relationship("Dish", backref="daily_quantities")
    
    def __repr__(self):
        return f"<DailyDishQuantity(dish_id={self.dish_id}, date={self.date}, booked={self.booked_quantity})>"

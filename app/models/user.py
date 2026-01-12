"""
User model for the private chef booking system.
Handles both foodie (customer) and chef roles.
"""
from sqlalchemy import Column, String, Enum, Text, JSON, DECIMAL, Integer, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base
import uuid


class User(Base):
    """
    User table storing both foodie and chef information.
    
    Requirements:
    - 2.1: WeChat login with openId
    - 2.2: Phone binding support
    - 3.1: User profile with avatar, nickname, bindingCode
    """
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    open_id = Column(String(64), unique=True, nullable=False, comment="微信openId")
    nickname = Column(String(64), default="", comment="昵称")
    avatar = Column(String(512), default="", comment="头像URL")
    phone = Column(String(20), nullable=True, comment="手机号")
    role = Column(Enum("foodie", "chef", name="user_role"), default="foodie", comment="角色")
    binding_code = Column(String(8), unique=True, nullable=False, comment="专属绑定码")
    introduction = Column(Text, nullable=True, comment="大厨简介")
    specialties = Column(JSON, nullable=True, comment="大厨擅长菜系")
    rating = Column(DECIMAL(2, 1), default=5.0, comment="大厨评分")
    total_orders = Column(Integer, default=0, comment="总订单数")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    def __repr__(self):
        return f"<User(id={self.id}, nickname={self.nickname}, role={self.role})>"

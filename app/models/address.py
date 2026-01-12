"""
Address model for the private chef booking system.
Handles user delivery addresses.
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Address(Base):
    """
    Address table storing user delivery addresses.
    
    Requirements:
    - 11.1: Address management with user ID
    """
    __tablename__ = "addresses"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="用户ID")
    name = Column(String(32), nullable=False, comment="联系人")
    phone = Column(String(20), nullable=False, comment="联系电话")
    province = Column(String(32), nullable=False, comment="省")
    city = Column(String(32), nullable=False, comment="市")
    district = Column(String(32), nullable=False, comment="区")
    detail = Column(String(256), nullable=False, comment="详细地址")
    is_default = Column(Boolean, default=False, comment="是否默认")
    is_deleted = Column(Boolean, default=False, comment="是否删除")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # Relationships
    user = relationship("User", backref="addresses")
    
    def __repr__(self):
        return f"<Address(id={self.id}, name={self.name}, is_default={self.is_default})>"

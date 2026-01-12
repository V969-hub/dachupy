"""
Binding model for the private chef booking system.
Handles exclusive binding between foodies and chefs.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Binding(Base):
    """
    Binding table storing foodie-chef binding relationships.
    Each foodie can only bind to one chef at a time.
    
    Requirements:
    - 12.1: Binding code validation and relationship creation
    """
    __tablename__ = "bindings"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    foodie_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False, comment="吃货ID")
    chef_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="大厨ID")
    binding_code = Column(String(8), nullable=False, comment="使用的绑定码")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    
    # Relationships
    foodie = relationship("User", foreign_keys=[foodie_id], backref="binding_as_foodie")
    chef = relationship("User", foreign_keys=[chef_id], backref="bindings_as_chef")
    
    def __repr__(self):
        return f"<Binding(id={self.id}, foodie_id={self.foodie_id}, chef_id={self.chef_id})>"

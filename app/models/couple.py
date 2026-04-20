"""
Couple-related models for the shared memo MVP.
"""
from sqlalchemy import Column, String, Date, DateTime, ForeignKey, Boolean, Text, Integer, Enum, JSON, DECIMAL
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
import uuid


class CoupleRelationship(Base):
    """One-to-one active relationship between two users."""
    __tablename__ = "couple_relationships"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_a_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="关系用户A")
    user_b_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment="关系用户B")
    anniversary_date = Column(Date, nullable=True, comment="在一起日期")
    status = Column(
        Enum("active", "inactive", name="couple_relationship_status"),
        nullable=False,
        default="active",
        comment="关系状态"
    )
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    user_a = relationship("User", foreign_keys=[user_a_id])
    user_b = relationship("User", foreign_keys=[user_b_id])


class CoupleMemo(Base):
    """Shared memos under one relationship."""
    __tablename__ = "couple_memos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    relationship_id = Column(String(36), ForeignKey("couple_relationships.id"), nullable=False, comment="情侣关系ID")
    title = Column(String(100), nullable=False, comment="标题")
    content = Column(Text, nullable=True, comment="内容")
    category = Column(String(32), nullable=False, default="日常", comment="分类")
    remind_at = Column(DateTime, nullable=True, comment="提醒时间")
    is_completed = Column(Boolean, default=False, nullable=False, comment="是否已完成")
    is_pinned = Column(Boolean, default=False, nullable=False, comment="是否置顶")
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False, comment="创建人")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    couple_relationship = relationship("CoupleRelationship", backref="memos")
    creator = relationship("User")


class CoupleAnniversary(Base):
    """Shared anniversaries under one relationship."""
    __tablename__ = "couple_anniversaries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    relationship_id = Column(String(36), ForeignKey("couple_relationships.id"), nullable=False, comment="情侣关系ID")
    title = Column(String(100), nullable=False, comment="标题")
    date = Column(Date, nullable=False, comment="纪念日日期")
    type = Column(String(32), nullable=False, default="自定义", comment="纪念日类型")
    remind_days_before = Column(Integer, nullable=False, default=0, comment="提前提醒天数")
    note = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    couple_relationship = relationship("CoupleRelationship", backref="anniversaries")


class CoupleDatePlan(Base):
    """Date/meal plans shared by a couple."""
    __tablename__ = "couple_date_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    relationship_id = Column(String(36), ForeignKey("couple_relationships.id"), nullable=False, comment="情侣关系ID")
    title = Column(String(100), nullable=False, comment="计划标题")
    plan_at = Column(DateTime, nullable=False, comment="约饭时间")
    location = Column(String(128), nullable=True, comment="约饭地点")
    note = Column(Text, nullable=True, comment="备注")
    anniversary_id = Column(String(36), ForeignKey("couple_anniversaries.id"), nullable=True, comment="关联纪念日")
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=True, comment="关联订单")
    status = Column(
        Enum("planned", "completed", "cancelled", name="couple_date_plan_status"),
        nullable=False,
        default="planned",
        comment="计划状态"
    )
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False, comment="创建人")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    couple_relationship = relationship("CoupleRelationship", backref="date_plans")
    anniversary = relationship("CoupleAnniversary")
    order = relationship("Order")
    creator = relationship("User")


class CoupleRestaurantCategory(Base):
    """Shared restaurant categories maintained by a couple."""
    __tablename__ = "couple_restaurant_categories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    relationship_id = Column(String(36), ForeignKey("couple_relationships.id"), nullable=False, comment="情侣关系ID")
    name = Column(String(64), nullable=False, comment="分类名称")
    image = Column(String(255), nullable=True, comment="分类图片")
    sort_order = Column(Integer, nullable=False, default=0, comment="排序值")
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False, comment="创建人")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    couple_relationship = relationship("CoupleRelationship", backref="restaurant_categories")
    creator = relationship("User")


class CoupleRestaurantItem(Base):
    """Shared restaurant dishes/items maintained by a couple."""
    __tablename__ = "couple_restaurant_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    relationship_id = Column(String(36), ForeignKey("couple_relationships.id"), nullable=False, comment="情侣关系ID")
    category_id = Column(String(36), ForeignKey("couple_restaurant_categories.id"), nullable=False, comment="分类ID")
    name = Column(String(100), nullable=False, comment="菜名")
    price = Column(DECIMAL(10, 2), nullable=False, comment="价格")
    images = Column(JSON, nullable=False, comment="图片列表")
    description = Column(Text, nullable=True, comment="描述")
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False, comment="创建人")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    couple_relationship = relationship("CoupleRelationship", backref="restaurant_items")
    category = relationship("CoupleRestaurantCategory", backref="items")
    creator = relationship("User")

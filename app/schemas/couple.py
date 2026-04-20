"""
Couple memo MVP schemas.
"""
from datetime import date as date_type, datetime as datetime_type
from typing import Optional

from pydantic import BaseModel, Field


class BindCoupleRequest(BaseModel):
    partner_code: str = Field(..., description="对方情侣邀请码")
    anniversary_date: Optional[date_type] = Field(None, description="在一起日期")


class CoupleMemoCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="备忘录标题")
    content: Optional[str] = Field(None, description="备忘录内容")
    category: str = Field(default="日常", description="备忘录分类")
    remind_at: Optional[datetime_type] = Field(None, description="提醒时间")
    is_pinned: bool = Field(default=False, description="是否置顶")


class CoupleMemoUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100, description="备忘录标题")
    content: Optional[str] = Field(None, description="备忘录内容")
    category: Optional[str] = Field(None, description="备忘录分类")
    remind_at: Optional[datetime_type] = Field(None, description="提醒时间")
    is_pinned: Optional[bool] = Field(None, description="是否置顶")


class CoupleMemoStatusRequest(BaseModel):
    is_completed: bool = Field(..., description="是否完成")


class CoupleAnniversaryCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="纪念日标题")
    date: date_type = Field(..., description="纪念日日期")
    type: str = Field(default="自定义", description="纪念日类型")
    remind_days_before: int = Field(default=0, ge=0, le=30, description="提前提醒天数")
    note: Optional[str] = Field(None, description="纪念日备注")


class CoupleAnniversaryUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100, description="纪念日标题")
    date: Optional[date_type] = Field(None, description="纪念日日期")
    type: Optional[str] = Field(None, description="纪念日类型")
    remind_days_before: Optional[int] = Field(None, ge=0, le=30, description="提前提醒天数")
    note: Optional[str] = Field(None, description="纪念日备注")


class CoupleDatePlanCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="约饭计划标题")
    plan_at: datetime_type = Field(..., description="约饭时间")
    location: Optional[str] = Field(None, max_length=128, description="约饭地点")
    note: Optional[str] = Field(None, description="备注")
    anniversary_id: Optional[str] = Field(None, description="关联纪念日ID")
    order_id: Optional[str] = Field(None, description="关联订单ID")


class CoupleDatePlanUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100, description="约饭计划标题")
    plan_at: Optional[datetime_type] = Field(None, description="约饭时间")
    location: Optional[str] = Field(None, max_length=128, description="约饭地点")
    note: Optional[str] = Field(None, description="备注")
    anniversary_id: Optional[str] = Field(None, description="关联纪念日ID")
    order_id: Optional[str] = Field(None, description="关联订单ID")


class CoupleDatePlanStatusRequest(BaseModel):
    status: str = Field(..., description="计划状态：planned/completed/cancelled")


class CoupleRestaurantCategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="分类名称")
    image: Optional[str] = Field(None, description="分类图片")
    sort_order: int = Field(default=0, ge=0, le=9999, description="排序值")


class CoupleRestaurantCategoryUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64, description="分类名称")
    image: Optional[str] = Field(None, description="分类图片")
    sort_order: Optional[int] = Field(None, ge=0, le=9999, description="排序值")


class CoupleRestaurantCategorySortItem(BaseModel):
    id: str = Field(..., description="分类ID")
    sort_order: int = Field(..., ge=0, le=9999, description="排序值")


class CoupleRestaurantCategorySortRequest(BaseModel):
    categories: list[CoupleRestaurantCategorySortItem] = Field(
        ...,
        min_length=1,
        description="分类排序列表"
    )


class CoupleRestaurantItemCreateRequest(BaseModel):
    category_id: str = Field(..., description="分类ID")
    name: str = Field(..., min_length=1, max_length=100, description="菜名")
    price: float = Field(..., ge=0, description="金额")
    images: list[str] = Field(..., min_length=1, max_length=9, description="菜品图片列表")
    description: Optional[str] = Field(None, description="描述")


class CoupleRestaurantItemUpdateRequest(BaseModel):
    category_id: Optional[str] = Field(None, description="分类ID")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="菜名")
    price: Optional[float] = Field(None, ge=0, description="金额")
    images: Optional[list[str]] = Field(None, min_length=1, max_length=9, description="菜品图片列表")
    description: Optional[str] = Field(None, description="描述")

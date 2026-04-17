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

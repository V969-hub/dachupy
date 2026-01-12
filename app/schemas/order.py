"""
订单相关的Pydantic模型

用于请求验证和响应序列化。
"""
from typing import Optional, List, Any
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator


# ==================== 请求模型 ====================

class OrderItemCreate(BaseModel):
    """创建订单项请求"""
    dish_id: str = Field(..., description="菜品ID")
    quantity: int = Field(default=1, ge=1, description="数量")


class OrderCreate(BaseModel):
    """创建订单请求"""
    items: List[OrderItemCreate] = Field(..., min_length=1, description="订单项列表")
    delivery_time: datetime = Field(..., description="配送时间")
    address_id: str = Field(..., description="地址ID")
    remarks: Optional[str] = Field(None, max_length=500, description="备注")
    
    @field_validator('delivery_time')
    @classmethod
    def validate_delivery_time(cls, v):
        if v < datetime.now():
            raise ValueError("配送时间不能早于当前时间")
        return v


class OrderCancel(BaseModel):
    """取消订单请求"""
    reason: Optional[str] = Field(None, max_length=256, description="取消原因")


class OrderReject(BaseModel):
    """拒绝订单请求"""
    reason: str = Field(..., min_length=1, max_length=256, description="拒绝原因")


class OrderStatusUpdate(BaseModel):
    """更新订单状态请求"""
    status: str = Field(..., description="目标状态")


# ==================== 响应模型 ====================

class OrderItemResponse(BaseModel):
    """订单项响应"""
    id: str
    dish_id: str
    dish_name: str
    dish_image: Optional[str] = None
    price: float
    quantity: int
    subtotal: float
    
    class Config:
        from_attributes = True


class UserBrief(BaseModel):
    """用户简要信息"""
    id: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    phone: Optional[str] = None
    rating: Optional[float] = None
    
    class Config:
        from_attributes = True


class AddressSnapshot(BaseModel):
    """地址快照"""
    name: str
    phone: str
    province: str
    city: str
    district: str
    detail: str


class OrderResponse(BaseModel):
    """订单详情响应"""
    id: str
    order_no: str
    status: str
    total_price: float
    delivery_time: Optional[str] = None
    address: Optional[AddressSnapshot] = None
    remarks: Optional[str] = None
    cancel_reason: Optional[str] = None
    is_reviewed: bool = False
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    items: List[OrderItemResponse] = []
    foodie: Optional[UserBrief] = None
    chef: Optional[UserBrief] = None
    
    class Config:
        from_attributes = True


class OrderListItem(BaseModel):
    """订单列表项响应"""
    id: str
    order_no: str
    status: str
    total_price: float
    delivery_time: Optional[str] = None
    cover_image: Optional[str] = None
    item_count: int = 0
    is_reviewed: bool = False
    created_at: Optional[str] = None
    chef: Optional[UserBrief] = None
    
    class Config:
        from_attributes = True


class OrderCreateResponse(BaseModel):
    """创建订单响应"""
    order_id: str
    order_no: str
    total_price: float
    payment_params: Optional[dict] = None  # 微信支付参数


class PaymentParams(BaseModel):
    """微信支付参数"""
    timeStamp: str
    nonceStr: str
    package: str
    signType: str
    paySign: str

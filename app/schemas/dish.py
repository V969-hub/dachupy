"""
菜品相关的Pydantic模型

用于请求验证和响应序列化
"""
from typing import Optional, List
from decimal import Decimal
from datetime import date
from pydantic import BaseModel, Field


# ==================== 请求模型 ====================

class DishCreateRequest(BaseModel):
    """创建菜品请求"""
    name: str = Field(..., min_length=1, max_length=128, description="菜品名称")
    price: Decimal = Field(..., gt=0, description="价格")
    images: List[str] = Field(..., min_length=1, description="图片URL列表")
    description: Optional[str] = Field(None, description="描述")
    ingredients: Optional[List[str]] = Field(None, description="食材列表")
    tags: Optional[List[str]] = Field(None, description="口味标签")
    category: Optional[str] = Field(None, max_length=32, description="菜系分类")
    available_dates: Optional[List[str]] = Field(None, description="可预订日期")
    max_quantity: int = Field(10, ge=1, description="每日最大份数")


class DishUpdateRequest(BaseModel):
    """更新菜品请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=128, description="菜品名称")
    price: Optional[Decimal] = Field(None, gt=0, description="价格")
    images: Optional[List[str]] = Field(None, description="图片URL列表")
    description: Optional[str] = Field(None, description="描述")
    ingredients: Optional[List[str]] = Field(None, description="食材列表")
    tags: Optional[List[str]] = Field(None, description="口味标签")
    category: Optional[str] = Field(None, max_length=32, description="菜系分类")
    available_dates: Optional[List[str]] = Field(None, description="可预订日期")
    max_quantity: Optional[int] = Field(None, ge=1, description="每日最大份数")


class DishStatusRequest(BaseModel):
    """切换菜品状态请求"""
    is_on_shelf: bool = Field(..., description="是否上架")


# ==================== 响应模型 ====================

class ChefInfo(BaseModel):
    """大厨信息"""
    id: str
    nickname: str
    avatar: str
    rating: float
    introduction: Optional[str] = None
    specialties: List[str] = []
    
    class Config:
        from_attributes = True


class DishResponse(BaseModel):
    """菜品响应"""
    id: str
    name: str
    price: float
    images: List[str]
    description: Optional[str] = None
    ingredients: List[str] = []
    tags: List[str] = []
    category: Optional[str] = None
    available_dates: List[str] = []
    max_quantity: int
    rating: float
    review_count: int
    is_on_shelf: bool
    available_quantity: Optional[int] = None
    is_favorited: bool = False
    created_at: Optional[str] = None
    chef: Optional[ChefInfo] = None
    
    class Config:
        from_attributes = True


class DishListResponse(BaseModel):
    """菜品列表响应"""
    id: str
    name: str
    price: float
    images: List[str]
    tags: List[str] = []
    category: Optional[str] = None
    rating: float
    review_count: int
    available_quantity: Optional[int] = None
    is_favorited: bool = False
    chef: Optional[ChefInfo] = None
    
    class Config:
        from_attributes = True

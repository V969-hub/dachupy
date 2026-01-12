"""
User and authentication schemas for request/response validation.

Requirements:
- 2.1-2.4: Authentication request/response schemas
- 3.1-3.3: User profile schemas
"""
from typing import Optional, List
from pydantic import BaseModel, Field


# ============ Authentication Schemas ============

class LoginRequest(BaseModel):
    """Request schema for WeChat login."""
    code: str = Field(..., description="微信登录code")
    role: str = Field(default="foodie", description="用户角色: foodie 或 chef")
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": "wx_login_code_from_miniprogram",
                "role": "foodie"
            }
        }


class BindPhoneRequest(BaseModel):
    """Request schema for binding phone number."""
    encrypted_data: str = Field(..., description="微信加密数据")
    iv: str = Field(..., description="初始向量")
    
    class Config:
        json_schema_extra = {
            "example": {
                "encrypted_data": "base64_encrypted_data",
                "iv": "base64_iv"
            }
        }


class BoundChefInfo(BaseModel):
    """Schema for bound chef information."""
    id: str
    nickname: str
    avatar: str
    rating: float
    
    class Config:
        from_attributes = True


class UserInfo(BaseModel):
    """Schema for user information in responses."""
    id: str
    nickname: str
    avatar: str
    phone: Optional[str] = None
    role: str
    binding_code: str
    introduction: Optional[str] = None
    specialties: Optional[List[str]] = None
    rating: Optional[float] = None
    total_orders: Optional[int] = None
    bound_chef: Optional[BoundChefInfo] = None
    
    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Response schema for login endpoint."""
    token: str
    user: UserInfo


# ============ User Profile Schemas ============

class UserProfileUpdate(BaseModel):
    """Request schema for updating user profile."""
    nickname: Optional[str] = Field(None, max_length=64, description="昵称")
    avatar: Optional[str] = Field(None, max_length=512, description="头像URL")
    introduction: Optional[str] = Field(None, description="大厨简介")
    specialties: Optional[List[str]] = Field(None, description="擅长菜系")
    
    class Config:
        json_schema_extra = {
            "example": {
                "nickname": "张大厨",
                "avatar": "https://example.com/avatar.jpg",
                "introduction": "专注川菜20年",
                "specialties": ["川菜", "粤菜"]
            }
        }

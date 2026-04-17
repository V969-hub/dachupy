"""
User and authentication schemas for request/response validation.

Requirements:
- 2.1-2.4: Authentication request/response schemas
- 3.1-3.3: User profile schemas
"""
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


# ============ Authentication Schemas ============

class LoginRequest(BaseModel):
    """Request schema for WeChat login."""
    code: str = Field(..., description="微信登录code")
    role: str = Field(default="foodie", description="用户角色: foodie 或 chef")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "wx_login_code_from_miniprogram",
                "role": "foodie"
            }
        }
    )


class AccountLoginRequest(BaseModel):
    """Request schema for account-password login."""
    account: str = Field(..., description="用户账号")
    password: str = Field(..., description="用户密码（当前不校验）")
    role: str = Field(default="foodie", description="用户角色: foodie 或 chef")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "account": "demo_user",
                "password": "any_password",
                "role": "foodie"
            }
        }
    )


class BindPhoneRequest(BaseModel):
    """Request schema for binding phone number."""
    encrypted_data: Optional[str] = Field(default=None, description="微信加密数据")
    iv: Optional[str] = Field(default=None, description="初始向量")
    phone: Optional[str] = Field(default=None, description="直接绑定的手机号（H5/dev）")
    verify_code: Optional[str] = Field(default=None, description="短信验证码（当前仅校验格式）")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "13800138000",
                "verify_code": "123456"
            }
        }
    )


class BoundChefInfo(BaseModel):
    """Schema for bound chef information."""
    id: str
    nickname: str
    avatar: str
    rating: float
    
    model_config = ConfigDict(from_attributes=True)


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
    
    model_config = ConfigDict(from_attributes=True)


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
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nickname": "张大厨",
                "avatar": "https://example.com/avatar.jpg",
                "introduction": "专注川菜20年",
                "specialties": ["川菜", "粤菜"]
            }
        }
    )

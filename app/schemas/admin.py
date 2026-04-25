"""
Schemas for the admin console APIs.
"""
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="后台账号")
    password: str = Field(..., min_length=1, max_length=128, description="后台密码")


class AdminUserUpdateRequest(BaseModel):
    nickname: Optional[str] = Field(None, max_length=64, description="用户昵称")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    is_open: Optional[bool] = Field(None, description="是否营业中")
    is_deleted: Optional[bool] = Field(None, description="是否禁用")
    rest_notice: Optional[str] = Field(None, max_length=255, description="休息说明")

    model_config = ConfigDict(extra="forbid")


class AdminUserWalletTopUpRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, le=100000, description="增加虚拟币金额")
    note: Optional[str] = Field(None, max_length=120, description="后台备注")

    model_config = ConfigDict(extra="forbid")


class AdminDishUpdateRequest(BaseModel):
    is_on_shelf: Optional[bool] = Field(None, description="是否上架")
    is_deleted: Optional[bool] = Field(None, description="是否删除")
    category: Optional[str] = Field(None, max_length=32, description="菜品分类")
    max_quantity: Optional[int] = Field(None, ge=0, le=9999, description="每日最大份数")

    model_config = ConfigDict(extra="forbid")


class AdminOrderStatusUpdateRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=32, description="订单状态")
    cancel_reason: Optional[str] = Field(None, max_length=256, description="取消原因")

    model_config = ConfigDict(extra="forbid")


class AdminUserCreateRequest(BaseModel):
    account: str = Field(..., min_length=1, max_length=64, description="账号(open_id/account)")
    role: str = Field(..., min_length=1, max_length=16, description="角色")
    nickname: str = Field(default="", max_length=64, description="昵称")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    avatar: Optional[str] = Field(None, max_length=512, description="头像")
    introduction: Optional[str] = Field(None, description="大厨简介")
    specialties: Optional[list[str]] = Field(None, description="擅长菜系")
    is_open: bool = Field(default=True, description="是否营业")

    model_config = ConfigDict(extra="forbid")


class AdminBroadcastCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=64, description="广播标题")
    content: str = Field(..., min_length=1, max_length=256, description="广播内容")
    target_role: Optional[str] = Field(None, max_length=16, description="目标角色")
    user_ids: Optional[list[str]] = Field(None, description="指定接收用户ID")
    min_wallet_balance: Optional[Decimal] = Field(None, ge=0, description="最小虚拟币余额")
    max_wallet_balance: Optional[Decimal] = Field(None, ge=0, description="最大虚拟币余额")
    reward_amount: Optional[Decimal] = Field(None, gt=0, le=10000, description="随广播发放的虚拟币金额")
    note: Optional[str] = Field(None, description="补充说明")

    model_config = ConfigDict(extra="forbid")


class AdminRefundCreateRequest(BaseModel):
    amount: Optional[Decimal] = Field(None, gt=0, description="退款金额，默认剩余可退金额")
    reason: str = Field(..., min_length=1, max_length=256, description="退款原因")
    note: Optional[str] = Field(None, description="退款备注")
    mark_manual_processed: bool = Field(default=False, description="微信退款是否已在线下完成，仅登记记录")

    model_config = ConfigDict(extra="forbid")

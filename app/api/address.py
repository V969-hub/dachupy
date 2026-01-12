"""
地址管理API接口。

Requirements:
- 11.1: 添加地址时保存用户ID
- 11.2: 更新地址时验证所有权
- 11.3: 软删除地址
- 11.4: 设置默认地址时更新标志
- 11.5: 返回地址列表时默认地址排在前面
"""
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.common import success_response, error_response
from app.middleware.auth import get_current_user
from app.services.address_service import (
    get_user_addresses,
    get_address_by_id,
    create_address,
    update_address,
    delete_address,
    set_default_address,
    address_to_dict,
    AddressServiceError
)


router = APIRouter(prefix="/addresses", tags=["地址"])


# ============ 请求模型 ============

class AddressCreate(BaseModel):
    """创建地址请求"""
    name: str = Field(..., min_length=1, max_length=32, description="联系人姓名")
    phone: str = Field(..., min_length=1, max_length=20, description="联系电话")
    province: str = Field(..., min_length=1, max_length=32, description="省")
    city: str = Field(..., min_length=1, max_length=32, description="市")
    district: str = Field(..., min_length=1, max_length=32, description="区")
    detail: str = Field(..., min_length=1, max_length=256, description="详细地址")
    is_default: bool = Field(default=False, description="是否设为默认地址")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "张三",
                "phone": "13800138000",
                "province": "广东省",
                "city": "深圳市",
                "district": "南山区",
                "detail": "科技园南区XX栋XX号",
                "is_default": True
            }
        }


class AddressUpdate(BaseModel):
    """更新地址请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=32, description="联系人姓名")
    phone: Optional[str] = Field(None, min_length=1, max_length=20, description="联系电话")
    province: Optional[str] = Field(None, min_length=1, max_length=32, description="省")
    city: Optional[str] = Field(None, min_length=1, max_length=32, description="市")
    district: Optional[str] = Field(None, min_length=1, max_length=32, description="区")
    detail: Optional[str] = Field(None, min_length=1, max_length=256, description="详细地址")
    is_default: Optional[bool] = Field(None, description="是否设为默认地址")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "李四",
                "phone": "13900139000",
                "detail": "科技园北区YY栋YY号"
            }
        }


# ============ API接口 ============

@router.get("")
async def list_addresses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取当前用户的地址列表。
    
    返回用户所有未删除的地址，默认地址排在最前面。
    
    Requirements: 11.5
    """
    addresses = get_user_addresses(db, current_user.id)
    address_list = [address_to_dict(addr) for addr in addresses]
    return success_response(data=address_list)


@router.post("")
async def add_address(
    request: AddressCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    添加新地址。
    
    如果是用户的第一个地址，会自动设为默认地址。
    如果设置is_default为true，会取消其他地址的默认状态。
    
    Requirements: 11.1, 11.4
    """
    try:
        address = create_address(
            db=db,
            user_id=current_user.id,
            name=request.name,
            phone=request.phone,
            province=request.province,
            city=request.city,
            district=request.district,
            detail=request.detail,
            is_default=request.is_default
        )
        return success_response(
            data=address_to_dict(address),
            message="地址添加成功"
        )
    except AddressServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"添加地址失败: {str(e)}")


@router.put("/{address_id}")
async def modify_address(
    address_id: str,
    request: AddressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新地址信息。
    
    只能更新自己的地址，支持部分更新。
    
    Requirements: 11.2, 11.4
    """
    # 获取地址
    address = get_address_by_id(db, address_id)
    if not address:
        return error_response(404, "地址不存在")
    
    try:
        updated_address = update_address(
            db=db,
            address=address,
            user_id=current_user.id,
            name=request.name,
            phone=request.phone,
            province=request.province,
            city=request.city,
            district=request.district,
            detail=request.detail,
            is_default=request.is_default
        )
        return success_response(
            data=address_to_dict(updated_address),
            message="地址更新成功"
        )
    except AddressServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"更新地址失败: {str(e)}")


@router.delete("/{address_id}")
async def remove_address(
    address_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    删除地址（软删除）。
    
    只能删除自己的地址。如果删除的是默认地址，会自动将最新的地址设为默认。
    
    Requirements: 11.3
    """
    # 获取地址
    address = get_address_by_id(db, address_id)
    if not address:
        return error_response(404, "地址不存在")
    
    try:
        delete_address(db, address, current_user.id)
        return success_response(message="地址删除成功")
    except AddressServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"删除地址失败: {str(e)}")


@router.put("/{address_id}/default")
async def set_address_default(
    address_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    设置地址为默认地址。
    
    只能设置自己的地址为默认，会自动取消其他地址的默认状态。
    
    Requirements: 11.4
    """
    # 获取地址
    address = get_address_by_id(db, address_id)
    if not address:
        return error_response(404, "地址不存在")
    
    try:
        updated_address = set_default_address(db, address, current_user.id)
        return success_response(
            data=address_to_dict(updated_address),
            message="已设为默认地址"
        )
    except AddressServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"设置默认地址失败: {str(e)}")

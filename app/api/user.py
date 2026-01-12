"""
User profile API endpoints.

Requirements:
- 3.1: Return user info including avatar, nickname, bindingCode
- 3.2: Validate and save profile changes
- 3.3: Allow chef to update introduction and specialties
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.common import success_response, error_response
from app.schemas.user import UserProfileUpdate
from app.middleware.auth import get_current_user
from app.services.user_service import (
    get_user_profile_data,
    update_user_profile,
    UserServiceError
)


router = APIRouter(prefix="/user", tags=["用户"])


@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取当前用户个人信息。
    
    返回用户的完整个人信息，包括：
    - 基本信息：id, nickname, avatar, phone, role, binding_code
    - 大厨专属：introduction, specialties, rating, total_orders
    - 绑定信息：bound_chef（仅吃货）
    
    Requirements: 3.1
    """
    profile_data = get_user_profile_data(db, current_user)
    return success_response(data=profile_data)


@router.put("/profile")
async def update_profile(
    request: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新当前用户个人信息。
    
    可更新字段：
    - nickname: 昵称（所有用户）
    - avatar: 头像URL（所有用户）
    - introduction: 简介（仅大厨）
    - specialties: 擅长菜系（仅大厨）
    
    Requirements: 3.2, 3.3
    """
    try:
        updated_user = update_user_profile(
            db=db,
            user=current_user,
            nickname=request.nickname,
            avatar=request.avatar,
            introduction=request.introduction,
            specialties=request.specialties
        )
        
        # 返回更新后的完整用户信息
        profile_data = get_user_profile_data(db, updated_user)
        return success_response(data=profile_data, message="个人信息更新成功")
        
    except UserServiceError as e:
        return error_response(e.code, e.message)
    except Exception as e:
        return error_response(500, f"更新失败: {str(e)}")

"""
User service for managing user profiles.

Requirements:
- 3.1: Return user info including avatar, nickname, bindingCode
- 3.2: Validate and save profile changes
- 3.3: Allow chef to update introduction and specialties
"""
import re
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.binding import Binding
from app.services.business_status_service import (
    DEFAULT_SERVICE_END_TIME,
    DEFAULT_SERVICE_START_TIME,
    TIME_PATTERN,
    build_chef_business_status,
    get_chef_service_window,
    normalize_service_time,
    service_time_to_minutes,
)
from app.services.wallet_service import build_wallet_payload

PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


class UserServiceError(Exception):
    """用户服务异常"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """
    根据ID获取用户信息。
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        用户对象，如果不存在则返回None
        
    Requirements: 3.1
    """
    return db.query(User).filter(
        User.id == user_id,
        User.is_deleted == False
    ).first()


def get_bound_chef(db: Session, foodie_id: str) -> Optional[User]:
    """
    获取吃货绑定的大厨信息。
    
    Args:
        db: 数据库会话
        foodie_id: 吃货用户ID
        
    Returns:
        绑定的大厨用户对象，如果未绑定则返回None
        
    Requirements: 3.1
    """
    binding = db.query(Binding).filter(
        Binding.foodie_id == foodie_id
    ).first()
    
    if not binding:
        return None
    
    return db.query(User).filter(
        User.id == binding.chef_id,
        User.is_deleted == False
    ).first()


def update_user_profile(
    db: Session,
    user: User,
    nickname: Optional[str] = None,
    avatar: Optional[str] = None,
    phone: Optional[str] = None,
    is_open: Optional[bool] = None,
    service_start_time: Optional[str] = None,
    service_end_time: Optional[str] = None,
    rest_notice: Optional[str] = None,
    introduction: Optional[str] = None,
    specialties: Optional[List[str]] = None
) -> User:
    """
    更新用户个人信息。
    
    Args:
        db: 数据库会话
        user: 用户对象
        nickname: 新昵称（可选）
        avatar: 新头像URL（可选）
        introduction: 大厨简介（可选，仅大厨可用）
        specialties: 擅长菜系（可选，仅大厨可用）
        
    Returns:
        更新后的用户对象
        
    Raises:
        UserServiceError: 如果验证失败
        
    Requirements: 3.2, 3.3
    """
    # 更新基本信息（所有用户都可以更新）
    if nickname is not None:
        if len(nickname) > 64:
            raise UserServiceError("昵称长度不能超过64个字符")
        user.nickname = nickname
    
    if avatar is not None:
        if len(avatar) > 512:
            raise UserServiceError("头像URL长度不能超过512个字符")
        user.avatar = avatar

    if phone is not None:
        normalized_phone = phone.strip()
        if not normalized_phone:
            user.phone = None
        else:
            if len(normalized_phone) > 20:
                raise UserServiceError("手机号长度不能超过20个字符")
            if not PHONE_PATTERN.match(normalized_phone):
                raise UserServiceError("手机号格式不正确")
            user.phone = normalized_phone

    if any(value is not None for value in (is_open, service_start_time, service_end_time, rest_notice)):
        if user.role != "chef":
            raise UserServiceError("只有大厨可以设置营业状态", code=403)

    if is_open is not None:
        user.is_open = bool(is_open)

    next_start_time, next_end_time = get_chef_service_window(user)

    if service_start_time is not None:
        normalized_start_time = normalize_service_time(service_start_time, "")
        if not normalized_start_time or not TIME_PATTERN.fullmatch(normalized_start_time):
            raise UserServiceError("接单开始时间格式不正确，请使用 HH:MM")
        next_start_time = normalized_start_time

    if service_end_time is not None:
        normalized_end_time = normalize_service_time(service_end_time, "")
        if not normalized_end_time or not TIME_PATTERN.fullmatch(normalized_end_time):
            raise UserServiceError("接单结束时间格式不正确，请使用 HH:MM")
        next_end_time = normalized_end_time

    if service_start_time is not None or service_end_time is not None:
        if service_time_to_minutes(next_start_time) >= service_time_to_minutes(next_end_time):
            raise UserServiceError("接单结束时间需晚于开始时间")
        user.service_start_time = next_start_time
        user.service_end_time = next_end_time
    else:
        user.service_start_time = normalize_service_time(
            getattr(user, "service_start_time", None),
            DEFAULT_SERVICE_START_TIME,
        )
        user.service_end_time = normalize_service_time(
            getattr(user, "service_end_time", None),
            DEFAULT_SERVICE_END_TIME,
        )

    if rest_notice is not None:
        normalized_rest_notice = rest_notice.strip()
        if len(normalized_rest_notice) > 255:
            raise UserServiceError("休息说明长度不能超过255个字符")
        user.rest_notice = normalized_rest_notice or None

    # 大厨专属字段（仅大厨可以更新）
    if introduction is not None:
        if user.role != "chef":
            raise UserServiceError("只有大厨可以设置简介", code=403)
        user.introduction = introduction
    
    if specialties is not None:
        if user.role != "chef":
            raise UserServiceError("只有大厨可以设置擅长菜系", code=403)
        # 验证擅长菜系格式
        if not isinstance(specialties, list):
            raise UserServiceError("擅长菜系必须是列表格式")
        if len(specialties) > 10:
            raise UserServiceError("擅长菜系最多10个")
        user.specialties = specialties
    
    db.commit()
    db.refresh(user)
    
    return user


def get_user_profile_data(db: Session, user: User) -> dict:
    """
    获取用户完整的个人信息数据。
    
    包含用户基本信息，如果是吃货还包含绑定的大厨信息。
    
    Args:
        db: 数据库会话
        user: 用户对象
        
    Returns:
        用户信息字典
        
    Requirements: 3.1
    """
    profile_data = {
        "id": user.id,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "phone": user.phone,
        "role": user.role,
        "binding_code": user.binding_code,
        "wallet": build_wallet_payload(user),
        "business_status": build_chef_business_status(user) if user.role == "chef" else None,
        "introduction": user.introduction,
        "specialties": user.specialties,
        "rating": float(user.rating) if user.rating else 5.0,
        "total_orders": user.total_orders,
        "bound_chef": None
    }
    
    # 如果是吃货，获取绑定的大厨信息
    if user.role == "foodie":
        bound_chef = get_bound_chef(db, user.id)
        if bound_chef:
            profile_data["bound_chef"] = {
                "id": bound_chef.id,
                "nickname": bound_chef.nickname,
                "avatar": bound_chef.avatar,
                "introduction": bound_chef.introduction,
                "specialties": bound_chef.specialties or [],
                "rating": float(bound_chef.rating) if bound_chef.rating else 5.0,
                "business_status": build_chef_business_status(bound_chef),
            }

    return profile_data

"""
User service for managing user profiles.

Requirements:
- 3.1: Return user info including avatar, nickname, bindingCode
- 3.2: Validate and save profile changes
- 3.3: Allow chef to update introduction and specialties
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.binding import Binding


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
                "rating": float(bound_chef.rating) if bound_chef.rating else 5.0
            }
    
    return profile_data

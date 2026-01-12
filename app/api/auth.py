"""
Authentication API endpoints.

Requirements:
- 2.1: Exchange WeChat login code for openId via WeChat API
- 2.2: Create user record and return JWT token for new users
- 2.3: Return JWT token with user info for existing users
- 2.4: Update user record with phone when binding
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.binding import Binding
from app.schemas.common import success_response, error_response
from app.schemas.user import (
    LoginRequest, 
    LoginResponse, 
    BindPhoneRequest, 
    UserInfo,
    BoundChefInfo
)
from app.services.wechat_service import code2session, WeChatServiceError, decrypt_phone_number
from app.utils.security import create_token, generate_binding_code
from app.middleware.auth import get_current_user


router = APIRouter(prefix="/auth", tags=["认证"])


def _get_user_info(user: User, db: Session) -> UserInfo:
    """Helper to build UserInfo with bound chef information."""
    bound_chef = None
    
    if user.role == "foodie":
        # Check if foodie is bound to a chef
        binding = db.query(Binding).filter(
            Binding.foodie_id == user.id
        ).first()
        
        if binding:
            chef = db.query(User).filter(User.id == binding.chef_id).first()
            if chef:
                bound_chef = BoundChefInfo(
                    id=chef.id,
                    nickname=chef.nickname,
                    avatar=chef.avatar,
                    rating=float(chef.rating) if chef.rating else 5.0
                )
    
    return UserInfo(
        id=user.id,
        nickname=user.nickname,
        avatar=user.avatar,
        phone=user.phone,
        role=user.role,
        binding_code=user.binding_code,
        introduction=user.introduction,
        specialties=user.specialties,
        rating=float(user.rating) if user.rating else None,
        total_orders=user.total_orders,
        bound_chef=bound_chef
    )


@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    WeChat mini-program login endpoint.
    
    Exchanges WeChat login code for openId, creates user if new,
    and returns JWT token with user information.
    
    Requirements: 2.1, 2.2, 2.3
    """
    # Validate role
    if request.role not in ["foodie", "chef"]:
        return error_response(400, "Invalid role. Must be 'foodie' or 'chef'")
    
    try:
        # Exchange code for WeChat session
        wechat_session = await code2session(request.code)
        open_id = wechat_session.openid
    except WeChatServiceError as e:
        return error_response(400, f"WeChat login failed: {e.errmsg}")
    except Exception as e:
        return error_response(500, f"WeChat API error: {str(e)}")
    
    # Check if user exists
    user = db.query(User).filter(
        User.open_id == open_id,
        User.is_deleted == False
    ).first()
    
    if user is None:
        # Create new user (Requirement 2.2)
        # Generate unique binding code
        binding_code = generate_binding_code()
        while db.query(User).filter(User.binding_code == binding_code).first():
            binding_code = generate_binding_code()
        
        user = User(
            open_id=open_id,
            role=request.role,
            binding_code=binding_code,
            nickname="",
            avatar=""
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Create JWT token
    token = create_token(user_id=user.id, role=user.role)
    
    # Build user info with bound chef
    user_info = _get_user_info(user, db)
    
    return success_response(
        data=LoginResponse(
            token=token,
            user=user_info
        ).model_dump()
    )


@router.post("/bind-phone")
async def bind_phone(
    request: BindPhoneRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Bind phone number to user account.
    
    Decrypts WeChat encrypted phone data and updates user record.
    
    Requirements: 2.4
    """
    # For now, we'll store a placeholder since we need the session_key
    # In production, you'd store session_key during login and use it here
    # This is a simplified implementation
    
    # Note: In a real implementation, you would:
    # 1. Store session_key in cache (Redis) during login
    # 2. Retrieve it here to decrypt the phone number
    # For now, we'll accept the phone directly or return an error
    
    # Since we don't have session_key stored, we'll return an error
    # indicating this needs proper implementation with session storage
    return error_response(
        501, 
        "Phone binding requires session key storage. Please implement Redis/cache for session management."
    )


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user information.
    
    Requirements: 3.1
    """
    user_info = _get_user_info(current_user, db)
    return success_response(data=user_info.model_dump())

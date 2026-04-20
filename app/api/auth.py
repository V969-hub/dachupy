"""
Authentication API endpoints.

Requirements:
- 2.1: Exchange WeChat login code for openId via WeChat API
- 2.2: Create user record and return JWT token for new users
- 2.3: Return JWT token with user info for existing users
- 2.4: Update user record with phone when binding
"""
import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.binding import Binding
from app.schemas.common import success_response, error_response
from app.schemas.user import (
    LoginRequest, 
    AccountLoginRequest,
    LoginResponse, 
    BindPhoneRequest, 
    UserInfo,
    BoundChefInfo
)
from app.services.wechat_service import code2session, WeChatServiceError
from app.utils.security import create_token, generate_binding_code
from app.middleware.auth import get_current_user


router = APIRouter(prefix="/auth", tags=["认证"])
VALID_ROLES = {"foodie", "chef"}
PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")
MOCK_WECHAT_CODES = {"the code is a mock one", "mock", "test", "mock_code"}


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


def _validate_role(role: str):
    """Validate login role against supported roles."""
    if role not in VALID_ROLES:
        return error_response(400, "Invalid role. Must be 'foodie' or 'chef'")
    return None


def _generate_unique_binding_code(db: Session) -> str:
    """Generate a unique binding code that does not collide with existing users."""
    binding_code = generate_binding_code()
    while db.query(User).filter(User.binding_code == binding_code).first():
        binding_code = generate_binding_code()
    return binding_code


def _create_user(db: Session, open_id: str, role: str) -> User:
    """Create a new user record with the shared default values."""
    user = User(
        open_id=open_id,
        role=role,
        binding_code=_generate_unique_binding_code(db),
        nickname="",
        avatar=""
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _build_login_response(user: User, db: Session) -> dict:
    """Build the shared login response payload."""
    token = create_token(user_id=user.id, role=user.role)
    user_info = _get_user_info(user, db)
    return success_response(
        data=LoginResponse(
            token=token,
            user=user_info
        ).model_dump()
    )


@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    WeChat mini-program login endpoint.
    
    Exchanges WeChat login code for openId, creates user if new,
    and returns JWT token with user information.
    
    Requirements: 2.1, 2.2, 2.3
    """
    invalid_role_response = _validate_role(request.role)
    if invalid_role_response:
        return invalid_role_response

    if request.code.strip() in MOCK_WECHAT_CODES:
        return error_response(
            400,
            "Mock WeChat code is not supported on this endpoint. Use a real uni.login code in WeChat Mini Program, or use /api/auth/login/account for local/H5 testing."
        )
    
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
        try:
            user = _create_user(db, open_id=open_id, role=request.role)
        except Exception as e:
            db.rollback()
            return error_response(500, f"Database error: {str(e)}")

    return _build_login_response(user, db)


@router.post("/login/account")
async def account_login(request: AccountLoginRequest, db: Session = Depends(get_db)):
    """
    Account-password login endpoint.

    Accepts any password, uses account as the unique identifier,
    and returns the same response structure as WeChat login.
    """
    account = request.account.strip()
    if not account:
        return error_response(400, "Account cannot be empty")

    invalid_role_response = _validate_role(request.role)
    if invalid_role_response:
        return invalid_role_response

    try:
        user = db.query(User).filter(
            User.open_id == account,
            User.is_deleted == False
        ).first()

        if user is None:
            user = _create_user(db, open_id=account, role=request.role)
    except Exception as e:
        db.rollback()
        return error_response(500, f"Database error: {str(e)}")

    return _build_login_response(user, db)


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
    direct_phone = (request.phone or "").strip()
    if direct_phone:
        if not PHONE_PATTERN.match(direct_phone):
            return error_response(400, "Invalid phone number")

        if request.verify_code and not re.fullmatch(r"\d{6}", request.verify_code):
            return error_response(400, "Verification code must be 6 digits")

        current_user.phone = direct_phone
        db.commit()
        db.refresh(current_user)
        return success_response(
            data={"phone": current_user.phone},
            message="Phone number bound successfully"
        )

    if request.encrypted_data and request.iv:
        return error_response(
            501,
            "Phone binding requires session key storage. Please implement Redis/cache for session management."
        )

    return error_response(400, "Phone number or WeChat encrypted phone data is required")


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

"""
Authentication middleware for JWT-based authentication.

Requirements:
- 1.3: JWT-based authentication for all protected endpoints
- 2.5: Validate JWT token for all protected endpoints
- 2.6: Return 401 error for invalid/expired tokens
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.security import verify_token


# HTTP Bearer security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.
    
    Validates the JWT token and returns the user object.
    
    Args:
        credentials: HTTP Bearer credentials containing the JWT token
        db: Database session
        
    Returns:
        User object for the authenticated user
        
    Raises:
        HTTPException: 401 if token is invalid or user not found
        
    Requirements: 1.3, 2.5, 2.6
    """
    token = credentials.credentials
    
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user = db.query(User).filter(
        User.id == user_id,
        User.is_deleted == False
    ).first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user


async def require_chef(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to require chef role for an endpoint.
    
    Args:
        current_user: The authenticated user from get_current_user
        
    Returns:
        User object if user is a chef
        
    Raises:
        HTTPException: 403 if user is not a chef
        
    Requirements: 1.3
    """
    if current_user.role != "chef":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chef role required"
        )
    return current_user


async def require_foodie(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to require foodie role for an endpoint.
    
    Args:
        current_user: The authenticated user from get_current_user
        
    Returns:
        User object if user is a foodie
        
    Raises:
        HTTPException: 403 if user is not a foodie
        
    Requirements: 1.3
    """
    if current_user.role != "foodie":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Foodie role required"
        )
    return current_user

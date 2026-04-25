"""
Admin console authentication middleware.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.utils.security import verify_admin_token


security = HTTPBearer()


async def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Validate the admin console JWT and return basic admin profile data.
    """
    payload = verify_admin_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return {
        "username": payload["username"],
        "display_name": settings.ADMIN_DISPLAY_NAME
    }

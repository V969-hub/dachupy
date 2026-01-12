"""
Security utilities for JWT authentication and binding code generation.

Requirements:
- 2.5: JWT token validation for protected endpoints
- 2.6: Return 401 error for invalid/expired tokens
- 3.4: Generate unique binding code for each user
"""
from datetime import datetime, timedelta
from typing import Optional
import secrets
import string

from jose import JWTError, jwt

from app.config import settings


def create_token(user_id: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT token for user authentication.
    
    Args:
        user_id: The user's unique identifier
        role: The user's role ('foodie' or 'chef')
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
        
    Requirements: 2.5
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_SECRET_KEY, 
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: The JWT token string to verify
        
    Returns:
        Decoded payload dict if valid, None if invalid/expired
        
    Requirements: 2.5, 2.6
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return payload
    except JWTError:
        return None


def generate_binding_code(length: int = 8) -> str:
    """
    Generate a unique binding code for user registration.
    
    The binding code consists of uppercase letters and digits,
    excluding ambiguous characters (0, O, I, 1, L).
    
    Args:
        length: Length of the binding code (default: 8)
        
    Returns:
        A random binding code string
        
    Requirements: 3.4
    """
    # Exclude ambiguous characters: 0, O, I, 1, L
    alphabet = string.ascii_uppercase + string.digits
    alphabet = alphabet.replace('0', '').replace('O', '').replace('I', '').replace('1', '').replace('L', '')
    
    return ''.join(secrets.choice(alphabet) for _ in range(length))

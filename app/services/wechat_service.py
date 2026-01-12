"""
WeChat API service for mini-program authentication.

Requirements:
- 2.1: Exchange WeChat login code for openId via WeChat API
"""
from typing import Optional
from dataclasses import dataclass
import httpx

from app.config import settings


@dataclass
class WeChatSession:
    """WeChat session data returned from code2session API."""
    openid: str
    session_key: str
    unionid: Optional[str] = None


class WeChatServiceError(Exception):
    """Exception raised for WeChat API errors."""
    def __init__(self, errcode: int, errmsg: str):
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"WeChat API Error {errcode}: {errmsg}")


async def code2session(code: str) -> WeChatSession:
    """
    Exchange WeChat login code for session information.
    
    Calls WeChat's jscode2session API to get the user's openId
    and session_key from the temporary login code.
    
    Args:
        code: The temporary login code from WeChat mini-program
        
    Returns:
        WeChatSession containing openid, session_key, and optional unionid
        
    Raises:
        WeChatServiceError: If WeChat API returns an error
        httpx.HTTPError: If network request fails
        
    Requirements: 2.1
    """
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.WECHAT_APP_ID,
        "secret": settings.WECHAT_APP_SECRET,
        "js_code": code,
        "grant_type": "authorization_code"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    
    # Check for WeChat API errors
    if "errcode" in data and data["errcode"] != 0:
        raise WeChatServiceError(
            errcode=data.get("errcode", -1),
            errmsg=data.get("errmsg", "Unknown error")
        )
    
    return WeChatSession(
        openid=data["openid"],
        session_key=data["session_key"],
        unionid=data.get("unionid")
    )


async def decrypt_phone_number(
    session_key: str,
    encrypted_data: str,
    iv: str
) -> Optional[str]:
    """
    Decrypt WeChat encrypted phone number data.
    
    Uses the session_key to decrypt the phone number data
    encrypted by WeChat mini-program.
    
    Args:
        session_key: The session key from code2session
        encrypted_data: Base64 encoded encrypted data
        iv: Base64 encoded initialization vector
        
    Returns:
        Decrypted phone number string, or None if decryption fails
        
    Requirements: 2.4
    """
    import base64
    from Crypto.Cipher import AES
    import json
    
    try:
        # Decode base64 strings
        session_key_bytes = base64.b64decode(session_key)
        encrypted_data_bytes = base64.b64decode(encrypted_data)
        iv_bytes = base64.b64decode(iv)
        
        # Create AES cipher
        cipher = AES.new(session_key_bytes, AES.MODE_CBC, iv_bytes)
        
        # Decrypt and remove padding
        decrypted = cipher.decrypt(encrypted_data_bytes)
        # Remove PKCS7 padding
        pad_len = decrypted[-1]
        decrypted = decrypted[:-pad_len]
        
        # Parse JSON
        data = json.loads(decrypted.decode('utf-8'))
        
        # Verify appId
        if data.get("watermark", {}).get("appid") != settings.WECHAT_APP_ID:
            return None
        
        return data.get("phoneNumber") or data.get("purePhoneNumber")
    except Exception:
        return None

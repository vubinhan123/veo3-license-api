from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from app.core.config import settings
import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_license_signature(data: dict):
    # Sử dụng RS256 hoặc HS256 tùy cấu hình để ký cho Tool Client
    # Ở đây dùng RS256 từ settings cho chuyên nghiệp
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_PRIVATE_KEY, algorithm="RS256")

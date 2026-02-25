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
    import base64
    private_key_str = settings.JWT_PRIVATE_KEY
    
    # Kiem tra xem key co phai la Base64 khong (khong chua khoang trang, khong chua header PEM)
    if "BEGIN" not in private_key_str and " " not in private_key_str:
        try:
            private_key = base64.b64decode(private_key_str).decode('utf-8')
        except Exception:
            private_key = private_key_str
    else:
        private_key = private_key_str
        
        # Van giu logic cu de du phong
        if "\\n" in private_key:
            private_key = private_key.replace("\\n", "\n")
        if "-----BEGIN PRIVATE KEY-----" in private_key and "\n" not in private_key:
            private_key = private_key.replace("-----BEGIN PRIVATE KEY----- ", "-----BEGIN PRIVATE KEY-----\n").replace(" -----END PRIVATE KEY-----", "\n-----END PRIVATE KEY-----")
            lines = private_key.split("\n")
            if len(lines) == 3:
                body_with_spaces = lines[1]
                body_with_newlines = body_with_spaces.replace(" ", "\n")
                private_key = f"{lines[0]}\n{body_with_newlines}\n{lines[2]}"
            
    return jwt.encode(to_encode, private_key, algorithm="RS256")

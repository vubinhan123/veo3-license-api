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
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    
    # 1. Thử ký bằng RSA (RS256)
    try:
        import base64
        private_key_str = settings.JWT_PRIVATE_KEY.strip()
        try:
            decoded = base64.b64decode(private_key_str).decode('utf-8')
            if "BEGIN" in decoded:
                private_key = decoded
            else:
                private_key = private_key_str
        except Exception:
            private_key = private_key_str
            
        if "BEGIN" in private_key:
            if "\\n" in private_key:
                private_key = private_key.replace("\\n", "\n")
            return jwt.encode(to_encode, private_key, algorithm="RS256")
    except Exception as e:
        print(f"[!] RSA Sign fallback to HS256: {e}")
        
    # 2. Ký bằng HMAC-SHA256 bảo mật cao (Secret Key)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

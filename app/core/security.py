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

def _get_clean_pem(pem_str: str) -> str:
    """Xử lý chuẩn hóa định dạng PEM (hỗ trợ base64, newline escaped)"""
    import base64
    s = pem_str.strip()
    # Nếu bị bọc ngoặc kép dư
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    try:
        decoded = base64.b64decode(s).decode('utf-8', errors='ignore')
        if "BEGIN" in decoded:
            s = decoded
    except Exception:
        pass
    if "\\n" in s:
        s = s.replace("\\n", "\n")
    return s

def create_license_signature(data: dict) -> str:
    """
    Ký số bản quyền bằng thuật toán bất đối xứng RSA-256 (RS256).
    Chỉ Server nắm Private Key mới có thể sinh chữ ký này.
    Kẻ gian dùng proxy/hosts giả lập Server không thể giả mạo chữ ký.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=2)
    to_encode = data.copy()
    to_encode.update({
        "exp": expire,
        "iss": "VEO3_AUTHORITY_SERVER",
        "iat": datetime.now(timezone.utc)
    })
    
    # 1. Ưu tiên ký bằng RSA Private Key (RS256)
    try:
        private_key = _get_clean_pem(settings.JWT_PRIVATE_KEY)
        if "BEGIN" in private_key:
            return jwt.encode(to_encode, private_key, algorithm="RS256")
    except Exception as e:
        print(f"[!] RSA Sign error: {e}, falling back to HS256")
        
    # 2. Fallback sang HS256 nếu chưa cấu hình RSA
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

def verify_license_signature(token: str) -> dict:
    """
    Xác minh chữ ký số của License Token bằng RSA Public Key (RS256).
    Client Tool dùng Public Key để kiểm tra toàn vẹn token từ Server.
    """
    public_key = _get_clean_pem(settings.JWT_PUBLIC_KEY)
    try:
        if "BEGIN" in public_key:
            return jwt.decode(token, public_key, algorithms=["RS256"], issuer="VEO3_AUTHORITY_SERVER")
    except Exception as e:
        # Fallback thử kiểm tra bằng SECRET_KEY nếu ký HS256
        pass
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256", "RS256"])

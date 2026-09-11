import time
import random
import uuid
import aiohttp
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta
from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import Token
from app.core import security
from app.core.config import settings
from app.core.dependencies import get_current_user
from pydantic import BaseModel, Field

router = APIRouter()

# Bộ nhớ đệm lưu phiên xác thực cấp 2: session_id -> { email, role, expires_at, client_ip }
pending_2fa: dict = {}

@router.post("/login", response_model=Token)
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    client_ip = request.client.host if request.client else "Unknown IP"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    # Tìm user theo email
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Tài khoản đã bị vô hiệu hóa")

    # BẢO MẬT 2 LỚP ĐỘC LẬP: Chuyển sang bước xác thực Mã Khóa Cấp 2
    session_id = uuid.uuid4().hex
    pending_2fa[session_id] = {
        "email": user.email,
        "role": user.role,
        "expires_at": time.time() + 300,  # 5 phút
        "client_ip": client_ip
    }

    return {
        "access_token": "",
        "refresh_token": "",
        "token_type": "bearer",
        "require_2fa": True,
        "session_id": session_id,
        "message": "Vui lòng nhập Mã Khóa Cấp 2 Bảo Mật để hoàn tất đăng nhập."
    }

class Verify2FARequest(BaseModel):
    session_id: str
    otp: str

@router.post("/verify-2fa", response_model=Token)
async def verify_2fa(
    data: Verify2FARequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    session = pending_2fa.get(data.session_id)
    if not session:
        raise HTTPException(
            status_code=400,
            detail="Phiên xác thực không tồn tại hoặc đã hết hạn. Vui lòng đăng nhập lại."
        )
        
    if time.time() > session["expires_at"]:
        del pending_2fa[data.session_id]
        raise HTTPException(
            status_code=400,
            detail="Phiên xác thực đã quá thời gian (5 phút). Vui lòng đăng nhập lại."
        )
        
    submitted_code = data.otp.strip()
    if submitted_code != settings.ADMIN_SECURITY_PIN:
        raise HTTPException(
            status_code=400,
            detail="Mã Khóa Cấp 2 Bảo Mật không chính xác. Vui lòng kiểm tra lại!"
        )

    email = session["email"]
    role = session["role"]
    del pending_2fa[data.session_id]

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": email, "role": role},
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "refresh_token": "N/A",
        "token_type": "bearer",
        "require_2fa": False
    }

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }

@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not security.verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu hiện tại không chính xác!"
        )
    current_user.hashed_password = security.get_password_hash(data.new_password)
    await db.commit()
    return {"status": "success", "message": "Đổi mật khẩu quản trị thành công!"}

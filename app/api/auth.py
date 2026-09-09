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

# Bộ nhớ đệm lưu phiên 2FA đang chờ: session_id -> { email, otp, expires_at, role, client_ip }
pending_2fa: dict = {}

async def send_telegram_alert(text: str):
    """Gửi cảnh báo an ninh hoặc mã OTP về Telegram của Admin"""
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ADMIN_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=8) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"[!] Warning: Cannot send Telegram 2FA/alert: {e}")
        return False

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
        # Bắn cảnh báo xâm nhập ngay lập tức về Telegram
        await send_telegram_alert(
            f"🚨 <b>CẢNH BÁO XÂM NHẬP WEB TẠO KEY:</b>\n\n"
            f"Phát hiện lần thử đăng nhập <b>THẤT BẠI (SAI MẬT KHẨU)</b>!\n"
            f"Email thử: <code>{form_data.username}</code>\n"
            f"Địa chỉ IP: <code>{client_ip}</code>\n"
            f"Thời gian: <code>{time.strftime('%Y-%m-%d %H:%M:%S')}</code>"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Tài khoản đã bị vô hiệu hóa")

    # NẾU BẬT 2FA TELEGRAM: Sinh mã OTP và gửi về điện thoại
    if settings.ENABLE_2FA_TELEGRAM:
        otp = f"{random.randint(100000, 999999)}"
        session_id = uuid.uuid4().hex
        pending_2fa[session_id] = {
            "email": user.email,
            "otp": otp,
            "role": user.role,
            "expires_at": time.time() + 180,  # 3 phút
            "client_ip": client_ip
        }

        # Gửi OTP về Telegram Admin
        msg = (
            f"🔐 <b>MÃ XÁC THỰC 2 LỚP (2FA) - WEB TẠO KEY</b>\n\n"
            f"Mã OTP của bạn: <b><code>{otp}</code></b>\n\n"
            f"⏳ <i>Hiệu lực: 3 phút. Tuyệt đối không gửi mã này cho bất kỳ ai!</i>\n"
            f"🌐 Thiết bị đăng nhập: <code>{client_ip}</code>"
        )
        await send_telegram_alert(msg)

        return {
            "access_token": "",
            "refresh_token": "",
            "token_type": "bearer",
            "require_2fa": True,
            "session_id": session_id,
            "message": "Mã xác thực 2FA đã được gửi về Telegram của bạn. Vui lòng nhập để hoàn tất đăng nhập."
        }
        
    # Nếu không bật 2FA: Cấp token trực tiếp
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "refresh_token": "N/A",
        "token_type": "bearer",
        "require_2fa": False
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
    client_ip = request.client.host if request.client else "Unknown IP"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    session = pending_2fa.get(data.session_id)
    if not session:
        raise HTTPException(
            status_code=400,
            detail="Phiên xác thực 2FA không tồn tại hoặc đã hết hạn. Vui lòng đăng nhập lại."
        )
        
    if time.time() > session["expires_at"]:
        del pending_2fa[data.session_id]
        raise HTTPException(
            status_code=400,
            detail="Mã OTP đã hết hiệu lực (quá 3 phút). Vui lòng đăng nhập lại."
        )
        
    if data.otp.strip() != session["otp"]:
        raise HTTPException(
            status_code=400,
            detail="Mã xác thực OTP không chính xác. Vui lòng kiểm tra lại Telegram!"
        )

    email = session["email"]
    role = session["role"]
    del pending_2fa[data.session_id]

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": email, "role": role},
        expires_delta=access_token_expires
    )

    # Báo đăng nhập thành công về Telegram
    await send_telegram_alert(
        f"✅ <b>ĐĂNG NHẬP WEB TẠO KEY THÀNH CÔNG:</b>\n"
        f"Admin: <code>{email}</code>\n"
        f"IP: <code>{client_ip}</code>\n"
        f"Thời gian: <code>{time.strftime('%Y-%m-%d %H:%M:%S')}</code>"
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

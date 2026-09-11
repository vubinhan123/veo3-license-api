from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.database import engine, Base
from app.api import license, auth, sepay, telegram
from app.core.config import settings
from app.core import security
from app.models.models import User, License, Device, Log
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo bảng dữ liệu và migration an toàn
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Tự động migrate thêm các cột nếu chưa có trong DB (PostgreSQL / SQLite)
            for col_sql in [
                ("tool_type", "ALTER TABLE licenses ADD COLUMN IF NOT EXISTS tool_type VARCHAR DEFAULT 'veo3_pro';", "ALTER TABLE licenses ADD COLUMN tool_type VARCHAR DEFAULT 'veo3_pro';"),
                ("reset_count", "ALTER TABLE licenses ADD COLUMN IF NOT EXISTS reset_count INTEGER DEFAULT 0;", "ALTER TABLE licenses ADD COLUMN reset_count INTEGER DEFAULT 0;"),
                ("last_heartbeat", "ALTER TABLE licenses ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMP WITH TIME ZONE;", "ALTER TABLE licenses ADD COLUMN last_heartbeat TIMESTAMP;"),
                ("note", "ALTER TABLE licenses ADD COLUMN IF NOT EXISTS note VARCHAR;", "ALTER TABLE licenses ADD COLUMN note VARCHAR;")
            ]:
                try:
                    from sqlalchemy import text
                    await conn.execute(text(col_sql[1]))
                except Exception:
                    try:
                        await conn.execute(text(col_sql[2]))
                    except Exception:
                        pass
    except Exception as e:
        print(f"[!] Warning: DB table init in lifespan: {e}")
    
    # Tạo User Admin mặc định nếu chưa có
    try:
        async with AsyncSession(engine) as session:
            admin_email = settings.ADMIN_DEFAULT_EMAIL
            result = await session.execute(select(User).where(User.email == admin_email))
            admin = result.scalar_one_or_none()
            if not admin:
                print(f"[*] Khoi tao tai khoan Admin mac dinh ({admin_email})...")
                hashed_pwd = security.get_password_hash(settings.ADMIN_DEFAULT_PASSWORD)
                new_admin = User(
                    email=admin_email,
                    hashed_password=hashed_pwd,
                    role="admin",
                    is_active=True
                )
                session.add(new_admin)
                await session.commit()
    except Exception as e:
        print(f"[!] Warning: Admin user creation in lifespan: {e}")

    # Đăng ký Telegram Webhook 24/7/365 với máy chủ Telegram
    try:
        await telegram.setup_telegram_webhook()
        print("✅ [CLOUD 24/7] Telegram Bot Webhook da kich hoat san sang 24/7 tren Render!")
    except Exception as e:
        print(f"[!] Warning setting Telegram Webhook: {e}")
            
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    docs_url=None,        # Ẩn hoàn toàn Swagger UI chống quét cổng
    redoc_url=None,       # Ẩn hoàn toàn ReDoc tài liệu API
    openapi_url=None,     # Vô hiệu hóa OpenAPI Schema chống rò rỉ cấu trúc hệ thống
    lifespan=lifespan
)

# Custom Middleware: Rate Limiting & Security Headers
import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class SecurityAndRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.request_history = defaultdict(list)

    async def dispatch(self, request, call_next):
        client_ip = request.client.host if request.client else "127.0.0.1"
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            client_ip = cf_ip.strip()

        path = request.url.path
        now = time.time()

        # Dọn dẹp request cũ hơn 60s
        history = [t for t in self.request_history[client_ip] if now - t[0] < 60]
        self.request_history[client_ip] = history

        # Kiểm tra Rate Limit cho các endpoint nhạy cảm
        if path.endswith("/auth/login") and request.method == "POST":
            login_attempts = sum(1 for t, p in history if p.endswith("/auth/login"))
            if login_attempts >= settings.RATE_LIMIT_LOGIN_PER_MINUTE:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Quá nhiều lần thử đăng nhập. Vui lòng thử lại sau 1 phút."}
                )
        elif path.endswith("/license/verify") and request.method == "POST":
            verify_attempts = sum(1 for t, p in history if p.endswith("/license/verify"))
            if verify_attempts >= settings.RATE_LIMIT_VERIFY_PER_MINUTE:
                return JSONResponse(
                    status_code=429,
                    content={"status": "fail", "message": "Quá nhiều yêu cầu xác thực bản quyền từ IP này. Vui lòng đợi 1 phút."}
                )

        self.request_history[client_ip].append((now, path))

        response = await call_next(request)

        # Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if "server" in response.headers:
            del response.headers["server"]

        return response

app.add_middleware(SecurityAndRateLimitMiddleware)

# Cấu hình CORS
origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
if not origins:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Auth"])
app.include_router(license.router, prefix=f"{settings.API_V1_STR}/license", tags=["License"])
app.include_router(sepay.router, prefix=f"{settings.API_V1_STR}/sepay", tags=["SePay"])
app.include_router(telegram.router, prefix=f"{settings.API_V1_STR}/telegram", tags=["Telegram"])

@app.get("/")
async def root():
    return {"message": "Welcome to VEO3 License Management API", "status": "online"}

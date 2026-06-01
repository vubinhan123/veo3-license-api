from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.database import engine, Base
from app.api import license, auth
from app.core.config import settings
from app.core import security
from app.models.models import User, License, Device, Log
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Khởi tạo bảng dữ liệu
    print("[*] Đang kiểm tra và khởi tạo database...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[+] Khởi tạo database thành công!")
    except Exception as e:
        print(f"[!] LỖI khởi tạo database: {e}")
    
    # 2. Tạo User Admin mặc định nếu chưa có
    print("[*] Kiểm tra tài khoản Admin...")
    try:
        async with AsyncSession(engine) as session:
            result = await session.execute(select(User).where(User.email == "vubinhan094@gmail.com"))
            admin = result.scalar_one_or_none()
            if not admin:
                print("[*] Khởi tạo tài khoản Admin mặc định...")
                hashed_pwd = security.get_password_hash("Vubinhan336!@#")
                new_admin = User(
                    email="vubinhan094@gmail.com",
                    hashed_password=hashed_pwd,
                    role="admin",
                    is_active=True
                )
                session.add(new_admin)
                await session.commit()
                print("[+] Đã tạo Admin mặc định.")
            else:
                print("[*] Đã có Admin, cập nhật mật khẩu mới...")
                admin.hashed_password = security.get_password_hash("Vubinhan336!@#")
                session.add(admin)
                await session.commit()
                print("[+] Đã cập nhật Admin.")
    except Exception as e:
        print(f"[!] LỖI khởi tạo Admin: {e}")
            
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Auth"])
app.include_router(license.router, prefix=f"{settings.API_V1_STR}/license", tags=["License"])

@app.get("/")
async def root():
    return {
        "message": "Welcome to VEO3 License Management API",
        "status": "online",
        "version": "1.2.62-patch-v3-reset-pwd-verified"
    }

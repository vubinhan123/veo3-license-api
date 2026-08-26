from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.database import engine, Base
from app.api import license, auth
from app.core.config import settings
from app.core import security
from app.models.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo bảng dữ liệu và migration an toàn
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Tự động migrate thêm cột tool_type nếu chưa có trong DB (PostgreSQL / SQLite)
            try:
                from sqlalchemy import text
                await conn.execute(text("ALTER TABLE licenses ADD COLUMN IF NOT EXISTS tool_type VARCHAR DEFAULT 'veo3_pro';"))
            except Exception:
                try:
                    await conn.execute(text("ALTER TABLE licenses ADD COLUMN tool_type VARCHAR DEFAULT 'veo3_pro';"))
                except Exception:
                    pass
    except Exception as e:
        print(f"[!] Warning: DB table init in lifespan: {e}")
    
    # Tạo User Admin mặc định nếu chưa có
    try:
        async with AsyncSession(engine) as session:
            result = await session.execute(select(User).where(User.email == "vubinhan094@gmail.com"))
            admin = result.scalar_one_or_none()
            if not admin:
                print("[*] Khoi tao tai khoan Admin mac dinh...")
                hashed_pwd = security.get_password_hash("Vubinhan336!@#")
                new_admin = User(
                    email="vubinhan094@gmail.com",
                    hashed_password=hashed_pwd,
                    role="admin",
                    is_active=True
                )
                session.add(new_admin)
                await session.commit()
    except Exception as e:
        print(f"[!] Warning: Admin user creation in lifespan: {e}")
            
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
    return {"message": "Welcome to VEO3 License Management API", "status": "online"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.database import engine, Base
from app.api import license
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo bảng dữ liệu trên SQLite nếu chưa có
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Trong sản xuất nên giới hạn domain cụ thể
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(license.router, prefix=f"{settings.API_V1_STR}/license", tags=["License"])

@app.get("/")
async def root():
    return {"message": "Welcome to VEO3 License Management API", "status": "online"}

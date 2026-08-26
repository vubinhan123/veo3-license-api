import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

import re

DATABASE_URL = getattr(settings, "DATABASE_URL", None) or os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./quanlykey.db")

# Fix Render PostgreSQL URL for asyncpg
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# asyncpg khong nhan tham so sslmode trong query string
if "asyncpg" in DATABASE_URL:
    DATABASE_URL = re.sub(r'[?&]sslmode=[^&]+', '', DATABASE_URL)
    if '?' not in DATABASE_URL and '&' in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace('&', '?', 1)
    if DATABASE_URL.endswith('?'):
        DATABASE_URL = DATABASE_URL[:-1]

# SQLite khong ho tro pool_size va max_overflow
engine_params = {}
if DATABASE_URL.startswith("sqlite"):
    engine_params = {"echo": False}
else:
    engine_params = {
        "echo": False,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,
    }

engine = create_async_engine(DATABASE_URL, **engine_params)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

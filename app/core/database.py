import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# Render.com tra ve URL dang postgres:// nhung SQLAlchemy can postgresql+asyncpg://
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./quanlykey.db")

# Fix Render PostgreSQL URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# SQLite khong ho tro pool_size va max_overflow
engine_params = {}
if DATABASE_URL.startswith("sqlite"):
    engine_params = {"echo": False}
else:
    engine_params = {
        "echo": False,
        "pool_size": 10,
        "max_overflow": 20
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

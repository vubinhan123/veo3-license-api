import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import ssl

# Render.com tra ve URL dang postgres:// nhung SQLAlchemy can postgresql+asyncpg://
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./quanlykey.db")

# Fix Render PostgreSQL URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Safely remove sslmode using urllib.parse
requires_ssl = False
parsed = urlparse(DATABASE_URL)
if parsed.query:
    qs = parse_qsl(parsed.query)
    for k, v in qs:
        if k == 'sslmode' and v == 'require':
            requires_ssl = True
    qs = [ (k, v) for k, v in qs if k != 'sslmode' ]
    new_query = urlencode(qs)
    parsed = parsed._replace(query=new_query)
    DATABASE_URL = urlunparse(parsed)

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
    # Create SSL context for NeonDB to support SNI
    if requires_ssl or "neon.tech" in DATABASE_URL:
        engine_params["connect_args"] = {"ssl": "require"}

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

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.models.models import Base
from urllib.parse import urlparse

DATABASE_URL = "postgresql://neondb_owner:npg_VTt2swnSMl9o@ep-royal-river-amsa2aql-pooler.c-5.us-east-1.aws.neon.tech/neondb?ssl=require"

engine_params = {
    "echo": True,
    "pool_size": 10,
    "max_overflow": 20
}

if "neon.tech" in DATABASE_URL:
    parsed = urlparse(DATABASE_URL)
    hostname = parsed.hostname
    if hostname and hostname.startswith("ep-"):
        endpoint_id = hostname.split(".")[0]
        engine_params["connect_args"] = {
            "server_settings": {"options": f"endpoint={endpoint_id}"}
        }

engine = create_async_engine(DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"), **engine_params)

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("Done creating tables")

if __name__ == "__main__":
    asyncio.run(init_models())

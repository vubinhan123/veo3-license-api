import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select, text

DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_VTt2swnSMl9o@ep-royal-river-amsa2aql.c-5.us-east-1.aws.neon.tech/neondb?ssl=require"

engine = create_async_engine(DATABASE_URL)

async def check():
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT * FROM licenses"))
        rows = result.fetchall()
        for row in rows:
            print(dict(row._mapping))

if __name__ == "__main__":
    asyncio.run(check())

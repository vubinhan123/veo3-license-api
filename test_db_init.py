import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

async def test_init():
    try:
        from app.core.database import engine, Base
        from app.models.models import User, License, Device, Log
        
        print("[*] Dang khoi tao bang du lieu...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[+] Khoi tao DB thanh cong!")
        
        # Kiem tra thu create User
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy import select
        async with AsyncSession(engine) as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
            print(f"[+] Tim thay {len(users)} user.")
            
    except Exception as e:
        print(f"[!] LOI: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_init())

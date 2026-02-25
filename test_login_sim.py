import asyncio
from app.core.database import SessionLocal
from app.models.models import User
from sqlalchemy import select
from app.core import security

async def test_login():
    try:
        async with SessionLocal() as db:
            print("[*] Connecting DB locally...")
            res = await db.execute(select(User).where(User.email == "vubinhan094@gmail.com"))
            user = res.scalar_one_or_none()
            print(f"[-] User found: {user.email if user else 'None'}")
            
            if user:
                print(f"[-] Hashed pwd: {user.hashed_password}")
                is_valid = security.verify_password("Vubinhan336!@#", user.hashed_password)
                print(f"[-] Password valid: {is_valid}")
                
                if is_valid:
                    try:
                        from app.core.config import settings
                        from datetime import timedelta
                        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
                        access_token = security.create_access_token(
                            data={"sub": user.email, "role": user.role},
                            expires_delta=access_token_expires
                        )
                        print(f"[+] Token created: {access_token[:20]}...")
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        print(f"[!] Token Error: {e}")
    except Exception as e:
        print(f"[!] DB Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_login())

import asyncio
from app.core.database import SessionLocal
from app.models.models import License
from sqlalchemy import select
from app.schemas.schemas import VerifyRequest
from datetime import datetime, timezone

async def test_verify():
    try:
        async with SessionLocal() as db:
            print("[*] Tim License moi nhat...")
            result = await db.execute(select(License).order_by(License.created_at.desc()))
            lic = result.scalars().first()
            if not lic:
                print("Khong co license")
                return
            
            print(f"[*] License: {lic.license_key}, Status: {lic.status}, HWID: {lic.hwid}")
            
            # Mo phong ham verify
            req = VerifyRequest(license_key=lic.license_key, hwid="TEST_HWID_ABC_123")
            
            if lic.status != "active":
                print("Loi: Trang thai khong active")
                return
            
            if lic.expire_date < datetime.now(timezone.utc):
                print("Loi: Key het han")
                return
                
            if lic.hwid and lic.hwid != req.hwid:
                print("Loi: Sai HWID")
                return
                
            if not lic.hwid:
                lic.hwid = req.hwid
                print(f"[*] Update HWID: {lic.hwid}")
                await db.commit()
                print("[+] Commit thanh cong")
            
            # Tao payload tao thu token
            from app.core import security
            token_payload = {
                "key": lic.license_key,
                "hwid": req.hwid,
                "plan": lic.plan_type,
                "modules": lic.enabled_modules
            }
            print("[*] Creating token...")
            token = security.create_license_signature(token_payload)
            print("[+] Token created:", token[:20])
            
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_verify())

import asyncio
import secrets
import sys
from datetime import datetime, timezone, timedelta

# Fix Windows console UTF-8 encoding
if sys.stdout:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
from app.core.database import SessionLocal
from app.models.models import License, Device, User
from app.schemas.schemas import VerifyRequest
from app.api.license import verify_license, create_license, list_licenses
from app.schemas import schemas
from sqlalchemy import select, delete

async def run_backtest():
    print("=" * 60)
    print("   BẮT ĐẦU BACKTEST TOÀN DIỆN: TOOL ISOLATION LICENSING")
    print("=" * 60)
    
    async with SessionLocal() as db:
        # Dọn dẹp key test cũ nếu có
        await db.execute(delete(License).where(License.customer_email.like("test_%@lvc.vn")))
        await db.commit()
        
        # 1. TẠO 3 KEY RIÊNG BIỆT CHO 3 TOOL & 1 KEY COMBO
        print("\n[*] 1. Tạo các Key đại diện cho từng Tab...")
        exp = datetime.now(timezone.utc) + timedelta(days=30)
        
        # Key 1: VEO3 PRO
        k1_data = schemas.LicenseCreate(
            customer_name="Khách VEO3",
            customer_email="test_veo3@lvc.vn",
            plan_type="Monthly",
            expire_date=exp,
            tool_type="veo3_pro"
        )
        lic_veo3 = await create_license(k1_data, db)
        print(f" [+] Đã tạo Key VEO3 PRO:    {lic_veo3.license_key} (tool_type={lic_veo3.tool_type})")
        
        # Key 2: IMAGE PRO
        k2_data = schemas.LicenseCreate(
            customer_name="Khách IMAGE",
            customer_email="test_image@lvc.vn",
            plan_type="Monthly",
            expire_date=exp,
            tool_type="image_pro"
        )
        lic_image = await create_license(k2_data, db)
        print(f" [+] Đã tạo Key IMAGE PRO:   {lic_image.license_key} (tool_type={lic_image.tool_type})")
        
        # Key 3: TOOL VOICE
        k3_data = schemas.LicenseCreate(
            customer_name="Khách VOICE",
            customer_email="test_voice@lvc.vn",
            plan_type="Monthly",
            expire_date=exp,
            tool_type="tool_voice"
        )
        lic_voice = await create_license(k3_data, db)
        print(f" [+] Đã tạo Key TOOL VOICE:  {lic_voice.license_key} (tool_type={lic_voice.tool_type})")
        
        # Key 4: COMBO ALL (Dùng chung cả 3 tool)
        k4_data = schemas.LicenseCreate(
            customer_name="Khách VIP COMBO",
            customer_email="test_combo@lvc.vn",
            plan_type="Yearly",
            expire_date=exp,
            tool_type="combo_all"
        )
        lic_combo = await create_license(k4_data, db)
        print(f" [+] Đã tạo Key COMBO ALL:   {lic_combo.license_key} (tool_type={lic_combo.tool_type})")
        
        HWID_MAY_KHACH = "TEST_HWID_PC_USER_01"
        passed_tests = 0
        total_tests = 0
        
        # -------------------------------------------------------------
        # TEST CASE 1: Key VEO3 mở Tool VEO3 -> Phải THÀNH CÔNG
        # -------------------------------------------------------------
        total_tests += 1
        print("\n[*] TEST 1: Khách dùng Key VEO3 mở Tool VEO3 PRO...")
        req = VerifyRequest(license_key=lic_veo3.license_key, hwid=HWID_MAY_KHACH, tool_type="veo3_pro")
        res = await verify_license(req, db)
        assert res.status == "success", f"Failed: {res.message}"
        print(f" -> KẾT QUẢ: [THÀNH CÔNG] - {res.message}")
        passed_tests += 1
        
        # -------------------------------------------------------------
        # TEST CASE 2: Khách lấy Key VEO3 mở sang Tool IMAGE PRO -> Phải BỊ CHẶN!
        # -------------------------------------------------------------
        total_tests += 1
        print("\n[*] TEST 2 (LỖ HỔNG CŨ): Khách lấy Key VEO3 mở sang Tool IMAGE PRO...")
        req = VerifyRequest(license_key=lic_veo3.license_key, hwid=HWID_MAY_KHACH, tool_type="image_pro")
        res = await verify_license(req, db)
        assert res.status == "fail", f"LỖI! Cho phép dùng chéo: {res}"
        print(f" -> KẾT QUẢ: [CHẶN THÀNH CÔNG] - Lý do: {res.message}")
        passed_tests += 1
        
        # -------------------------------------------------------------
        # TEST CASE 3: Khách lấy Key VEO3 mở sang Tool VOICE -> Phải BỊ CHẶN!
        # -------------------------------------------------------------
        total_tests += 1
        print("\n[*] TEST 3 (LỖ HỔNG CŨ): Khách lấy Key VEO3 mở sang Tool VOICE...")
        req = VerifyRequest(license_key=lic_veo3.license_key, hwid=HWID_MAY_KHACH, tool_type="tool_voice")
        res = await verify_license(req, db)
        assert res.status == "fail", f"LỖI! Cho phép dùng chéo: {res}"
        print(f" -> KẾT QUẢ: [CHẶN THÀNH CÔNG] - Lý do: {res.message}")
        passed_tests += 1
        
        # -------------------------------------------------------------
        # TEST CASE 4: Khách dùng Key IMAGE PRO mở Tool IMAGE PRO -> Phải THÀNH CÔNG
        # -------------------------------------------------------------
        total_tests += 1
        print("\n[*] TEST 4: Khách dùng Key IMAGE PRO mở Tool IMAGE PRO...")
        req = VerifyRequest(license_key=lic_image.license_key, hwid=HWID_MAY_KHACH, tool_type="image_pro")
        res = await verify_license(req, db)
        assert res.status == "success", f"Failed: {res.message}"
        print(f" -> KẾT QUẢ: [THÀNH CÔNG] - {res.message}")
        passed_tests += 1
        
        # -------------------------------------------------------------
        # TEST CASE 5: Khách lấy Key IMAGE PRO mở sang Tool VEO3 -> Phải BỊ CHẶN!
        # -------------------------------------------------------------
        total_tests += 1
        print("\n[*] TEST 5: Khách lấy Key IMAGE PRO mở sang Tool VEO3 PRO...")
        req = VerifyRequest(license_key=lic_image.license_key, hwid=HWID_MAY_KHACH, tool_type="veo3_pro")
        res = await verify_license(req, db)
        assert res.status == "fail", f"LỖI! Cho phép dùng chéo: {res}"
        print(f" -> KẾT QUẢ: [CHẶN THÀNH CÔNG] - Lý do: {res.message}")
        passed_tests += 1
        
        # -------------------------------------------------------------
        # TEST CASE 6: Khách dùng Key VOICE mở Tool VOICE -> Phải THÀNH CÔNG
        # -------------------------------------------------------------
        total_tests += 1
        print("\n[*] TEST 6: Khách dùng Key VOICE mở Tool VOICE...")
        req = VerifyRequest(license_key=lic_voice.license_key, hwid=HWID_MAY_KHACH, tool_type="tool_voice")
        res = await verify_license(req, db)
        assert res.status == "success", f"Failed: {res.message}"
        print(f" -> KẾT QUẢ: [THÀNH CÔNG] - {res.message}")
        passed_tests += 1
        
        # -------------------------------------------------------------
        # TEST CASE 7: Key COMBO ALL mở Tool VEO3 -> Phải THÀNH CÔNG
        # -------------------------------------------------------------
        total_tests += 1
        print("\n[*] TEST 7: Khách VIP (Key COMBO) mở Tool VEO3 PRO...")
        req = VerifyRequest(license_key=lic_combo.license_key, hwid=HWID_MAY_KHACH, tool_type="veo3_pro")
        res = await verify_license(req, db)
        assert res.status == "success", f"Failed: {res.message}"
        print(f" -> KẾT QUẢ: [THÀNH CÔNG] - {res.message}")
        passed_tests += 1
        
        # -------------------------------------------------------------
        # TEST CASE 8: Key COMBO ALL mở Tool IMAGE PRO -> Phải THÀNH CÔNG
        # -------------------------------------------------------------
        total_tests += 1
        print("\n[*] TEST 8: Khách VIP (Key COMBO) mở Tool IMAGE PRO...")
        req = VerifyRequest(license_key=lic_combo.license_key, hwid=HWID_MAY_KHACH, tool_type="image_pro")
        res = await verify_license(req, db)
        assert res.status == "success", f"Failed: {res.message}"
        print(f" -> KẾT QUẢ: [THÀNH CÔNG] - {res.message}")
        passed_tests += 1
        
        # -------------------------------------------------------------
        # TEST CASE 9: Key COMBO ALL mở Tool VOICE -> Phải THÀNH CÔNG
        # -------------------------------------------------------------
        total_tests += 1
        print("\n[*] TEST 9: Khách VIP (Key COMBO) mở Tool VOICE...")
        req = VerifyRequest(license_key=lic_combo.license_key, hwid=HWID_MAY_KHACH, tool_type="tool_voice")
        res = await verify_license(req, db)
        assert res.status == "success", f"Failed: {res.message}"
        print(f" -> KẾT QUẢ: [THÀNH CÔNG] - {res.message}")
        passed_tests += 1
        
        # -------------------------------------------------------------
        # TEST CASE 10: Kiểm tra API lọc danh sách key theo Tab...
        # -------------------------------------------------------------
        total_tests += 1
        print("\n[*] TEST 10: Kiểm tra API lọc danh sách key theo Tab...")
        veo3_list = await list_licenses(tool_type="veo3_pro", db=db)
        image_list = await list_licenses(tool_type="image_pro", db=db)
        voice_list = await list_licenses(tool_type="tool_voice", db=db)
        
        assert all(l.tool_type == "veo3_pro" for l in veo3_list), "Lọc VEO3 bị lẫn key khác!"
        assert all(l.tool_type == "image_pro" for l in image_list), "Lọc IMAGE bị lẫn key khác!"
        assert all(l.tool_type == "tool_voice" for l in voice_list), "Lọc VOICE bị lẫn key khác!"
        print(f" -> KẾT QUẢ: [THÀNH CÔNG] - Tab VEO3: {len(veo3_list)} keys, Tab IMAGE: {len(image_list)} keys, Tab VOICE: {len(voice_list)} keys.")
        passed_tests += 1
        
        # Dọn dẹp key test
        await db.execute(delete(License).where(License.customer_email.like("test_%@lvc.vn")))
        await db.commit()
        
    print("\n" + "=" * 60)
    print(f" [HOÀN TẤT] BACKTEST THÀNH CÔNG {passed_tests}/{total_tests} BÀI KIỂM THỬ (100% PASS)")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_backtest())

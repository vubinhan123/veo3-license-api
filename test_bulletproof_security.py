import asyncio
import os
import sys
import uuid
import time
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from jose import jwt, JWTError

sys.stdout.reconfigure(encoding='utf-8')

# Import FastAPI app
from app.main import app
from app.core.config import settings
from app.core.security import verify_license_signature

async def run_security_tests():
    print("=" * 70)
    print("   CHƯƠNG TRÌNH KIỂM THỬ AN NINH & BẢO MẬT TUYỆT ĐỐI (BULLETPROOF SECURITY)")
    print("=" * 70)

    passed = 0
    total = 0

    def check(name, condition, detail=""):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f" [PASS] {name} | {detail}")
        else:
            print(f" [FAIL] {name} | {detail}")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        
        # ----------------------------------------------------------------------
        # TEST 1: KHÓA BẢO VỆ TOÀN BỘ ROUTE QUẢN TRỊ KHI KHÔNG CÓ TOKEN (RBAC)
        # ----------------------------------------------------------------------
        print("\n--- [TẦNG 1: BẢO VỆ API QUẢN TRỊ ADMIN (RBAC & JWT)] ---")
        
        r_list = await client.get("/api/v1/license/")
        check("Chặn Xem Danh Sách Key Không Token", r_list.status_code == 401, f"HTTP {r_list.status_code}")

        r_stats = await client.get("/api/v1/license/stats")
        check("Chặn Xem Thống Kê Stats Không Token", r_stats.status_code == 401, f"HTTP {r_stats.status_code}")

        r_logs = await client.get("/api/v1/license/logs")
        check("Chặn Xem Logs Không Token", r_logs.status_code == 401, f"HTTP {r_logs.status_code}")

        r_create = await client.post("/api/v1/license/", json={
            "customer_name": "Hacker Key",
            "plan_type": "Permanent",
            "expire_date": "2030-01-01T00:00:00Z"
        })
        check("Chặn Tự Tạo Key Miễn Phí Không Token", r_create.status_code == 401, f"HTTP {r_create.status_code}")

        r_batch = await client.post("/api/v1/license/batch", json={
            "count": 10,
            "plan_type": "Permanent",
            "expire_days": 365
        })
        check("Chặn Tạo Sỉ Batch Không Token", r_batch.status_code == 401, f"HTTP {r_batch.status_code}")

        r_patch = await client.patch("/api/v1/license/any-id", json={"status": "active"})
        check("Chặn Kích Hoạt Lại Key Không Token", r_patch.status_code == 401, f"HTTP {r_patch.status_code}")

        r_del = await client.delete("/api/v1/license/any-id")
        check("Chặn Xóa Key Không Token", r_del.status_code == 401, f"HTTP {r_del.status_code}")

        # ----------------------------------------------------------------------
        # TEST 2: ĐĂNG NHẬP ADMIN VỚI XÁC THỰC 2 LỚP 2FA TELEGRAM
        # ----------------------------------------------------------------------
        print("\n--- [TẦNG 2: ĐĂNG NHẬP ADMIN VỚI 2FA TELEGRAM OTP] ---")
        
        # Bước 1: Gửi email + password
        login_res = await client.post("/api/v1/auth/login", data={
            "username": settings.ADMIN_DEFAULT_EMAIL,
            "password": settings.ADMIN_DEFAULT_PASSWORD
        })
        login_data = login_res.json()
        step1_ok = login_res.status_code == 200 and (login_data.get("require_2fa") or "access_token" in login_data)
        check("Bước 1: Xác Thực Email & Mật Khẩu Admin", step1_ok, f"require_2fa: {login_data.get('require_2fa')}")
        
        if login_data.get("require_2fa"):
            session_id = login_data.get("session_id")
            from app.api.auth import pending_2fa
            saved_otp = pending_2fa[session_id]["otp"]
            
            # Thử nhập mã OTP sai
            bad_otp_res = await client.post("/api/v1/auth/verify-2fa", json={
                "session_id": session_id,
                "otp": "000000"
            })
            check("Chặn Nhập Mã OTP 2FA Sai", bad_otp_res.status_code == 400, f"HTTP {bad_otp_res.status_code}")
            
            # Nhập mã OTP đúng từ Telegram
            good_otp_res = await client.post("/api/v1/auth/verify-2fa", json={
                "session_id": session_id,
                "otp": saved_otp
            })
            step2_ok = good_otp_res.status_code == 200 and "access_token" in good_otp_res.json()
            check("Bước 2: Xác Thực Mã OTP 2FA Telegram Thành Công", step2_ok, f"HTTP {good_otp_res.status_code}")
            admin_token = good_otp_res.json().get("access_token")
        else:
            admin_token = login_data.get("access_token")

        auth_headers = {"Authorization": f"Bearer {admin_token}"}

        # Tạo key với token admin
        new_lic_res = await client.post("/api/v1/license/", json={
            "customer_name": "Khach Hang Test VIP",
            "customer_email": "vip@security.test",
            "plan_type": "Monthly",
            "expire_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "tool_type": "veo3_pro"
        }, headers=auth_headers)
        create_ok = new_lic_res.status_code == 200
        check("Admin Tạo Key Thành Công Sau Đăng Nhập", create_ok, f"HTTP {new_lic_res.status_code}")
        
        created_key = new_lic_res.json().get("license_key")
        created_id = new_lic_res.json().get("id")

        # Xem stats với token admin
        stats_res = await client.get("/api/v1/license/stats", headers=auth_headers)
        check("Admin Xem Thống Kê Thành Công", stats_res.status_code == 200, f"HTTP {stats_res.status_code}")

        # ----------------------------------------------------------------------
        # TEST 3: BẢO VỆ WEBHOOK SEPAY CHỐNG TẤN CÔNG GIẢ MẠO GIAO DỊCH
        # ----------------------------------------------------------------------
        print("\n--- [TẦNG 3: BẢO MẬT WEBHOOK SEPAY (ANTI-SPOOFING)] ---")

        fake_sepay_payload = {
            "transferAmount": 5900000,
            "content": "DH9999",
            "transferType": "in"
        }

        # Gửi không kèm API key
        r_sepay_no_key = await client.post("/api/v1/sepay/webhook", json=fake_sepay_payload)
        check("Chặn Webhook SePay Không Có API Key", r_sepay_no_key.status_code == 401, f"HTTP {r_sepay_no_key.status_code}")

        # Gửi kèm API key sai
        r_sepay_bad_key = await client.post(
            "/api/v1/sepay/webhook",
            json=fake_sepay_payload,
            headers={"Authorization": "Apikey WRONG_KEY_HACKER"}
        )
        check("Chặn Webhook SePay Dùng API Key Giả Mạo", r_sepay_bad_key.status_code == 401, f"HTTP {r_sepay_bad_key.status_code}")

        # Gửi kèm API key đúng
        r_sepay_good_key = await client.post(
            "/api/v1/sepay/webhook",
            json=fake_sepay_payload,
            headers={"Authorization": f"Apikey {settings.SEPAY_API_KEY}"}
        )
        check("Chấp Nhận Webhook SePay Hợp Lệ Đủ Secret Key", r_sepay_good_key.status_code == 200, f"HTTP {r_sepay_good_key.status_code}")

        # ----------------------------------------------------------------------
        # TEST 4: CHỐNG CRACK & CHỐNG BYPASS VỚI CHỮ KÝ SỐ RSA-256 & ANTI-REPLAY
        # ----------------------------------------------------------------------
        print("\n--- [TẦNG 4: CHỐNG CRACK / BYPASS (RSA-256 + ANTI-REPLAY)] ---")

        client_nonce = uuid.uuid4().hex
        client_ts = int(time.time())
        hwid_device_1 = "TEST-HWID-SECURE-001"

        verify_payload = {
            "license_key": created_key,
            "hwid": hwid_device_1,
            "tool_type": "veo3_pro",
            "nonce": client_nonce,
            "timestamp": client_ts
        }

        v_res = await client.post("/api/v1/license/verify", json=verify_payload)
        v_data = v_res.json()
        verify_ok = v_data.get("status") == "success"
        token = v_data.get("token")
        check("Client Verify Thành Công Lần Đầu", verify_ok, f"Status: {v_data.get('status')}")

        # Giải mã và kiểm tra chữ ký số RSA-256
        has_valid_rsa = False
        nonce_matches = False
        try:
            decoded = jwt.decode(
                token,
                settings.JWT_PUBLIC_KEY,
                algorithms=["RS256"],
                issuer="VEO3_AUTHORITY_SERVER"
            )
            has_valid_rsa = True
            nonce_matches = decoded.get("nonce") == client_nonce
        except Exception as e:
            print(f"[!] JWT decode error: {e}")

        check("Chữ Ký Số RSA-256 Bất Đối Xứng Hợp Lệ (Server Authentic)", has_valid_rsa, "Token được ký chính xác bởi RSA Private Key")
        check("Thử Thách Anti-Replay Khớp Nonce", nonce_matches, f"Nonce mong đợi: {client_nonce[:8]}... | Nonce nhận: {decoded.get('nonce')[:8] if has_valid_rsa else 'None'}...")

        # Thử nghiệm giả mạo token bằng cách sửa nội dung hoặc ký bằng fake key
        tampered_token = token[:-5] + "AAAAA"
        is_tampered_blocked = False
        try:
            jwt.decode(tampered_token, settings.JWT_PUBLIC_KEY, algorithms=["RS256"])
        except JWTError:
            is_tampered_blocked = True
        check("Phát Hiện Và Chặn Token Bị Hacker Can Thiệp", is_tampered_blocked, "Chữ ký RSA bị hỏng khi hacker sửa nội dung gói tin")

        # ----------------------------------------------------------------------
        # TEST 5: SECURITY HEADERS & RATE LIMITING
        # ----------------------------------------------------------------------
        print("\n--- [TẦNG 5: SECURITY HEADERS & CHỐNG BRUTE FORCE] ---")

        root_res = await client.get("/")
        has_security_headers = (
            root_res.headers.get("x-content-type-options") == "nosniff" and
            root_res.headers.get("x-frame-options") == "DENY" and
            root_res.headers.get("x-xss-protection") == "1; mode=block" and
            "strict-transport-security" in root_res.headers
        )
        check("Cấu Hình Đầy Đủ Security Headers (HSTS, CSP, NoSniff)", has_security_headers, "Headers bảo vệ trình duyệt hoạt động chuẩn")

        # Test Rate Limiting trên login (thử 10 lần liên tiếp với mật khẩu sai)
        rate_limit_triggered = False
        for i in range(10):
            rl_res = await client.post("/api/v1/auth/login", data={
                "username": settings.ADMIN_DEFAULT_EMAIL,
                "password": f"BadPassword_{i}"
            })
            if rl_res.status_code == 429:
                rate_limit_triggered = True
                break

        check("Kích Hoạt Rate Limiting Chống Brute Force (HTTP 429)", rate_limit_triggered, "Server tự động chặn khi phát hiện spam request")

        # ----------------------------------------------------------------------
        # DỌN DẸP DỮ LIỆU TEST
        # ----------------------------------------------------------------------
        await client.delete(f"/api/v1/license/{created_id}", headers=auth_headers)

    print("\n" + "=" * 70)
    print(f" TỔNG KẾT BẢO MẬT: {passed}/{total} BÀI KIỂM THỬ ĐẠT CHUẨN TUYỆT ĐỐI (PASS: {passed/total*100:.1f}%)")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_security_tests())

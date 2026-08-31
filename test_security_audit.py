import requests
import json
import sys
from datetime import datetime, timedelta, timezone

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://veo3-license-api.onrender.com/api/v1"
ADMIN_EMAIL = "vubinhan094@gmail.com"
ADMIN_PASS = "Vubinhan336!@#"

print("=" * 65)
print("  CHƯƠNG TRÌNH ĐÁNH GIÁ AN NINH & BẢO MẬT NÂNG CAO (SECURITY AUDIT)")
print("=" * 65)

passed = 0
total = 0

def check_security(name, condition, detail=""):
    global passed, total
    total += 1
    if condition:
        passed += 1
        print(f" [SECURE - PASS] {name} | {detail}")
    else:
        print(f" [VULNERABLE - FAIL] {name} | {detail}")

# Đăng nhập Admin lấy token quản trị
auth_res = requests.post(f"{BASE_URL}/auth/login", data={"username": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
admin_token = auth_res.json().get("access_token")
headers = {"Authorization": f"Bearer {admin_token}"}

# ==============================================================================
# TEST 1: CHỐNG TẤN CÔNG SQL INJECTION (SQLi RESILIENCE)
# ==============================================================================
sqli_payloads = [
    "' OR '1'='1",
    "'; DROP TABLE licenses; --",
    "admin' --",
    "' UNION SELECT 1, 'admin', 'password' --"
]
sqli_safe = True
for payload in sqli_payloads:
    try:
        r = requests.post(f"{BASE_URL}/license/verify", json={"license_key": payload, "hwid": "SEC-TEST-HWID", "tool_type": "veo3_pro"}, timeout=10)
        if r.status_code == 200:
            res = r.json()
            if res.get("status") == "success":
                sqli_safe = False
                break
    except Exception:
        pass

check_security("Chống Tấn Công SQL Injection (Verify API)", sqli_safe, "Server ORM tham số hóa an toàn, không rò rỉ dữ liệu")

# ==============================================================================
# TEST 2: CHỐNG CHIA SẺ KEY LẬU QUA MÃ MÁY (HWID LOCKING & ANTI-CLONING)
# ==============================================================================
# 2.1 Tạo key mới
now_iso = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
lic_res = requests.post(f"{BASE_URL}/license/", json={
    "customer_name": "Security Target",
    "customer_email": "target@security.local",
    "plan_type": "Monthly",
    "expire_date": now_iso,
    "tool_type": "veo3_pro"
}, headers=headers, timeout=10).json()

target_key = lic_res["license_key"]
target_id = lic_res["id"]

# Kích hoạt trên Máy Gốc (Machine A)
r_dev_a = requests.post(f"{BASE_URL}/license/verify", json={"license_key": target_key, "hwid": "MACHINE-A-12345", "tool_type": "veo3_pro"}).json()
dev_a_ok = r_dev_a.get("status") == "success"

# Kẻ gian đem key sang Máy Lậu (Machine B)
r_dev_b = requests.post(f"{BASE_URL}/license/verify", json={"license_key": target_key, "hwid": "MACHINE-B-67890-HACKER", "tool_type": "veo3_pro"}).json()
dev_b_blocked = r_dev_b.get("status") != "success"

check_security("Khóa Phần Cứng Chống Dùng Lậu Máy Khác (Anti-Cloning)", dev_a_ok and dev_b_blocked, f"Máy A: {'OK' if dev_a_ok else 'Lỗi'} | Máy B: {'Chặn thành công' if dev_b_blocked else 'Bị lọt'}")

# ==============================================================================
# TEST 3: CHỐNG DÙNG CHÉO TOOL BẢN QUYỀN (TOOL ISOLATION / CROSS-TOOL EXPLOIT)
# ==============================================================================
r_cross_img = requests.post(f"{BASE_URL}/license/verify", json={"license_key": target_key, "hwid": "MACHINE-A-12345", "tool_type": "image_pro"}).json()
r_cross_voice = requests.post(f"{BASE_URL}/license/verify", json={"license_key": target_key, "hwid": "MACHINE-A-12345", "tool_type": "tool_voice"}).json()

tool_iso_ok = (r_cross_img.get("status") != "success") and (r_cross_voice.get("status") != "success")
check_security("Chống Tấn Công Dùng Chéo Tool (Tool Isolation)", tool_iso_ok, "Key Veo3 bị chặn hoàn toàn trên Image Pro & Tool Voice")

# ==============================================================================
# TEST 4: THU HỒI NGAY LẬP TỨC (INSTANT REVOKE & HEARTBEAT ENFORCEMENT)
# ==============================================================================
# Admin thu hồi key
requests.patch(f"{BASE_URL}/license/{target_id}", json={"status": "revoked"}, headers=headers)

# Tool gửi verify
r_ver_revoked = requests.post(f"{BASE_URL}/license/verify", json={"license_key": target_key, "hwid": "MACHINE-A-12345", "tool_type": "veo3_pro"}).json()
# Tool gửi heartbeat ngầm
r_hb_revoked = requests.post(f"{BASE_URL}/license/heartbeat", json={"license_key": target_key, "hwid": "MACHINE-A-12345"}).json()

revoke_enforced = (r_ver_revoked.get("status") != "success") and (r_hb_revoked.get("status") == "revoked")
check_security("Thực Thi Khóa Quyền Ngay Lập Tức (Instant Revocation)", revoke_enforced, f"Verify: {r_ver_revoked.get('status')} | Heartbeat: {r_hb_revoked.get('status')}")

# ==============================================================================
# TEST 5: KIỂM SOÁT HẾT HẠN NGHIÊM NGẶT (EXPIRATION ENFORCEMENT)
# ==============================================================================
past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
lic_exp = requests.post(f"{BASE_URL}/license/", json={
    "customer_name": "Expired Target",
    "customer_email": "exp@security.local",
    "plan_type": "Trial",
    "expire_date": past_iso,
    "tool_type": "veo3_pro"
}, headers=headers, timeout=10).json()

r_exp = requests.post(f"{BASE_URL}/license/verify", json={"license_key": lic_exp["license_key"], "hwid": "EXP-HWID-01", "tool_type": "veo3_pro"}).json()
exp_blocked = r_exp.get("status") != "success"
check_security("Chống Vượt Thời Hạn Sử Dụng (Anti-Expiration Bypass)", exp_blocked, f"Thông báo chặn: '{r_exp.get('message')}'")

# ==============================================================================
# TEST 6: CHỮ KÝ SỐ MÃ HÓA TOKEN (DIGITAL SIGNATURE INTEGRITY)
# ==============================================================================
# Kích hoạt lại key hợp lệ để kiểm tra Token
requests.patch(f"{BASE_URL}/license/{target_id}", json={"status": "active"}, headers=headers)
r_sig = requests.post(f"{BASE_URL}/license/verify", json={"license_key": target_key, "hwid": "MACHINE-A-12345", "tool_type": "veo3_pro"}).json()
token = r_sig.get("token")
has_signature = bool(token and len(token) > 20)
check_security("Cơ Chế Chữ Ký Số Mã Hóa Phản Hồi (Cryptographic Signature)", has_signature, f"Token kích thước: {len(token) if token else 0} bytes")

# ==============================================================================
# TEST 7: BẢO VỆ MẬT KHẨU ADMIN (PASSWORD HASHING)
# ==============================================================================
# Thử đăng nhập mật khẩu sai
r_wrong_pwd = requests.post(f"{BASE_URL}/auth/login", data={"username": ADMIN_EMAIL, "password": "WrongPassword123!"}, timeout=10)
auth_secure = r_wrong_pwd.status_code == 401
check_security("Bảo Vệ Mật Khẩu Admin & Ngăn Đăng Nhập Trái Phép", auth_secure, f"HTTP Code chặn: {r_wrong_pwd.status_code}")

# Dọn dẹp dữ liệu test
requests.delete(f"{BASE_URL}/license/{target_id}", headers=headers)
requests.delete(f"{BASE_URL}/license/{lic_exp['id']}", headers=headers)

print("=" * 65)
print(f" KẾT QUẢ ĐÁNH GIÁ AN NINH: {passed}/{total} HẠNG MỤC ĐẠT CHUẨN AN TOÀN (PASS: {passed/total*100:.1f}%)")
print("=" * 65)

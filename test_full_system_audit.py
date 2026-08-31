import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://veo3-license-api.onrender.com/api/v1"
ADMIN_EMAIL = "vubinhan094@gmail.com"
ADMIN_PASS = "Vubinhan336!@#"

print("=" * 60)
print("  AUDIT KIEM THU TOAN DIEN HE THONG QUAN LY KEY (VEO3 PRO)")
print("=" * 60)

passed = 0
total = 0

def test(name, condition, detail=""):
    global passed, total
    total += 1
    if condition:
        passed += 1
        print(f" [PASS] {name} {detail}")
    else:
        print(f" [FAIL] {name} - {detail}")

# 1. Test Server Root & Health
try:
    r = requests.get("https://veo3-license-api.onrender.com/", timeout=15)
    test("Backend Server Live", r.status_code == 200, f"Status: {r.status_code}")
except Exception as e:
    test("Backend Server Live", False, str(e))

# 2. Test Admin Login
access_token = None
try:
    r = requests.post(f"{BASE_URL}/auth/login", data={"username": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    test("Admin Login Auth", r.status_code == 200, f"Status: {r.status_code}")
    if r.status_code == 200:
        access_token = r.json().get("access_token")
except Exception as e:
    test("Admin Login Auth", False, str(e))

headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}

# 3. Test Dashboard Stats
try:
    r = requests.get(f"{BASE_URL}/license/stats", timeout=15)
    test("Dashboard Stats API", r.status_code == 200 and "total_licenses" in r.json(), f"Total licenses: {r.json().get('total_licenses') if r.status_code == 200 else 'N/A'}")
except Exception as e:
    test("Dashboard Stats API", False, str(e))

# 4. Test Single Create & Tool Isolation
created_keys = {}
for tool in ["veo3_pro", "image_pro", "tool_voice", "combo_all"]:
    try:
        from datetime import datetime, timedelta, timezone
        exp_iso = (datetime.now(timezone.utc) + timedelta(days=36500)).isoformat()
        payload = {
            "customer_name": f"Audit Test {tool}",
            "customer_email": f"audit_{tool}@test.com",
            "plan_type": "Permanent",
            "expire_date": exp_iso,
            "tool_type": tool
        }
        r = requests.post(f"{BASE_URL}/license/", json=payload, headers=headers, timeout=15)
        ok = r.status_code == 200 and "license_key" in r.json()
        test(f"Create Key ({tool})", ok, f"Key: {r.json().get('license_key') if ok else r.text}")
        if ok:
            created_keys[tool] = r.json()
    except Exception as e:
        test(f"Create Key ({tool})", False, str(e))

# 5. Test Tool Isolation Verification
# 5.1 Veo3 Pro key on Veo3 Pro -> SHOULD PASS
if "veo3_pro" in created_keys:
    k = created_keys["veo3_pro"]["license_key"]
    r = requests.post(f"{BASE_URL}/license/verify", json={"license_key": k, "hwid": "HWID-TEST-VEO3-01", "tool_type": "veo3_pro"})
    test("Veo3 Key on Veo3 Pro", r.status_code == 200 and r.json().get("status") == "success" and bool(r.json().get("token")), f"Token: {bool(r.json().get('token'))}")

    # Veo3 Pro key on Image Pro -> SHOULD FAIL
    r = requests.post(f"{BASE_URL}/license/verify", json={"license_key": k, "hwid": "HWID-TEST-VEO3-01", "tool_type": "image_pro"})
    test("Veo3 Key blocked on Image Pro", r.json().get("status") != "success" or r.status_code != 200, f"Msg: {r.json().get('message')}")

# 5.2 Image Pro key on Image Pro -> SHOULD PASS
if "image_pro" in created_keys:
    k = created_keys["image_pro"]["license_key"]
    r = requests.post(f"{BASE_URL}/license/verify", json={"license_key": k, "hwid": "HWID-TEST-IMG-01", "tool_type": "image_pro"})
    test("Image Pro Key on Image Pro", r.status_code == 200 and r.json().get("status") == "success" and bool(r.json().get("token")), f"Token: {bool(r.json().get('token'))}")

    # Image Pro key on Tool Voice -> SHOULD FAIL
    r = requests.post(f"{BASE_URL}/license/verify", json={"license_key": k, "hwid": "HWID-TEST-IMG-01", "tool_type": "tool_voice"})
    test("Image Pro Key blocked on Tool Voice", r.json().get("status") != "success" or r.status_code != 200, f"Msg: {r.json().get('message')}")

# 5.3 KEY TEST (combo_all) -> SHOULD PASS ON ALL 3 TOOLS
if "combo_all" in created_keys:
    k = created_keys["combo_all"]["license_key"]
    r1 = requests.post(f"{BASE_URL}/license/verify", json={"license_key": k, "hwid": "HWID-TEST-ALL-01", "tool_type": "veo3_pro"})
    r2 = requests.post(f"{BASE_URL}/license/verify", json={"license_key": k, "hwid": "HWID-TEST-ALL-01", "tool_type": "image_pro"})
    r3 = requests.post(f"{BASE_URL}/license/verify", json={"license_key": k, "hwid": "HWID-TEST-ALL-01", "tool_type": "tool_voice"})
    test("KEY TEST opens Veo3 Pro", r1.status_code == 200 and r1.json().get("status") == "success")
    test("KEY TEST opens Image Pro", r2.status_code == 200 and r2.json().get("status") == "success")
    test("KEY TEST opens Tool Voice", r3.status_code == 200 and r3.json().get("status") == "success")

# 6. Test Batch Generation
try:
    batch_payload = {
        "count": 3,
        "plan_type": "Monthly",
        "expire_days": 30,
        "customer_prefix": "Audit Batch",
        "tool_type": "veo3_pro"
    }
    r = requests.post(f"{BASE_URL}/license/batch", json=batch_payload, headers=headers, timeout=15)
    ok = r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) == 3
    test("Batch Key Generator (3 keys)", ok, f"Count: {len(r.json()) if ok else 'N/A'}")
except Exception as e:
    test("Batch Key Generator", False, str(e))

# 7. Test Renew 1-Click
if "veo3_pro" in created_keys:
    lic_id = created_keys["veo3_pro"]["id"]
    try:
        r = requests.post(f"{BASE_URL}/license/renew/{lic_id}", json={"days": 30}, headers=headers)
        test("1-Click License Renewal (+30D)", r.status_code == 200 and "expire_date" in r.json())
    except Exception as e:
        test("1-Click License Renewal", False, str(e))

# 8. Test Reset HWID
if "veo3_pro" in created_keys:
    lic_id = created_keys["veo3_pro"]["id"]
    try:
        r = requests.post(f"{BASE_URL}/license/reset-hwid/{lic_id}", headers=headers)
        test("Reset HWID (Doi may cho khach)", r.status_code == 200 and r.json().get("hwid") is None, f"Reset count: {r.json().get('reset_count')}")
    except Exception as e:
        test("Reset HWID", False, str(e))

# 9. Test Heartbeat Online Ping
if "veo3_pro" in created_keys:
    k = created_keys["veo3_pro"]["license_key"]
    try:
        r = requests.post(f"{BASE_URL}/license/heartbeat", json={"license_key": k, "hwid": "HWID-TEST-VEO3-01"})
        test("Heartbeat Online Ping", r.status_code == 200 and r.json().get("status") == "active", f"Status: {r.json().get('status')}")
    except Exception as e:
        test("Heartbeat Online Ping", False, str(e))

# 10. Clean up test licenses
for tool, lic in created_keys.items():
    try:
        requests.delete(f"{BASE_URL}/license/{lic['id']}", headers=headers)
    except:
        pass

print("=" * 60)
print(f" KET QUA AUDIT: {passed}/{total} BAI KIEM THU THANH CONG (PASS: {passed/total*100:.1f}%)")
print("=" * 60)

"""Test CRUD v3 - With customer info and new key format"""
import requests

BASE = "http://localhost:8000/api/v1/license"

# 1. POST - Create with customer info
print("=== TAO KEY MOI ===")
r = requests.post(f"{BASE}/", json={
    "customer_name": "Vu Binh An",
    "customer_email": "vubinhan094@gmail.com",
    "plan_type": "Monthly",
    "expire_date": "2026-03-25T00:00:00",
    "max_devices": 1,
    "enabled_modules": {}
})
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"Key: {data['license_key']}")
    print(f"Ten: {data['customer_name']}")
    print(f"Email: {data['customer_email']}")
    print(f"ID: {data['id']}")
    
    # 2. PATCH - Revoke
    print("\n=== THU HOI KEY ===")
    r2 = requests.patch(f"{BASE}/{data['id']}", json={"status": "revoked"})
    print(f"Status: {r2.status_code}, New status: {r2.json()['status']}")
    
    # 3. Re-activate
    print("\n=== KICH HOAT LAI ===")
    r3 = requests.patch(f"{BASE}/{data['id']}", json={"status": "active"})
    print(f"Status: {r3.status_code}, New status: {r3.json()['status']}")
else:
    print(f"Error: {r.text}")

# 4. GET all
print("\n=== DANH SACH ===")
r = requests.get(f"{BASE}/")
print(f"Status: {r.status_code}, Count: {len(r.json())}")
for lic in r.json():
    print(f"  {lic['license_key']} | {lic['customer_name']} | {lic['customer_email']} | {lic['status']}")

print("\nTAT CA THANH CONG!")

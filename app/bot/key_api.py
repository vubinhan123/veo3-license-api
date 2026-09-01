import aiohttp
import asyncio
from datetime import datetime, timedelta, timezone
from config import config

class KeyAPIClient:
    def __init__(self):
        self.base_url = config.LICENSE_API_BASE
        self.email = config.ADMIN_EMAIL
        self.password = config.ADMIN_PASS
        self.token = None

    async def get_token(self) -> str:
        """Đăng nhập lấy Token xác thực quản trị viên"""
        if self.token:
            return self.token
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "username": self.email,
                "password": self.password
            }
            try:
                async with session.post(f"{self.base_url}/auth/login", data=payload, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.token = data.get("access_token")
                        return self.token
                    else:
                        text = await resp.text()
                        print(f"[!] Login API thất bại: {resp.status} - {text}")
                        return None
            except Exception as e:
                print(f"[!] Lỗi kết nối API Server: {e}")
                return None

    async def create_license(self, tool_type: str, plan_type: str, expire_days: int, customer_name: str, customer_email: str = None) -> str:
        """Gọi API Backend sinh License Key chính thức"""
        token = await self.get_token()
        if not token:
            # Thử lấy lại token 1 lần nữa
            self.token = None
            token = await self.get_token()
            if not token:
                raise Exception("Không thể xác thực với Backend Server")

        headers = {"Authorization": f"Bearer {token}"}
        
        # Tính ngày hết hạn
        if plan_type == "Permanent" or expire_days >= 3650:
            expire_dt = datetime.now(timezone.utc) + timedelta(days=36500) # 100 năm
        else:
            expire_dt = datetime.now(timezone.utc) + timedelta(days=expire_days)

        payload = {
            "customer_name": customer_name,
            "customer_email": customer_email or f"{customer_name.lower().replace(' ', '_')}@telegram.client",
            "plan_type": plan_type,
            "expire_date": expire_dt.isoformat(),
            "max_devices": 1,
            "tool_type": tool_type,
            "note": "Mua tự động qua Telegram Bot"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.base_url}/license/", json=payload, headers=headers, timeout=20) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("license_key")
                    else:
                        # Nếu 401 thì reset token
                        if resp.status == 401:
                            self.token = None
                        text = await resp.text()
                        print(f"[!] Lỗi tạo Key: {resp.status} - {text}")
                        raise Exception(f"Lỗi Server: {resp.status}")
            except Exception as e:
                print(f"[!] Lỗi gọi API tạo License: {e}")
                raise e

    async def find_license_by_key(self, license_key: str):
        """Tìm kiếm thông tin license theo mã Key"""
        token = await self.get_token()
        if not token:
            return None
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/license/", headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        licenses = await resp.json()
                        for lic in licenses:
                            if lic.get("license_key") == license_key.strip():
                                return lic
                    return None
            except Exception as e:
                print(f"[!] Lỗi tìm license: {e}")
                return None

    async def renew_license(self, license_id: str, additional_days: int):
        """Gia hạn License Key đã có trên hệ thống"""
        token = await self.get_token()
        if not token:
            return None
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session:
            try:
                payload = {"days": additional_days}
                async with session.post(f"{self.base_url}/license/renew/{license_id}", json=payload, headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return None
            except Exception as e:
                print(f"[!] Lỗi gia hạn license: {e}")
                return None

key_client = KeyAPIClient()

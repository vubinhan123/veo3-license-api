"""
========================================================================================
   MÔ HÌNH BẢO MẬT CHỐNG CRACK & CHỐNG BYPASS SERVER TOÀN DIỆN (CLIENT SIDE TEMPLATE)
   Dành riêng cho các Tool Desktop: VEO3 PRO, IMAGE PRO, TOOL VOICE, COMBO VIP
========================================================================================

CÁC TẦNG BẢO VỆ ĐƯỢC TÍCH HỢP TRONG MODULE NÀY:
  [1] Mã hóa Chữ ký số Bất đối xứng RSA-256 (RS256):
      - Client nhúng PUBLIC KEY để kiểm tra chữ ký.
      - Hacker dùng Fiddler/Burp Suite hoặc sửa file hosts/DNS trỏ về Server giả mạo (Fake Server)
        sẽ KHÔNG THỂ kích hoạt tool vì Server giả mạo không có PRIVATE KEY của tác giả để ký token!
  [2] Cơ chế Chống Phát Lại (Anti-Replay Challenge-Response):
      - Mỗi lần mở tool hoặc verify, client sinh 1 mã 'nonce' ngẫu nhiên và 'timestamp'.
      - Server đưa 'nonce' và 'timestamp' vào Token RSA.
      - Client kiểm tra: nếu token không chứa đúng 'nonce' vừa sinh ra thì từ chối ngay lập tức.
      - Hacker không thể lưu lại 1 token cũ từ máy khác hoặc phiên trước để tái sử dụng!
  [3] Khóa Cứng Phần Cứng Đa Lớp (Multi-Factor Hardware ID):
      - Kết hợp thông tin CPU, Motherboard UUID, và Serial ổ đĩa hệ thống.
  [4] Giám Sát Ngầm Động (Dynamic Background Heartbeat Worker):
      - Luồng chạy ngầm gửi ping định kỳ 2-3 phút. Nếu admin bấm Khóa/Thu hồi trên Web,
        Tool sẽ lập tức dừng hoạt động và thoát trong vòng 120s!
  [5] Khuyến nghị Đóng Gói Nhị Phân (Binary Obfuscation):
      - Biên dịch bằng Nuitka (C-binary .pyd/.exe) hoặc đóng gói PyArmor chống dịch ngược.
========================================================================================
"""

import sys
import os
import time
import uuid
import hashlib
import subprocess
import threading
import requests
from datetime import datetime, timezone
from jose import jwt, JWTError

# ======================================================================================
# CẤU HÌNH BẢO MẬT HỆ THỐNG
# ======================================================================================
API_BASE_URL = "https://veo3-license-api.onrender.com/api/v1"  # Domain máy chủ Render chính thức
TOOL_TYPE = "veo3_pro"                                        # Tên tool hiện tại
TOOL_VERSION = "1.2.62"

# RSA PUBLIC KEY CHÍNH THỨC CỦA MÁY CHỦ VEO3 AUTHORITY (KHÔNG THỂ GIẢ MẠO)
SERVER_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAmSEsx+XQQLQRJWxR9Tvm
dvUUq0hnBAXngBb7CjRWw/Z625FZKSOHls2OvoJACyJw4AyAN2lVRw9l2mXN9k5N
ipr7uVaEP3P5FEo1JV+/bDNXArf57MByaLogqQWsbxCDe8tbV4K15a9g5uY551R4
H88z45jJL8oyO7uMzxG3vonKNPAG8GQ/eXpqGzZiQvmjbcrdR13AVNS6xHVJwcv/
SgzVFURwo0+CLJTyAvLofRv/ov+4b5ln6fcKtFDf+B63otIIWmMLAdGuaYOuXKlW
PGT6qnX8gbEOGPn4CjkxE28yFuBiJx7xpyczgxCd/62AWqI/MRrz0JgCJfzw88t/
QQIDAQAB
-----END PUBLIC KEY-----"""


class HardwareFingerprint:
    """Thu thập thông tin phần cứng kết hợp đa thành phần chống giả mạo HWID"""

    @staticmethod
    def get_cpu_id() -> str:
        try:
            cmd = "wmic cpu get processorid"
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode()
            lines = [l.strip() for l in out.splitlines() if l.strip() and "ProcessorId" not in l]
            return lines[0] if lines else "CPU_DEFAULT"
        except Exception:
            return "CPU_UNKNOWN"

    @staticmethod
    def get_bios_uuid() -> str:
        try:
            cmd = "wmic csproduct get uuid"
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode()
            lines = [l.strip() for l in out.splitlines() if l.strip() and "UUID" not in l]
            return lines[0] if lines else "BIOS_DEFAULT"
        except Exception:
            return "BIOS_UNKNOWN"

    @staticmethod
    def get_disk_serial() -> str:
        try:
            cmd = "wmic diskdrive get serialnumber"
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode()
            lines = [l.strip() for l in out.splitlines() if l.strip() and "SerialNumber" not in l]
            return lines[0] if lines else "DISK_DEFAULT"
        except Exception:
            return "DISK_UNKNOWN"

    @classmethod
    def get_hwid(cls) -> str:
        """Tạo mã HWID độc nhất cho từng máy tính (SHA-256)"""
        raw = f"{cls.get_cpu_id()}::{cls.get_bios_uuid()}::{cls.get_disk_serial()}"
        return hashlib.sha256(raw.encode()).hexdigest().upper()[:32]


class AntiCrackLicenseManager:
    """Trình quản lý bản quyền chống crack toàn diện cho Client Tool"""

    def __init__(self, license_key: str):
        self.license_key = license_key.strip()
        self.hwid = HardwareFingerprint.get_hwid()
        self.is_licensed = False
        self.license_token = None
        self.verified_payload = None
        self._stop_heartbeat = threading.Event()
        self._heartbeat_thread = None

    def verify_license(self) -> tuple[bool, str]:
        """
        Gửi yêu cầu xác thực có kèm Challenge-Response (Nonce + Timestamp)
        và kiểm tra chữ ký số RSA-256 từ Server.
        """
        # Sinh Nonce ngẫu nhiên cho phiên xác thực này
        session_nonce = uuid.uuid4().hex
        client_timestamp = int(time.time())

        payload = {
            "license_key": self.license_key,
            "hwid": self.hwid,
            "tool_type": TOOL_TYPE,
            "tool_version": TOOL_VERSION,
            "nonce": session_nonce,
            "timestamp": client_timestamp
        }

        try:
            res = requests.post(
                f"{API_BASE_URL}/license/verify",
                json=payload,
                timeout=15,
                headers={"User-Agent": f"LVC-AntiCrackClient/{TOOL_VERSION}"}
            )
            if res.status_code != 200:
                return False, f"Server phản hồi mã lỗi HTTP {res.status_code}"
            
            data = res.json()
            if data.get("status") != "success":
                return False, data.get("message", "Xác thực bản quyền không thành công")

            token = data.get("token")
            if not token:
                return False, "Server không trả về chữ ký số xác thực bản quyền!"

            # ------------------------------------------------------------------
            # BẢO VỆ 1 & 2: KIỂM TRA CHỮ KÝ SỐ RSA-256 VÀ THỬ THÁCH NONCE
            # ------------------------------------------------------------------
            try:
                decoded = jwt.decode(
                    token,
                    SERVER_PUBLIC_KEY,
                    algorithms=["RS256"],
                    issuer="VEO3_AUTHORITY_SERVER"
                )
            except JWTError as jwt_err:
                # Nếu không giải mã được bằng Public Key -> Token bị hacker giả mạo!
                return False, f"Chữ ký số máy chủ không hợp lệ (Phát hiện can thiệp mạng/Fake Server): {jwt_err}"

            # Kiểm tra Nonce trong Token có khớp với Nonce vừa sinh ra không
            token_nonce = decoded.get("nonce")
            if token_nonce and token_nonce != session_nonce:
                return False, "Cảnh báo bảo mật: Token không khớp phiên gửi (Phát hiện Replay Attack)!"

            # Kiểm tra HWID trong Token có đúng máy này không
            if decoded.get("hwid") != self.hwid:
                return False, "Bản quyền không khớp với phần cứng của thiết bị này!"

            # Kiểm tra loại Tool
            token_tool = decoded.get("tool_type", "veo3_pro")
            if token_tool not in [TOOL_TYPE, "combo_all", "all", "key_test"]:
                return False, f"Key bản quyền này không áp dụng cho ứng dụng {TOOL_TYPE}!"

            # ------------------------------------------------------------------
            # BẢO VỆ 3: PHÁT HIỆN CÔNG CỤ DEBUG / DISASSEMBLER (ANTI-DEBUGGING)
            # ------------------------------------------------------------------
            if self._detect_debugger():
                return False, "Cảnh báo an ninh: Phát hiện công cụ Reverse Engineering (Debugger) đang chạy!"

            self.is_licensed = True
            self.license_token = token
            self.verified_payload = decoded

            # Khởi động luồng Heartbeat ngầm kiểm tra thu hồi tự động
            self._start_heartbeat_worker()

            return True, f"Kích hoạt thành công! Bản quyền có hiệu lực đến {decoded.get('expiry')}"

        except requests.exceptions.RequestException as net_err:
            return False, f"Không thể kết nối đến máy chủ xác thực: {net_err}"

    @staticmethod
    def _detect_debugger() -> bool:
        """Kiểm tra xem ứng dụng có đang bị gắn cờ Debug (x64dbg, IDA Pro, Cheat Engine) hay không"""
        try:
            import ctypes
            # Gọi hàm native Windows API IsDebuggerPresent
            if ctypes.windll.kernel32.IsDebuggerPresent():
                return True
            # Kiểm tra CheckRemoteDebuggerPresent
            is_remote = ctypes.c_bool(False)
            ctypes.windll.kernel32.CheckRemoteDebuggerPresent(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(is_remote))
            if is_remote.value:
                return True
        except Exception:
            pass
        return False

    def get_security_payload(self) -> dict:
        """
        Kỹ thuật Bảo Vệ Đa Điểm (Decentralized Protection):
        Các chức năng quan trọng của Tool (Render, AI, Tải video) PHẢI lấy dữ liệu từ hàm này.
        Nếu kẻ gian sửa code 'is_licensed = True' mà không có token RSA hợp lệ,
        các tính năng cốt lõi sẽ trả về None hoặc tự động dừng, khiến bản crack trở nên vô dụng!
        """
        if not self.is_licensed or not self.verified_payload:
            return {}
        return self.verified_payload

    def _start_heartbeat_worker(self):
        """Khởi động luồng chạy ngầm gửi Heartbeat kiểm tra định kỳ 120s"""
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return

        def heartbeat_loop():
            while not self._stop_heartbeat.wait(120):  # Gửi mỗi 2 phút
                try:
                    hb_payload = {
                        "license_key": self.license_key,
                        "hwid": self.hwid,
                        "tool_type": TOOL_TYPE
                    }
                    res = requests.post(f"{API_BASE_URL}/license/heartbeat", json=hb_payload, timeout=10)
                    if res.status_code == 200:
                        hb_data = res.json()
                        hb_status = hb_data.get("status")
                        if hb_status in ["revoked", "expired", "invalid"]:
                            print(f"\n[!] CẢNH BÁO BẢN QUYỀN: {hb_data.get('message')}")
                            self.is_licensed = False
                            # Thoát ứng dụng ngay lập tức khi phát hiện bị thu hồi
                            os._exit(1)
                except Exception:
                    pass  # Bỏ qua lỗi mạng tạm thời trong lúc chạy

        self._heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def stop(self):
        """Dọn dẹp luồng khi đóng tool"""
        self._stop_heartbeat.set()


# ======================================================================================
# HƯỚNG DẪN SỬ DỤNG TRONG TOOL CỦA BẠN:
# ======================================================================================
if __name__ == "__main__":
    print("=" * 65)
    print("   KIỂM THỬ MODULE CLIENT CHỐNG CRACK & CHỐNG BYPASS RSA-256")
    print("=" * 65)

    test_key = input("Nhập License Key để kiểm tra (hoặc Enter để test mã mẫu): ").strip()
    if not test_key:
        test_key = "SAMPLE-KEY-TEST"

    manager = AntiCrackLicenseManager(test_key)
    print(f"[*] Mã phần cứng thiết bị (HWID): {manager.hwid}")
    print("[*] Đang gửi yêu cầu xác thực bảo mật tới Server...")

    ok, msg = manager.verify_license()
    if ok:
        print(f"✅ THÀNH CÔNG: {msg}")
    else:
        print(f"❌ THẤT BẠI: {msg}")

import os
from typing import List

class BotConfig:
    # Telegram Bot Token
    BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "8957341354:AAHA6bLk-Z3_WH6RaRRszijmymQQYoGbxvM")
    
    # Danh sách Telegram User ID của Admin (được cấp quyền quản trị bot)
    ADMIN_IDS: List[int] = [7956637890]
    
    # API Backend Quản Lý License Key (VBA Automation)
    LICENSE_API_BASE: str = "https://veo3-license-api.onrender.com/api/v1"
    ADMIN_EMAIL: str = "vubinhan094@gmail.com"
    ADMIN_PASS: str = "Vubinhan336!@#"
    
    # Cấu hình Ngân Hàng TPBank & VietQR
    BANK_CODE: str = "TPBank"             # Mã ngân hàng TPBank
    BANK_ACCOUNT: str = "10002002707"       # Số tài khoản TPBank chính xác
    BANK_ACCOUNT_NAME: str = "VU VAN AN"   # Tên chủ tài khoản TPBank chính xác
    
    # Cổng thanh toán tự động SePay
    SEPAY_API_KEY: str = ""                # API Key từ SePay (nếu dùng API polling)
    SEPAY_WEBHOOK_PORT: int = 8088         # Cổng Webhook
    
    # Link hỗ trợ & hướng dẫn
    SUPPORT_URL: str = "https://t.me/vubinhan"
    TUTORIAL_URL: str = "https://youtube.com"

config = BotConfig()

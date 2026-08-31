import re
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.models import License, Log
from app.services.license_service import create_license_record

router = APIRouter()

BOT_TOKEN = "8957341354:AAHA6bLk-Z3_WH6RaRRszijmymQQYoGbxvM"
ADMIN_IDS = [7956637890]
SUPPORT_URL = "https://t.me/vubinhan"
TUTORIAL_URL = "https://youtube.com"

async def send_telegram_msg(chat_id: int, text: str):
    """Gửi tin nhắn qua Telegram Bot API"""
    import aiohttp
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"[!] Error sending Telegram message: {e}")
        return False

@router.post("/webhook")
async def sepay_webhook_handler(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Webhook nhận thông báo biến động số dư từ SePay
    Tự động sinh Key và gửi trực tiếp về Telegram của khách hàng
    """
    try:
        data = await request.json()
        print(f"[*] Nhận Webhook SePay từ Render: {data}")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    content = data.get("content", "") or data.get("description", "") or ""
    amount_in = int(data.get("transferAmount", 0) or data.get("amount", 0) or 0)
    transfer_type = data.get("transferType", "in")

    if transfer_type != "in" or amount_in <= 0:
        return {"status": "ignored", "reason": "Not an incoming payment"}

    # Tìm mã đơn hàng dạng VBAxxxx
    match = re.search(r"(VBA\d+)", content.upper())
    if not match:
        match = re.search(r"(VBA\d{4,6})", content.upper().replace(" ", ""))

    if not match:
        return {"status": "ignored", "reason": "No valid order code found in content"}

    order_code = match.group(1)
    
    # Kiểm tra xem mã đơn này đã từng được cấp key chưa (tránh trùng lặp)
    existing_log = await db.execute(select(Log).where(Log.action == f"PAID_{order_code}"))
    if existing_log.scalar_one_or_none():
        return {"status": "success", "message": f"Order {order_code} already processed"}

    # Xác định loại tool và thời hạn dựa trên số tiền nhận được
    # Tool lẻ: 179k (1M), 499k (3M), 1.490k (1Y), 2.990k (Life)
    # Combo 2: 300k (1M), 799k (3M), 2.490k (1Y), 4.500k (Life)
    # Combo 3: 399k (1M), 999k (3M), 2.990k (1Y), 5.900k (Life)
    
    tool_type = "veo3_pro"
    plan_type = "Monthly"
    expire_days = 30
    tool_name = "🤖 VEO3 PRO (Video AI)"

    if amount_in >= 5900000:
        tool_type = "combo_all"
        plan_type = "Permanent"
        expire_days = 36500
        tool_name = "👑 COMBO ALL 3 TOOL VIP"
    elif amount_in >= 4500000:
        tool_type = "combo_2"
        plan_type = "Permanent"
        expire_days = 36500
        tool_name = "⚡ COMBO 2 TOOL"
    elif amount_in >= 2990000:
        tool_type = "combo_all"
        plan_type = "Yearly"
        expire_days = 365
        tool_name = "👑 COMBO ALL 3 TOOL VIP"
    elif amount_in >= 2490000:
        tool_type = "combo_2"
        plan_type = "Yearly"
        expire_days = 365
        tool_name = "⚡ COMBO 2 TOOL"
    elif amount_in >= 1490000:
        tool_type = "veo3_pro"
        plan_type = "Yearly"
        expire_days = 365
        tool_name = "🤖 VEO3 PRO"
    elif amount_in >= 799000:
        tool_type = "combo_2"
        plan_type = "Monthly"
        expire_days = 90
        tool_name = "⚡ COMBO 2 TOOL"
    elif amount_in >= 499000:
        tool_type = "veo3_pro"
        plan_type = "Monthly"
        expire_days = 90
        tool_name = "🤖 VEO3 PRO"
    elif amount_in >= 399000:
        tool_type = "combo_all"
        plan_type = "Monthly"
        expire_days = 30
        tool_name = "👑 COMBO ALL 3 TOOL VIP"
    elif amount_in >= 300000:
        tool_type = "combo_2"
        plan_type = "Monthly"
        expire_days = 30
        tool_name = "⚡ COMBO 2 TOOL"
    else:
        tool_type = "veo3_pro"
        plan_type = "Monthly"
        expire_days = 30
        tool_name = "🤖 VEO3 PRO"

    # Tạo License Key
    expire_dt = datetime.now(timezone.utc) + timedelta(days=expire_days)
    customer_email = f"client_{order_code.lower()}@telegram.com"

    try:
        new_license = await create_license_record(
            db=db,
            customer_name=f"Order {order_code}",
            customer_email=customer_email,
            plan_type=plan_type,
            expire_date=expire_dt,
            max_devices=1,
            tool_type=tool_type,
            note=f"Thanh toán SePay TPBank - {order_code} - {amount_in:,}d"
        )
        
        # Ghi log để chống duplicate
        paid_log = Log(action=f"PAID_{order_code}", details=f"License: {new_license.license_key}, Amount: {amount_in}")
        db.add(paid_log)
        await db.commit()

        # Báo thông báo cho Admin
        for admin_id in ADMIN_IDS:
            admin_msg = (
                f"🔔 <b>SEPAY TPBANK: NHẬN THANH TOÁN TỰ ĐỘNG!</b>\n\n"
                f"💰 Số tiền: <b>+{amount_in:,} VNĐ</b>\n"
                f"📦 Sản phẩm: {tool_name}\n"
                f"🔖 Mã đơn: <code>{order_code}</code>\n"
                f"🔑 Key đã cấp: <code>{new_license.license_key}</code>"
            )
            await send_telegram_msg(admin_id, admin_msg)

        return {
            "status": "success",
            "order_code": order_code,
            "license_key": new_license.license_key,
            "amount": amount_in
        }

    except Exception as e:
        print(f"[!] Error creating license in SePay webhook: {e}")
        return {"status": "error", "message": str(e)}

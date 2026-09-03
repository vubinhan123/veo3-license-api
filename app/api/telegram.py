import os
import sys
import logging
from fastapi import APIRouter, Request
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update, BotCommand

# Thêm đường dẫn bot vào sys.path
bot_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot")
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from config import config
from handlers.start import router as start_router
from handlers.shop import router as shop_router
from handlers.admin import router as admin_router
from database import init_db

logger = logging.getLogger("TelegramWebhook")

router = APIRouter()

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(admin_router)
dp.include_router(start_router)
dp.include_router(shop_router)

async def setup_telegram_webhook():
    """Đăng ký Webhook chính thức với máy chủ Telegram để chạy 24/7/365"""
    init_db()
    commands = [
        BotCommand(command="start", description="🏠 Khởi động / Menu chính"),
        BotCommand(command="menu", description="🛒 Danh mục Tool & Bảng giá"),
        BotCommand(command="renew", description="🔄 Gia hạn License Key"),
        BotCommand(command="voucher", description="🎟️ Nhập mã giảm giá"),
        BotCommand(command="orders", description="📋 Xem lại License Key đã mua"),
        BotCommand(command="support", description="📞 Hỗ trợ kỹ thuật 24/7"),
    ]
    try:
        await bot.set_my_commands(commands)
    except Exception as e:
        logger.warning(f"Error setting bot commands: {e}")

    webhook_url = "https://veo3-license-api.onrender.com/api/v1/telegram/webhook"
    try:
        await bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=False
        )
        print(f"✅ [24/7 CLOUD] Telegram Webhook registered: {webhook_url}")
    except Exception as e:
        print(f"❌ [!] Failed to set Telegram Webhook: {e}")

@router.post("/webhook")
async def handle_telegram_update(request: Request):
    """Nhận và xử lý tức thì mọi sự kiện từ Telegram qua Webhook 24/7"""
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error handling Telegram update: {e}")
        return {"ok": False, "error": str(e)}

@router.get("/status")
async def get_telegram_status():
    """Kiểm tra trạng thái Webhook"""
    info = await bot.get_webhook_info()
    return {
        "status": "online",
        "webhook_url": info.url,
        "pending_updates": info.pending_update_count
    }

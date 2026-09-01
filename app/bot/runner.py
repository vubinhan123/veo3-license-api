import asyncio
import os
import sys

# Đảm bảo đường dẫn import cho bot
bot_dir = os.path.dirname(os.path.abspath(__file__))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import config
from handlers.start import router as start_router
from handlers.shop import router as shop_router
from handlers.admin import router as admin_router
from database import init_db

telegram_bot_instance = Bot(token=config.BOT_TOKEN)
telegram_dp_instance = Dispatcher(storage=MemoryStorage())

telegram_dp_instance.include_router(admin_router)
telegram_dp_instance.include_router(start_router)
telegram_dp_instance.include_router(shop_router)

async def setup_bot_commands(bot: Bot):
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
        print(f"[!] Warning set commands: {e}")

async def start_telegram_bot_cloud():
    """Khởi chạy Bot Telegram trên máy chủ Render Cloud 24/7/365"""
    try:
        init_db()
        await telegram_bot_instance.delete_webhook(drop_pending_updates=True)
        await setup_bot_commands(telegram_bot_instance)
        print("🤖 [CLOUD 24/7] Telegram Shop Bot (@tool_tu_dong_bot) da khoi dong thanh cong tren Cloud Render!")
        await telegram_dp_instance.start_polling(telegram_bot_instance)
    except Exception as e:
        print(f"[!] Telegram Bot Cloud runner error: {e}")

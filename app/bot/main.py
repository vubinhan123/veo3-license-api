import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from handlers.start import router as start_router
from handlers.shop import router as shop_router
from handlers.admin import router as admin_router
from sepay import process_payment_webhook

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("VBA_TelegramBot")

# Khởi tạo Bot và Dispatcher
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(admin_router)
dp.include_router(start_router)
dp.include_router(shop_router)

# -----------------------------------------------------------------------------
# WEB SERVER NHẬN WEBHOOK TỪ SEPAY (MBBANK)
# -----------------------------------------------------------------------------
async def handle_sepay_webhook(request: web.Request):
    """Endpoint nhận biến động số dư từ SePay"""
    try:
        data = await request.json()
        logger.info(f"Nhận webhook SePay: {data}")
        success = await process_payment_webhook(data, bot)
        return web.json_response({"status": "success" if success else "ignored"}, status=200)
    except Exception as e:
        logger.error(f"Lỗi xử lý webhook: {e}")
        return web.json_response({"error": str(e)}, status=400)

async def handle_health(request: web.Request):
    return web.json_response({"status": "online", "bot": "VBA Auto Shop Bot"})

async def start_webhook_server():
    app = web.Application()
    app.router.add_post("/sepay-webhook", handle_sepay_webhook)
    app.router.add_post("/api/sepay", handle_sepay_webhook)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/", handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.SEPAY_WEBHOOK_PORT)
    await site.start()
    logger.info(f"🚀 SePay Webhook Server đang lắng nghe trên cổng {config.SEPAY_WEBHOOK_PORT}...")

from aiogram.types import BotCommand

async def setup_bot_commands(bot: Bot):
    """Cài đặt danh sách lệnh hiển thị trong nút Menu góc dưới bên trái"""
    commands = [
        BotCommand(command="start", description="🏠 Khởi động / Menu chính"),
        BotCommand(command="menu", description="🛒 Danh mục Tool & Bảng giá"),
        BotCommand(command="renew", description="🔄 Gia hạn License Key"),
        BotCommand(command="voucher", description="🎟️ Nhập mã giảm giá"),
        BotCommand(command="orders", description="📋 Xem lại License Key đã mua"),
        BotCommand(command="support", description="📞 Hỗ trợ kỹ thuật 24/7"),
    ]
    await bot.set_my_commands(commands)

# -----------------------------------------------------------------------------
# MAIN ASYNC RUNNER
# -----------------------------------------------------------------------------
async def main():
    logger.info("🤖 Đang khởi động Telegram Shop Bot (@tool_tu_dong_bot)...")
    
    # 1. Chạy Webhook Server nhận thanh toán ngầm
    await start_webhook_server()
    
    # 2. Xóa webhook cũ & cài đặt nút Menu lệnh góc trái
    await bot.delete_webhook(drop_pending_updates=True)
    await setup_bot_commands(bot)
    logger.info("✅ Đã thiết lập nút Menu góc trái và sẵn sàng phục vụ!")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot đã dừng.")

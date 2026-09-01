from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import register_user
from config import config

router = Router()

def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="🤖 1. VEO3 PRO — Video AI (179k/tháng)", callback_data="select_tool_veo3_pro")],
        [InlineKeyboardButton(text="🎨 2. IMAGE PRO — Xử Lý Ảnh (179k/tháng)", callback_data="select_tool_image_pro")],
        [InlineKeyboardButton(text="🎙️ 3. TOOL VOICE — Lồng Tiếng (179k/tháng)", callback_data="select_tool_tool_voice")],
        [
            InlineKeyboardButton(text="⚡ COMBO 2 TOOL (300k)", callback_data="select_tool_combo_2"),
            InlineKeyboardButton(text="👑 COMBO ALL 3 TOOL (399k)", callback_data="select_tool_combo_all")
        ],
        [
            InlineKeyboardButton(text="🔄 GIA HẠN KEY CŨ", callback_data="menu_renew_key"),
            InlineKeyboardButton(text="🎟️ NHẬP VOUCHER", callback_data="menu_enter_voucher")
        ],
        [
            InlineKeyboardButton(text="📋 LỊCH SỬ ĐƠN HÀNG", callback_data="menu_my_orders"),
            InlineKeyboardButton(text="📞 HỖ TRỢ KỸ THUẬT", url=config.SUPPORT_URL)
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name or ""
    
    register_user(user_id, username, full_name)
    if user_id not in config.ADMIN_IDS:
        config.ADMIN_IDS.append(user_id)
        
    welcome_text = (
        f"👋 <b>Xin chào {full_name}!</b>\n\n"
        f"Chào mừng bạn đến với <b>Hệ Thống Bán Phần Mềm Tự Động VBA Automation</b> 🚀\n\n"
        f"🔥 <b>DANH MỤC TOÀN BỘ 3 TOOL HIỆN CÓ:</b>\n"
        f"1️⃣ <b>VEO3 PRO</b>: Tự động hóa tạo & render Video AI chuyên nghiệp (179k/tháng)\n"
        f"2️⃣ <b>IMAGE PRO</b>: Tạo, biến đổi & xử lý ảnh hàng loạt siêu tốc (179k/tháng)\n"
        f"3️⃣ <b>TOOL VOICE</b>: Lồng tiếng, dịch & clone giọng đọc AI đỉnh cao (179k/tháng)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>Gói Combo Tiết Kiệm:</b>\n"
        f"• Combo 2 Tool / 2 Máy: <b>300.000đ/tháng</b>\n"
        f"• Combo Trọn Bộ 3 Tool: <b>399.000đ/tháng</b>\n\n"
        f"👇 <b>Chạm trực tiếp vào Tool bạn muốn mua bên dưới:</b>"
    )
    
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "back_to_main")
@router.callback_query(F.data == "cancel_order")
async def back_to_main_menu(call: CallbackQuery):
    welcome_text = (
        f"👋 <b>MENU CHÍNH - VBA AUTOMATION SHOP</b> 🚀\n\n"
        f"👇 <b>Vui lòng chọn danh mục bên dưới để tiếp tục:</b>"
    )
    try:
        await call.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")
    except Exception:
        try:
            await call.message.delete()
        except:
            pass
        await call.message.answer(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")
    await call.answer("Đã trở về Menu Chính")

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    welcome_text = (
        f"🛒 <b>DANH MỤC PHẦN MỀM TỰ ĐỘNG HÓA VBA AUTOMATION</b> 🚀\n\n"
        f"👇 <b>Vui lòng chọn danh mục bên dưới:</b>"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")

@router.message(Command("support"))
async def cmd_support(message: Message):
    support_text = (
        f"📞 <b>TRUNG TÂM HỖ TRỢ KỸ THUẬT VBA AUTOMATION</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"• Hỗ trợ kích hoạt, cài đặt và bảo hành 24/7.\n"
        f"• Telegram trực tiếp: <a href='{config.SUPPORT_URL}'>@vubinhan</a>\n"
        f"• Hotline / Zalo: <b>0944.336.336</b>\n"
    )
    await message.answer(support_text, parse_mode="HTML", disable_web_page_preview=True)

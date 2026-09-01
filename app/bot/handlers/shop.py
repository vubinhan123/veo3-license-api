import random
import re
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import config
from database import (
    get_product, get_all_products, create_order, get_order_by_code,
    get_voucher, use_voucher, get_user_orders, mark_order_paid
)
from sepay import generate_vietqr_url
from key_api import key_client

router = Router()

class OrderState(StatesGroup):
    waiting_for_email = State()

class VoucherState(StatesGroup):
    waiting_for_code = State()

class RenewState(StatesGroup):
    waiting_for_key = State()

async def auto_expire_order_timer(bot, chat_id: int, message_id: int, order_code: str, delay_seconds: int = 300):
    """Tự động đếm ngược 5 phút (300s): Nếu chưa thanh toán thì tự động xóa mã QR và hủy đơn hàng"""
    await asyncio.sleep(delay_seconds)
    order = get_order_by_code(order_code)
    if order and order["status"] == "pending":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET status = 'expired' WHERE order_code = ? AND status = 'pending'", (order_code,))
        conn.commit()
        conn.close()

        # Xóa tin nhắn ảnh QR
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass

        # Gửi thông báo hết hạn
        from handlers.start import get_main_menu_keyboard
        expire_msg = (
            f"⏰ <b>ĐƠN HÀNG ĐÃ HẾT HẠN THANH TOÁN (5 PHÚT)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>Sản phẩm:</b> {order['tool_name']}\n"
            f"🔖 <b>Mã đơn:</b> <code>{order_code}</code>\n"
            f"❌ <i>Mã QR thanh toán đã tự động hủy do quá hạn 5 phút.</i>\n\n"
            f"👇 <b>Vui lòng chọn lại sản phẩm bạn muốn mua hoặc gia hạn bên dưới:</b>"
        )
        try:
            await bot.send_message(chat_id=chat_id, text=expire_msg, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")
        except Exception:
            pass

# -----------------------------------------------------------------------------
# 1. DANH MỤC TOOL & COMBO
# -----------------------------------------------------------------------------
@router.callback_query(F.data == "menu_single_tools")
async def show_single_tools(call: CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="🤖 VEO3 PRO (179k/tháng/máy)", callback_data="select_tool_veo3_pro")],
        [InlineKeyboardButton(text="🎨 IMAGE PRO (179k/tháng/máy)", callback_data="select_tool_image_pro")],
        [InlineKeyboardButton(text="🎙️ TOOL VOICE (179k/tháng/máy)", callback_data="select_tool_tool_voice")],
        [InlineKeyboardButton(text="🔙 Quay Lại Menu Chính", callback_data="back_to_main")]
    ]
    text = (
        "🛒 <b>DANH MỤC PHẦN MỀM TỰ ĐỘNG HÓA CHUYÊN NGHIỆP</b>\n\n"
        "Vui lòng chọn Tool bạn muốn mua hoặc nâng cấp bản quyền:"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "menu_combo_tools")
async def show_combo_tools(call: CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="⚡ COMBO 2 TOOL / 2 MÁY (300k/tháng)", callback_data="select_tool_combo_2")],
        [InlineKeyboardButton(text="👑 COMBO ALL 3 TOOL VIP (399k/tháng)", callback_data="select_tool_combo_all")],
        [InlineKeyboardButton(text="🔙 Quay Lại Menu Chính", callback_data="back_to_main")]
    ]
    text = (
        "📦 <b>GÓI COMBO PHẦN MỀM TIẾT KIỆM CỰC LỚN</b>\n\n"
        "💡 <i>Gói Combo 2 Tool / 2 Máy chỉ <b>300.000đ/tháng</b> giúp bạn tối ưu chi phí tối đa!</i>\n\n"
        "Vui lòng chọn gói Combo bên dưới:"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await call.answer()

# Khi khách chọn Combo 2 Tool -> Cho khách chọn cụ thể 2 Tool nào
@router.callback_query(F.data == "select_tool_combo_2")
async def choose_combo2_types(call: CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="1️⃣ 🤖 Veo3 Pro + 🎨 Image Pro", callback_data="select_tool_combo2_veo3_image")],
        [InlineKeyboardButton(text="2️⃣ 🤖 Veo3 Pro + 🎙️ Tool Voice", callback_data="select_tool_combo2_veo3_voice")],
        [InlineKeyboardButton(text="3️⃣ 🎨 Image Pro + 🎙️ Tool Voice", callback_data="select_tool_combo2_image_voice")],
        [InlineKeyboardButton(text="4️⃣ 💻 1 Tool Bất Kỳ (Dùng Cho 2 Máy)", callback_data="select_tool_combo2_2devices")],
        [InlineKeyboardButton(text="🔙 Quay Lại Menu Chính", callback_data="back_to_main")]
    ]
    text = (
        "⚡ <b>CHỌN CẶP 2 TOOL TRONG GÓI COMBO (300K/THÁNG)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Bạn được tùy chọn kết hợp 2 công cụ bất kỳ phù hợp với nhu cầu sáng tạo của bạn:</i>\n\n"
        "👇 <b>Vui lòng chọn tổ hợp 2 Tool bên dưới:</b>"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await call.answer()

# -----------------------------------------------------------------------------
# 2. CHỌN GÓI THỜI HẠN
# -----------------------------------------------------------------------------
@router.callback_query(F.data.startswith("select_tool_"))
async def show_plan_options(call: CallbackQuery):
    tool_key = call.data.replace("select_tool_", "")
    
    # Mapping tên sản phẩm cho các gói Combo 2 tùy chọn
    combo_names = {
        "combo2_veo3_image": "⚡ COMBO: [🤖 VEO3 PRO + 🎨 IMAGE PRO]",
        "combo2_veo3_voice": "⚡ COMBO: [🤖 VEO3 PRO + 🎙️ TOOL VOICE]",
        "combo2_image_voice": "⚡ COMBO: [🎨 IMAGE PRO + 🎙️ TOOL VOICE]",
        "combo2_2devices": "⚡ COMBO: 1 TOOL DÙNG CHO 2 MÁY",
    }
    
    base_key = "combo_2" if tool_key.startswith("combo2_") else tool_key
    product = get_product(base_key)
    if not product:
        await call.answer("Không tìm thấy thông tin sản phẩm!", show_alert=True)
        return

    display_name = combo_names.get(tool_key, product['name'])

    keyboard = [
        [InlineKeyboardButton(text=f"📅 Gói 1 Tháng — {product['price_1m']:,}đ", callback_data=f"buy_{tool_key}_1m")],
        [InlineKeyboardButton(text=f"📅 Gói 3 Tháng — {product['price_3m']:,}đ", callback_data=f"buy_{tool_key}_3m")],
        [InlineKeyboardButton(text=f"⭐ Gói 1 Năm — {product['price_1y']:,}đ", callback_data=f"buy_{tool_key}_1y")],
        [InlineKeyboardButton(text=f"♾️ Gói VĨNH VIỄN — {product['price_life']:,}đ", callback_data=f"buy_{tool_key}_life")],
        [InlineKeyboardButton(text="🔙 Chọn Lại Tool Khác", callback_data="back_to_main" if not tool_key.startswith("combo2_") else "select_tool_combo_2")]
    ]

    text = (
        f"📦 <b>{display_name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ <i>Bản quyền chính hãng, không giới hạn máy kích hoạt (1 máy/lần, hỗ trợ đổi máy miễn phí), cập nhật tính năng mới liên tục!</i>\n\n"
        f"👇 <b>Vui lòng chọn thời hạn bạn muốn sử dụng:</b>"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await call.answer()

# -----------------------------------------------------------------------------
# 3. YÊU CẦU NHẬP GMAIL TRƯỚC KHI TẠO ĐƠN HÀNG
# -----------------------------------------------------------------------------
@router.callback_query(F.data.startswith("buy_"))
async def ask_customer_email(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    plan = parts[-1]
    tool_key = "_".join(parts[1:-1])

    combo_names = {
        "combo2_veo3_image": "⚡ COMBO: [🤖 VEO3 PRO + 🎨 IMAGE PRO]",
        "combo2_veo3_voice": "⚡ COMBO: [🤖 VEO3 PRO + 🎙️ TOOL VOICE]",
        "combo2_image_voice": "⚡ COMBO: [🎨 IMAGE PRO + 🎙️ TOOL VOICE]",
        "combo2_2devices": "⚡ COMBO: 1 TOOL DÙNG CHO 2 MÁY",
    }
    base_key = "combo_2" if tool_key.startswith("combo2_") else tool_key
    product = get_product(base_key)
    if not product:
        await call.answer("Lỗi sản phẩm!", show_alert=True)
        return

    display_name = combo_names.get(tool_key, product['name'])

    # Lưu thông tin tạm vào state
    await state.update_data(pending_tool=tool_key, pending_plan=plan, pending_name=display_name)
    await state.set_state(OrderState.waiting_for_email)

    plan_label = "1 Tháng" if plan == "1m" else "3 Tháng" if plan == "3m" else "1 Năm" if plan == "1y" else "Vĩnh Viễn"

    text = (
        f"👇 <b>Gửi Gmail của bạn vào ô chat bên dưới để nhận Key Tool:</b>\n"
        f"<i>(Ví dụ: <code>tudongtoool123@gmail.com</code>)</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Gói:</b> {display_name} ({plan_label})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>Gmail dùng để lưu trữ và bảo hành bản quyền tự động.</i>"
    )
    keyboard = [[InlineKeyboardButton(text="🔙 Hủy Bỏ", callback_data="back_to_main")]]
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await call.answer()

@router.message(OrderState.waiting_for_email)
async def process_email_and_generate_qr(message: Message, state: FSMContext):
    email = message.text.strip().lower()
    
    # Kiểm tra format email
    if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email):
        await message.answer("⚠️ <b>Địa chỉ Gmail không đúng định dạng!</b>\nVui lòng nhập lại đúng chuẩn (Ví dụ: <code>example@gmail.com</code>):", parse_mode="HTML")
        return

    data = await state.get_data()
    tool_key = data.get("pending_tool", "veo3_pro")
    plan = data.get("pending_plan", "1m")
    display_name = data.get("pending_name")
    voucher_code = data.get("applied_voucher")

    base_key = "combo_2" if tool_key.startswith("combo2_") else tool_key
    product = get_product(base_key)
    if not display_name:
        display_name = product["name"]

    plan_days_map = {"1m": 30, "3m": 90, "1y": 365, "life": 36500}
    plan_type_map = {"1m": "Monthly", "3m": "Monthly", "1y": "Yearly", "life": "Permanent"}
    plan_price_map = {
        "1m": product["price_1m"],
        "3m": product["price_3m"],
        "1y": product["price_1y"],
        "life": product["price_life"]
    }

    price = plan_price_map.get(plan, 179000)
    expire_days = plan_days_map.get(plan, 30)
    plan_type = plan_type_map.get(plan, "Monthly")

    discount_amount = 0
    if voucher_code:
        voucher = get_voucher(voucher_code)
        if voucher:
            if voucher["discount_type"] == "percent":
                discount_amount = int(price * voucher["discount_val"] / 100)
            else:
                discount_amount = min(price, voucher["discount_val"])

    final_price = max(0, price - discount_amount)
    order_code = f"TOOL{random.randint(10000, 99999)}"

    # Lưu đơn hàng có Gmail
    create_order(
        order_code=order_code,
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or "",
        customer_email=email,
        order_type="new",
        tool_type=tool_key,
        tool_name=product["name"],
        plan_type=plan_type,
        expire_days=expire_days,
        original_price=price,
        discount_amount=discount_amount,
        final_price=final_price,
        voucher_code=voucher_code
    )

    qr_url = generate_vietqr_url(
        bank_code=config.BANK_CODE,
        account_number=config.BANK_ACCOUNT,
        account_name=config.BANK_ACCOUNT_NAME,
        amount=final_price,
        order_code=order_code
    )

    plan_label = "1 Tháng" if plan == "1m" else "3 Tháng" if plan == "3m" else "1 Năm" if plan == "1y" else "Vĩnh Viễn (Không thời hạn)"

    keyboard = [
        [InlineKeyboardButton(text="🔄 Kiểm Tra Thanh Toán", callback_data=f"check_pay_{order_code}")],
        [
            InlineKeyboardButton(text="🎟️ Nhập Mã Giảm Giá", callback_data="menu_enter_voucher"),
            InlineKeyboardButton(text="🛒 Đổi Gói / Tool Khác", callback_data="menu_single_tools")
        ],
        [InlineKeyboardButton(text="❌ Hủy Đơn & Về Menu Chính", callback_data="cancel_order")]
    ]

    caption = (
        f"💳 <b>THANH TOÁN ĐƠN HÀNG MỚI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Sản phẩm:</b> {display_name} ({plan_label})\n"
        f"📧 <b>Gmail:</b> <code>{email}</code>\n"
    )
    if discount_amount > 0:
        caption += f"🎟️ <b>Voucher:</b> -{discount_amount:,}đ\n"
    caption += (
        f"🔥 <b>Số tiền:</b> <b>{final_price:,} VNĐ</b>\n"
        f"🔖 <b>Nội dung CK:</b> <code>{order_code}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 <b>{config.BANK_CODE}:</b> <code>{config.BANK_ACCOUNT}</code>\n"
        f"👤 <b>Chủ TK:</b> {config.BANK_ACCOUNT_NAME}\n"
        f"⏳ <b>Hạn thanh toán:</b> 5 Phút <i>(Tự động hủy)</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <i>Quét mã chuyển tiền xong là nhận Key tự động trong 2 giây!</i>"
    )

    sent_msg = await message.answer_photo(
        photo=qr_url,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    
    # Bắt đầu đếm ngược 5 phút (300 giây) tự động xóa QR và hủy đơn
    asyncio.create_task(auto_expire_order_timer(
        bot=message.bot,
        chat_id=message.chat.id,
        message_id=sent_msg.message_id,
        order_code=order_code,
        delay_seconds=300
    ))
    
    await state.clear()

# -----------------------------------------------------------------------------
# 4. GIA HẠN LICENSE KEY CŨ
# -----------------------------------------------------------------------------
@router.callback_query(F.data == "menu_renew_key")
async def start_renew_flow(call: CallbackQuery, state: FSMContext):
    await state.set_state(RenewState.waiting_for_key)
    
    user_orders = get_user_orders(call.from_user.id)
    text = (
        "🔄 <b>GIA HẠN LICENSE KEY ĐÃ HẾT HẠN HOẶC SẮP HẾT HẠN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        "Vui lòng <b>gửi Mã License Key bạn muốn gia hạn</b> vào ô chat bên dưới:\n"
        "<i>(Ví dụ: 8DC6-20C7-4CAC-132A-AAB5-09D9-7CDC-BEC4)</i>\n"
    )
    
    keyboard = []
    # Nếu khách đã từng mua key, hiện sẵn danh sách để bấm 1 chạm
    if user_orders:
        text += "\n👇 <b>Hoặc chạm vào Key bạn đã mua bên dưới để gia hạn nhanh:</b>"
        for o in user_orders[:3]:
            keyboard.append([InlineKeyboardButton(
                text=f"🔑 {o['tool_name']} ({o['license_key'][:8]}...)", 
                callback_data=f"renew_select_{o['license_key']}"
            )])

    keyboard.append([InlineKeyboardButton(text="🔙 Hủy Bỏ", callback_data="back_to_main")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("renew_select_"))
async def handle_renew_select(call: CallbackQuery, state: FSMContext):
    key = call.data.replace("renew_select_", "").strip()
    await process_renew_key_lookup(call.message, key, state, is_callback=True)
    await call.answer()

@router.message(RenewState.waiting_for_key)
async def handle_renew_key_input(message: Message, state: FSMContext):
    key = message.text.strip()
    await process_renew_key_lookup(message, key, state, is_callback=False)

async def process_renew_key_lookup(message_or_call, key: str, state: FSMContext, is_callback=False):
    # Tra cứu trên Backend
    lic = await key_client.find_license_by_key(key)
    
    if not lic:
        msg = "❌ <b>Không tìm thấy License Key này trên hệ thống!</b>\nVui lòng kiểm tra lại mã Key và gửi lại:"
        if is_callback:
            await message_or_call.answer(msg, parse_mode="HTML")
        else:
            await message_or_call.answer(msg, parse_mode="HTML")
        return

    tool_type = lic.get("tool_type", "veo3_pro")
    product = get_product(tool_type) or get_product("veo3_pro")
    
    # Lưu thông tin gia hạn vào state
    await state.update_data(
        renew_lic_id=lic["id"],
        renew_key=key,
        renew_tool=tool_type,
        renew_tool_name=product["name"]
    )

    keyboard = [
        [InlineKeyboardButton(text=f"📅 Gia Hạn 1 Tháng — {product['price_1m']:,}đ", callback_data="do_renew_1m")],
        [InlineKeyboardButton(text=f"📅 Gia Hạn 3 Tháng — {product['price_3m']:,}đ", callback_data="do_renew_3m")],
        [InlineKeyboardButton(text=f"⭐ Gia Hạn 1 Năm — {product['price_1y']:,}đ", callback_data="do_renew_1y")],
        [InlineKeyboardButton(text=f"♾️ Nâng Cấp VĨNH VIỄN — {product['price_life']:,}đ", callback_data="do_renew_life")],
        [InlineKeyboardButton(text="🔙 Hủy Bỏ", callback_data="cancel_order")]
    ]

    exp_text = (lic.get("expire_date") or "").split("T")[0]
    text = (
        f"✅ <b>TÌM THẤY THÔNG TIN LICENSE KEY:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 <b>Mã Key:</b> <code>{key}</code>\n"
        f"📦 <b>Tool:</b> {product['name']}\n"
        f"⏳ <b>Hạn hiện tại:</b> {exp_text}\n"
        f"🔄 <b>Trạng thái:</b> {lic.get('status', 'active').upper()}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 <b>Vui lòng chọn thời gian bạn muốn gia hạn cộng thêm:</b>"
    )

    if is_callback:
        await message_or_call.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    else:
        await message_or_call.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("do_renew_"))
async def process_renew_checkout(call: CallbackQuery, state: FSMContext):
    plan = call.data.replace("do_renew_", "")
    data = await state.get_data()
    
    lic_id = data.get("renew_lic_id")
    license_key = data.get("renew_key")
    tool_key = data.get("renew_tool", "veo3_pro")
    tool_name = data.get("renew_tool_name", "VEO3 PRO")

    product = get_product(tool_key)
    plan_days_map = {"1m": 30, "3m": 90, "1y": 365, "life": 36500}
    plan_type_map = {"1m": "Monthly", "3m": "Monthly", "1y": "Yearly", "life": "Permanent"}
    plan_price_map = {
        "1m": product["price_1m"],
        "3m": product["price_3m"],
        "1y": product["price_1y"],
        "life": product["price_life"]
    }

    price = plan_price_map.get(plan, 179000)
    expire_days = plan_days_map.get(plan, 30)
    plan_type = plan_type_map.get(plan, "Monthly")

    order_code = f"TOOL{random.randint(10000, 99999)}"

    # Lưu đơn hàng GIA HẠN vào DB
    create_order(
        order_code=order_code,
        user_id=call.from_user.id,
        username=call.from_user.username or "",
        full_name=call.from_user.full_name or "",
        customer_email="",
        order_type="renew",
        renew_license_id=lic_id,
        tool_type=tool_key,
        tool_name=tool_name,
        plan_type=plan_type,
        expire_days=expire_days,
        original_price=price,
        discount_amount=0,
        final_price=price,
        voucher_code=""
    )

    qr_url = generate_vietqr_url(
        bank_code=config.BANK_CODE,
        account_number=config.BANK_ACCOUNT,
        account_name=config.BANK_ACCOUNT_NAME,
        amount=price,
        order_code=order_code
    )

    plan_label = "1 Tháng" if plan == "1m" else "3 Tháng" if plan == "3m" else "1 Năm" if plan == "1y" else "Vĩnh Viễn (Không thời hạn)"

    keyboard = [
        [InlineKeyboardButton(text="🔄 Kiểm Tra Thanh Toán", callback_data=f"check_pay_{order_code}")],
        [InlineKeyboardButton(text="❌ Hủy Đơn & Về Menu Chính", callback_data="cancel_order")]
    ]

    caption = (
        f"💳 <b>THANH TOÁN GIA HẠN KEY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Sản phẩm:</b> {tool_name}\n"
        f"⏳ <b>Gia hạn:</b> +{expire_days} ngày ({plan_label})\n"
        f"🔑 <b>Key:</b> <code>{license_key}</code>\n"
        f"🔥 <b>Số tiền:</b> <b>{price:,} VNĐ</b>\n"
        f"🔖 <b>Nội dung CK:</b> <code>{order_code}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 <b>{config.BANK_CODE}:</b> <code>{config.BANK_ACCOUNT}</code>\n"
        f"👤 <b>Chủ TK:</b> {config.BANK_ACCOUNT_NAME}\n"
        f"⏳ <b>Hạn thanh toán:</b> 5 Phút <i>(Tự động hủy)</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <i>Quét mã chuyển tiền xong là Key được kích hoạt cộng ngày tự động tức thì!</i>"
    )

    try:
        await call.message.delete()
    except:
        pass

    sent_msg = await call.message.answer_photo(
        photo=qr_url,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    
    # Bắt đầu đếm ngược 5 phút (300 giây) tự động xóa QR và hủy đơn
    asyncio.create_task(auto_expire_order_timer(
        bot=call.bot,
        chat_id=call.message.chat.id,
        message_id=sent_msg.message_id,
        order_code=order_code,
        delay_seconds=300
    ))
    
    await state.clear()
    await call.answer()

# -----------------------------------------------------------------------------
# 5. CÁC TIỆN ÍCH KHÁC (CHECK PAY, LỊCH SỬ, VOUCHER)
# -----------------------------------------------------------------------------
@router.callback_query(F.data.startswith("check_pay_"))
async def manual_check_payment(call: CallbackQuery):
    order_code = call.data.replace("check_pay_", "")
    order = get_order_by_code(order_code)
    
    if not order:
        await call.answer("Đơn hàng không tồn tại hoặc đã hết hạn!", show_alert=True)
        return

    if order["status"] == "paid":
        await call.answer("✅ Đơn hàng đã thanh toán thành công!", show_alert=True)
    else:
        await call.answer(
            f"⏳ Đang chờ nhận tiền cho đơn {order_code}...\n\nNếu bạn đã chuyển khoản, hệ thống sẽ tự động giao Key trong vòng 1-3 giây!",
            show_alert=True
        )

@router.callback_query(F.data == "menu_my_orders")
async def show_my_orders(call: CallbackQuery):
    user_id = call.from_user.id
    orders = get_user_orders(user_id)

    if not orders:
        text = "📋 Bạn chưa có đơn hàng bản quyền nào đã thanh toán.\nHãy chọn mua tool để trải nghiệm nhé!"
        keyboard = [[InlineKeyboardButton(text="🛒 Mua Tool Ngay", callback_data="menu_single_tools")]]
        await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await call.answer()
        return

    text = "📋 <b>LỊCH SỬ LICENSE KEY BẢN QUYỀN CỦA BẠN:</b>\n\n"
    for idx, o in enumerate(orders[:5], 1):
        text += (
            f"<b>{idx}. {o['tool_name']}</b>\n"
            f"• Gói: {o['plan_type']} ({o['expire_days']} ngày)\n"
            f"• Mã Key: <code>{o['license_key']}</code>\n"
            f"• Ngày mua: {o['paid_at']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )

    keyboard = [[InlineKeyboardButton(text="🔙 Quay Lại Menu", callback_data="back_to_main")]]
    await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "menu_enter_voucher")
async def ask_voucher(call: CallbackQuery, state: FSMContext):
    await state.set_state(VoucherState.waiting_for_code)
    text = (
        "🎟️ <b>NHẬP MÃ GIẢM GIÁ (VOUCHER)</b>\n\n"
        "Vui lòng gửi mã giảm giá của bạn vào ô chat (Ví dụ: <code>VBA20</code> hoặc <code>GIAM50K</code>):"
    )
    keyboard = [[InlineKeyboardButton(text="🔙 Hủy Bỏ", callback_data="back_to_main")]]
    await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await call.answer()

@router.message(VoucherState.waiting_for_code)
async def process_voucher_input(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    voucher = get_voucher(code)

    if not voucher:
        await message.answer("❌ Mã giảm giá không tồn tại hoặc đã hết hạn!\nVui lòng thử lại hoặc gõ /start để quay lại menu.")
        return

    if voucher["current_uses"] >= voucher["max_uses"]:
        await message.answer("⚠️ Mã giảm giá này đã hết lượt sử dụng!")
        await state.clear()
        return

    await state.update_data(applied_voucher=code)
    discount_desc = f"{voucher['discount_val']}%" if voucher["discount_type"] == "percent" else f"{voucher['discount_val']:,}đ"
    
    keyboard = [
        [InlineKeyboardButton(text="🛒 Mua Tool Ngay Để Áp Dụng", callback_data="menu_single_tools")],
        [InlineKeyboardButton(text="📦 Mua Gói Combo", callback_data="menu_combo_tools")]
    ]
    await message.answer(
        f"🎉 <b>Áp dụng mã <code>{code}</code> thành công!</b>\n"
        f"Bạn được giảm <b>{discount_desc}</b> cho đơn hàng tiếp theo.\n\n"
        f"Hãy chọn sản phẩm bạn muốn mua ngay:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    await state.clear()

# -----------------------------------------------------------------------------
# CÁC LỆNH TRỰC TIẾP TỪ MENU GÓC TRÁI (/renew, /voucher, /orders)
# -----------------------------------------------------------------------------
from aiogram.filters import Command

@router.message(Command("renew"))
async def cmd_renew_direct(message: Message, state: FSMContext):
    await state.set_state(RenewState.waiting_for_key)
    user_orders = get_user_orders(message.from_user.id)
    text = (
        "🔄 <b>GIA HẠN LICENSE KEY ĐÃ HẾT HẠN HOẶC SẮP HẾT HẠN</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        "Vui lòng <b>gửi Mã License Key bạn muốn gia hạn</b> vào ô chat bên dưới:\n"
        "<i>(Ví dụ: 8DC6-20C7-4CAC-132A-AAB5-09D9-7CDC-BEC4)</i>\n"
    )
    keyboard = []
    if user_orders:
        text += "\n👇 <b>Hoặc chạm vào Key bạn đã mua bên dưới để gia hạn nhanh:</b>"
        for o in user_orders[:3]:
            keyboard.append([InlineKeyboardButton(
                text=f"🔑 {o['tool_name']} ({o['license_key'][:8]}...)", 
                callback_data=f"renew_select_{o['license_key']}"
            )])
    keyboard.append([InlineKeyboardButton(text="🔙 Hủy Bỏ", callback_data="back_to_main")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.message(Command("voucher"))
async def cmd_voucher_direct(message: Message, state: FSMContext):
    await state.set_state(VoucherState.waiting_for_code)
    text = (
        "🎟️ <b>NHẬP MÃ GIẢM GIÁ (VOUCHER)</b>\n\n"
        "Vui lòng gửi mã giảm giá của bạn vào ô chat (Ví dụ: <code>VBA20</code> hoặc <code>GIAM50K</code>):"
    )
    keyboard = [[InlineKeyboardButton(text="🔙 Hủy Bỏ", callback_data="back_to_main")]]
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.message(Command("orders"))
@router.callback_query(F.data == "menu_my_orders")
async def cmd_orders_direct(event):
    message = event if isinstance(event, Message) else event.message
    user_id = event.from_user.id
    orders = get_user_orders(user_id)

    if not orders:
        text = (
            "📋 <b>LỊCH SỬ ĐƠN HÀNG CỦA BẠN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Bạn chưa có đơn hàng bản quyền nào đã thanh toán.\n"
            "Hãy bấm nút bên dưới để chọn mua Tool nhé!"
        )
        keyboard = [
            [InlineKeyboardButton(text="🛒 Mua Tool Ngay", callback_data="back_to_main")]
        ]
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
            await event.answer()
        else:
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
        return

    text = (
        "📋 <b>LỊCH SỬ LICENSE KEY BẢN QUYỀN CỦA BẠN</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    for idx, o in enumerate(orders[:10], 1):
        email_str = f"\n• Gmail: <code>{o['customer_email']}</code>" if o.get("customer_email") else ""
        text += (
            f"<b>{idx}. {o['tool_name']}</b>\n"
            f"• Gói: {o['plan_type']} ({o['expire_days']} ngày){email_str}\n"
            f"• Key: <code>{o['license_key']}</code>\n"
            f"• Ngày mua: {o['paid_at']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )

    keyboard = [
        [InlineKeyboardButton(text="🔄 Gia Hạn Key Nhanh", callback_data="menu_renew_key")],
        [InlineKeyboardButton(text="🔙 Quay Lại Menu", callback_data="back_to_main")]
    ]
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
        await event.answer()
    else:
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

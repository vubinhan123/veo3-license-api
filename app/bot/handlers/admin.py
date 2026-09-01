from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from config import config
from database import get_stats, get_db, update_product_price, get_order_by_code

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS

@router.message(Command("thongke"))
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    stats = get_stats()
    text = (
        f"📊 <b>BÁO CÁO DOANH THU & HOẠT ĐỘNG SHOP (VBA AUTO)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Tổng khách hàng:</b> {stats['total_users']:,} người\n"
        f"📦 <b>Tổng đơn đã bán:</b> {stats['total_orders']:,} đơn\n"
        f"💰 <b>Tổng doanh thu:</b> <b>{stats['total_revenue']:,} VNĐ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>Hôm nay:</b> {stats['orders_today']} đơn | <b>+{stats['revenue_today']:,}đ</b>\n"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("vouchers"))
async def admin_list_vouchers(message: Message):
    if not is_admin(message.from_user.id):
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vouchers WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("Chưa có mã giảm giá nào đang hoạt động!")
        return

    text = "🎟️ <b>DANH SÁCH MÃ GIẢM GIÁ (VOUCHERS) ĐANG CHẠY:</b>\n\n"
    for r in rows:
        val = f"{r['discount_val']}%" if r["discount_type"] == "percent" else f"{r['discount_val']:,}đ"
        text += (
            f"• <b>{r['code']}</b>: Giảm {val} | Đã dùng: {r['current_uses']}/{r['max_uses']} lượt\n"
        )
    text += "\n<i>Cú pháp tạo mã mới: /addvoucher [MÃ] [GIÁ_TRỊ] [SỐ_LƯỢNG]\nVí dụ: /addvoucher KM30 30 50 (Giảm 30% cho 50 lượt)</i>"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("addvoucher"))
async def admin_add_voucher(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    # /addvoucher CODE VALUE MAX_USES
    if len(parts) < 4:
        await message.answer(
            "⚠️ <b>Sai cú pháp!</b>\n"
            "Ví dụ giảm 20%: <code>/addvoucher SALE20 20 100</code>\n"
            "Ví dụ giảm 50k: <code>/addvoucher GIAM50K 50000 50</code>",
            parse_mode="HTML"
        )
        return

    code = parts[1].upper()
    val = int(parts[2])
    max_uses = int(parts[3])
    disc_type = "percent" if val <= 100 else "fixed"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO vouchers (code, discount_type, discount_val, max_uses, current_uses, is_active)
    VALUES (?, ?, ?, ?, 0, 1)
    ON CONFLICT(code) DO UPDATE SET discount_val=excluded.discount_val, max_uses=excluded.max_uses, is_active=1
    """, (code, disc_type, val, max_uses))
    conn.commit()
    conn.close()

    val_str = f"{val}%" if disc_type == "percent" else f"{val:,}đ"
    await message.answer(f"✅ Đã tạo/cập nhật Voucher <b>{code}</b> thành công (Giảm {val_str} cho {max_uses} lượt)!", parse_mode="HTML")

@router.message(Command("setgia"))
async def admin_set_price(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    # /setgia [tool_key] [1m|3m|1y|life] [price]
    if len(parts) < 4:
        await message.answer(
            "⚠️ <b>Cú pháp đổi giá:</b>\n"
            "<code>/setgia [tool] [goi] [gia_tien]</code>\n\n"
            "Ví dụ: <code>/setgia veo3_pro 1m 250000</code>\n"
            "Tools: <code>veo3_pro</code>, <code>image_pro</code>, <code>tool_voice</code>, <code>combo_2</code>, <code>combo_all</code>\n"
            "Gói: <code>1m</code>, <code>3m</code>, <code>1y</code>, <code>life</code>",
            parse_mode="HTML"
        )
        return

    tool_key = parts[1]
    plan = parts[2]
    price = int(parts[3])

    try:
        update_product_price(tool_key, plan, price)
        await message.answer(f"✅ Đã cập nhật giá <b>{tool_key}</b> gói <b>{plan}</b> thành <b>{price:,} VNĐ</b>!", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Lỗi cập nhật giá: {e}")

@router.message(Command("checkorder"))
async def admin_check_order(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("⚠️ Gõ: <code>/checkorder [MÃ_ĐƠN]</code> (Ví dụ: /checkorder VBA1234)", parse_mode="HTML")
        return

    order_code = parts[1].upper()
    order = get_order_by_code(order_code)
    if not order:
        await message.answer("❌ Không tìm thấy đơn hàng này!")
        return

    text = (
        f"🔖 <b>CHI TIẾT ĐƠN HÀNG {order_code}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Khách: @{order['username']} (ID: {order['user_id']})\n"
        f"📦 Sản phẩm: {order['tool_name']}\n"
        f"⏳ Gói: {order['plan_type']} ({order['expire_days']} ngày)\n"
        f"💵 Số tiền: {order['final_price']:,}đ\n"
        f"🔄 Trạng thái: <b>{order['status'].upper()}</b>\n"
        f"🔑 Key đã cấp: <code>{order['license_key'] or 'Chưa cấp'}</code>\n"
        f"🕒 Tạo lúc: {order['created_at']}\n"
        f"✅ Thanh toán lúc: {order['paid_at'] or 'Chưa'}\n"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("broadcast"))
async def admin_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return

    content = message.text.replace("/broadcast", "").strip()
    if not content:
        await message.answer("⚠️ Gõ: <code>/broadcast [Nội dung tin nhắn muốn gửi cho tất cả khách]</code>", parse_mode="HTML")
        return

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    sent = 0
    for u in users:
        try:
            await message.bot.send_message(chat_id=u["user_id"], text=f"📢 <b>THÔNG BÁO TỪ VBA AUTOMATION:</b>\n\n{content}", parse_mode="HTML")
            sent += 1
        except:
            pass

    await message.answer(f"✅ Đã gửi thông báo thành công đến <b>{sent}/{len(users)}</b> khách hàng!", parse_mode="HTML")

@router.message(Command("testpay"))
async def admin_simulate_pay(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("⚠️ Gõ: <code>/testpay [MÃ_ĐƠN]</code> (Ví dụ: <code>/testpay VBA8291</code>)", parse_mode="HTML")
        return

    order_code = parts[1].upper()
    order = get_order_by_code(order_code)
    if not order:
        await message.answer(f"❌ Không tìm thấy đơn hàng mã <code>{order_code}</code>!", parse_mode="HTML")
        return

    from sepay import process_payment_webhook
    fake_webhook_data = {
        "content": f"{order_code} chuyen tien test",
        "transferAmount": order["final_price"],
        "transferType": "in",
        "gateway": "MBBank"
    }
    await message.answer(f"⏳ Đang giả lập thanh toán <b>{order['final_price']:,}đ</b> cho đơn <code>{order_code}</code>...", parse_mode="HTML")
    success = await process_payment_webhook(fake_webhook_data, message.bot)
    if success:
        await message.answer(f"✅ Giả lập thanh toán đơn <code>{order_code}</code> thành công! Đã tự động tạo và gửi Key cho khách hàng!", parse_mode="HTML")
    else:
        await message.answer("❌ Giả lập thanh toán thất bại!", parse_mode="HTML")


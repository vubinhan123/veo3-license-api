import urllib.parse
from config import config
from database import get_order_by_code, mark_order_paid
from key_api import key_client

def generate_vietqr_url(bank_code: str, account_number: str, account_name: str, amount: int, order_code: str) -> str:
    """Tạo link ảnh mã QR sạch tinh gọn (chỉ mã QR, không khung viền thừa)"""
    encoded_name = urllib.parse.quote(account_name)
    encoded_desc = urllib.parse.quote(order_code)
    # Template qr_only: Chỉ hiển thị duy nhất mã QR vuông gọn gàng
    return f"https://img.vietqr.io/image/{bank_code.lower()}-{account_number}-qr_only.png?amount={amount}&addInfo={encoded_desc}&accountName={encoded_name}"

async def process_payment_webhook(data: dict, bot) -> bool:
    """
    Xử lý Webhook bắn sang từ SePay khi có biến động số dư MBBank
    Format SePay mẫu:
    {
      "gateway": "MBBank",
      "transactionDate": "2026-08-29 15:40:00",
      "accountNumber": "0944336336",
      "subAccount": null,
      "code": null,
      "content": "VBA8921 chuyen tien",
      "transferType": "in",
      "description": "...",
      "transferAmount": 200000,
      "referenceCode": "FT26..."
    }
    """
    try:
        content = data.get("content", "") or data.get("description", "") or ""
        amount_in = int(data.get("transferAmount", 0) or data.get("amount", 0) or 0)
        transfer_type = data.get("transferType", "in")

        if transfer_type != "in" or amount_in <= 0:
            return False

        # Tìm mã đơn hàng dạng TOOLxxxx hoặc VBAxxxx trong nội dung chuyển khoản
        import re
        match = re.search(r"((?:TOOL|VBA|KEY|DH)\d+)", content.upper())
        if not match:
            # Fallback nếu viết liền không dấu cách
            match = re.search(r"((?:TOOL|VBA|KEY|DH)\d{4,6})", content.upper().replace(" ", ""))
            
        if not match:
            try:
                print(f"[!] Khong tim thay ma don hang trong noi dung: {content}")
            except:
                pass
            return False

        order_code = match.group(1)
        order = get_order_by_code(order_code)
        if not order:
            try:
                print(f"[!] Khong tim thay don hang ma: {order_code}")
            except:
                pass
            return False

        if order["status"] == "paid":
            print(f"[*] Đơn hàng {order_code} đã được thanh toán trước đó.")
            return True

        # Kiểm tra số tiền
        if amount_in < order["final_price"]:
            print(f"[!] Khách chuyển thiếu: Cần {order['final_price']} nhưng chỉ nhận {amount_in}")
            # Gửi tin nhắn báo khách chuyển thiếu
            try:
                msg = (
                    f"⚠️ <b>THÔNG BÁO CHUYỂN KHOẢN THIẾU TIỀN</b>\n\n"
                    f"📦 Đơn hàng: <code>{order_code}</code>\n"
                    f"💵 Số tiền cần thanh toán: <b>{order['final_price']:,}đ</b>\n"
                    f"📥 Số tiền vừa nhận được: <b>{amount_in:,}đ</b>\n"
                    f"👉 Còn thiếu: <b>{(order['final_price'] - amount_in):,}đ</b>\n\n"
                    f"Vui lòng chuyển tiếp số tiền còn thiếu với cùng nội dung <code>{order_code}</code> để nhận key tự động!"
                )
                await bot.send_message(chat_id=order["user_id"], text=msg, parse_mode="HTML")
            except Exception as e:
                print(f"[!] Lỗi gửi tin nhắn cho user: {e}")
            return False

        order_type = order.get("order_type", "new")
        email = order.get("customer_email") or f"{order['username'] or order['user_id']}@gmail.com"
        email_prefix = email.split("@")[0] if "@" in email else email
        plan_label = "1 Tháng" if order["plan_type"] == "Monthly" else "3 Tháng" if order["expire_days"] == 90 else "1 Năm" if order["plan_type"] == "Yearly" else "Vĩnh Viễn"

        if order_type == "renew":
            # Đơn hàng Gia Hạn
            print(f"[*] Đang thực hiện GIA HẠN cho đơn {order_code} (Key: {order['license_key']})...")
            renew_res = await key_client.renew_license(
                license_id=order["renew_license_id"],
                additional_days=order["expire_days"]
            )
            license_key = order["license_key"]
            mark_order_paid(order_code, license_key)

            success_msg = (
                f"🎉 <b>GIA HẠN BẢN QUYỀN THÀNH CÔNG!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 <b>Sản phẩm:</b> {order['tool_name']}\n"
                f"⏳ <b>Thời gian cộng thêm:</b> +{order['expire_days']} ngày ({plan_label})\n"
                f"💵 <b>Số tiền:</b> {amount_in:,} VNĐ\n"
                f"🔖 <b>Mã đơn:</b> <code>{order_code}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🔑 <b>MÃ LICENSE KEY CỦA BẠN ĐÃ ĐƯỢC KÍCH HOẠT TIẾP TỤC:</b>\n"
                f"👉 <code>{license_key}</code>\n\n"
                f"✨ <i>Bạn có thể tiếp tục mở phần mềm trên máy tính sử dụng bình thường mà không cần đổi mã key mới!</i>\n\n"
                f"💬 <i>Hỗ trợ kỹ thuật:</i> {config.SUPPORT_URL}"
            )
        else:
            # Đơn hàng Mua Mới
            print(f"[*] Đang sinh License Key cho đơn {order_code} ({order['tool_type']})...")
            license_key = await key_client.create_license(
                tool_type=order["tool_type"],
                plan_type=order["plan_type"],
                expire_days=order["expire_days"],
                customer_name=email,
                customer_email=email
            )
            mark_order_paid(order_code, license_key)

            success_msg = (
                f"🎉 <b>THANH TOÁN THÀNH CÔNG! ĐƠN HÀNG HOÀN TẤT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 <b>Sản phẩm:</b> {order['tool_name']}\n"
                f"⏳ <b>Thời hạn:</b> {plan_label}\n"
                f"💵 <b>Số tiền:</b> {amount_in:,} VNĐ\n"
                f"🔖 <b>Mã đơn:</b> <code>{order_code}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📋 <b>THÔNG TIN GỬI BẢN QUYỀN:</b>\n"
                f"<code>Tên: {email}\n"
                f"Mail: {email}\n"
                f"Username: {email_prefix}\n"
                f"Pass: {email_prefix}\n"
                f"Key active: {license_key}</code>\n\n"
                f"📁 <b>LINK TẢI BỘ CÀI PHẦN MỀM:</b>\n"
                f"👉 <a href='{config.TUTORIAL_URL}'>Bấm vào đây để tải File Tool</a>\n\n"
                f"📖 <b>HƯỚNG DẪN KÍCH HOẠT:</b>\n"
                f"1. Tải và giải nén File tool về máy tính.\n"
                f"2. Mở file tool lên, dán mã Key ở trên vào ô kích hoạt.\n"
                f"3. Bấm <b>Xác nhận</b> là sử dụng được ngay!\n\n"
                f"💬 <i>Nếu cần hỗ trợ kỹ thuật, hãy liên hệ:</i> {config.SUPPORT_URL}"
            )

        # 3. Gửi cho khách
        await bot.send_message(chat_id=order["user_id"], text=success_msg, parse_mode="HTML", disable_web_page_preview=True)

        # 4. Báo thông báo về Admin
        for admin_id in config.ADMIN_IDS:
            try:
                admin_msg = (
                    f"🔔 <b>CÓ ĐƠN HÀNG {order_type.upper()} ĐÃ THANH TOÁN!</b>\n\n"
                    f"👤 Khách hàng: @{order['username']} (ID: <code>{order['user_id']}</code>)\n"
                    f"📧 Email: <code>{email}</code>\n"
                    f"📦 Sản phẩm: {order['tool_name']}\n"
                    f"💰 Doanh thu: <b>+{amount_in:,}đ</b>\n"
                    f"🔑 Key: <code>{license_key}</code>\n"
                    f"🔖 Mã đơn: <code>{order_code}</code>"
                )
                await bot.send_message(chat_id=admin_id, text=admin_msg, parse_mode="HTML")
            except Exception:
                pass

        return True

    except Exception as e:
        print(f"[!] Lỗi xử lý Webhook SePay: {e}")
        return False

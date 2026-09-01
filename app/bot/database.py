import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "shop.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Bảng Đơn Hàng (Orders)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        username TEXT,
        full_name TEXT,
        customer_email TEXT,
        order_type TEXT DEFAULT 'new', -- 'new' hoặc 'renew'
        renew_license_id TEXT,
        tool_type TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        plan_type TEXT NOT NULL,
        expire_days INTEGER NOT NULL,
        original_price INTEGER NOT NULL,
        discount_amount INTEGER DEFAULT 0,
        final_price INTEGER NOT NULL,
        voucher_code TEXT,
        status TEXT DEFAULT 'pending',
        license_key TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        paid_at DATETIME
    )
    """)

    # Tự động cập nhật cột nếu chưa có (migration an toàn)
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN customer_email TEXT")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN order_type TEXT DEFAULT 'new'")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN renew_license_id TEXT")
    except:
        pass
    
    # 2. Bảng Mã Giảm Giá (Vouchers)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vouchers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        discount_type TEXT NOT NULL, -- 'percent' hoặc 'fixed'
        discount_val INTEGER NOT NULL,
        max_uses INTEGER DEFAULT 100,
        current_uses INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 3. Bảng Người Dùng (Users)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        trial_used INTEGER DEFAULT 0,
        total_spent INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_active DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 4. Bảng Bảng Giá Sản Phẩm (Pricing)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        key TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        price_1m INTEGER NOT NULL,
        price_3m INTEGER NOT NULL,
        price_1y INTEGER NOT NULL,
        price_life INTEGER NOT NULL,
        download_url TEXT,
        guide_url TEXT
    )
    """)
    
    # Khởi tạo giá mặc định chuẩn theo yêu cầu
    default_products = [
        ("veo3_pro", "🤖 VEO3 PRO (Tự Động Hóa Video AI)", 179000, 499000, 1490000, 2990000, "https://drive.google.com", "https://youtube.com"),
        ("image_pro", "🎨 IMAGE PRO (Tạo & Xử Lý Ảnh Hàng Loạt)", 179000, 499000, 1490000, 2990000, "https://drive.google.com", "https://youtube.com"),
        ("tool_voice", "🎙️ TOOL VOICE (Lồng Tiếng & Clone Giọng AI)", 179000, 499000, 1490000, 2990000, "https://drive.google.com", "https://youtube.com"),
        ("combo_2", "⚡ COMBO 2 TOOL / 2 MÁY (Tiết Kiệm)", 300000, 799000, 2490000, 4500000, "https://drive.google.com", "https://youtube.com"),
        ("combo_all", "👑 COMBO ALL 3 TOOL VIP (TRỌN BỘ)", 399000, 999000, 2990000, 5900000, "https://drive.google.com", "https://youtube.com"),
    ]
    for p in default_products:
        cursor.execute("""
        INSERT INTO products (key, name, price_1m, price_3m, price_1y, price_life, download_url, guide_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET 
            price_1m=excluded.price_1m,
            price_3m=excluded.price_3m,
            price_1y=excluded.price_1y,
            price_life=excluded.price_life,
            name=excluded.name
        """, p)
        
    # Tạo sẵn 1 voucher mẫu TEST
    cursor.execute("""
    INSERT OR IGNORE INTO vouchers (code, discount_type, discount_val, max_uses, current_uses, is_active)
    VALUES ('VBA20', 'percent', 20, 100, 0, 1)
    """)
    cursor.execute("""
    INSERT OR IGNORE INTO vouchers (code, discount_type, discount_val, max_uses, current_uses, is_active)
    VALUES ('GIAM50K', 'fixed', 50000, 50, 0, 1)
    """)
    
    conn.commit()
    conn.close()

# Helper functions
def register_user(user_id: int, username: str = None, full_name: str = None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO users (user_id, username, full_name, last_active)
    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(user_id) DO UPDATE SET 
        username=excluded.username, 
        full_name=excluded.full_name, 
        last_active=CURRENT_TIMESTAMP
    """, (user_id, username or "", full_name or ""))
    conn.commit()
    conn.close()

def get_product(key: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_products() -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_product_price(key: str, plan: str, new_price: int):
    conn = get_db()
    cursor = conn.cursor()
    col = f"price_{plan}" # price_1m, price_3m, price_1y, price_life
    cursor.execute(f"UPDATE products SET {col} = ? WHERE key = ?", (new_price, key))
    conn.commit()
    conn.close()

def create_order(order_code: str, user_id: int, username: str, full_name: str,
                 tool_type: str, tool_name: str, plan_type: str, expire_days: int,
                 original_price: int, discount_amount: int, final_price: int,
                 voucher_code: str = None, customer_email: str = None,
                 order_type: str = "new", renew_license_id: str = None) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO orders (
        order_code, user_id, username, full_name, customer_email, order_type, renew_license_id,
        tool_type, tool_name, plan_type, expire_days,
        original_price, discount_amount, final_price, voucher_code, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
    """, (
        order_code, user_id, username or "", full_name or "", customer_email or "", order_type, renew_license_id or "",
        tool_type, tool_name, plan_type, expire_days,
        original_price, discount_amount, final_price, voucher_code
    ))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id

def get_order_by_code(order_code: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE order_code = ?", (order_code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def mark_order_paid(order_code: str, license_key: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE orders 
    SET status = 'paid', license_key = ?, paid_at = CURRENT_TIMESTAMP 
    WHERE order_code = ?
    """, (license_key, order_code))
    
    # Cập nhật tổng chi tiêu của user
    cursor.execute("SELECT user_id, final_price FROM orders WHERE order_code = ?", (order_code,))
    row = cursor.fetchone()
    if row:
        cursor.execute("""
        UPDATE users SET total_spent = total_spent + ? WHERE user_id = ?
        """, (row["final_price"], row["user_id"]))
        
    conn.commit()
    conn.close()

def get_voucher(code: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vouchers WHERE code = ? AND is_active = 1", (code.upper().strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def use_voucher(code: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE vouchers SET current_uses = current_uses + 1 WHERE code = ?
    """, (code.upper().strip(),))
    conn.commit()
    conn.close()

def get_user_orders(user_id: int) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id = ? AND status = 'paid' ORDER BY paid_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def check_trial_used(user_id: int) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT trial_used FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row["trial_used"]) if row else False

def set_trial_used(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET trial_used = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_stats() -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total_users FROM users")
    total_users = cursor.fetchone()["total_users"]
    
    cursor.execute("SELECT COUNT(*) as total_orders, SUM(final_price) as total_rev FROM orders WHERE status = 'paid'")
    res = cursor.fetchone()
    total_orders = res["total_orders"] or 0
    total_rev = res["total_rev"] or 0
    
    cursor.execute("SELECT COUNT(*) as orders_today, SUM(final_price) as rev_today FROM orders WHERE status = 'paid' AND date(paid_at) = date('now')")
    res_today = cursor.fetchone()
    orders_today = res_today["orders_today"] or 0
    rev_today = res_today["rev_today"] or 0
    
    conn.close()
    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "total_revenue": total_rev,
        "orders_today": orders_today,
        "revenue_today": rev_today
    }

# Khởi tạo DB khi load module
init_db()

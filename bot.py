import os
import random
import string
import threading
import telebot
from telebot import types
import psycopg
from psycopg.rows import dict_row
from flask import Flask

# Cấu hình Token và biến môi trường
TOKEN = os.getenv('BOT_TOKEN', '8483501766:AAEQzYZG1iX5bO0y46pWCesqKmlWucKoxlg')
DATABASE_URL = os.getenv('DATABASE_URL', '')
ADMIN_ID = 7907990385
REQUIRED_GROUP = "@nhomsharemodallgame"

bot = telebot.TeleBot(TOKEN)

# --- FLASK SERVER CHO RENDER WEB SERVICE ---
app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Axiom Bot Web Service is running successfully!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- KẾT NỐI VÀ KHỞI TẠO DATABASE ---
def get_db_connection():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id BIGINT PRIMARY KEY,
            balance INT DEFAULT 0,
            verified BOOLEAN DEFAULT FALSE,
            referred_by BIGINT DEFAULT NULL,
            referred_ids TEXT DEFAULT '',
            ref_xu INT DEFAULT 0
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            category VARCHAR(50),
            account_data TEXT,
            sold BOOLEAN DEFAULT FALSE
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS purchase_history (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT,
            category VARCHAR(50),
            account_data TEXT,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

# --- KIỂM TRA THÀNH VIÊN NHÓM ---
def check_user_membership(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_GROUP, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        print(f"Lỗi kiểm tra nhóm: {e}")
    return False

# --- XỬ LÝ /START & XÁC MINH ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM users WHERE telegram_id = %s", (user_id,))
    user = cur.fetchone()
    
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        ref_potential = int(args[1])
        if ref_potential != user_id:
            referrer_id = ref_potential

    if not user:
        cur.execute(
            "INSERT INTO users (telegram_id, referred_by) VALUES (%s, %s)",
            (user_id, referrer_id)
        )
        conn.commit()
        cur.execute("SELECT * FROM users WHERE telegram_id = %s", (user_id,))
        user = cur.fetchone()

    cur.close()
    conn.close()

    if not user['verified']:
        if check_user_membership(user_id):
            verify_user(user_id)
            send_command_guide(message.chat.id)
        else:
            send_verification_prompt(message.chat.id)
    else:
        send_command_guide(message.chat.id)

def verify_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET verified = TRUE WHERE telegram_id = %s AND verified = FALSE", (user_id,))
    
    cur.execute("SELECT referred_by FROM users WHERE telegram_id = %s", (user_id,))
    res = cur.fetchone()
    
    if res and res['referred_by']:
        ref_id = res['referred_by']
        cur.execute("SELECT referred_ids FROM users WHERE telegram_id = %s", (ref_id,))
        ref_user = cur.fetchone()
        
        if ref_user:
            current_ids = ref_user['referred_ids'] or ""
            id_list = current_ids.split(',') if current_ids else []
            
            if str(user_id) not in id_list:
                id_list.append(str(user_id))
                new_ids_str = ','.join(id_list)
                
                cur.execute(
                    "UPDATE users SET balance = balance + 2, referred_ids = %s, ref_xu = ref_xu + 2 WHERE telegram_id = %s",
                    (new_ids_str, ref_id)
                )
                try:
                    bot.send_message(ref_id, f"🎉 **THƯỞNG GIỚI THIỆU**\n\nBạn nhận được **+2 Xu** do có thành viên mới (`{user_id}`) đã xác minh!", parse_mode="Markdown")
                except:
                    pass

    conn.commit()
    cur.close()
    conn.close()

def send_verification_prompt(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 Tham gia nhóm ngay", url=f"https://t.me/{REQUIRED_GROUP.replace('@','')}"),
        types.InlineKeyboardButton("🔄 Tôi đã tham gia (Xác minh)", callback_data="check_membership")
    )
    
    text = (
        "⚠️ **YÊU CẦU XÁC MINH TÀI KHOẢN**\n\n"
        f"Chào bạn đến với hệ thống **Shop Acc Free Fire**!\n"
        f"Bạn cần tham gia nhóm **{REQUIRED_GROUP}** để sử dụng bot."
    )
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def callback_check_membership(call):
    user_id = call.from_user.id
    if check_user_membership(user_id):
        verify_user(user_id)
        bot.answer_callback_query(call.id, "🎉 Xác minh thành công!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        send_command_guide(call.message.chat.id)
    else:
        bot.answer_callback_query(call.id, "❌ Bạn chưa tham gia nhóm yêu cầu!", show_alert=True)

def send_command_guide(chat_id):
    text = (
        "🔥 **HỆ THỐNG SHOP ACC FREE FIRE** 🔥\n"
        "────────────────────────\n"
        "Danh sách lệnh hệ thống:\n\n"
        "• /shop - Xem danh mục và mua tài khoản\n"
        "• /info - Kiểm tra số Xu cá nhân\n"
        "• /ref - Lấy link giới thiệu nhận Xu\n"
        "• /lenh - Xem bảng hướng dẫn lệnh"
    )
    bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(commands=['lenh', 'help'])
def handle_lenh(message):
    send_command_guide(message.chat.id)

# --- SHOP ACC FREE FIRE ---
@bot.message_handler(commands=['shop'])
def shop_menu(message):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM accounts WHERE category = 'level_5_8' AND sold = FALSE")
    stock_5_8 = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) FROM accounts WHERE category = 'level_30' AND sold = FALSE")
    stock_30 = cur.fetchone()['count']
    
    cur.close()
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"📦 Clone Level 5–8 (Kho: {stock_5_8}) - 10 Xu", callback_data="shop_view_level_5_8"),
        types.InlineKeyboardButton(f"📦 Clone Level 30 (Kho: {stock_30}) - 15 Xu", callback_data="shop_view_level_30")
    )
    text = (
        "🔥 **DANH MỤC SHOP ACC FREE FIRE**\n"
        "────────────────────────\n"
        "⚡ Chọn loại tài khoản bạn muốn xem:"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("shop_view_"))
def callback_shop_view(call):
    category = call.data.replace("shop_view_", "")
    cat_name = "Clone Level 5–8" if category == "level_5_8" else "Clone Level 30"
    price = 10 if category == "level_5_8" else 15
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM accounts WHERE category = %s AND sold = FALSE", (category,))
    count = cur.fetchone()['count']
    cur.close()
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    if count > 0:
        markup.add(types.InlineKeyboardButton(f"🛒 Mua ngay ({price} Xu)", callback_data=f"buy_{category}"))
    markup.add(types.InlineKeyboardButton("⬅️ Quay lại", callback_data="back_shop"))

    text = (
        f"📦 **CHI TIẾT SẢN PHẨM**\n"
        f"────────────────────────\n"
        f"• **Loại:** `{cat_name}`\n"
        f"• **Giá:** `{price} Xu`\n"
        f"• **Kho:** `{count} acc`"
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "back_shop")
def callback_back_shop(call):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM accounts WHERE category = 'level_5_8' AND sold = FALSE")
    stock_5_8 = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FROM accounts WHERE category = 'level_30' AND sold = FALSE")
    stock_30 = cur.fetchone()['count']
    cur.close()
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"📦 Clone Level 5–8 (Kho: {stock_5_8}) - 10 Xu", callback_data="shop_view_level_5_8"),
        types.InlineKeyboardButton(f"📦 Clone Level 30 (Kho: {stock_30}) - 15 Xu", callback_data="shop_view_level_30")
    )
    text = (
        "🔥 **DANH MỤC SHOP ACC FREE FIRE**\n"
        "────────────────────────\n"
        "⚡ Chọn loại tài khoản bạn muốn xem:"
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def callback_buy(call):
    category = call.data.replace("buy_", "")
    user_id = call.from_user.id
    price = 10 if category == "level_5_8" else 15

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT balance FROM users WHERE telegram_id = %s", (user_id,))
    user = cur.fetchone()
    if not user or user['balance'] < price:
        bot.answer_callback_query(call.id, "❌ Bạn không đủ Xu để mua!", show_alert=True)
        cur.close()
        conn.close()
        return

    cur.execute("SELECT id, account_data FROM accounts WHERE category = %s AND sold = FALSE LIMIT 1 FOR UPDATE", (category,))
    acc = cur.fetchone()
    if not acc:
        bot.answer_callback_query(call.id, "❌ Kho tài khoản này đã hết hàng!", show_alert=True)
        cur.close()
        conn.close()
        return

    acc_id = acc['id']
    acc_data = acc['account_data']

    cur.execute("UPDATE users SET balance = balance - %s WHERE telegram_id = %s", (price, user_id))
    cur.execute("UPDATE accounts SET sold = TRUE WHERE id = %s", (acc_id,))
    cur.execute("INSERT INTO purchase_history (telegram_id, category, account_data) VALUES (%s, %s, %s)", (user_id, category, acc_data))
    
    conn.commit()
    cur.close()
    conn.close()

    bot.answer_callback_query(call.id, "✅ Mua thành công!")
    success_text = (
        "🎉 **MUA HÀNG THÀNH CÔNG!**\n"
        "────────────────────────\n"
        f"📦 **Thông tin tài khoản:**\n"
        f"`{acc_data}`"
    )
    bot.send_message(call.message.chat.id, success_text, parse_mode="Markdown")

@bot.message_handler(commands=['info'])
def account_info(message):
    user_id = message.from_user.id
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        bot.send_message(message.chat.id, "Vui lòng gõ /start để khởi tạo.")
        return

    current_ids = user['referred_ids'] or ""
    ref_count = len(current_ids.split(',')) if current_ids else 0

    text = (
        "👤 **THÔNG TIN TÀI KHOẢN**\n"
        "────────────────────────\n"
        f"🆔 ID: `{user['telegram_id']}`\n"
        f"💰 Số dư: `{user['balance']} Xu`\n"
        f"👥 Đã giới thiệu: `{ref_count}`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['ref'])
def referral_info(message):
    user_id = message.from_user.id
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT referred_ids, ref_xu FROM users WHERE telegram_id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    current_ids = user['referred_ids'] or ""
    ref_count = len(current_ids.split(',')) if current_ids else 0

    text = (
        "🎁 **GIỚI THIỆU NHẬN XU**\n"
        "────────────────────────\n"
        f"🔗 Link của bạn:\n`{ref_link}`\n\n"
        f"• Đã giới thiệu: `{ref_count}`\n"
        f"• Thưởng nhận được: `{user['ref_xu']} Xu`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


# ==========================================
# --- ADMIN LỆNH TRỰC TIẾP (SIÊU NHANH) ---
# ==========================================

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    text = (
        "👑 **BẢNG QUẢN TRỊ ADMIN**\n"
        "────────────────────────\n"
        "Các lệnh trực tiếp:\n\n"
        "1️⃣ Thêm kho tự động:\n"
        "• `/themkho level_5_8 [số_lượng]`\n"
        "• `/themkho level_30 [số_lượng]`\n"
        "*(Ví dụ: `/themkho level_5_8 100`)*\n\n"
        "2️⃣ Cộng xu:\n"
        "• `/addxu [id_user] [số_xu]`\n\n"
        "3️⃣ Thống kê:\n"
        "• `/thongke`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['themkho'])
def admin_add_stock_direct(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        bot.send_message(message.chat.id, "❌ Sai cú pháp!\n👉 Dùng: `/themkho level_5_8 100` hoặc `/themkho level_30 50`", parse_mode="Markdown")
        return
    
    category = parts[1]
    if category not in ['level_5_8', 'level_30']:
        bot.send_message(message.chat.id, "❌ Danh mục không hợp lệ! Chỉ dùng `level_5_8` hoặc `level_30`.")
        return
        
    if not parts[2].isdigit():
        bot.send_message(message.chat.id, "❌ Số lượng phải là một con số nguyên!")
        return
        
    count_to_add = int(parts[2])

    conn = get_db_connection()
    cur = conn.cursor()
    
    added_count = 0
    for _ in range(count_to_add):
        rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        acc_email = f"ff_{rand_str}@gmail.com"
        acc_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        line_data = f"{acc_email}|{acc_pass}"
        
        cur.execute("INSERT INTO accounts (category, account_data, sold) VALUES (%s, %s, FALSE)", (category, line_data))
        added_count += 1

    cur.execute("SELECT COUNT(*) FROM accounts WHERE category = 'level_5_8' AND sold = FALSE")
    stock_5_8 = cur.fetchone()['count']

    cur.execute("SELECT COUNT(*) FROM accounts WHERE category = 'level_30' AND sold = FALSE")
    stock_30 = cur.fetchone()['count']

    conn.commit()
    cur.close()
    conn.close()

    response_text = (
        f"✅ **ĐÃ THÊM KHO THÀNH CÔNG!**\n"
        f"────────────────────────\n"
        f"• Thêm vào: `{category}`\n"
        f"• Số lượng tạo: `{added_count} acc`\n\n"
        f"📦 Kho hiện tại:\n"
        f"• Level 5–8: `{stock_5_8}`\n"
        f"• Level 30: `{stock_30}`"
    )
    bot.send_message(message.chat.id, response_text, parse_mode="Markdown")

@bot.message_handler(commands=['addxu'])
def admin_add_xu_direct(message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        bot.send_message(message.chat.id, "❌ Sai cú pháp!\n👉 Dùng: `/addxu [id_user] [số_xu]`", parse_mode="Markdown")
        return
        
    target_id = int(parts[1])
    amount = int(parts[2])

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + %s WHERE telegram_id = %s", (amount, target_id))
    conn.commit()
    cur.close()
    conn.close()

    bot.send_message(message.chat.id, f"✅ Đã cộng `{amount} Xu` cho user `{target_id}`!")
    try:
        bot.send_message(target_id, f"🎉 Bạn vừa nhận được **+{amount} Xu** từ Admin!", parse_mode="Markdown")
    except:
        pass

@bot.message_handler(commands=['thongke'])
def admin_stats_direct(message):
    if message.from_user.id != ADMIN_ID:
        return
        
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FROM accounts WHERE category = 'level_5_8' AND sold = FALSE")
    stock_5_8 = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FROM accounts WHERE category = 'level_30' AND sold = FALSE")
    stock_30 = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FROM accounts WHERE sold = TRUE")
    total_sold = cur.fetchone()['count']

    cur.close()
    conn.close()

    text = (
        "📊 **THỐNG KÊ HỆ THỐNG**\n"
        "────────────────────────\n"
        f"• Tổng user: `{total_users}`\n"
        f"• Kho 5–8: `{stock_5_8} acc`\n"
        f"• Kho 30: `{stock_30} acc`\n"
        f"• Đã bán: `{total_sold} acc`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['thongbao'])
def admin_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    text_to_send = message.text.replace('/thongbao', '').strip()
    if not text_to_send:
        bot.send_message(message.chat.id, "❌ Vui lòng nhập nội dung sau lệnh `/thongbao`.", parse_mode="Markdown")
        return

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT telegram_id FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()

    success = 0
    for u in users:
        try:
            bot.send_message(u['telegram_id'], f"📢 **THÔNG BÁO**\n\n{text_to_send}", parse_mode="Markdown")
            success += 1
        except:
            pass

    bot.send_message(message.chat.id, f"✅ Đã gửi thông báo cho `{success}` người dùng.")

# --- CHẠY WEB SERVER VÀ BOT SONG SONG ---
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    print("✨ Bot đang chạy...")
    bot.infinity_polling()

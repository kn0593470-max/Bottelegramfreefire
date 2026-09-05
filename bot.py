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

# --- HÀM HIỂN THỊ MENU CHÍNH (KÈM SỐ DƯ VÀ KHO ACC) ---
def send_main_shop_menu(chat_id, user_id, message_id=None, edit=False):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Lấy số dư user
    cur.execute("SELECT balance FROM users WHERE telegram_id = %s", (user_id,))
    user_data = cur.fetchone()
    balance = user_data['balance'] if user_data else 0
    
    # Lấy số lượng tồn kho
    cur.execute("SELECT COUNT(*) FROM accounts WHERE category = 'level_5_8' AND sold = FALSE")
    stock_5_8 = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) FROM accounts WHERE category = 'level_30' AND sold = FALSE")
    stock_30 = cur.fetchone()['count']
    
    cur.close()
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"📦 Clone Level 5–8 (Còn: {stock_5_8} acc) - 10 Xu", callback_data="shop_view_level_5_8"),
        types.InlineKeyboardButton(f"📦 Clone Level 30 (Còn: {stock_30} acc) - 15 Xu", callback_data="shop_view_level_30"),
        types.InlineKeyboardButton("💡 Cách kiếm Xu miễn phí", callback_data="how_to_earn_xu"),
        types.InlineKeyboardButton("👤 Kiểm tra tài khoản & Số dư (/info)", callback_data="view_my_info")
    )
    
    text = (
        "🔥 **HỆ THỐNG SHOP ACC FREE FIRE TỰ ĐỘNG** 🔥\n"
        "────────────────────────\n"
        f"💰 **Số dư của bạn:** `{balance} Xu`\n"
        "⚡ *Vui lòng chọn loại tài khoản hoặc tính năng bên dưới:*"
    )
    
    if edit and message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
        except:
            pass
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

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
            send_main_shop_menu(message.chat.id, user_id)
        else:
            send_verification_prompt(message.chat.id)
    else:
        send_main_shop_menu(message.chat.id, user_id)

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
                    bot.send_message(ref_id, f"🎉 **THƯỞNG GIỚI THIỆU THÀNH VIÊN**\n\nBạn vừa nhận thành công **+2 Xu** do có thành viên mới (`{user_id}`) thông qua link giới thiệu đã hoàn tất xác minh nhóm!", parse_mode="Markdown")
                except:
                    pass

    conn.commit()
    cur.close()
    conn.close()

def send_verification_prompt(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 Tham gia nhóm/kênh ngay", url=f"https://t.me/{REQUIRED_GROUP.replace('@','')}"),
        types.InlineKeyboardButton("🔄 Xác minh (Tôi đã tham gia)", callback_data="check_membership")
    )
    
    text = (
        "⚠️ **YÊU CẦU XÁC MINH TÀI KHOẢN**\n\n"
        f"Chào mừng bạn đến với hệ thống **Shop Acc Free Fire Tự Động**!\n\n"
        f"🔒 Để đảm bảo quyền lợi và mở khóa toàn bộ cửa hàng, bạn bắt buộc phải tham gia kênh/nhóm tại: **{REQUIRED_GROUP}**.\n\n"
        "👉 *Sau khi đã tham gia nhóm xong, vui lòng bấm nút màu xanh bên dưới.*"
    )
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def callback_check_membership(call):
    user_id = call.from_user.id
    if check_user_membership(user_id):
        verify_user(user_id)
        bot.answer_callback_query(call.id, "🎉 Xác minh tài khoản thành công!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        send_main_shop_menu(call.message.chat.id, user_id)
    else:
        bot.answer_callback_query(call.id, "❌ Bạn vẫn chưa tham gia nhóm yêu cầu!", show_alert=True)

# Lệnh /shop và /lenh đồng bộ mở thẳng menu chính
@bot.message_handler(commands=['shop', 'lenh', 'help'])
def shop_menu(message):
    send_main_shop_menu(message.chat.id, message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_shop")
def callback_back_shop(call):
    send_main_shop_menu(call.message.chat.id, call.from_user.id, call.message.message_id, edit=True)

# --- NÚT HƯỚNG DẪN CÁCH KIẾM XU MIỄN PHÍ ---
@bot.callback_query_handler(func=lambda call: call.data == "how_to_earn_xu")
def callback_how_to_earn_xu(call):
    user_id = call.from_user.id
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

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("⬅️ Quay lại Cửa hàng", callback_data="back_shop"))

    text = (
        "💡 **HƯỚNG DẪN CÁCH KIẾM XU MIỄN PHÍ**\n"
        "────────────────────────\n"
        "Bạn có thể nhận thêm Xu hoàn toàn miễn phí bằng cách giới thiệu bạn bè tham gia bot thông qua đường link riêng của bạn:\n\n"
        f"🔗 **Link giới thiệu của bạn:**\n`{ref_link}`\n\n"
        "📌 **Quy chế nhận thưởng:**\n"
        "• Gửi link này cho bạn bè hoặc chia sẻ lên các nhóm.\n"
        "• Khi có người bấm vào link, mở bot và **hoàn tất xác minh tham gia nhóm**, hệ thống sẽ tự động cộng ngay **+2 Xu** vào ví của bạn!\n\n"
        f"📊 **Thống kê của bạn:**\n"
        f"• Đã mời thành công: `{ref_count} người`\n"
        f"• Tổng Xu nhận được: `{user['ref_xu']} Xu`"
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        pass

@bot.message_handler(commands=['ref'])
def referral_info(message):
    # Lệnh /ref gọi tương đương tính năng kiếm xu
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
        "🎁 **HỆ THỐNG GIỚI THIỆU BÈ BẠN - NHẬN XU**\n"
        "────────────────────────\n"
        f"🔗 **Link của bạn:**\n`{ref_link}`\n\n"
        f"• Đã giới thiệu: `{ref_count} người`\n"
        f"• Thưởng nhận được: `{user['ref_xu']} Xu`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# --- XEM CHI TIẾT SẢN PHẨM ---
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
        markup.add(types.InlineKeyboardButton(f"🛒 Xác nhận mua ngay ({price} Xu)", callback_data=f"buy_{category}"))
    markup.add(types.InlineKeyboardButton("⬅️ Quay lại Cửa hàng", callback_data="back_shop"))

    text = (
        f"📦 **CHI TIẾT TÀI KHOẢN**\n"
        f"────────────────────────\n"
        f"• **Loại:** `{cat_name}`\n"
        f"• **Giá:** `{price} Xu`\n"
        f"• **Kho còn lại:** `{count} tài khoản`\n\n"
        f"📌 *Hệ thống sẽ tự động trừ Xu và gửi thông tin tài khoản (Email|Mật khẩu) ngay lập tức khi mua.*"
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        pass

# --- MUA HÀNG ---
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
        bot.answer_callback_query(call.id, "❌ Bạn không đủ Xu để mua sản phẩm này! Hãy bấm vào mục 'Cách kiếm Xu miễn phí' để nhận thêm.", show_alert=True)
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
        "🎉 **MUA TÀI KHOẢN THÀNH CÔNG!**\n"
        "────────────────────────\n"
        f"📦 **Thông tin tài khoản:**\n"
        f"`{acc_data}`"
    )
    bot.send_message(call.message.chat.id, success_text, parse_mode="Markdown")

# --- XEM THÔNG TIN CÁ NHÂN ---
@bot.callback_query_handler(func=lambda call: call.data == "view_my_info")
def callback_view_info(call):
    user_id = call.from_user.id
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    current_ids = user['referred_ids'] or ""
    ref_count = len(current_ids.split(',')) if current_ids else 0

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("⬅️ Quay lại Cửa hàng", callback_data="back_shop"))

    text = (
        "👤 **HỒ SƠ TÀI KHOẢN CÁ NHÂN**\n"
        "────────────────────────\n"
        f"🆔 ID: `{user['telegram_id']}`\n"
        f"💰 Số dư: `{user['balance']} Xu`\n"
        f"👥 Đã giới thiệu: `{ref_count} người`\n"
        f"🎁 Tổng Xu kiếm được từ ref: `{user['ref_xu']} Xu`"
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        pass

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
        "👤 **HỒ SƠ TÀI KHOẢN CÁ NHÂN**\n"
        "────────────────────────\n"
        f"🆔 ID: `{user['telegram_id']}`\n"
        f"💰 Số dư: `{user['balance']} Xu`\n"
        f"👥 Đã giới thiệu: `{ref_count} người`\n"
        f"🎁 Tổng Xu kiếm được từ ref: `{user['ref_xu']} Xu`"
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
        "• `/themkho level_5_8 [số_lượng]`\n"
        "• `/themkho level_30 [số_lượng]`\n"
        "• `/addxu [id_user] [số_xu]`\n"
        "• `/thongke`\n"
        "• `/thongbao [nội_dung]`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['themkho'])
def admin_add_stock_direct(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        bot.send_message(message.chat.id, "❌ Sai cú pháp! Dùng: `/themkho level_5_8 100`", parse_mode="Markdown")
        return
    
    category = parts[1]
    if category not in ['level_5_8', 'level_30']:
        bot.send_message(message.chat.id, "❌ Danh mục không hợp lệ! Chỉ dùng `level_5_8` hoặc `level_30`.")
        return
        
    if not parts[2].isdigit():
        bot.send_message(message.chat.id, "❌ Số lượng phải là số nguyên!")
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
        f"✅ **THÊM KHO THÀNH CÔNG!**\n"
        f"• Loại: `{category}` | Thêm: `{added_count} acc`\n"
        f"📦 Kho hiện tại -> 5-8: `{stock_5_8}` | 30: `{stock_30}`"
    )
    bot.send_message(message.chat.id, response_text, parse_mode="Markdown")

@bot.message_handler(commands=['addxu'])
def admin_add_xu_direct(message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        bot.send_message(message.chat.id, "❌ Sai cú pháp! Dùng: `/addxu [id_user] [số_xu]`", parse_mode="Markdown")
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

    print("✨ Bot đang chạy mượt mà...")
    bot.infinity_polling()
 

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

# Bộ nhớ tạm để lưu trạng thái chat của Admin (Hỏi - Đáp từng bước)
admin_states = {}

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
                    bot.send_message(ref_id, f"🎉 **THƯỞNG GIỚI THIỆU**\n\nBạn vừa nhận được **+2 Xu** do có thành viên mới (ID: `{user_id}`) đã hoàn tất xác minh nhóm!", parse_mode="Markdown")
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
        f"Chào bạn đến với hệ thống **Axiom**!\n"
        f"Để sử dụng các lệnh của bot, bạn bắt buộc phải tham gia kênh/nhóm: **{REQUIRED_GROUP}**.\n\n"
        "👉 *Sau khi tham gia xong, hãy bấm nút bên dưới để mở khóa hệ thống.*"
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
        bot.answer_callback_query(call.id, "❌ Bạn vẫn chưa tham gia nhóm yêu cầu!", show_alert=True)

# --- HƯỚNG DẪN LỆNH CHO USER ---
def send_command_guide(chat_id):
    text = (
        "✨ **HỆ THỐNG GIAO DỊCH AXIOM** ✨\n"
        "────────────────────────\n"
        "Hệ thống hiện sử dụng các lệnh gõ trực tiếp. Các lệnh khả dụng:\n\n"
        "• /shop - Xem và mua tài khoản Free Fire\n"
        "• /info - Xem thông tin tài khoản cá nhân & số Xu\n"
        "• /ref - Lấy link giới thiệu nhận Xu miễn phí\n"
        "• /lenh - Xem lại danh sách lệnh này"
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
        "⚡ *Chọn loại tài khoản bạn muốn xem chi tiết bên dưới:*"
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
        markup.add(types.InlineKeyboardButton(f"🛒 Tiến hành mua ngay ({price} Xu)", callback_data=f"buy_{category}"))
    markup.add(types.InlineKeyboardButton("⬅️ Quay lại danh mục", callback_data="back_shop"))

    text = (
        f"📦 **CHI TIẾT SẢN PHẨM**\n"
        f"────────────────────────\n"
        f"• **Loại tài khoản:** `{cat_name}`\n"
        f"• **Giá bán:** `{price} Xu`\n"
        f"• **Tồn kho hiện tại:** `{count} acc`\n\n"
        f"📌 *Hệ thống tự động trừ Xu và trả thông tin ngay khi bấm mua.*"
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
        "⚡ *Chọn loại tài khoản bạn muốn xem chi tiết bên dưới:*"
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
        bot.answer_callback_query(call.id, "❌ Tài khoản của bạn không đủ Xu để mua hàng!", show_alert=True)
        cur.close()
        conn.close()
        return

    cur.execute("SELECT id, account_data FROM accounts WHERE category = %s AND sold = FALSE LIMIT 1 FOR UPDATE", (category,))
    acc = cur.fetchone()
    if not acc:
        bot.answer_callback_query(call.id, "❌ Rất tiếc, kho tài khoản này đã hết hàng!", show_alert=True)
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

    bot.answer_callback_query(call.id, "✅ Giao dịch thành công!")
    success_text = (
        "🎉 **GIAO DỊCH THÀNH CÔNG!**\n"
        "────────────────────────\n"
        f"📦 **Thông tin tài khoản nhận được:**\n"
        f"`{acc_data}`\n\n"
        "⚠️ *Hệ thống đã tự động trừ Xu và khóa kho chống bán trùng.*"
    )
    bot.send_message(call.message.chat.id, success_text, parse_mode="Markdown")

# --- THÔNG TIN TÀI KHOẢN (/info) ---
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
        bot.send_message(message.chat.id, "Vui lòng gõ /start để khởi tạo hệ thống.")
        return

    current_ids = user['referred_ids'] or ""
    ref_count = len(current_ids.split(',')) if current_ids else 0

    text = (
        "👤 **HỒ SƠ CÁ NHÂN TÀI KHOẢN**\n"
        "────────────────────────\n"
        f"🆔 **ID Telegram:** `{user['telegram_id']}`\n"
        f"💰 **Số Xu hiện có:** `{user['balance']} Xu`\n"
        f"👥 **Đã giới thiệu:** `{ref_count} thành viên`\n"
        f"🎁 **Tổng Xu từ ref:** `{user['ref_xu']} Xu`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# --- GIỚI THIỆU (/ref) ---
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
        "🎁 **HỆ THỐNG GIỚI THIỆU BẠN BÈ**\n"
        "────────────────────────\n"
        "🔗 **Link giới thiệu riêng của bạn:**\n"
        f"`{ref_link}`\n\n"
        f"📊 **Thống kê của bạn:**\n"
        f"• Số bạn bè đã giới thiệu: `{ref_count} người`\n"
        f"• Tổng Xu thưởng: `{user['ref_xu']} Xu`\n\n"
        f"📌 Gửi link này cho bạn bè tham gia nhóm `{REQUIRED_GROUP}` để nhận ngay **+2 Xu**!"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


# ==========================================
# --- ADMIN INTERACTIVE (GỎI LỆNH) ---
# ==========================================

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Cộng Xu", callback_data="adm_addxu"),
        types.InlineKeyboardButton("📦 Thêm kho (Tự động tạo)", callback_data="adm_themkho"),
        types.InlineKeyboardButton("📊 Thống kê", callback_data="adm_thongke")
    )
    text = (
        "👑 **BẢNG ĐIỀU KHIỂN QUẢN TRỊ VIÊN**\n"
        "────────────────────────\n"
        "Chọn chức năng bên dưới:"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_callback_router(call):
    if call.from_user.id != ADMIN_ID:
        return
    user_id = call.from_user.id
    action = call.data.replace("adm_", "")

    if action == "addxu":
        admin_states[user_id] = {"step": "addxu_await_id"}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "👉 **[Cộng Xu]** Bước 1/2: Vui lòng nhập **Telegram ID** của người cần cộng xu:")

    elif action == "themkho":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("Clone Level 5–8", callback_data="adm_stock_level_5_8"),
            types.InlineKeyboardButton("Clone Level 30", callback_data="adm_stock_level_30")
        )
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📦 **[Thêm Kho Tự Động]** Bước 1/2: Chọn loại kho bạn muốn thêm:", reply_markup=markup)

    elif action == "thongke":
        bot.answer_callback_query(call.id)
        send_admin_stats(call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_stock_"))
def admin_stock_category_chosen(call):
    if call.from_user.id != ADMIN_ID:
        return
    user_id = call.from_user.id
    category = call.data.replace("adm_stock_", "")
    
    admin_states[user_id] = {"step": "themkho_await_count", "category": category}
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"📦 **[Thêm Kho: {category}]** Bước 2/2:\nNhập **số lượng tài khoản** bạn muốn bot tự động tạo (Ví dụ: `100`):"
    )

@bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.from_user.id in admin_states)
def admin_interactive_handler(message):
    user_id = message.from_user.id
    state = admin_states[user_id]
    step = state.get("step")

    if step == "addxu_await_id":
        text_id = message.text.strip()
        if not text_id.isdigit():
            bot.send_message(message.chat.id, "❌ ID không hợp lệ! Vui lòng chỉ nhập số Telegram ID:")
            return
        
        state["target_id"] = int(text_id)
        state["step"] = "addxu_await_amount"
        bot.send_message(message.chat.id, f"👉 Đã nhận ID: `{text_id}`.\n\nBước 2/2: Nhập **số lượng Xu** muốn cộng:")

    elif step == "addxu_await_amount":
        text_amount = message.text.strip()
        if not text_amount.isdigit():
            bot.send_message(message.chat.id, "❌ Số lượng không hợp lệ! Vui lòng nhập số nguyên:")
            return
        
        amount = int(text_amount)
        target_id = state["target_id"]
        
        del admin_states[user_id]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance = balance + %s WHERE telegram_id = %s", (amount, target_id))
        conn.commit()
        cur.close()
        conn.close()

        bot.send_message(message.chat.id, f"✅ Đã cộng thành công `{amount} Xu` cho user ID: `{target_id}`!", parse_mode="Markdown")
        try:
            bot.send_message(target_id, f"🎉 **THÔNG BÁO TỪ HỆ THỐNG**\n\nBạn vừa được Admin thưởng nóng **+{amount} Xu** vào tài khoản!", parse_mode="Markdown")
        except:
            pass

    elif step == "themkho_await_count":
        text_count = message.text.strip()
        if not text_count.isdigit():
            bot.send_message(message.chat.id, "❌ Vui lòng nhập một con số hợp lệ (Ví dụ: 50, 100):")
            return

        count_to_add = int(text_count)
        category = state["category"]
        del admin_states[user_id]

        conn = get_db_connection()
        cur = conn.cursor()
        
        added_count = 0
        for _ in range(count_to_add):
            # Tự động tạo email và mật khẩu ngẫu nhiên cho bạn
            rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            acc_email = f"ff_clone_{rand_str}@gmail.com"
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
            f"✅ **TỰ ĐỘNG THÊM KHO THÀNH CÔNG!**\n"
            f"────────────────────────\n"
            f"• Đã tạo tự động: `{added_count}` acc cho mục `{category}`\n\n"
            f"📦 **KHO HIỆN TẠI:**\n"
            f"• Clone Level 5–8 còn: `{stock_5_8}` acc\n"
            f"• Clone Level 30 còn: `{stock_30}` acc"
        )
        bot.send_message(message.chat.id, response_text, parse_mode="Markdown")

def send_admin_stats(chat_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()['count']

    cur.execute("SELECT COUNT(*) FROM users WHERE verified = TRUE")
    verified_users = cur.fetchone()['count']

    cur.execute("SELECT referred_ids FROM users")
    all_refs = cur.fetchall()
    total_refs = sum(len(r['referred_ids'].split(',')) for r in all_refs if r['referred_ids'])

    cur.execute("SELECT SUM(ref_xu) FROM users")
    total_ref_xu = cur.fetchone()['sum'] or 0

    cur.execute("SELECT SUM(balance) FROM users")
    circulating_xu = cur.fetchone()['sum'] or 0

    cur.execute("SELECT COUNT(*) FROM purchase_history")
    total_purchases = cur.fetchone()['count']

    cur.execute("SELECT COUNT(*) FROM accounts WHERE category = 'level_5_8' AND sold = FALSE")
    stock_5_8 = cur.fetchone()['count']

    cur.execute("SELECT COUNT(*) FROM accounts WHERE category = 'level_30' AND sold = FALSE")
    stock_30 = cur.fetchone()['count']

    cur.execute("SELECT COUNT(*) FROM accounts WHERE sold = TRUE")
    total_sold = cur.fetchone()['count']

    cur.close()
    conn.close()

    text = (
        "📊 **THỐNG KÊ HỆ THỐNG AXIOM**\n"
        "────────────────────────\n"
        f"• Tổng user: `{total_users}`\n"
        f"• User đã xác minh: `{verified_users}`\n"
        f"• Tổng lượt giới thiệu: `{total_refs}`\n"
        f"• Kho Level 5–8 còn: `{stock_5_8} acc`\n"
        f"• Kho Level 30 còn: `{stock_30} acc`\n"
        f"• Tổng acc đã bán: `{total_sold} acc`"
    )
    bot.send_message(chat_id, text, parse_mode="Markdown")

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
    failed = 0

    for u in users:
        try:
            bot.send_message(u['telegram_id'], f"📢 **THÔNG BÁO TỪ HỆ THỐNG**\n\n{text_to_send}", parse_mode="Markdown")
            success += 1
        except:
            failed += 1

    bot.send_message(message.chat.id, f"✅ Gửi Broadcast hoàn tất!\n- Thành công: `{success}`\n- Thất bại: `{failed}`", parse_mode="Markdown")

# --- CHẠY WEB SERVER VÀ BOT SONG SONG ---
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    print("✨ Axiom Bot Web Service đang chạy...")
    bot.infinity_polling()

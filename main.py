import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import uuid
import time
import os
import threading
import psutil  # RAM ও CPU দেখার জন্য
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

# ================= বটের আপটাইম ট্র্যাকার =================
START_TIME = time.time()

# ================= আপনার দেওয়া টোকেন ও এডমিন আইডি =================
TOKEN = '8401364281:AAFvM3qv3vGXvCA5EUT30e43vnmTlevMHX4'
ADMIN_IDS =[6113272565, 8672231989,  7450191608] 

bot = telebot.TeleBot(TOKEN)

# ================= ডাটাবেস ও সেটিংস সেটআপ (Firebase) =================
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://viral-link-tg-bot-default-rtdb.asia-southeast1.firebasedatabase.app/'
})

DATA_FILE = 'data'
USERS_FILE = 'users'
BANNED_FILE = 'banned'
SETTINGS_FILE = 'settings'

def load_data(node_name, default_type):
    ref = db.reference(node_name)
    data = ref.get()
    return data if data is not None else default_type

def save_data(node_name, data):
    ref = db.reference(node_name)
    ref.set(data)

default_settings = {
    "FORCE_SUB_CHANNELS": "", 
    "OWNER_USERNAME": "owner_username",
    "CUSTOM_CAPTION": "\n\n📥 **Downloaded from our Bot**",
    "AUTO_DELETE_TIME": 300, 
    "PROTECT_CONTENT": True,
    "DB_CHANNEL_ID": "",
    "WELCOME_MESSAGE": "👋 স্বাগতম! আমার মাধ্যমে ফাইল পেতে চাইলে সঠিক শেয়ারিং লিংকটি ওপেন করুন।\n\nনিচের বাটনগুলো থেকে আমাদের চ্যানেল বা এডমিনের সাথে যোগাযোগ করতে পারেন👇"
}

file_storage = load_data(DATA_FILE, {})
users_data = load_data(USERS_FILE,[])
banned_users = load_data(BANNED_FILE,[])
settings = load_data(SETTINGS_FILE, default_settings)

user_temp_files = {}
messages_to_delete =[]

# ================= অটো-ডিলিট এবং অটো-ক্লিনআপ থ্রেড =================
def auto_delete_worker():
    while True:
        time.sleep(5)
        current_time = time.time()
        for item in list(messages_to_delete):
            if current_time >= item['delete_at']:
                try: bot.delete_message(item['chat_id'], item['msg_id'])
                except: pass
                if item in messages_to_delete: messages_to_delete.remove(item)

threading.Thread(target=auto_delete_worker, daemon=True).start()

def auto_cleanup_links_worker():
    while True:
        time.sleep(3600)  # প্রতি ১ ঘণ্টা পর পর চেক করবে
        current_time = time.time()
        expired_links =[]
        for link_id, data in list(file_storage.items()):
            if isinstance(data, dict):
                exp_time = data.get('expire_time', -1)
                if exp_time != -1 and current_time > exp_time:
                    expired_links.append(link_id)
        if expired_links:
            for lid in expired_links: del file_storage[lid]
            save_data(DATA_FILE, file_storage)

threading.Thread(target=auto_cleanup_links_worker, daemon=True).start()

# ================= অ্যান্টি-স্প্যাম সিস্টেম =================
SPAM_DICT = {}
def is_spam(user_id):
    if user_id in ADMIN_IDS: return False
    current_time = time.time()
    if user_id in SPAM_DICT and current_time - SPAM_DICT[user_id] < 2: return True
    SPAM_DICT[user_id] = current_time
    return False

def is_admin(user_id): return user_id in ADMIN_IDS

def get_not_joined_channels(user_id):
    channels_str = settings.get("FORCE_SUB_CHANNELS", "").strip()
    if not channels_str: return []
    not_joined = []
    channels =[ch.strip() for ch in channels_str.split(',') if ch.strip()]
    for channel in channels:
        try:
            status = bot.get_chat_member(channel, user_id).status
            if status not in ['member', 'administrator', 'creator']: not_joined.append(channel)
        except: not_joined.append(channel) 
    return not_joined

@bot.chat_join_request_handler()
def handle_join_request(message):
    try:
        bot.approve_chat_join_request(message.chat.id, message.from_user.id)
        bot.send_message(message.from_user.id, f"✅ <b>{message.chat.title}</b> চ্যানেলে আপনার জয়েন রিকোয়েস্ট এক্সেপ্ট করা হয়েছে!", parse_mode="HTML")
    except: pass

# ================= অ্যাডমিন এবং ইউজার কাস্টম কিবোর্ড =================
def get_admin_reply_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("📣 Updates Channel"))
    markup.add(KeyboardButton("📤 Upload File"), KeyboardButton("📊 Statistics"))
    markup.add(KeyboardButton("👥 Manage Users"), KeyboardButton("🔗 Manage Links"))
    markup.add(KeyboardButton("🖥 System Stats"), KeyboardButton("✉️ Send Notice"))
    markup.add(KeyboardButton("⚙️ Settings"), KeyboardButton("📞 Contact Owner"))
    return markup

def get_user_reply_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("📢 Our Channel"), KeyboardButton("📞 Contact Owner"))
    markup.add(KeyboardButton("📝 Request File/Movie"))
    return markup

# ================= অ্যাডমিন মেনু ও সেটিংস টেক্সট জেনারেটর =================
def get_admin_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    owner = settings.get("OWNER_USERNAME", "")
    markup.add(InlineKeyboardButton("📤 Upload File", callback_data="btn_upload"),
               InlineKeyboardButton("📊 Statistics", callback_data="btn_stats"))
    markup.add(InlineKeyboardButton("🖥 System Stats", callback_data="btn_sys_stats"),
               InlineKeyboardButton("👥 Manage Users", callback_data="btn_users_0"))
    markup.add(InlineKeyboardButton("🔗 Manage Links", callback_data="btn_links_0"),
               InlineKeyboardButton("✉️ Send Notice", callback_data="btn_notice"))
    markup.add(InlineKeyboardButton("⚙️ Settings", callback_data="btn_settings"),
               InlineKeyboardButton("📞 Contact Owner", url=f"https://t.me/{owner.replace('@','')}" if owner else "https://t.me/telegram"))
    return markup

def get_settings_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    protect_status = "✅ On" if settings.get("PROTECT_CONTENT", True) else "❌ Off"
    markup.add(
        InlineKeyboardButton("⏱ Auto Delete", callback_data="set_autodelete"),
        InlineKeyboardButton("📝 Custom Caption", callback_data="set_caption")
    )
    markup.add(
        InlineKeyboardButton("📢 Force Sub", callback_data="set_forcesub"),
        InlineKeyboardButton("👤 Owner", callback_data="set_owner")
    )
    markup.add(
        InlineKeyboardButton(f"🛡 Protect: {protect_status}", callback_data="toggle_protect"),
        InlineKeyboardButton("🗄 DB Channel", callback_data="set_dbchannel")
    )
    markup.add(
        InlineKeyboardButton("✉️ Welcome Msg", callback_data="set_welcomemsg"),
        InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main_menu")
    )
    return markup

def get_settings_text():
    caption = str(settings.get('CUSTOM_CAPTION', '')).replace('<', '&lt;').replace('>', '&gt;')
    welcome = str(settings.get('WELCOME_MESSAGE', 'Not Set')).replace('<', '&lt;').replace('>', '&gt;')[:40] + "..."
    return (
        f"⚙️ <b>Current Settings:</b>\n\n"
        f"⏱ <b>Auto Delete:</b> <code>{settings.get('AUTO_DELETE_TIME')} sec</code>\n"
        f"📢 <b>Force Sub:</b> <code>{settings.get('FORCE_SUB_CHANNELS', 'Not Set')}</code>\n"
        f"👤 <b>Owner:</b> <code>{settings.get('OWNER_USERNAME', 'Not Set')}</code>\n"
        f"🗄 <b>DB Channel:</b> <code>{settings.get('DB_CHANNEL_ID', 'Not Set')}</code>\n"
        f"🛡 <b>Protection:</b> <code>{'ON' if settings.get('PROTECT_CONTENT', True) else 'OFF'}</code>\n"
        f"📝 <b>Caption:</b>\n{caption}\n\n"
        f"✉️ <b>Welcome:</b> {welcome}"
    )

def get_sys_stats_text():
    uptime_seconds = int(time.time() - START_TIME)
    uptime_str = f"{uptime_seconds//86400}d {(uptime_seconds%86400)//3600}h {(uptime_seconds%3600)//60}m {uptime_seconds%60}s"
    try:
        cpu = psutil.cpu_percent()
        
        # RAM ক্যালকুলেশন (GB এবং MB)
        mem = psutil.virtual_memory()
        total_ram_gb = round(mem.total / (1024**3), 2)
        used_ram_mb = round(mem.used / (1024**2), 2)
        if used_ram_mb >= 1024:
            used_ram_str = f"{round(used_ram_mb/1024, 2)} GB"
        else:
            used_ram_str = f"{used_ram_mb} MB"
        ram_display = f"{used_ram_str} / {total_ram_gb} GB ({mem.percent}%)"
        
        # Disk/Storage ক্যালকুলেশন (GB)
        disk_info = psutil.disk_usage('/')
        total_disk_gb = round(disk_info.total / (1024**3), 2)
        used_disk_gb = round(disk_info.used / (1024**3), 2)
        disk_display = f"{used_disk_gb} GB / {total_disk_gb} GB ({disk_info.percent}%)"
        
    except:
        cpu, ram_display, disk_display = "N/A", "N/A", "N/A"
        
    start_ping = time.time()
    try:
        bot.get_me()
        ping = round((time.time() - start_ping) * 1000)
    except:
        ping = "N/A"
    
    return (
        f"🖥 <b>System & Server Stats:</b>\n\n"
        f"⏳ <b>Uptime:</b> <code>{uptime_str}</code>\n"
        f"🏓 <b>Ping:</b> <code>{ping} ms</code>\n"
        f"🧠 <b>CPU Usage:</b> <code>{cpu}%</code>\n"
        f"💾 <b>RAM Usage:</b> <code>{ram_display}</code>\n"
        f"💿 <b>Disk Usage:</b> <code>{disk_display}</code>\n"
    )

# ================= ফাইল সেন্ড ফলব্যাক সিস্টেম =================
def safe_send_file(chat_id, f_type, f_id, caption, is_protected):
    sent_msg = None
    try:
        if f_type == 'text':
            text_msg = f"{f_id}\n\n{caption}" if caption else f_id
            sent_msg = bot.send_message(chat_id, text_msg, parse_mode="HTML", protect_content=is_protected, disable_web_page_preview=False)
        elif f_type == 'photo': sent_msg = bot.send_photo(chat_id, f_id, caption=caption, parse_mode="Markdown", protect_content=is_protected)
        elif f_type == 'video': sent_msg = bot.send_video(chat_id, f_id, caption=caption, parse_mode="Markdown", protect_content=is_protected)
        elif f_type == 'audio': sent_msg = bot.send_audio(chat_id, f_id, caption=caption, parse_mode="Markdown", protect_content=is_protected)
        else: sent_msg = bot.send_document(chat_id, f_id, caption=caption, parse_mode="Markdown", protect_content=is_protected)
    except Exception as e:
        try:
            if f_type == 'text':
                text_msg = f"{f_id}\n\n{caption}" if caption else f_id
                sent_msg = bot.send_message(chat_id, text_msg, protect_content=is_protected, disable_web_page_preview=False)
            elif f_type == 'photo': sent_msg = bot.send_photo(chat_id, f_id, caption=caption, protect_content=is_protected)
            elif f_type == 'video': sent_msg = bot.send_video(chat_id, f_id, caption=caption, protect_content=is_protected)
            elif f_type == 'audio': sent_msg = bot.send_audio(chat_id, f_id, caption=caption, protect_content=is_protected)
            else: sent_msg = bot.send_document(chat_id, f_id, caption=caption, protect_content=is_protected)
        except: pass
    return sent_msg

# ================= স্টার্ট কমান্ড =================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    if is_spam(user_id): return 
    if user_id in banned_users: return bot.send_message(message.chat.id, "⛔ আপনাকে এই বট থেকে ব্যান করা হয়েছে।")
    
    if user_id not in users_data:
        users_data.append(user_id)
        save_data(USERS_FILE, users_data)

    text_parts = message.text.split()
    if len(text_parts) > 1:
        unique_id = text_parts[1]
        
        not_joined_channels = get_not_joined_channels(user_id)
        if not_joined_channels:
            markup = InlineKeyboardMarkup(row_width=1)
            for idx, ch in enumerate(not_joined_channels):
                try:
                    if ch.startswith('-100') or ch.replace('-','').isdigit():
                        chat_info = bot.get_chat(ch)
                        url = chat_info.invite_link if chat_info.invite_link else bot.export_chat_invite_link(ch)
                    else:
                        url = f"https://t.me/{ch.replace('@', '')}"
                except:
                    url = "https://t.me/telegram"
                    
                markup.add(InlineKeyboardButton(f"📢 Join Channel {idx+1}", url=url))
                
            markup.add(InlineKeyboardButton("🔄 Try Again", url=f"https://t.me/{bot.get_me().username}?start={unique_id}"))
            return bot.reply_to(message, "⚠️ <b>ফাইল পেতে হলে আগে আমাদের টেলিগ্রাম চ্যানেলগুলোতে জয়েন করুন!</b>", reply_markup=markup, parse_mode="HTML")

        if unique_id in file_storage:
            link_data = file_storage[unique_id]
            if isinstance(link_data, list):
                files, views_left, expire_time = link_data, -1, -1
            else:
                files = link_data['files']
                views_left = link_data.get('views_left', -1)
                expire_time = link_data.get('expire_time', -1)

            if expire_time != -1 and time.time() > expire_time:
                bot.send_message(message.chat.id, "❌ <b>দুঃখিত, এই লিংকটির মেয়াদ শেষ হয়ে গেছে!</b>", parse_mode="HTML")
                del file_storage[unique_id]; save_data(DATA_FILE, file_storage)
                return

            if views_left != -1:
                if views_left <= 0:
                    bot.send_message(message.chat.id, "❌ <b>দুঃখিত, এই লিংকটির সর্বোচ্চ ভিউ লিমিট শেষ!</b>", parse_mode="HTML")
                    del file_storage[unique_id]; save_data(DATA_FILE, file_storage)
                    return
                else:
                    views_left -= 1
                    file_storage[unique_id]['views_left'] = views_left
                    if views_left == 0: del file_storage[unique_id] 
                    save_data(DATA_FILE, file_storage)

            msg = bot.send_message(message.chat.id, "আপনার ফাইলগুলো পাঠানো হচ্ছে, অপেক্ষা করুন... ⏳")
            caption_text = settings.get("CUSTOM_CAPTION", "")
            delete_time = int(settings.get("AUTO_DELETE_TIME", 300))
            is_protected = settings.get("PROTECT_CONTENT", True)
            
            for file_info in files:
                f_id, f_type = file_info['id'], file_info['type']
                caption = caption_text if file_info == files[0] else "" 
                
                sent_msg = safe_send_file(message.chat.id, f_type, f_id, caption, is_protected)
                if sent_msg and delete_time > 0:
                    messages_to_delete.append({'chat_id': message.chat.id, 'msg_id': sent_msg.message_id, 'delete_at': time.time() + delete_time})
            
            if delete_time > 0:
                bot.send_message(message.chat.id, f"⚠️ <b>সতর্কতা:</b> ফাইলগুলো {delete_time//60} মিনিট পর অটোমেটিক ডিলিট হয়ে যাবে।", parse_mode="HTML")
            delete_message(message.chat.id, msg.message_id) 
            
        else:
            bot.send_message(message.chat.id, "❌ লিংকটি ভুল অথবা মুছে ফেলা হয়েছে!")
    else:
        if is_admin(user_id): 
            bot.send_message(message.chat.id, f"👋 স্বাগতম এডমিন! \n\nনিচের মেনু থেকে কাজ করুন👇", reply_markup=get_admin_reply_menu())
        else: 
            welcome_text = settings.get("WELCOME_MESSAGE", "👋 স্বাগতম! আমার মাধ্যমে ফাইল পেতে চাইলে সঠিক শেয়ারিং লিংকটি ওপেন করুন।")
            bot.send_message(message.chat.id, welcome_text, reply_markup=get_user_reply_menu(), parse_mode="HTML")

def delete_message(chat_id, message_id):
    try: bot.delete_message(chat_id, message_id)
    except: pass

# ================= অ্যাডমিন মেনু ও সেটিংস রেসপন্স =================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if not is_admin(call.from_user.id): return
    
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    
    if call.data == "btn_main_menu":
        bot.edit_message_text("👋 এডমিন প্যানেল:\nনিচের মেনু থেকে আপনার পছন্দমতো কাজ করুন👇", call.message.chat.id, call.message.message_id, reply_markup=get_admin_menu())
    
    elif call.data == "btn_stats":
        total_files = sum(len(f) if isinstance(f, list) else len(f['files']) for f in file_storage.values())
        stat_msg = f"📊 <b>Bot Statistics:</b>\n\n👥 Total Users: {len(users_data)}\n🔗 Total Links: {len(file_storage)}\n📁 Total Files: {total_files}\n🚫 Banned Users: {len(banned_users)}"
        bot.send_message(call.message.chat.id, stat_msg, parse_mode="HTML")

    elif call.data == "btn_sys_stats":
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back", callback_data="btn_main_menu"))
        bot.edit_message_text(get_sys_stats_text(), call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    elif call.data == "btn_upload":
        bot.send_message(call.message.chat.id, "📤 আমাকে ছবি, ভিডিও বা ডকুমেন্ট পাঠানো শুরু করুন অথবা অন্য চ্যানেল থেকে <b>Forward</b> করুন।\nসব পাঠানো শেষ হলে ফাইলের নিচে থাকা বাটনে ক্লিক করবেন。", parse_mode="HTML")
            
    elif call.data == "btn_notice":
        msg = bot.send_message(call.message.chat.id, "✉️ আপনি ইউজারদের যে মেসেজটি পাঠাতে চান তা আমাকে লিখে বা ফরোয়ার্ড করে দিন:")
        bot.register_next_step_handler(msg, process_broadcast)

    # ================= লিংকের লিস্ট দেখা (Manage Links) =================
    elif call.data.startswith("btn_links_"):
        page = int(call.data.split("_")[2])
        per_page = 5
        items = list(file_storage.items())
        total_pages = max(1, (len(items) + per_page - 1) // per_page)
        
        if len(items) == 0:
            return bot.send_message(call.message.chat.id, "⚠️ আপনার ডাটাবেসে এখনও কোনো লিংক তৈরি করা নেই।")
            
        start = page * per_page
        end = start + per_page
        current_items = items[start:end]
        
        bot_username = bot.get_me().username
        msg_text = f"📂 <b>All Generated Links (Page {page+1}/{total_pages})</b>\nTotal Links: {len(items)}\n\n"
        
        for idx, (link_id, data) in enumerate(current_items):
            if isinstance(data, list):
                f_count, v_left, exp = len(data), "∞", "∞"
            else:
                f_count = len(data.get('files',[]))
                v_left = data.get('views_left', -1)
                v_left = "∞" if v_left == -1 else v_left
                exp_time = data.get('expire_time', -1)
                if exp_time == -1: exp = "∞"
                else:
                    t_left = exp_time - time.time()
                    exp = "Expired" if t_left < 0 else f"{int(t_left//3600)}h {int((t_left%3600)//60)}m"
            
            title = data.get('title', 'Untitled') if isinstance(data, dict) else 'Untitled'
            msg_text += f"{start + idx + 1}. <b>Title:</b> {title}\n"
            msg_text += f"<b>ID:</b> <code>{link_id}</code> | 📁 Files: {f_count}\n"
            msg_text += f"👁 Views: {v_left} | ⏳ Exp: {exp}\n"
            msg_text += f"🔗 https://t.me/{bot_username}?start={link_id}\n\n"

        markup = InlineKeyboardMarkup(row_width=2)
        nav =[]
        if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"btn_links_{page-1}"))
        if end < len(items): nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"btn_links_{page+1}"))
        if nav: markup.add(*nav)
        
        markup.add(InlineKeyboardButton("🔍 Search Link", callback_data="btn_search_link"))
        markup.add(InlineKeyboardButton("🗑 Delete a Link", callback_data="btn_delete_link"))
        markup.add(InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main_menu"))

        bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)

    elif call.data == "btn_delete_link":
        msg = bot.send_message(call.message.chat.id, "🗑 যে লিংকটি ডিলিট করতে চান তার <b>ID</b> দিন (যেমন: a1b2c3d4):", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_delete_link)
        
    elif call.data == "btn_search_link":
        msg = bot.send_message(call.message.chat.id, "🔍 লিংকের <b>ID</b> অথবা <b>Title (নাম)</b> লিখে পাঠান:", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_search_link)
        
    elif call.data == "btn_search_user":
        msg = bot.send_message(call.message.chat.id, "🔍 ইউজারের <b>ID</b> লিখে পাঠান:")
        bot.register_next_step_handler(msg, process_search_user)

    elif call.data.startswith("del_search_"):
        link_id = call.data.split("del_search_")[1]
        if link_id in file_storage:
            del file_storage[link_id]
            save_data(DATA_FILE, file_storage)
            bot.answer_callback_query(call.id, "✅ লিংক সফলভাবে ডিলিট করা হয়েছে!", show_alert=True)
            bot.edit_message_text(f"✅ লিংক <b>{link_id}</b> ডিলিট করা হয়েছে!", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        else:
            bot.answer_callback_query(call.id, "❌ লিংকটি ডাটাবেসে নেই।", show_alert=True)

    # ================= ইউজার লিস্ট ও ব্যান/আনব্যান =================
    elif call.data.startswith("btn_users_"):
        page = int(call.data.split("_")[2])
        per_page = 10
        start = page * per_page
        end = start + per_page
        current_users = users_data[start:end]

        markup = InlineKeyboardMarkup(row_width=2)
        for uid in current_users:
            status = "🚫" if uid in banned_users else "👤"
            markup.add(InlineKeyboardButton(f"{status} {uid}", callback_data=f"manage_usr_{uid}_{page}"))

        nav =[]
        if page > 0: nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"btn_users_{page-1}"))
        if end < len(users_data): nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"btn_users_{page+1}"))
        if nav: markup.add(*nav)
        markup.add(InlineKeyboardButton("🔍 Search User", callback_data="btn_search_user"))
        markup.add(InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main_menu"))

        bot.edit_message_text(f"👥 <b>User Management (Page {page+1})</b>\nTotal Users: {len(users_data)}\nযেকোনো ইউজারের আইডিতে ক্লিক করে Ban/Unban করুন:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    elif call.data.startswith("manage_usr_"):
        uid = int(call.data.split("_")[2])
        page = int(call.data.split("_")[3])
        markup = InlineKeyboardMarkup()
        if uid in banned_users: markup.add(InlineKeyboardButton("✅ Unban User", callback_data=f"act_unban_{uid}_{page}"))
        else: markup.add(InlineKeyboardButton("🚫 Ban User", callback_data=f"act_ban_{uid}_{page}"))
        markup.add(InlineKeyboardButton("🔙 Back to List", callback_data=f"btn_users_{page}"))

        try:
            u_info = bot.get_chat(uid)
            name = (u_info.first_name or "Unknown").replace('<', '&lt;').replace('>', '&gt;')
            username = f"@{u_info.username}" if u_info.username else "N/A"
        except: 
            name = "Unknown"
            username = "N/A"

        user_info_msg = (
            f"👤 <b>User Info:</b>\n\n"
            f"<b>ID:</b> <code>{uid}</code>\n"
            f"<b>Name:</b> {name}\n"
            f"<b>Username:</b> {username}\n"
            f"<b>Status:</b> {'Banned 🚫' if uid in banned_users else 'Active ✅'}"
        )
        bot.edit_message_text(user_info_msg, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    elif call.data.startswith("act_ban_"):
        uid = int(call.data.split("_")[2])
        page = call.data.split("_")[3]
        if uid not in banned_users:
            banned_users.append(uid)
            save_data(BANNED_FILE, banned_users)
        bot.answer_callback_query(call.id, "✅ User Banned Successfully!", show_alert=True)
        bot.edit_message_text(f"✅ User {uid} has been banned.", call.message.chat.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back to List", callback_data=f"btn_users_{page}")))

    elif call.data.startswith("act_unban_"):
        uid = int(call.data.split("_")[2])
        page = call.data.split("_")[3]
        if uid in banned_users:
            banned_users.remove(uid)
            save_data(BANNED_FILE, banned_users)
        bot.answer_callback_query(call.id, "✅ User Unbanned Successfully!", show_alert=True)
        bot.edit_message_text(f"✅ User {uid} has been unbanned.", call.message.chat.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Back to List", callback_data=f"btn_users_{page}")))

    # ================= সেটিংস ও অন্যান্য =================
    elif call.data == "btn_settings":
        try: bot.edit_message_text(get_settings_text(), call.message.chat.id, call.message.message_id, reply_markup=get_settings_menu(), parse_mode="HTML")
        except: pass

    elif call.data == "toggle_protect":
        settings["PROTECT_CONTENT"] = not settings.get("PROTECT_CONTENT", True)
        save_data(SETTINGS_FILE, settings)
        try: bot.edit_message_text(get_settings_text(), call.message.chat.id, call.message.message_id, reply_markup=get_settings_menu(), parse_mode="HTML")
        except: pass

    elif call.data == "set_autodelete":
        msg = bot.send_message(call.message.chat.id, "⏱ অটো-ডিলিট টাইম (সেকেন্ডে) দিন। (যেমন: 300 মানে ৫ মিনিট, 0 দিলে ডিলিট হবে না):")
        bot.register_next_step_handler(msg, update_setting, "AUTO_DELETE_TIME", int)
    elif call.data == "set_caption":
        msg = bot.send_message(call.message.chat.id, "📝 নতুন কাস্টম ক্যাপশনটি লিখে পাঠান:")
        bot.register_next_step_handler(msg, update_setting, "CUSTOM_CAPTION", str)
    elif call.data == "set_forcesub":
        msg = bot.send_message(call.message.chat.id, "📢 ফোর্স সাব চ্যানেলের ইউজারনেম (@channel) অথবা প্রাইভেট চ্যানেলের ID (-100123...) দিন। একাধিক হলে কমা দিয়ে লিখুন।\nবন্ধ করতে চাইলে 0 লিখে পাঠান:")
        bot.register_next_step_handler(msg, update_setting, "FORCE_SUB_CHANNELS", str)
    elif call.data == "set_owner":
        msg = bot.send_message(call.message.chat.id, "👤 মালিকের ইউজারনেম দিন (শুধু নাম দিন, @ ছাড়া):")
        bot.register_next_step_handler(msg, update_setting, "OWNER_USERNAME", str)
    elif call.data == "set_welcomemsg":
        msg = bot.send_message(call.message.chat.id, "✉️ নতুন ইউজারদের জন্য ওয়েলকাম মেসেজটি লিখে বা ফরোয়ার্ড করে পাঠান (HTML সাপোর্ট করে):")
        bot.register_next_step_handler(msg, update_setting, "WELCOME_MESSAGE", str)
    elif call.data == "set_dbchannel":
        msg = bot.send_message(call.message.chat.id, "🗄 ডাটাবেস প্রাইভেট চ্যানেলের ID দিন (যেমন: -1001234567890)।\nবন্ধ করতে চাইলে 0 লিখে পাঠান:")
        bot.register_next_step_handler(msg, update_setting, "DB_CHANNEL_ID", str)

    # আপলোড ফিনিশ বাটনসমূহ
    elif call.data == "finish_normal":
        msg = bot.send_message(call.message.chat.id, "📝 এই লিংকের জন্য একটি নাম বা টাইটেল দিন (যাতে পরে সহজে খুঁজে পান):")
        bot.register_next_step_handler(msg, lambda m: generate_link(call.from_user.id, views=-1, expire_hours=-1, chat_id=call.message.chat.id, title=m.text))
    elif call.data == "finish_views":
        msg = bot.send_message(call.message.chat.id, "👁 কতজন দেখার পর লিংকটি নষ্ট হয়ে যাবে? (সংখ্যা দিন, যেমন: 10):")
        bot.register_next_step_handler(msg, lambda m: process_limit_input(m, call.from_user.id, "views"))
    elif call.data == "finish_time":
        msg = bot.send_message(call.message.chat.id, "⏳ কত ঘণ্টা পর লিংকটি নষ্ট হয়ে যাবে? (সংখ্যা দিন, যেমন: 24):")
        bot.register_next_step_handler(msg, lambda m: process_limit_input(m, call.from_user.id, "time"))
    elif call.data == "cancel_upload":
        if str(call.from_user.id) in user_temp_files: user_temp_files[str(call.from_user.id)].clear()
        bot.edit_message_text("❌ আপলোড বাতিল করা হয়েছে।", call.message.chat.id, call.message.message_id)

# ================= ইনপুট ও আপডেট হ্যান্ডলার =================
def update_setting(message, key, val_type):
    if not message.text: return bot.reply_to(message, "❌ টেক্সট ইনপুট দিন!")
    if message.text.startswith('/'): return bot.reply_to(message, "❌ সেটিং আপডেট বাতিল করা হয়েছে।")
    try:
        val = message.text.strip()
        if key in["FORCE_SUB_CHANNELS", "DB_CHANNEL_ID"] and val == "0": val = ""
        settings[key] = val_type(val)
        save_data(SETTINGS_FILE, settings)
        bot.reply_to(message, f"✅ <b>{key}</b> আপডেট করা হয়েছে। চেক করতে /start দিন।", parse_mode="HTML")
    except ValueError: bot.reply_to(message, "❌ সঠিক ফরম্যাটে ইনপুট দিন!")

def process_search_link(message):
    query = message.text.strip().lower()
    found = False
    for link_id, data in file_storage.items():
        title = data.get('title', '').lower() if isinstance(data, dict) else ''
        if query == link_id.lower() or query in title:
            found = True
            bot_username = bot.get_me().username
            if isinstance(data, list): f_count, v_left, exp, real_title = len(data), "∞", "∞", "Untitled"
            else:
                f_count = len(data.get('files',[]))
                v_left = data.get('views_left', -1)
                v_left = "∞" if v_left == -1 else v_left
                exp_time = data.get('expire_time', -1)
                if exp_time == -1: exp = "∞"
                else:
                    t_left = exp_time - time.time()
                    exp = "Expired" if t_left < 0 else f"{int(t_left//3600)}h {int((t_left%3600)//60)}m"
                real_title = data.get('title', 'Untitled')
            
            msg_text = f"🔍 <b>Search Result:</b>\n\n📝 <b>Title:</b> {real_title}\n🆔 <b>ID:</b> <code>{link_id}</code>\n"
            msg_text += f"📁 Files: {f_count} | 👁 Views: {v_left} | ⏳ Exp: {exp}\n🔗 https://t.me/{bot_username}?start={link_id}\n"
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🗑 Delete This Link", callback_data=f"del_search_{link_id}"))
            bot.send_message(message.chat.id, msg_text, reply_markup=markup, parse_mode="HTML")
    
    if not found: bot.reply_to(message, "❌ এই ID বা Title দিয়ে কোনো লিংক পাওয়া যায়নি।")

def process_search_user(message):
    query = message.text.strip()
    if not query.isdigit(): return bot.reply_to(message, "❌ দয়া করে সঠিক ইউজার ID (সংখ্যা) দিন।")
    uid = int(query)
    if uid in users_data:
        markup = InlineKeyboardMarkup()
        if uid in banned_users: markup.add(InlineKeyboardButton("✅ Unban User", callback_data=f"act_unban_{uid}_0"))
        else: markup.add(InlineKeyboardButton("🚫 Ban User", callback_data=f"act_ban_{uid}_0"))
        try:
            u_info = bot.get_chat(uid)
            name = (u_info.first_name or "Unknown").replace('<', '&lt;').replace('>', '&gt;')
        except: name = "Unknown"
        bot.send_message(message.chat.id, f"🔍 <b>User Found:</b>\n\n<b>ID:</b> <code>{uid}</code>\n<b>Name:</b> {name}\n<b>Status:</b> {'Banned 🚫' if uid in banned_users else 'Active ✅'}", reply_markup=markup, parse_mode="HTML")
    else:
        bot.reply_to(message, "❌ এই ID দিয়ে ডাটাবেসে কোনো ইউজার পাওয়া যায়নি।")

def process_delete_link(message):
    link_id = message.text.strip()
    if link_id in file_storage:
        del file_storage[link_id]
        save_data(DATA_FILE, file_storage)
        bot.reply_to(message, f"✅ লিংক <b>{link_id}</b> সফলভাবে ডিলিট করা হয়েছে!", parse_mode="HTML")
    else:
        bot.reply_to(message, "❌ এই আইডি দিয়ে ডাটাবেসে কোনো লিংক পাওয়া যায়নি।", parse_mode="HTML")

def process_broadcast(message):
    bot.reply_to(message, "📢 ব্রডকাস্ট শুরু হচ্ছে...")
    success = 0
    for uid in users_data:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
            success += 1
            time.sleep(0.05)
        except: pass
    bot.send_message(message.chat.id, f"✅ সফলভাবে {success} জন ইউজারকে মেসেজ পাঠানো হয়েছে।")

def process_limit_input(message, user_id, limit_type):
    if not message.text: return bot.reply_to(message, "❌ সঠিক সংখ্যা দিন!")
    try:
        val = float(message.text) if limit_type == "time" else int(message.text)
        msg = bot.send_message(message.chat.id, "📝 এই লিংকের জন্য একটি নাম বা টাইটেল দিন (যাতে পরে সহজে খুঁজে পান):")
        if limit_type == "views":
            bot.register_next_step_handler(msg, lambda m: generate_link(user_id, views=val, expire_hours=-1, chat_id=message.chat.id, title=m.text))
        else:
            bot.register_next_step_handler(msg, lambda m: generate_link(user_id, views=-1, expire_hours=val, chat_id=message.chat.id, title=m.text))
    except: bot.reply_to(message, "❌ সঠিক সংখ্যা দিন!")

def generate_link(user_id, views, expire_hours, chat_id, title="Untitled"):
    user_id_str = str(user_id)
    if user_id_str not in user_temp_files or not user_temp_files[user_id_str]: 
        return bot.send_message(chat_id, "⚠️ লিস্টে কোনো ফাইল নেই!")
        
    unique_id = str(uuid.uuid4())[:8] 
    expire_timestamp = time.time() + (expire_hours * 3600) if expire_hours != -1 else -1
    
    file_storage[unique_id] = {
        'title': title,
        'files': user_temp_files[user_id_str].copy(),
        'views_left': views,
        'expire_time': expire_timestamp
    }
    save_data(DATA_FILE, file_storage)
    
    # ডাটাবেস চ্যানেলের প্রথম ফাইলে Title ও ID আপডেট করা
    db_channel = str(settings.get("DB_CHANNEL_ID", "")).strip()
    if db_channel and user_temp_files[user_id_str]:
        first_file = user_temp_files[user_id_str][0]
        if first_file.get('db_msg_id'):
            db_caption = f"📝 <b>Title:</b> {title}\n🆔 <b>ID:</b> <code>{unique_id}</code>\n🔗 <b>Link:</b> https://t.me/{bot.get_me().username}?start={unique_id}"
            try: 
                if first_file.get('type') == 'text':
                    bot.edit_message_text(text=f"{first_file['id']}\n\n{db_caption}", chat_id=db_channel, message_id=first_file['db_msg_id'], parse_mode="HTML")
                else:
                    bot.edit_message_caption(caption=db_caption, chat_id=db_channel, message_id=first_file['db_msg_id'], parse_mode="HTML")
            except: pass

    user_temp_files[user_id_str].clear() 
    
    link = f"https://t.me/{bot.get_me().username}?start={unique_id}"
    msg_text = f"🎉 <b>আপনার লিংক তৈরি হয়েছে:</b>\n\n📝 <b>Title:</b> {title}\n🔗 <code>{link}</code>\n\n"
    if views != -1: msg_text += f"👁 <b>লিমিট:</b> {views} জন দেখার পর নষ্ট হয়ে যাবে。\n"
    if expire_hours != -1: msg_text += f"⏳ <b>মেয়াদ:</b> {expire_hours} ঘণ্টা পর নষ্ট হয়ে যাবে。\n"
    
    bot.send_message(chat_id, msg_text, parse_mode="HTML")

# ================= রিকোয়েস্ট সিস্টেম এবং এডমিন রিপ্লাই =================
def process_user_request(message):
    if not message.text:
        return bot.reply_to(message, "❌ দয়া করে শুধুমাত্র টেক্সট লিখে রিকোয়েস্ট করুন!")
    
    bot.reply_to(message, "✅ <b>আপনার রিকোয়েস্টটি আমাদের কাছে পাঠানো হয়েছে!</b>\nএডমিন মেসেজটি দেখে শীঘ্রই আপনার কাছে ফাইল পাঠিয়ে দিবে।", parse_mode="HTML")
    
    request_msg = f"📝 <b>New File Request!</b>\n\n"
    request_msg += f"👤 <b>Name:</b> {message.from_user.first_name}\n"
    request_msg += f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n\n"
    request_msg += f"💬 <b>Request:</b> {message.text}"
    
    for admin_id in ADMIN_IDS:
        try: bot.send_message(admin_id, request_msg, parse_mode="HTML")
        except: pass

@bot.message_handler(func=lambda message: message.reply_to_message is not None and is_admin(message.from_user.id))
def handle_admin_reply_to_request(message):
    try:
        replied_text = message.reply_to_message.text
        if replied_text and "🆔 ID:" in replied_text:
            user_id_str = replied_text.split("🆔 ID:")[1].split("\n")[0].strip()
            target_user_id = int(user_id_str)
            bot.copy_message(target_user_id, message.chat.id, message.message_id)
            bot.reply_to(message, "✅ <b>আপনার রিপ্লাইটি ইউজারের কাছে পাঠানো হয়েছে!</b>", parse_mode="HTML")
    except Exception as e:
        pass

# ================= কাস্টম কিবোর্ড বাটন হ্যান্ডলার (Admin & User) =================
@bot.message_handler(func=lambda message: message.text in[
    "📣 Updates Channel", "📤 Upload File", "📊 Statistics", "🖥 System Stats",
    "👥 Manage Users", "🔗 Manage Links", "✉️ Send Notice", "⚙️ Settings", "📞 Contact Owner", "📢 Our Channel", "📝 Request File/Movie"
])
def handle_reply_keyboard(message):
    user_id = message.from_user.id
    text = message.text

    # --- সবার জন্য উন্মুক্ত (User & Admin Both) ---
    if text in["📞 Contact Owner", "📢 Our Channel", "📣 Updates Channel"]:
        if text == "📞 Contact Owner":
            owner = settings.get("OWNER_USERNAME", "")
            bot.send_message(message.chat.id, f"📞 <b>Contact Owner:</b>\nhttps://t.me/{owner.replace('@','')}" if owner else "https://t.me/telegram", parse_mode="HTML", disable_web_page_preview=True)
        else: 
            channels_str = settings.get("FORCE_SUB_CHANNELS", "").strip()
            first_channel = channels_str.split(',')[0].strip() if channels_str else ""
            if first_channel:
                bot.send_message(message.chat.id, f"📢 <b>Our Channel:</b>\nhttps://t.me/{first_channel.replace('@', '')}", parse_mode="HTML", disable_web_page_preview=True)
            else:
                bot.send_message(message.chat.id, "📢 <b>Channel:</b>\nNot set by admin yet.")
        return

    if text == "📝 Request File/Movie":
        msg = bot.send_message(message.chat.id, "📝 <b>আপনি কোন ফাইল বা মুভিটি খুঁজছেন?</b>\n\nদয়া করে মুভির নাম এবং রিলিজ ইয়ার লিখে সেন্ড করুন:", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_user_request)
        return

    # --- শুধুমাত্র এডমিনের জন্য ---
    if not is_admin(user_id): return

    if text == "📤 Upload File":
        bot.send_message(message.chat.id, "📤 আমাকে ছবি, ভিডিও বা ডকুমেন্ট পাঠানো শুরু করুন অথবা অন্য চ্যানেল থেকে <b>Forward</b> করুন।\nসব পাঠানো শেষ হলে ফাইলের নিচে থাকা বাটনে ক্লিক করবেন।", parse_mode="HTML")
    elif text == "📊 Statistics":
        total_files = sum(len(f) if isinstance(f, list) else len(f['files']) for f in file_storage.values())
        stat_msg = f"📊 <b>Bot Statistics:</b>\n\n👥 Total Users: {len(users_data)}\n🔗 Total Links: {len(file_storage)}\n📁 Total Files: {total_files}\n🚫 Banned Users: {len(banned_users)}"
        bot.send_message(message.chat.id, stat_msg, parse_mode="HTML")
    elif text == "🖥 System Stats":
        bot.send_message(message.chat.id, get_sys_stats_text(), parse_mode="HTML")
    elif text == "✉️ Send Notice":
        msg = bot.send_message(message.chat.id, "✉️ আপনি ইউজারদের যে মেসেজটি পাঠাতে চান তা আমাকে লিখে বা ফরোয়ার্ড করে দিন:")
        bot.register_next_step_handler(msg, process_broadcast)
    elif text == "⚙️ Settings":
        bot.send_message(message.chat.id, get_settings_text(), reply_markup=get_settings_menu(), parse_mode="HTML")
    elif text == "👥 Manage Users":
        bot.send_message(message.chat.id, "ক্লিক করুন 👇", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("👥 Open Manage Users", callback_data="btn_users_0")))
    elif text == "🔗 Manage Links":
        bot.send_message(message.chat.id, "ক্লিক করুন 👇", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔗 Open Manage Links", callback_data="btn_links_0")))

# ================= ফাইল রিসিভ ও আপলোড (DB Channel সংযুক্ত) =================
@bot.message_handler(content_types=['document', 'video', 'photo', 'audio', 'animation', 'text'])
def handle_files(message):
    user_id = message.from_user.id
    if not is_admin(user_id): return
    
    # মেনু বাটন বা কমান্ড হলে আপলোড হবে না
    if message.text and (message.text.startswith('/') or message.text in ["📣 Updates Channel", "📤 Upload File", "📊 Statistics", "🖥 System Stats", "👥 Manage Users", "🔗 Manage Links", "✉️ Send Notice", "⚙️ Settings", "📞 Contact Owner", "📢 Our Channel", "📝 Request File/Movie"]):
        return
        
    user_id_str = str(user_id)
    if user_id_str not in user_temp_files: user_temp_files[user_id_str] =[]

    file_id, file_type = "", ""
    if message.document: file_id, file_type = message.document.file_id, "document"
    elif message.video: file_id, file_type = message.video.file_id, "video"
    elif message.audio: file_id, file_type = message.audio.file_id, "audio"
    elif message.photo: file_id, file_type = message.photo[-1].file_id, "photo"
    elif message.animation: file_id, file_type = message.animation.file_id, "document" 
    elif message.text: file_id, file_type = message.text, "text" 

    db_msg_id = None
    # DB Channel এ ফাইল কপি করা
    db_channel = str(settings.get("DB_CHANNEL_ID", "")).strip()
    if db_channel and file_id:
        try: 
            db_msg = bot.copy_message(db_channel, message.chat.id, message.message_id)
            db_msg_id = db_msg.message_id
        except Exception as e: 
            bot.send_message(message.chat.id, f"⚠️ ডাটাবেস চ্যানেলে সেভ করতে সমস্যা হচ্ছে!\nError: {e}")

    if file_id:
        user_temp_files[user_id_str].append({'id': file_id, 'type': file_type, 'db_msg_id': db_msg_id})
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(InlineKeyboardButton("✅ Finish (Normal)", callback_data="finish_normal"))
        markup.add(InlineKeyboardButton("👁 View Limit", callback_data="finish_views"),
                   InlineKeyboardButton("⏳ Time Limit", callback_data="finish_time"))
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_upload"))
        bot.reply_to(message, f"✅ ফাইল সেভ হয়েছে! মোট ফাইল: {len(user_temp_files[user_id_str])}", reply_markup=markup)

# ================= MULTI-CLIENT STREAMING ENGINE (Pyrogram + aiohttp) =================
import asyncio

# Pyrogram-এর Event Loop Error ফিক্স করার জন্য
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from aiohttp import web
from pyrogram import Client
import math

# ⚠️ এখানে আপনার my.telegram.org এর ডাটা দিন
API_ID = 33445387  # আপনার API_ID দিন (Integer)
API_HASH = "5b1badf6d0f44c940a2263cef28d6689"

# ⚠️ এখানে আপনার মেইন বট এবং ডামি বটগুলোর টোকেন কমা দিয়ে দিন
MULTI_CLIENT_TOKENS = [
    TOKEN,  

    # ডামি বট speedbost1_bot
    
    "8703236011:AAEA3279_ak38POI_TAVK0b9tKZVe_0fBN8"  
    
    # ডামি বট speedbost2_bot
    
 "8430400718:AAHpjC4R07SrHCO-6-J8ZMT2P8LcMarpm8k"  
 
 # ডামি বট speedbost3_bot
 
 "8711817641:AAGYG1DACABDKYgxxSPrSudm4BJnXcw999U"
]

clients = []
client_index = 0

async def init_clients():
    global clients
    for i, tok in enumerate(MULTI_CLIENT_TOKENS):
        # সেশন ফাইল মেমোরিতে রাখতে ইন-মেমোরি স্ট্রিং ব্যবহার করা হচ্ছে
        client = Client(f"session_{i}", api_id=API_ID, api_hash=API_HASH, bot_token=tok, in_memory=True)
        await client.start()
        clients.append(client)
    print(f"✅ {len(clients)} Multi-Clients Started Successfully!")

def get_next_client():
    # Load Balancing: প্রতিবার নতুন ক্লায়েন্ট ব্যবহার করবে
    global client_index
    client = clients[client_index]
    client_index = (client_index + 1) % len(clients)
    return client

async def web_home(request):
    return web.Response(text="Bot & Multi-Client Streaming Server is Running 24/7!")

async def stream_handler(request):
    try:
        message_id = int(request.match_info.get('message_id'))
        db_channel = settings.get("DB_CHANNEL_ID", "").strip()
        if not db_channel:
            return web.Response(text="DB Channel not configured!", status=500)
            
        client = get_next_client()
        message = await client.get_messages(chat_id=int(db_channel), message_ids=message_id)
        
        if not message or not message.media:
            return web.Response(text="File not found or invalid message_id!", status=404)
            
        file = getattr(message, message.media.value)
        file_size = file.file_size
        file_name = getattr(file, "file_name", f"video_{message_id}.mp4")

        # স্ট্রিমিং নাকি ডিরেক্ট ডাউনলোড?
        is_download = request.query.get("download", "").lower() in ["true", "1", "yes"]
        disp = "attachment" if is_download else "inline"

        # Range Header (ভিডিও টেনে দেখার জন্য)
        range_header = request.headers.get('Range', 0)
        if range_header:
            range_match = range_header.replace('bytes=', '').split('-')
            start = int(range_match[0])
            end = int(range_match[1]) if range_match[1] else file_size - 1
        else:
            start = 0
            end = file_size - 1

        chunk_size = (end - start) + 1
        
        headers = {
            'Content-Type': getattr(file, "mime_type", "video/mp4"),
            'Accept-Ranges': 'bytes',
            'Content-Range': f'bytes {start}-{end}/{file_size}',
            'Content-Length': str(chunk_size),
            'Content-Disposition': f'{disp}; filename="{file_name}"'
        }

        response = web.StreamResponse(status=206 if range_header else 200, headers=headers)
        await response.prepare(request)

        # Pyrogram থেকে ডাটা এনে ব্রাউজারে পাঠানো (Chunking)
        offset = start
        async for chunk in client.stream_media(message, offset=offset, limit=chunk_size):
            try:
                await response.write(chunk)
            except Exception:
                # ইউজার ভিডিও কেটে দিলে বা রিফ্রেশ করলে এরর এড়াতে
                break

        return response
    except Exception as e:
        print(f"Streaming Error: {e}")
        return web.Response(status=500)

async def run_web_and_clients():
    await init_clients()
    app = web.Application()
    app.router.add_get('/', web_home)
    app.router.add_get('/watch/{message_id}', stream_handler)  # এই লিংকেই মুভি চলবে
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    # ইনফিনিট লুপ যেন সার্ভার বন্ধ না হয়
    while True:
        await asyncio.sleep(3600)

def start_asyncio_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_web_and_clients())

# ব্যাকগ্রাউন্ডে Asyncio (Pyrogram + Web Server) রান করা
threading.Thread(target=start_asyncio_thread, daemon=True).start()
# ====================================================================

print("বট এবং স্ট্রিমিং সার্ভার সফলভাবে রান করছে...")
while True:
    try:
        bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Telebot Error: {e}")
        time.sleep(5)

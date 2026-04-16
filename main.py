import asyncio
import re
import logging
import traceback

# ====== Logging Setup (সমস্যা ধরার জন্য) ======
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ====== Pyrogram & Python 3.10+ Event Loop Fix ======
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
# ====================================================

from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated

from info import API_ID, API_HASH, MAIN_BOT_TOKEN, OWNER_ID
from database import (add_user, get_all_users, get_bot_mode, set_bot_mode,
                      is_admin, add_admin, remove_admin, get_expired_files,
                      update_expired_link, save_broadcast_data, get_last_broadcast, clear_broadcast_data)
from server import start_web_server
from worker import start_dummy_bots, worker_loop, add_task_to_queue

# মেইন বটের Pyrogram Client তৈরি
app = Client(
    "main_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=MAIN_BOT_TOKEN
)

# অ্যাডমিন চেক করার কাস্টম ফিল্টার
async def admin_check(_, __, message: Message):
    return is_admin(message.from_user.id)
admin_filter = filters.create(admin_check)


# ==========================================
# 0. Ping Test (ডাটাবেস ছাড়াই চেক করার জন্য)
# ==========================================
@app.on_message(filters.command("ping"))
async def ping_cmd(client, message: Message):
    print(f"📥 [TEST LOG] Ping command received from {message.from_user.id}")
    await message.reply("🏓 **Pong!**\n\nYes, the bot is alive and receiving your messages properly!")


# ==========================================
# 1. Start Command & User Tracking
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    try:
        print(f"📥[TEST LOG] Start command received from {message.from_user.id}")
        user_id = message.from_user.id
        add_user(user_id) # ব্রডকাস্টের জন্য ডাটাবেসে সেভ
        print("✅ User saved to Firebase successfully.")

        # প্রাইভেট মোড চেক
        if get_bot_mode() == "private" and not is_admin(user_id):
            return await message.reply("🛠 **Bot is currently under maintenance / Private Mode.**\nPlease try again later.")

        welcome_text = (
            f"👋 Hello {message.from_user.first_name}!\n\n"
            f"🎬 **Advanced Video Stream & Download Bot** 🚀\n\n"
            f"Send me any direct video link or YouTube/Facebook link.\n"
            f"I will provide you with a high-speed streaming and download link!"
        )
        await message.reply(welcome_text)
    except Exception as e:
        print("❌ [ERROR in START COMMAND]:")
        traceback.print_exc()
        await message.reply("❌ **Database Connection Error!** Please check Render logs.")


# ==========================================
# 2. Public / Private Mode Toggle (Owner Only)
# ==========================================
@app.on_message(filters.command("mode") & filters.user(OWNER_ID))
async def toggle_mode(client, message: Message):
    if len(message.command) < 2 or message.command[1].lower() not in ["public", "private"]:
        return await message.reply("❌ Usage: `/mode public` or `/mode private`")
    
    new_mode = message.command[1].lower()
    set_bot_mode(new_mode)
    await message.reply(f"✅ Bot mode successfully changed to: **{new_mode.upper()}**")


# ==========================================
# 3. Admin Management (Owner Only)
# ==========================================
@app.on_message(filters.command("addadmin") & filters.user(OWNER_ID))
async def add_admin_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("❌ Usage: `/addadmin UserID`")
    add_admin(message.command[1])
    await message.reply(f"✅ User `{message.command[1]}` added as Admin.")

@app.on_message(filters.command("deladmin") & filters.user(OWNER_ID))
async def del_admin_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("❌ Usage: `/deladmin UserID`")
    remove_admin(message.command[1])
    await message.reply(f"✅ User `{message.command[1]}` removed from Admin list.")


# ==========================================
# 4. Broadcast & Revoke System (Admins Only)
# ==========================================
@app.on_message(filters.command("broadcast") & admin_filter & filters.reply)
async def broadcast_cmd(client, message: Message):
    users = get_all_users()
    if not users:
        return await message.reply("❌ No users found in database.")

    status = await message.reply("⏳ Broadcasting message...")
    broadcast_data = {}
    success, failed = 0, 0

    for user in users:
        try:
            sent_msg = await message.reply_to_message.copy(chat_id=int(user))
            broadcast_data[str(user)] = sent_msg.id
            success += 1
            await asyncio.sleep(0.1) 
        except Exception:
            failed += 1

    save_broadcast_data(broadcast_data)
    await status.edit_text(f"✅ **Broadcast Complete!**\n\nSuccess: {success}\nFailed: {failed}\n\n_Use /revokebroadcast to delete this message._")

@app.on_message(filters.command("revokebroadcast") & admin_filter)
async def revoke_broadcast_cmd(client, message: Message):
    data = get_last_broadcast()
    if not data:
        return await message.reply("❌ No active broadcast found.")

    status = await message.reply("⏳ Revoking broadcast...")
    deleted = 0

    for user_id, msg_id in data.items():
        try:
            await client.delete_messages(chat_id=int(user_id), message_ids=int(msg_id))
            deleted += 1
            await asyncio.sleep(0.05)
        except:
            pass

    clear_broadcast_data()
    await status.edit_text(f"🗑 **Broadcast Revoked!**\nSuccessfully deleted from {deleted} users.")


# ==========================================
# 6. Link Processing & Auto-Delete Logic
# ==========================================
@app.on_message(filters.text & filters.private)
async def handle_links(client, message: Message):
    # Ping বা Start কমান্ড হলে ইগনোর করবে
    if message.text.startswith("/"):
        return

    try:
        user_id = message.from_user.id
        if get_bot_mode() == "private" and not is_admin(user_id):
            return await message.reply("🛠 **Bot is in Private Mode.**", quote=True)

        url_match = re.search(r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))", message.text)
        
        if not url_match:
            msg = await message.reply("❌ Please send a valid Video Link.")
            await asyncio.sleep(10)
            await message.delete()
            await msg.delete()
            return

        url = url_match.group(0)
        status_msg = await message.reply("🔍 **Link detected!** Adding to processing queue...", quote=True)
        await add_task_to_queue(url, status_msg, user_id)

        try:
            await message.delete()
        except:
            pass
    except Exception as e:
        print("❌ [ERROR in LINK PROCESSING]:")
        traceback.print_exc()


# ==========================================
# 7. Main Application Runner
# ==========================================
async def main():
    print("Starting Main Bot...")
    await app.start()
    
    print("Starting Dummy Bots...")
    await start_dummy_bots()
    
    print("Starting Web Server...")
    await start_web_server(app)
    
    print("Starting Background Worker Queue...")
    asyncio.create_task(worker_loop(app))
    
    print("✅ All services are up and running smoothly!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

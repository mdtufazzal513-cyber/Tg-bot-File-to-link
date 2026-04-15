import os
import asyncio
import urllib.parse
import uuid
import yt_dlp
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import API_ID, API_HASH, DUMMY_BOT_TOKENS, BIN_CHANNEL_ID, WEB_URL
from database import save_file

# ==========================================
# Global Variables & Queue
# ==========================================
dummy_clients =[]
task_queue = asyncio.Queue()
bot_index = 0  # Round-Robin সিলেক্ট করার জন্য ইন্ডেক্স

# ==========================================
# Dummy Bots Initialization
# ==========================================
async def start_dummy_bots():
    global dummy_clients
    if not DUMMY_BOT_TOKENS:
        print("No dummy bots found. Main bot will handle everything.")
        return
    
    for i, token in enumerate(DUMMY_BOT_TOKENS):
        try:
            # প্রতিটা ডামি বটের জন্য আলাদা Pyrogram Client তৈরি করা হচ্ছে
            client = Client(f"dummy_{i}", api_id=API_ID, api_hash=API_HASH, bot_token=token)
            await client.start()
            dummy_clients.append(client)
        except Exception as e:
            print(f"Failed to start Dummy Bot {i}: {e}")
            
    print(f"{len(dummy_clients)} Dummy bots started successfully for Load Balancing!")

# ==========================================
# Video Downloading Logic (yt-dlp)
# ==========================================
def download_video_sync(url):
    """এটি ব্যাকগ্রাউন্ড থ্রেডে চলবে যেন Render সার্ভার ক্র্যাশ না করে"""
    
    # প্রথমে শুধু মেটাডেটা (নাম, সাইজ) বের করবো
    ydl_opts_info = {'format': 'best', 'quiet': True, 'noplaylist': True}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)
            file_name = info.get('title', 'video') + '.mp4'
            
            # স্পেশাল ক্যারেক্টার ক্লিন করা (যাতে লিংকে সমস্যা না হয়)
            valid_chars = "-_.() %s%s" % (import_string.ascii_letters if 'import_string' in locals() else 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', '0123456789')
            file_name = ''.join(c for c in file_name if c in valid_chars)
            
            # সাইজ চেক (১.৯ জিবি বা 2000000000 bytes লিমিট)
            filesize = info.get('filesize') or info.get('filesize_approx') or 0
            if filesize > 2000000000:
                return None, None, "❌ File is too large (Over 1.9GB). Limit exceeded."
    except Exception as e:
        return None, None, f"❌ Link extraction failed: {e}"

    # ডিরেক্টরি তৈরি করা
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
        
    unique_id = str(uuid.uuid4())[:8] # ইউনিক আইডি যেন ফাইলের নাম রিপ্লেস না হয়
    file_path = f"downloads/{unique_id}_{file_name}"
    
    # আসল ডাউনলোড শুরু
    ydl_opts_download = {
        'format': 'best',
        'outtmpl': file_path,
        'quiet': True,
        'noplaylist': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
            ydl.download([url])
        return file_path, file_name, None
    except Exception as e:
        return None, None, f"❌ Download failed: {e}"

# ==========================================
# Task Processor (Background Worker)
# ==========================================
async def process_task(dummy_client, main_client, url, status_msg, user_id):
    try:
        # ১. ডাউনলোড শুরু
        await status_msg.edit_text("⏳ **Downloading video...**\n_Please wait, extracting metadata and downloading..._")
        
        # Asyncio Thread-এ সিংক ফাংশন চালানো
        file_path, file_name, error_msg = await asyncio.to_thread(download_video_sync, url)
        
        if error_msg:
            await status_msg.edit_text(error_msg)
            return
            
        if not file_path or not os.path.exists(file_path):
            await status_msg.edit_text("❌ Failed to download the file.")
            return

        # ২. ডামি বট দিয়ে টেলিগ্রামে আপলোড
        await status_msg.edit_text("📤 **Uploading to Secure Cloud...**\n_Transferring file to Telegram Database..._")
        
        try:
            # ডামি বট ফাইলটি প্রাইভেট চ্যানেলে পাঠাবে
            uploaded_msg = await dummy_client.send_document(
                chat_id=BIN_CHANNEL_ID,
                document=file_path,
                caption=f"📁 {file_name}\n👤 Uploaded by: {user_id}"
            )
        except Exception as e:
            await status_msg.edit_text(f"❌ Upload failed: {e}")
            os.remove(file_path)
            return
            
        # ৩. আপলোড শেষ হলে ফাইল ডিলিট (Render স্টোরেজ ফাঁকা করার জন্য)
        if os.path.exists(file_path):
            os.remove(file_path)

        # ৪. ডাটাবেসে সেভ করা
        file_id = str(uuid.uuid4())[:12] # ফায়ারবেস ইউনিক Key
        save_file(file_id, file_name, uploaded_msg.id, url)

        # ৫. ইউজারকে সুন্দর বাটনসহ ফাইনাল লিংক দেওয়া
        encoded_name = urllib.parse.quote(file_name)
        stream_link = f"{WEB_URL}/stream/{encoded_name}"
        download_link = f"{WEB_URL}/stream/{encoded_name}?d=true"

        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Watch Online / Stream", url=stream_link)],
            [InlineKeyboardButton("📥 Direct Download", url=download_link)]
        ])

        # ফাইনাল মেসেজ দিয়ে স্ট্যাটাস মেসেজ আপডেট
        await status_msg.edit_text(
            f"✅ **Task Completed Successfully!**\n\n"
            f"📁 **File Name:** `{file_name}`\n\n"
            f"🔗 **Stream/Website Link:**\n`{stream_link}`\n\n"
            f"_Note: Click the buttons below or copy the link for your website._",
            reply_markup=buttons
        )

        # ১০ সেকেন্ড পর অরিজিনাল ইউজার লিংক ও অন্য মেসেজগুলো চাইলে মেইন বট থেকে অটো-ডিলিট করা যাবে
        # (অটো-ডিলিট লজিক আমরা main.py তে রাখবো)

    except Exception as e:
        await status_msg.edit_text(f"❌ An unexpected error occurred: {e}")


# ==========================================
# Worker Loop (Queue Consumer)
# ==========================================
async def worker_loop(main_client):
    global bot_index
    print("Worker loop started! Waiting for tasks...")
    
    while True:
        # টাস্ক কিউ থেকে কাজ নিবে
        task = await task_queue.get()
        url, status_msg, user_id = task
        
        # Round-Robin পদ্ধতিতে ডামি বট সিলেক্ট করা
        if dummy_clients:
            current_dummy = dummy_clients[bot_index % len(dummy_clients)]
            bot_index += 1
        else:
            current_dummy = main_client # ডামি বট না থাকলে মেইন বট আপলোড করবে
            
        # ব্যাকগ্রাউন্ডে প্রসেস শুরু করবে, যেন কিউ আটকে না থাকে
        asyncio.create_task(process_task(current_dummy, main_client, url, status_msg, user_id))
        
        # টাস্ক কমপ্লিট মার্ক করা
        task_queue.task_done()

# 외부 থেকে কিউতে টাস্ক যুক্ত করার ফাংশন
async def add_task_to_queue(url, status_msg, user_id):
    await task_queue.put((url, status_msg, user_id))
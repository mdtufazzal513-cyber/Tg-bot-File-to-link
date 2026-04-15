import os

# ==========================================
# Telegram API Credentials
# ==========================================
# my.telegram.org থেকে পাওয়া API ID এবং Hash
API_ID = int(os.environ.get("API_ID", "1234567"))
API_HASH = os.environ.get("API_HASH", "your_api_hash_here")

# ==========================================
# Bot Tokens & Load Balancing Config
# ==========================================
# মেইন বটের টোকেন (BotFather থেকে)
MAIN_BOT_TOKEN = os.environ.get("MAIN_BOT_TOKEN", "your_main_bot_token_here")

# ডামি বটের টোকেনগুলো (কমা দিয়ে একাধিক টোকেন Render-এ বসাতে পারবে)
# যেমন: "token1,token2,token3"
dummy_tokens_str = os.environ.get("DUMMY_BOT_TOKENS", "")
DUMMY_BOT_TOKENS =[t.strip() for t in dummy_tokens_str.split(",") if t.strip()]

# ==========================================
# Admin & Channel Config
# ==========================================
# তোমার (Owner) টেলিগ্রাম ইউজার আইডি
OWNER_ID = int(os.environ.get("OWNER_ID", "123456789"))

# প্রাইভেট টেলিগ্রাম চ্যানেলের আইডি (যেখানে ভিডিও আপলোড হবে)
# অবশ্যই -100 দিয়ে শুরু হতে হবে
BIN_CHANNEL_ID = int(os.environ.get("BIN_CHANNEL_ID", "-1001234567890"))

# ==========================================
# Firebase Configuration
# ==========================================
# ফায়ারবেসের ডাউনলোড করা JSON ফাইলের নাম
FIREBASE_CREDENTIALS_PATH = os.environ.get("FIREBASE_CREDENTIALS_PATH", "firebase.json")

# ফায়ারবেস রিয়েলটাইম ডাটাবেসের URL
FIREBASE_DATABASE_URL = os.environ.get("FIREBASE_DATABASE_URL", "https://your-project-id-default-rtdb.firebaseio.com/")

# ==========================================
# Web Server & Streaming Config
# ==========================================
# Render-এর জন্য ডিফল্ট পোর্ট
PORT = int(os.environ.get("PORT", "8080"))
BIND_ADDRESS = os.environ.get("BIND_ADDRESS", "0.0.0.0")

# Render-এ তোমার অ্যাপের ডোমেইন লিংক (লিংক জেনারেট করার জন্য)
# শেষে যেন স্লাশ (/) না থাকে, যেমন: https://my-bot.onrender.com
WEB_URL = os.environ.get("WEB_URL", "https://your-app-name.onrender.com")
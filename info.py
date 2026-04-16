import os

# ==========================================
# Telegram API Credentials
# ==========================================
# my.telegram.org থেকে পাওয়া API ID এবং Hash
API_ID = int(os.environ.get("API_ID", "33445387"))
API_HASH = os.environ.get("API_HASH", "5b1badf6d0f44c940a2263cef28d6689")

# ==========================================
# Bot Tokens & Load Balancing Config
# ==========================================
# মেইন বটের টোকেন (BotFather থেকে)
MAIN_BOT_TOKEN = os.environ.get("MAIN_BOT_TOKEN", "8668849495:AAHN9Lka5xPqQ5uHsh-z8Fg5bT1h0nm65QI")

# ডামি বটের টোকেনগুলো (কমা দিয়ে একাধিক টোকেন)
dummy_tokens_str = os.environ.get("DUMMY_BOT_TOKENS", "8703236011:AAEA3279_ak38POI_TAVK0b9tKZVe_0fBN8,8430400718:AAHpjC4R07SrHCO-6-J8ZMT2P8LcMarpm8k,8711817641:AAGYG1DACABDKYgxxSPrSudm4BJnXcw999U")
DUMMY_BOT_TOKENS =[t.strip() for t in dummy_tokens_str.split(",") if t.strip()]

# ==========================================
# Admin & Channel Config
# ==========================================
# তোমার (Owner) টেলিগ্রাম ইউজার আইডি
OWNER_ID = int(os.environ.get("OWNER_ID", "8672231989"))

# প্রাইভেট টেলিগ্রাম চ্যানেলের আইডি (যেখানে ভিডিও আপলোড হবে)
# অবশ্যই -100 দিয়ে শুরু হতে হবে
BIN_CHANNEL_ID = int(os.environ.get("BIN_CHANNEL_ID", "-1003984468691"))

# ==========================================
# Firebase Configuration
# ==========================================
# ফায়ারবেসের ডাউনলোড করা JSON ফাইলের নাম
FIREBASE_CREDENTIALS_PATH = os.environ.get("FIREBASE_CREDENTIALS_PATH", "firebase_key.json")

# ফায়ারবেস রিয়েলটাইম ডাটাবেসের URL
FIREBASE_DATABASE_URL = os.environ.get("FIREBASE_DATABASE_URL", "https://file-to-stream-default-rtdb.asia-southeast1.firebasedatabase.app/")

# ==========================================
# Web Server & Streaming Config
# ==========================================
# Render-এর জন্য ডিফল্ট পোর্ট
PORT = int(os.environ.get("PORT", "8080"))
BIND_ADDRESS = os.environ.get("BIND_ADDRESS", "0.0.0.0")

# Render-এ তোমার অ্যাপের ডোমেইন লিংক (লিংক জেনারেট করার জন্য)
# শেষে যেন স্লাশ (/) না থাকে, যেমন: https://my-bot.onrender.com
WEB_URL = os.environ.get("WEB_URL", "https://tg-bot-file-to-link.onrender.com")

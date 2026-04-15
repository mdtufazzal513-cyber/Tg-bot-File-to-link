import asyncio
import aiohttp
from aiohttp import web
import yt_dlp
import math
from database import get_file_by_name, mark_expired
from info import PORT, BIND_ADDRESS, BIN_CHANNEL_ID

# yt-dlp দিয়ে ডাইনামিক র-লিংক (Raw Link) বের করার ফাংশন
def extract_raw_link(url):
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'simulate': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('url', url)
    except Exception as e:
        return None

# লিংকটি এখনও জীবিত (Alive) আছে কিনা চেক করার ফাংশন
async def check_link_alive(url):
    try:
        async with aiohttp.ClientSession() as session:
            # শুধু হেড (HEAD) রিকোয়েস্ট পাঠাবো, যাতে ডেটা খরচ না হয়
            async with session.head(url, allow_redirects=True, timeout=5) as resp:
                return resp.status < 400
    except:
        return False

# ==========================================
# Web Server Request Handlers
# ==========================================

class WebServer:
    def __init__(self, bot_client):
        self.bot = bot_client # Pyrogram client for Telegram streaming
        self.app = web.Application()
        self.app.add_routes([
            web.get('/', self.handle_home),
            web.get('/stream/{file_name}', self.handle_stream)
        ])

    async def handle_home(self, request):
        return web.Response(text="Bot is Running and Web Server is Alive!")

    async def handle_stream(self, request):
        file_name = request.match_info['file_name']
        is_download = request.query.get('d') == 'true'

        # ডাটাবেস থেকে ফাইল ডিটেইলস বের করা
        file_data = get_file_by_name(file_name)

        if not file_data:
            return web.Response(text="404 Error: File not found in database.", status=404)

        if file_data.get('expired', False):
            return web.Response(
                text="❌ This link has expired.\n\nPlease contact Admin to report this issue.",
                status=403,
                content_type='text/html'
            )

        original_link = file_data['original_link']
        message_id = file_data['message_id']
        file_id = file_data['file_id']

        # ============================================
        # স্ট্রিমিং মোড (On-the-fly Redirect)
        # ============================================
        if not is_download:
            # ব্যাকগ্রাউন্ডে র-লিংক বের করা (Render ব্লক না হওয়ার জন্য)
            raw_url = await asyncio.to_thread(extract_raw_link, original_link)

            if raw_url:
                # লিংকটা জীবিত আছে কিনা চেক করা
                is_alive = await check_link_alive(raw_url)
                if is_alive:
                    # র-লিংকে 302 রিডাইরেক্ট করে দেওয়া (ব্যান্ডউইথ বাঁচবে)
                    raise web.HTTPFound(raw_url)
                else:
                    # লিংক ডেড হলে ডাটাবেসে Expired মার্ক করা
                    mark_expired(file_id)
                    return web.Response(
                        text="❌ The original server link is dead.\n\nPlease contact Admin to fix it.",
                        status=403,
                        content_type='text/html'
                    )

        # ============================================
        # ফলব্যাক / ডাইরেক্ট ডাউনলোড (Telegram Streaming)
        # ============================================
        # যদি ?d=true থাকে অথবা মূল লিংক রিডাইরেক্ট করা সম্ভব না হয়
        return await self.stream_from_telegram(request, message_id, file_name, is_download)

    async def stream_from_telegram(self, request, message_id, file_name, is_download):
        try:
            # প্রাইভেট চ্যানেল থেকে মেসেজ/ফাইল অবজেক্ট নিয়ে আসা
            message = await self.bot.get_messages(BIN_CHANNEL_ID, message_id)
            if not message or not message.video and not message.document:
                return web.Response(text="File not found in Telegram Channel.", status=404)

            file_size = message.video.file_size if message.video else message.document.file_size

            # Range Request (206 Partial Content) হ্যান্ডেল করা
            headers = request.headers
            range_header = headers.get('Range', '')
            offset = 0
            limit = file_size - 1

            if range_header:
                # Example: bytes=0-1024
                range_match = range_header.replace('bytes=', '').split('-')
                offset = int(range_match[0]) if range_match[0] else 0
                limit = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1

            content_length = (limit - offset) + 1

            # Headers সেট করা
            response_headers = {
                'Accept-Ranges': 'bytes',
                'Content-Range': f'bytes {offset}-{limit}/{file_size}',
                'Content-Length': str(content_length),
                'Content-Type': 'video/mp4' if not is_download else 'application/octet-stream'
            }

            if is_download:
                response_headers['Content-Disposition'] = f'attachment; filename="{file_name}"'
            else:
                response_headers['Content-Disposition'] = f'inline; filename="{file_name}"'

            # aiohttp Stream Response রেডি করা
            response = web.StreamResponse(
                status=206 if range_header else 200,
                headers=response_headers
            )
            await response.prepare(request)

            # Pyrogram দিয়ে Chunk বাই Chunk ফাইল ডাউনলোড ও স্ট্রিম করা
            # Render এর র‍্যাম বাঁচানোর জন্য 1MB এর চাঙ্ক (Chunk) ব্যবহার করবো
            chunk_size = 1024 * 1024 
            
            async for chunk in self.bot.stream_media(message, limit=content_length, offset=offset):
                try:
                    await response.write(chunk)
                except (ConnectionResetError, aiohttp.ClientPayloadError):
                    break # ইউজার প্লেয়ার ক্লোজ করে দিলে স্ট্রিম থামিয়ে দিবে

            return response

        except Exception as e:
            print(f"Streaming Error: {e}")
            return web.Response(text="Internal Server Error during streaming.", status=500)

# ওয়েব সার্ভার স্টার্ট করার ফাংশন
async def start_web_server(bot_client):
    server = WebServer(bot_client)
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, BIND_ADDRESS, PORT)
    await site.start()
    print(f"Web server is running on port {PORT}")
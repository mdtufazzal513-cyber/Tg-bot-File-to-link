import firebase_admin
from firebase_admin import credentials, db
from info import FIREBASE_CREDENTIALS_PATH, FIREBASE_DATABASE_URL, OWNER_ID

# ==========================================
# Firebase Initialization
# ==========================================
def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_DATABASE_URL
        })

# অ্যাপ রান হওয়ার সাথে সাথেই ফায়ারবেস কানেক্ট হবে
init_firebase()


# ==========================================
# Bot Mode (Public / Private)
# ==========================================
def get_bot_mode():
    ref = db.reference("bot_config/mode")
    mode = ref.get()
    return mode if mode else "public"  # ডিফল্ট মোড public

def set_bot_mode(mode_name):
    ref = db.reference("bot_config/mode")
    ref.set(mode_name)


# ==========================================
# Admin Management (Dynamic Admins)
# ==========================================
def is_admin(user_id):
    if int(user_id) == OWNER_ID:
        return True
    ref = db.reference(f"bot_config/admins/{user_id}")
    return bool(ref.get())

def add_admin(user_id):
    ref = db.reference(f"bot_config/admins/{user_id}")
    ref.set(True)

def remove_admin(user_id):
    ref = db.reference(f"bot_config/admins/{user_id}")
    ref.delete()


# ==========================================
# User Management (For Broadcast)
# ==========================================
def add_user(user_id):
    ref = db.reference(f"users/{user_id}")
    if not ref.get():
        ref.set(True)

def get_all_users():
    ref = db.reference("users")
    users = ref.get()
    return list(users.keys()) if users else[]


# ==========================================
# File & Link Management
# ==========================================
def save_file(file_id, file_name, message_id, original_link):
    ref = db.reference(f"files/{file_id}")
    ref.set({
        "file_name": file_name,
        "message_id": message_id,
        "original_link": original_link,
        "expired": False
    })

def get_file_by_name(file_name):
    """ফাইলের নাম দিয়ে ডেটাবেস থেকে ভিডিওর ডিটেইলস খুঁজে বের করবে"""
    ref = db.reference("files")
    # Firebase query to search by child 'file_name'
    results = ref.order_by_child("file_name").equal_to(file_name).get()
    if results:
        for file_id, data in results.items():
            data['file_id'] = file_id # রিটার্ন করার সময় আইডিটাও দিয়ে দিলাম
            return data
    return None

def mark_expired(file_id):
    ref = db.reference(f"files/{file_id}/expired")
    ref.set(True)

def get_expired_files():
    ref = db.reference("files")
    results = ref.order_by_child("expired").equal_to(True).get()
    return results if results else {}

def update_expired_link(file_id, new_original_link):
    ref = db.reference(f"files/{file_id}")
    ref.update({
        "original_link": new_original_link,
        "expired": False
    })


# ==========================================
# Broadcast Revoke System (অটো ডিলিট)
# ==========================================
def save_broadcast_data(broadcast_dict):
    """
    broadcast_dict এর ফরম্যাট হবে: {"user_id_1": "message_id_1", "user_id_2": "message_id_2"}
    """
    ref = db.reference("broadcast/last_messages")
    ref.set(broadcast_dict)

def get_last_broadcast():
    ref = db.reference("broadcast/last_messages")
    data = ref.get()
    return data if data else {}

def clear_broadcast_data():
    ref = db.reference("broadcast/last_messages")
    ref.delete()
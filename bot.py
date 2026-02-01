import requests, json, time, os, uuid, hashlib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

BOT_TOKEN = "6253935996:AAGZ5k8SsxBt_BXyYe0eC0XOnw1tWRIpINg"
ALLOWED_USERS = [1361430088]  # ايديك فقط

# ================= API CLASS (بدون تغيير) =================
class PixWithAI:
    def __init__(self):
        self.base_url = "https://api.pixwith.ai/api"
        self.session_token = hashlib.md5(f"{uuid.uuid4()}{int(time.time()*1000)}".encode()).hexdigest() + "0"
        self.headers = {
            'authority': 'api.pixwith.ai',
            'accept': '*/*',
            'origin': 'https://pixwith.ai',
            'referer': 'https://pixwith.ai/',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K)',
            'x-session-token': self.session_token
        }

    def _opts(self, url):
        try: requests.options(url, headers={'origin':'https://pixwith.ai','referer':'https://pixwith.ai/'})
        except: pass

    def get_upload_url(self, file_path):
        r = requests.post(f"{self.base_url}/chats/pre_url", headers=self.headers,
            json={"image_name": os.path.basename(file_path), "content_type": "image/jpeg"})
        return r.json()

    def upload_image(self, data, file_path):
        s3 = data.get("data", {}).get("url", data)
        url, fields = s3.get("url"), s3.get("fields", {})
        files = [(k, (None, str(v))) for k, v in fields.items()]
        with open(file_path, 'rb') as f:
            files.append(('file', (os.path.basename(file_path), f.read(), 'image/jpeg')))
        r = requests.post(url, files=files)
        return fields.get("key") if r.status_code in [200,204] else None

    def create_video(self, image_key, prompt):
        return requests.post(f"{self.base_url}/items/create", headers=self.headers, json={
            "images":{"image1":image_key},
            "prompt":prompt,
            "options":{"prompt_optimization":True,"num_outputs":1,"aspect_ratio":"16:9",
                       "resolution":"480p","duration":4,"sound":True},
            "model_id":"3-38"
        }).json()

    def get_history(self):
        return requests.post(f"{self.base_url}/items/history", headers=self.headers,
            json={"tool_type":"3","page":0,"page_size":12}).json()

# ================= BOT =================
sessions = {}

def is_allowed(uid): 
    return uid in ALLOWED_USERS

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 إنشاء فيديو", callback_data="make")],
        [InlineKeyboardButton("♻️ إعادة تعيين", callback_data="reset")],
        [InlineKeyboardButton("ℹ️ مساعدة", callback_data="help")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_allowed(uid):
        await update.message.reply_text("🚫 هذا البوت خاص")
        return
    await update.message.reply_text("👋 أهلاً بك\nاختر من الأزرار 👇", reply_markup=main_menu())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if not is_allowed(uid):
        await query.message.reply_text("🚫 غير مصرح")
        return

    if query.data == "make":
        sessions[uid] = {"step": "image", "api": PixWithAI()}
        await query.message.reply_text("📷 أرسل الصورة")

    elif query.data == "reset":
        sessions.pop(uid, None)
        await query.message.reply_text("♻️ تم إعادة التعيين", reply_markup=main_menu())

    elif query.data == "help":
        await query.message.reply_text("1️⃣ اضغط إنشاء فيديو\n2️⃣ أرسل صورة\n3️⃣ أرسل البرومنت")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in sessions: return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    path = f"{uid}.jpg"
    await file.download_to_drive(path)

    sessions[uid]["image"] = path
    sessions[uid]["step"] = "prompt"
    await update.message.reply_text("✍️ أرسل البرومنت")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in sessions or sessions[uid]["step"] != "prompt":
        return

    api = sessions[uid]["api"]
    image = sessions[uid]["image"]
    prompt = update.message.text

    await update.message.reply_text("⬆️ جاري الرفع...")
    up = api.get_upload_url(image)
    key = api.upload_image(up, image)

    await update.message.reply_text("🎬 المعالجة بدأت...")
    api.create_video(key, prompt)

    for _ in range(30):
        time.sleep(10)
        h = api.get_history()
        items = h.get("data", {}).get("items", [])
        if items and items[0].get("status") == 2:
            for r in items[0]["result_urls"]:
                if not r.get("is_input", True):
                    await update.message.reply_text(f"✅ تم\n{r['hd']}")
                    return

async def run():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    run()



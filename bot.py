import requests, json, time, os, uuid, hashlib, asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# إعداد السجلات لمراقبة العمليات
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- جلب البيانات مع تنظيفها من الفراغات ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
raw_admin = os.getenv("ADMIN_ID", "0").strip()

# تحويل آمن للأيدي
try:
    ADMIN_ID = int(raw_admin)
except ValueError:
    ADMIN_ID = 0

ALLOWED_USERS = [ADMIN_ID]

# ================= API CLASS =================
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

# ================= BOT FUNCTIONS =================
sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        await update.message.reply_text("🚫 هذا البوت خاص بالمطور فقط")
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 إنشاء فيديو", callback_data="make")],
        [InlineKeyboardButton("ℹ️ مساعدة", callback_data="help")]
    ])
    await update.message.reply_text("👋 أهلاً بك في بوت PixWith\nاختر من الأسفل 👇", reply_markup=keyboard)

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "make":
        sessions[query.from_user.id] = {"step": "image", "api": PixWithAI()}
        await query.message.reply_text("📷 أرسل الصورة الآن")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in sessions: return
    
    photo = update.message.photo[-1]
    file = await photo.get_file()
    path = f"{uid}.jpg"
    await file.download_to_drive(path)
    
    sessions[uid].update({"image": path, "step": "prompt"})
    await update.message.reply_text("✍️ الآن أرسل الوصف (Prompt) للفيديو")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in sessions or sessions[uid].get("step") != "prompt": return

    prompt = update.message.text
    api, image = sessions[uid]["api"], sessions[uid]["image"]
    
    msg = await update.message.reply_text("⬆️ جاري المعالجة... قد يستغرق الأمر دقيقة")
    
    try:
        up = api.get_upload_url(image)
        key = api.upload_image(up, image)
        api.create_video(key, prompt)

        for _ in range(15):
            await asyncio.sleep(10)
            h = api.get_history()
            items = h.get("data", {}).get("items", [])
            if items and items[0].get("status") == 2:
                url = items[0]["result_urls"][0]["hd"]
                await update.message.reply_video(video=url, caption="✅ تم صنع الفيديو بنجاح!")
                if os.path.exists(image): os.remove(image)
                return
        await msg.edit_text("⚠️ استغرقت المعالجة وقتاً طويلاً.")
    except Exception as e:
        await msg.edit_text(f"❌ حدث خطأ: {str(e)}")

def main():
    if not BOT_TOKEN or BOT_TOKEN == "":
        logging.error("No BOT_TOKEN found!")
        return
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("--- البوت يعمل الآن بنجاح ---")
    app.run_polling()

if __name__ == "__main__":
    main()

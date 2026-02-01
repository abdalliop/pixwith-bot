import requests, json, time, os, uuid, hashlib, asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# إعداد السجلات لمراقبة الأخطاء
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
raw_admin = os.getenv("ADMIN_ID", "0").strip()

try:
    ADMIN_ID = int(raw_admin)
except ValueError:
    ADMIN_ID = 0

# القائمة الكاملة والمحدثة للنماذج
AI_MODELS = {
    "wan_26": {"name": "🎬 WAN 2.6", "id": "3-36"},
    "wan_22": {"name": "🎬 WAN 2.2", "id": "3-10"},
    "veo_31": {"name": "🎥 Veo 3.1 (Google)", "id": "3-11"},
    "sora_2p": {"name": "🌟 Sora 2 Pro", "id": "3-18"},
    "sora_2": {"name": "🌟 Sora 2", "id": "3-13"},
    "kling_o1": {"name": "🔥 Kling O1", "id": "3-35"},
    "kling_26": {"name": "🔥 Kling 2.6", "id": "3-33"},
    "kling_1": {"name": "🔥 Kling 2.5", "id": "3-1"},
    "seed_15": {"name": "💎 Seedance 1.5 Pro", "id": "3-38"},
    "runway": {"name": "🚀 Runway Gen-4", "id": "3-25"},
    "luma": {"name": "🌈 Luma Ray 2", "id": "3-4"},
    "hailuo": {"name": "🌊 Hailuo 2.3", "id": "3-17"},
    "pixverse": {"name": "🔮 Pixverse V5", "id": "3-27"},
    "pika": {"name": "🦊 Pika 2.2", "id": "3-26"}
}

class PixWithAI:
    def __init__(self):
        self.base_url = "https://api.pixwith.ai/api"
        self.session_token = hashlib.md5(f"{uuid.uuid4()}{int(time.time()*1000)}".encode()).hexdigest() + "0"
        self.headers = {
            'authority': 'api.pixwith.ai',
            'x-session-token': self.session_token,
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def get_upload_url(self, file_path):
        try:
            r = requests.post(f"{self.base_url}/chats/pre_url", headers=self.headers,
                json={"image_name": os.path.basename(file_path), "content_type": "image/jpeg"}, timeout=15)
            return r.json()
        except: return None

    def upload_image(self, data, file_path):
        try:
            s3 = data.get("data", {}).get("url", data)
            url, fields = s3.get("url"), s3.get("fields", {})
            files = [(k, (None, str(v))) for k, v in fields.items()]
            with open(file_path, 'rb') as f:
                files.append(('file', (os.path.basename(file_path), f.read(), 'image/jpeg')))
            r = requests.post(url, files=files, timeout=30)
            return fields.get("key") if r.status_code in [200, 204] else None
        except: return None

    def create_video(self, image_key, prompt, model_id):
        try:
            return requests.post(f"{self.base_url}/items/create", headers=self.headers, json={
                "images": {"image1": image_key},
                "prompt": prompt,
                "options": {"prompt_optimization": True, "num_outputs": 1, "aspect_ratio": "16:9",
                           "resolution": "480p", "duration": 4, "sound": True},
                "model_id": model_id
            }, timeout=15).json()
        except: return None

    def get_history(self):
        try:
            return requests.post(f"{self.base_url}/items/history", headers=self.headers,
                json={"tool_type": "3", "page": 0, "page_size": 5}, timeout=15).json()
        except: return {}

sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 ابدأ الآن", callback_data="make")]])
    await update.message.reply_text("مرحباً بك! اختر نموذج الذكاء الاصطناعي لتحريك صورك.", reply_markup=kb)

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if query.data == "make":
        btns = []
        keys = list(AI_MODELS.keys())
        for i in range(0, len(keys), 2):
            row = [InlineKeyboardButton(AI_MODELS[keys[i]]["name"], callback_data=f"sel_{keys[i]}")]
            if i+1 < len(keys):
                row.append(InlineKeyboardButton(AI_MODELS[keys[i+1]]["name"], callback_data=f"sel_{keys[i+1]}"))
            btns.append(row)
        await query.message.edit_text("🤖 اختر الموديل:", reply_markup=InlineKeyboardMarkup(btns))

    elif query.data.startswith("sel_"):
        m_key = query.data.replace("sel_", "")
        model = AI_MODELS[m_key]
        sessions[uid] = {"step": "image", "api": PixWithAI(), "model_id": model["id"], "model_name": model["name"]}
        await query.message.edit_text(f"✅ تم اختيار {model['name']}\n📷 أرسل الصورة الآن...")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in sessions or sessions[uid]["step"] != "image": return
    file = await update.message.photo[-1].get_file()
    path = f"img_{uid}.jpg"
    await file.download_to_drive(path)
    sessions[uid].update({"image": path, "step": "prompt"})
    await update.message.reply_text("✍️ أرسل وصف الفيديو (Prompt) بالإنجليزية:")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in sessions or sessions[uid]["step"] != "prompt": return

    prompt = update.message.text
    s = sessions[uid]
    msg = await update.message.reply_text(f"⏳ جاري التوليد بواسطة {s['model_name']}...")

    try:
        up = s["api"].get_upload_url(s["image"])
        key = s["api"].upload_image(up, s["image"])
        if not key: raise Exception("فشل الرفع")
        
        s["api"].create_video(key, prompt, s["model_id"])

        for _ in range(25): # انتظار حتى 250 ثانية
            await asyncio.sleep(10)
            h = s["api"].get_history()
            items = h.get("data", {}).get("items", [])
            
            if items and items[0].get("status") == 2:
                res = items[0].get("result_urls", [{}])[0]
                video_url = res.get("hd") or res.get("url")
                
                # التأكد من أنه فيديو MP4 وليس صورة JPG
                if video_url and ".mp4" in video_url.lower():
                    await update.message.reply_video(video=video_url, caption=f"✅ النموذج: {s['model_name']}")
                    await msg.delete()
                    if os.path.exists(s["image"]): os.remove(s["image"])
                    del sessions[uid]
                    return
        await msg.edit_text("⚠️ استغرق الطلب وقتاً طويلاً.")
    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {str(e)}")
    finally:
        if uid in sessions and os.path.exists(sessions[uid]["image"]): os.remove(sessions[uid]["image"])

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()

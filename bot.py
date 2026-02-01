import os, time, httpx, asyncio, logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# إعداد السجلات لمراقبة العمل
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# جلب المتغيرات من Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# اختيار نموذج قوي لتحريك الصور (I2VGen-XL من شركة Alibaba)
MODEL_URL = "https://api-inference.huggingface.co/models/ali-vilab/i2vgen-xl"

async def generate_video_hf(image_path, prompt):
    """هذه الدالة ترسل الصورة لـ Hugging Face وتعيد الفيديو"""
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    with open(image_path, "rb") as f:
        img_data = f.read()
    
    async with httpx.AsyncClient() as client:
        # إرسال الطلب (Hugging Face سيعالج الصورة والبرومبت)
        response = await client.post(
            MODEL_URL, 
            headers=headers, 
            content=img_data, 
            timeout=300 # وقت انتظار طويل لأن الفيديو يحتاج معالجة
        )
        
        if response.status_code == 200:
            video_name = f"video_{int(time.time())}.mp4"
            with open(video_name, "wb") as v_file:
                v_file.write(response.content)
            return video_name
        else:
            logging.error(f"خطأ من Hugging Face: {response.status_code}")
            return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("✨ أهلاً بك في نظام Hugging Face المتطور!\n\nارسل لي الصورة التي تريد تحويلها لفيديو.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    file = await update.message.photo[-1].get_file()
    path = f"img_{update.effective_user.id}.jpg"
    await file.download_to_drive(path)
    
    context.user_data['image_path'] = path
    await update.message.reply_text("📸 وصلت الصورة.. الآن أرسل وصف التحريك (بالإنجليزي):")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or 'image_path' not in context.user_data:
        return

    prompt = update.message.text
    image_path = context.user_data['image_path']
    
    msg = await update.message.reply_text("🚀 جاري إرسال الطلب لـ Hugging Face.. انتظر قليلاً.")

    try:
        video_file = await generate_video_hf(image_path, prompt)
        
        if video_file:
            await update.message.reply_video(video=open(video_file, 'rb'), caption="✅ تم التوليد بواسطة I2VGen-XL")
            os.remove(video_file)
        else:
            await msg.edit_text("❌ فشل التوليد. قد يكون النموذج مشغولاً حالياً، جرب لاحقاً.")
            
    except Exception as e:
        await msg.edit_text(f"⚠️ حدث خطأ: {str(e)}")
    finally:
        if os.path.exists(image_path): os.remove(image_path)
        context.user_data.clear()

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("البوت يعمل الآن بنظام Hugging Face...")
    app.run_polling()

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

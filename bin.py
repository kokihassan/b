
import os
import re
import sqlite3
import asyncio
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ================= الإعدادات =================
BOT_TOKEN = "1910891378:AAHBvScDJ9O3wECe_Ea_Dt4wr7X7rssWZno"
ADMIN_ID = 1116526399

# ================= دوال المعالجة =================
def process_file(user_id, path):
    db_path = f"data_{user_id}.db"
    if os.path.exists(db_path): os.remove(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('CREATE TABLE counts (val TEXT, line TEXT)')
    
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        data = []
        for line in f:
            line = line.strip()
            if not line: continue
            first = re.split(r'[/|:\s,;]+', line)[0]
            data.append((first, line))
            if len(data) >= 50000:
                cur.executemany('INSERT INTO counts VALUES (?, ?)', data)
                data = []
        cur.executemany('INSERT INTO counts VALUES (?, ?)', data)
    
    cur.execute('CREATE INDEX idx_val ON counts(val)')
    conn.commit()
    conn.close()
    if os.path.exists(path): os.remove(path)

# ================= الهاندلرز =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("📂 حالة ملفي", callback_data="status"), 
           InlineKeyboardButton("🗑️ حذف ملفي", callback_data="delete")]]
    await update.message.reply_text("👑 أهلاً بك. أرسل ملفك (.txt) للبدء.", reply_markup=InlineKeyboardMarkup(kb))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    db = f"data_{uid}.db"
    if query.data == "status":
        txt = "✅ ملفك نشط وجاهز." if os.path.exists(db) else "❌ لا يوجد ملف مرفوع."
        await query.answer(txt, show_alert=True)
    elif query.data == "delete":
        if os.path.exists(db): os.remove(db)
        await query.answer("🗑️ تم حذف ملفك.", show_alert=True)

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if update.message.document:
        msg = await update.message.reply_text("⏳ جاري التحميل المباشر من تليجرام...")
        try:
            # استخدام محرك البوت الرسمي للتحميل (أكثر استقراراً)
            file = await context.bot.get_file(update.message.document.file_id)
            path = f"temp_{uid}.txt"
            await file.download_to_drive(custom_path=path)
            
            if os.path.exists(path):
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, process_file, uid, path)
                await msg.edit_text("✅ تم تفعيل الملف بنجاح.")
            else:
                raise Exception("فشل تنزيل الملف محلياً.")
        except Exception:
            await context.bot.send_message(ADMIN_ID, f"⚠️ خطأ: {traceback.format_exc()}")
            await msg.edit_text("❌ حدث خطأ أثناء تحميل الملف.")
    
    elif update.message.text and update.message.text.isdigit():
        db = f"data_{uid}.db"
        if not os.path.exists(db):
            await update.message.reply_text("❌ ارفع ملفك أولاً!")
            return
        
        conn = sqlite3.connect(db)
        res = conn.cursor().execute('SELECT line FROM counts WHERE val LIKE ?', (f"{update.message.text}%",)).fetchall()
        conn.close()
        
        if res:
            out = "\n".join([r[0] for r in res[:20]])
            await update.message.reply_text(f"🔍 النتائج:\n{out}")
        else:
            await update.message.reply_text("❌ لم يتم العثور على نتائج.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL, handle_msg))
    print("البوت يعمل الآن...")
    app.run_polling()

if __name__ == '__main__':
    main()

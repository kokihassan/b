import os
import re
import sqlite3
import asyncio
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

BOT_TOKEN = "1910891378:AAHBvScDJ9O3wECe_Ea_Dt4wr7X7rssWZno"
ADMIN_ID = 1116526399

# دالة الفهرسة (تأخذ المسار مباشرة)
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
            first = line.split('|')[0]
            data.append((first, line))
            if len(data) >= 50000:
                cur.executemany('INSERT INTO counts VALUES (?, ?)', data)
                data = []
        cur.executemany('INSERT INTO counts VALUES (?, ?)', data)
    cur.execute('CREATE INDEX idx_val ON counts(val)')
    conn.commit()
    conn.close()
    if os.path.exists(path): os.remove(path)

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    if update.message.document:
        msg = await update.message.reply_text("⏳ جاري التحميل بوضع التدفق الثابت...")
        try:
            # تحميل الملف بأكثر طريقة آمنة
            file = await context.bot.get_file(update.message.document.file_id)
            path = f"temp_{uid}.txt"
            # استخدام download_to_drive وهو الأفضل حالياً
            await file.download_to_drive(custom_path=path)
            
            # الفهرسة في Thread منفصل لعدم تجميد البوت
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, process_file, uid, path)
            await msg.edit_text("✅ تم فهرسة الملف بنجاح.")
        except Exception as e:
            await msg.edit_text(f"❌ فشل التحميل: {str(e)}")
    
    elif update.message.text:
        # (نفس كود الفلترة السابق)
        bins = [b.strip() for b in update.message.text.split('\n') if b.strip()]
        if not bins or not os.path.exists(f"data_{uid}.db"): return
        
        conn = sqlite3.connect(f"data_{uid}.db")
        cursor = conn.cursor()
        query = " OR ".join(["val LIKE ?"] * len(bins))
        cursor.execute(f'SELECT line FROM counts WHERE {query}', [f"{b}%" for b in bins])
        res = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if res:
            f_name = f"Filtered_{uid}.txt"
            with open(f_name, 'w', encoding='utf-8') as f: f.write('\n'.join(res))
            await update.message.reply_document(open(f_name, 'rb'), caption=f"✅ النتائج: {len(res)}")
            os.remove(f_name)
        else:
            await update.message.reply_text("❌ لا يوجد تطابقات.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, handle_msg))
    app.run_polling()

if __name__ == '__main__':
    main()


import os
import re
import sqlite3
import asyncio
from telethon import TelegramClient
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ============================================================
# ⚙️ الإعدادات الأساسية
# ============================================================
BOT_TOKEN = "1910891378:AAHBvScDJ9O3wECe_Ea_Dt4wr7X7rssWZno"      # توكن البوت من BotFather
ADMIN_ID = 1116526399               # الآي دي الرقمي لحسابك الشخصي
ADMIN_USERNAME = "ARLOUefg"      # يوزر حسابك الشخصي بدون @

# بيانات الـ API لكسر حماية الـ 20 ميجا من تليجرام
API_ID = 1488415                           # الـ api_id (رقم)
API_HASH = 'bcbd5e3700a2ef6bbf90b6425437f69d'           # الـ api_hash (نص)

USERS_FILE_PATH = "allowed_users.txt"

# ============================================================
# 👥 دالات إدارة المستخدمين
# ============================================================
def get_allowed_users():
    if not os.path.exists(USERS_FILE_PATH): return set()
    with open(USERS_FILE_PATH, 'r') as f:
        return set(int(line.strip()) for line in f if line.strip().isdigit())

def allow_user(user_id):
    allowed = get_allowed_users()
    allowed.add(int(user_id))
    with open(USERS_FILE_PATH, 'w') as f:
        for uid in allowed: f.write(f"{uid}\n")

def block_user(user_id):
    allowed = get_allowed_users()
    allowed.discard(int(user_id))
    with open(USERS_FILE_PATH, 'w') as f:
        for uid in allowed: f.write(f"{uid}\n")

def extract_first_column(line):
    parts = re.split(r'[/|:\s]+', line.strip())
    return parts[0] if parts else None

# ============================================================
# ⚡ دالة تحويل الفهرسة المستقلة لكل مستخدم (Dynamic DB per User)
# ============================================================
def process_and_index_user_file(user_id, txt_path):
    db_path = f"data_{user_id}.db"
    print(f"⚡ جاري إنشاء قاعدة بيانات مستقلة للمستخدم {user_id}...")
    
    # لو عنده قاعدة بيانات قديمة بنمسحها عشان نحدث بالجديدة
    if os.path.exists(db_path):
        os.remove(db_path)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS counts (first_col TEXT, full_line TEXT)')
    
    buffer = []
    with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line_str = line.strip()
            if not line_str: continue
            first_col = extract_first_column(line_str)
            if first_col:
                buffer.append((first_col, line_str))
            if len(buffer) >= 100000:
                cursor.executemany('INSERT INTO counts VALUES (?, ?)', buffer)
                buffer = []
                
    if buffer:
        cursor.executemany('INSERT INTO counts VALUES (?, ?)', buffer)
        
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_first_col ON counts(first_col)')
    conn.commit()
    conn.close()
    
    # مسح ملف الـ txt لتوفير مساحة السيرفر
    if os.path.exists(txt_path):
        os.remove(txt_path)
    print(f"✅ اكتمل إنشاء قاعدة البيانات للمستخدم {user_id}")

# ============================================================
# 🤖 منطق عمل البوت ولوحة التحكم
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        keyboard = [
            ['📊 إحصائيات البوت', '👥 إدارة المستخدمين']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("👑 أهلاً بك يا زعيم في لوحة التحكم الشاملة.", reply_markup=reply_markup)
        return

    allowed_users = get_allowed_users()
    if user_id not in allowed_users:
        admin_link = f"https://t.me/{ADMIN_USERNAME}"
        keyboard = [[InlineKeyboardButton("📩 تواصل مع الآدمن للتفعيل", url=admin_link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"🚫 **حسابك غير مفعل.**\nالآي دي الخاص بك: `{user_id}`", parse_mode="Markdown", reply_markup=reply_markup)
        
        # إشعار للآدمن
        username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون يوزر"
        admin_keyboard = [[InlineKeyboardButton("✅ تفعيل فوراً", callback_data=f"activate_{user_id}")]]
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 **محاولة دخول:**\n👤 الاسم: {update.effective_user.first_name}\n🆔 الـ ID: `{user_id}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(admin_keyboard))
        return

    await update.message.reply_text("🎯 أهلاً بك! البوت متاح لك بالكامل.\n\n"
                                   "📥 **لرفع الداتا الخاصة بك:** ارفع ملف الـ `.txt` (حتى لو 600 ميجا) هنا مباشرة في الشات.\n"
                                   "🔍 **لفحص الأرقام:** بعد اكتمال رفع ملفك، ارسل لي قائمة الأرقام (كل رقم في سطر).")

async def handle_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID: return

    text = update.message.text
    if text == '📊 إحصائيات البوت':
        allowed = get_allowed_users()
        # حساب كم مستخدم رفع داتا فعلياً على السيرفر
        db_files = [f for f in os.listdir('.') if f.startswith('data_') and f.endswith('.db')]
        await update.message.reply_text(f"📊 **إحصائيات السيرفر:**\n\n"
                                       f"👥 عدد المشتركين المفعلين: {len(allowed)}\n"
                                       f"🗂️ عدد قواعد البيانات النشطة حالياً: {len(db_files)} قاعدة.")
            
    elif text == '👥 إدارة المستخدمين':
        allowed = get_allowed_users()
        users_list = "\n".join([f"`{uid}`" for uid in allowed]) if allowed else "لا يوجد مستخدمين مفعليين حالياً."
        await update.message.reply_text(f"👥 **المستخدمين المفعلين:**\n{users_list}\n\n➕ لتفعيل: `تفعيل 12345`\n➖ لتعطيل: `تعطيل 12345`", parse_mode="Markdown")

async def handle_admin_text_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID: return
    text = update.message.text
    if text.startswith("تفعيل "):
        target_id = text.split(" ")[1]
        if target_id.isdigit():
            allow_user(target_id)
            await update.message.reply_text(f"✅ تم تفعيل `{target_id}`.")
    elif text.startswith("تعطيل "):
        target_id = text.split(" ")[1]
        if target_id.isdigit():
            block_user(target_id)
            # مسح قاعدة بياناته لو اتعطل لتوفير مساحة السيرفر
            db_path = f"data_{target_id}.db"
            if os.path.exists(db_path): os.remove(db_path)
            await update.message.reply_text(f"❌ تم تعطيل `{target_id}` ومسح بياناته.")

async def inline_buttons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("activate_"):
        target_id = query.data.split("_")[1]
        allow_user(target_id)
        await query.edit_message_text(text=f"✅ تم تفعيل الـ ID: `{target_id}` بنجاح.", parse_mode="Markdown")

# ============================================================
# 📥 استقبال وتحميل الملفات الضخمة من أي مستخدم مفعّل
# ============================================================
async def handle_large_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    allowed_users = get_allowed_users()
    
    # التحقق من الصلاحية (آدمن أو مستخدم مفعل)
    if user_id != ADMIN_ID and user_id not in allowed_users: return 
    
    doc = update.message.document
    if doc.file_name.endswith('.txt'):
        status_msg = await update.message.reply_text("⏳ جاري تحميل ملفك الضخم مباشرة إلى السيرفر وكسر الحماية... ثواني معايا.")
        
        try:
            # اسم مؤقت لملف الـ txt الخاص باليوزر
            temp_txt_path = f"temp_{user_id}.txt"
            
            client = TelegramClient('downloader_session', API_ID, API_HASH)
            await client.start()
            
            msg_id = update.message.message_id
            chat_id = update.effective_chat.id
            
            # تحميل الملف الخاص باليوزر ده بالذات
            await client.download_media(await client.get_messages(chat_id, ids=msg_id), file=temp_txt_path)
            await client.disconnect()
            
            await status_msg.edit_text("📥 تم اكتمال التحميل! جاري الآن بناء وتكشيف قاعدة بياناتك الخاصة لتصبح سريعة طلقة...")
            
            # معالجة الملف وعمل داتابيز منفصلة باسم اليوزر
            process_and_index_user_file(user_id, temp_txt_path)
            
            await status_msg.edit_text("✅ تم تحديث ملفك الخاص بنجاح! البوت الآن جاهز لفحص أرقامك في الداتا بتاعتك وبأعلى سرعة.")
            
        except Exception as e:
            await status_msg.edit_text(f"❌ حدث خطأ أثناء التحميل: {str(e)}")

# ============================================================
# 🔍 فحص الأرقام في قاعدة البيانات الخاصة بكل مستخدم
# ============================================================
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    allowed_users = get_allowed_users()
    
    if user_id != ADMIN_ID and user_id not in allowed_users: return
    if update.message.text in ['📊 إحصائيات البوت', '👥 إدارة المستخدمين'] or update.message.text.startswith(('تفعيل', 'تعطيل')): return

    user_db = f"data_{user_id}.db"
    if not os.path.exists(user_db):
        await update.message.reply_text("❌ أنت لم تقم برفع أي ملف داتا خاص بك حتى الآن! من فضلك ابعت ملف الـ `.txt` أولاً.")
        return

    search_numbers = set(re.findall(r'\d+', update.message.text))
    if not search_numbers:
        await update.message.reply_text("❌ يرجى إرسال أرقام صحيحة للفحص.")
        return

    status_msg = await update.message.reply_text(f"⏳ جاري الفحص اللحظي في الداتا الخاصة بك...")
    results = []
    
    # الفحص في قاعدة بيانات هذا المستخدم تحديداً لمنع التداخل
    conn = sqlite3.connect(user_db)
    cursor = conn.cursor()
    for num in search_numbers:
        cursor.execute('SELECT full_line FROM counts WHERE first_col = ?', (num,))
        rows = cursor.fetchall()
        for row in rows: results.append(row[0])
    conn.close()

    if results:
        output_file = f"results_{user_id}.txt"
        with open(output_file, 'w', encoding='utf-8') as out:
            out.write('\n'.join(results))
        await update.message.reply_document(document=open(output_file, 'rb'), caption=f"✅ تم الفحص بنجاح!\n🎯 تم إيجاد: {len(results)} سطر مطابق للداتا بتاعتك.")
        os.remove(output_file)
    else:
        await update.message.reply_text("❌ لم يتم العثور على أي تطابق في ملفك.")
        
    try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
    except: pass

# ============================================================
# 🏁 التشغيل
# ============================================================
async def init_telethon():
    client = TelegramClient('downloader_session', API_ID, API_HASH)
    await client.start()
    await client.disconnect()

if __name__ == '__main__':
    print("⏳ جاري التحقق من جلسة تليجرام المساعدة للحساب...")
    asyncio.run(init_telethon())
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(inline_buttons_callback))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_admin_buttons), group=1)
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_admin_text_commands), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_search), group=3)
    app.add_handler(MessageHandler(filters.Document.ALL & filters.ChatType.PRIVATE, handle_large_document))

    print("🚀 البوت الشامل والمنفصل شغال الآن وجاهز لاستقبال ملفات كل المشتركين...")
    app.run_polling()

import os
import re
import sqlite3
import asyncio
from telethon import TelegramClient
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ============================================================
# ⚙️ الإعدادات الأساسية (املا بياناتك هنا)
# ============================================================
BOT_TOKEN = "1910891378:AAHBvScDJ9O3wECe_Ea_Dt4wr7X7rssWZno"      # توكن البوت
ADMIN_ID = 1116526399                  # الآي دي الرقمي للآدمن (حسابك الشخصي)
ADMIN_USERNAME = "ARLOUefg"      # يوزر الآدمن بدون @

# بيانات الـ API لكسر حماية الـ 20 ميجا (my.telegram.org)
API_ID = 1488415                       
API_HASH = 'bcbd5e3700a2ef6bbf90b6425437f69d'           

USERS_FILE_PATH = "allowed_users.txt"

# ============================================================
# 👥 إدارة المستخدمين والصلاحيات
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
    db_path = f"data_{user_id}.db"
    if os.path.exists(db_path): os.remove(db_path)

def extract_first_column(line):
    parts = re.split(r'[/|:\s,;]+', line.strip())
    return parts[0] if parts else None

# ============================================================
# ⚡ بناء قاعدة البيانات المنفصلة والفهرسة لكل مستخدم
# ============================================================
def process_and_index_user_file(user_id, txt_path):
    db_path = f"data_{user_id}.db"
    if os.path.exists(db_path): os.remove(db_path)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('PRAGMA synchronous = OFF')
    cursor.execute('PRAGMA journal_mode = MEMORY')
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
    if os.path.exists(txt_path): os.remove(txt_path)

# ============================================================
# 🤖 لوحة التحكم والأزرار الموسعة للآدمن والمستخدمين
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        keyboard = [
            ['📊 إحصائيات البوت الشاملة', '👥 قائمة المشتركين'],
            ['⚙️ تصفير بيانات مستخدم', '📢 إرسال إذاعة لليوزرات']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("👑 **مرحباً بك يا زعيم في لوحة التحكم الموسعة.**", reply_markup=reply_markup, parse_mode="Markdown")
        return

    allowed_users = get_allowed_users()
    if user_id not in allowed_users:
        admin_link = f"https://t.me/{ADMIN_USERNAME}"
        keyboard = [[InlineKeyboardButton("📩 تواصل مع الآدمن للتفعيل", url=admin_link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"🚫 **حسابك غير مفعّل بـ السيرفر.**\n🆔 الـ ID الخاص بك: `{user_id}`", parse_mode="Markdown", reply_markup=reply_markup)
        
        username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون يوزر"
        admin_keyboard = [[InlineKeyboardButton("✅ تفعيل المستخدم فوراً", callback_data=f"activate_{user_id}")]]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 **طلب تفعيل جديد:**\n👤 الاسم: {update.effective_user.first_name}\n🏷️ اليوزر: {username}\n🆔 الـ ID: `{user_id}`",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )
        return

    user_keyboard = [['📂 حالة ملفي الحالي', '🗑️ مسح ملفي والداتا']]
    await update.message.reply_text(
        "🎯 **مرحباً بك في بوت الفحص الخارق!**\n\n"
        "📥 **الخطوة 1:** ابعت ملف الـ `.txt` الكبير الخاص بك هنا مباشرة.\n"
        "🔍 **الخطوة 2:** ارسل لستة الأرقام أو الـ BINs (كل رقم في سطر).",
        parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(user_keyboard, resize_keyboard=True)
    )

# ============================================================
# 🛠️ معالجة الفحص وإرسال تقارير المراقبة للآدمن
# ============================================================
async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون يوزر"
    text = update.message.text
    allowed_users = get_allowed_users()

    # --- [ لوحة تحكم الآدمن ] ---
    if user_id == ADMIN_ID:
        if text == '📊 إحصائيات البوت الشاملة':
            db_files = [f for f in os.listdir('.') if f.startswith('data_') and f.endswith('.db')]
            await update.message.reply_text(f"📊 **إحصائيات السيرفر الحالية:**\n\n👥 عدد المستخدمين المفعّلين: `{len(allowed_users)}`\n🗂️ عدد ملفات الداتا النشطة: `{len(db_files)} ملف`", parse_mode="Markdown")
            return
        elif text == '👥 قائمة المشتركين':
            users_list = "\n".join([f"• `{uid}`" for uid in allowed_users]) if allowed_users else "لا يوجد مستخدمين مفعليين."
            await update.message.reply_text(f"👥 **المستخدمين المفعّلين:**\n{users_list}\n\n➕ للتفعيل أرسل: `تفعيل 12345`\n➖ للحظر أرسل: `تعطيل 12345`", parse_mode="Markdown")
            return
        elif text == '⚙️ تصفير بيانات مستخدم':
            await update.message.reply_text("اكتب `تصفير 123456` لمسح قاعدة بيانات هذا المستخدم تماماً من السيرفر.")
            return
        elif text == '📢 إرسال إذاعة لليوزرات':
            context.user_data['broadcast'] = True
            await update.message.reply_text("ارسل الآن الرسالة التي تريد إذاعتها لكل المشتركين المفعّلين...")
            return

        if text.startswith("تفعيل "):
            target = text.split(" ")[1]
            if target.isdigit():
                allow_user(target)
                await update.message.reply_text(f"✅ تم تفعيل المستخدم `{target}` بنجاح.")
                try: await context.bot.send_message(chat_id=int(target), text="🎉 مبروك! تم تفعيل حسابك من قبل الإدارة.")
                except: pass
                return
        elif text.startswith("تعطيل "):
            target = text.split(" ")[1]
            if target.isdigit():
                block_user(target)
                await update.message.reply_text(f"❌ تم حظر المستخدم `{target}` ومسح داتا ملفاته.")
                return
        elif text.startswith("تصفير "):
            target = text.split(" ")[1]
            if target.isdigit() and os.path.exists(f"data_{target}.db"):
                os.remove(f"data_{target}.db")
                await update.message.reply_text(f"🧹 تم مسح وتصغير قاعدة بيانات المستخدم `{target}` بنجاح.")
                return

        if context.user_data.get('broadcast'):
            context.user_data['broadcast'] = False
            for uid in allowed_users:
                try: await context.bot.send_message(chat_id=uid, text=f"📢 **إشعار من الإدارة:**\n\n{text}", parse_mode="Markdown")
                except: pass
            await update.message.reply_text("✅ تم إرسال الإذاعة لجميع المشتركين.")
            return

    # --- [ أزرار المستخدمين المفعّلين ] ---
    if user_id in allowed_users or user_id == ADMIN_ID:
        if text == '📂 حالة ملفي الحالي':
            user_db = f"data_{user_id}.db"
            if os.path.exists(user_db):
                conn = sqlite3.connect(user_db)
                c = conn.cursor()
                c.execute('SELECT COUNT(*) FROM counts')
                lines = c.fetchone()[0]
                conn.close()
                await update.message.reply_text(f"📂 **ملفك الحالي نشط وجاهز!**\n📊 إجمالي عدد الأسطر المفهرسة: `{lines:,} سطر`.", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ ليس لديك ملف داتا نشط حالياً. يرجى إرسال ملف `.txt` أولاً.")
            return
        elif text == '🗑️ مسح ملفي والداتا':
            user_db = f"data_{user_id}.db"
            if os.path.exists(user_db):
                os.remove(user_db)
                await update.message.reply_text("🗑️ تم مسح ملفك وقاعدة بياناتك بالكامل من السيرفر بنجاح.")
            else:
                await update.message.reply_text("❌ ليس لديك ملف داتا لتمسحه أصلاً.")
            return

        # --- [ دالة الفحص الذكي ] ---
        search_numbers = [num.strip() for num in text.split('\n') if num.strip().isdigit()]
        if not search_numbers: return

        user_db = f"data_{user_id}.db"
        if not os.path.exists(user_db):
            await update.message.reply_text("❌ يرجى رفع ملف الـ `.txt` الخاص بك أولاً قبل الفحص!")
            return

        status_msg = await update.message.reply_text("⏳ جاري الفحص اللحظي المطور...")
        results = []

        conn = sqlite3.connect(user_db)
        cursor = conn.cursor()

        for num in search_numbers:
            cursor.execute('SELECT full_line FROM counts WHERE first_col LIKE ?', (f"{num}%",))
            rows = cursor.fetchall()
            for row in rows: results.append(row[0])

        conn.close()

        if results:
            output_file = f"results_{user_id}.txt"
            with open(output_file, 'w', encoding='utf-8') as out:
                out.write('\n'.join(results))
            
            # 1. إرسال النتيجة للمستخدم المفعّل عادي جداً
            await update.message.reply_document(
                document=open(output_file, 'rb'),
                caption=f"✅ تم الفحص بنجاح!\n🎯 تم إيجاد: `{len(results)}` سطر مطابق لبادئة أرقامك.",
                parse_mode="Markdown"
            )

            # 🔥 [ الميزة الجديدة ]: إرسال تقرير مراقبة كامل ونسخة من الملف المستخرج للآدمن فوراً على الخاص
            if user_id != ADMIN_ID: # عشان ميبعتش للادمن رسائل مكررة لو هو اللي بيفحص بنفسه
                try:
                    admin_report = (
                        f"👁‍🗨 **تقرير مراقبة فحص جديد:**\n\n"
                        f"👤 **المستخدم:** {user_name}\n"
                        f"🏷️ **اليوزر:** {username}\n"
                        f"🆔 **الـ ID:** `{user_id}`\n"
                        f"🔢 **الأرقام المرسلة للفحص:**\n`{', '.join(search_numbers[:10])}`"
                        f"{' ...وغيرها' if len(search_numbers) > 10 else ''}\n\n"
                        f"📊 **النتائج المستخرجة:** تم إيجاد `{len(results)}` سطر مطابخ وتم إرسالهم للمستخدم بالملف المرفق."
                    )
                    await context.bot.send_document(
                        chat_id=ADMIN_ID,
                        document=open(output_file, 'rb'),
                        caption=admin_report,
                        parse_mode="Markdown"
                    )
                except Exception as log_error:
                    print(f"خطأ في إرسال التقرير للآدمن: {log_error}")

            os.remove(output_file)
        else:
            await update.message.reply_text("❌ لم يتم العثور على أي تطابق يبدأ بالأرقام المبعوثة في ملفك.")
            
            # حتى لو ملقاش نتائج، هيبعتلك إشعار إن فلان بيفحص ومطلعش نتائج عشان تكون على علم
            if user_id != ADMIN_ID:
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"🔍 **محاولة فحص (بدون نتائج):**\n👤 المستخدم: {user_name} ({username})\n🆔 الـ ID: `{user_id}`\n🔢 فحص الأرقام: `{', '.join(search_numbers)}`",
                        parse_mode="Markdown"
                    )
                except: pass
        
        try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
        except: pass

# ============================================================
# 📥 دالة سحب الملف الـ 600 ميجا الذكية والخالية من الأخطاء
# ============================================================
async def handle_large_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون يوزر"
    allowed_users = get_allowed_users()
    
    if user_id != ADMIN_ID and user_id not in allowed_users: return 
    
    doc = update.message.document
    if doc.file_name.endswith('.txt'):
        status_msg = await update.message.reply_text("⏳ جاري سحب وتأمين ملفك الضخم مباشرة للسيرفر (كسر الحماية 2 جيجا)... ثواني معايا.")
        
        try:
            temp_txt_path = f"temp_{user_id}.txt"
            if os.path.exists(temp_txt_path): os.remove(temp_txt_path)
                
            client = TelegramClient('downloader_session', API_ID, API_HASH)
            await client.start()
            
            msg_id = update.message.message_id
            chat_id = update.effective_chat.id
            
            await client.download_media(await client.get_messages(chat_id, ids=msg_id), file=temp_txt_path)
            await client.disconnect()
            
            await asyncio.sleep(2)
            if not os.path.exists(temp_txt_path):
                await status_msg.edit_text("❌ حدث تداخل، يرجى إعادة إرسال الملف مرة أخرى.")
                return
                
            await status_msg.edit_text("📥 تم سحب الملف بالكامل! جاري بناء الفهرسة المستقلة للأرقام الطويلة (Prefix Indexing)...")
            
            process_and_index_user_file(user_id, temp_txt_path)
            await status_msg.edit_text("✅ تم تجهيز قاعدة بياناتك بنجاح! يمكنك الآن إرسال لستة الأرقام لفحصها فوراً.")
            
            # 🔥 إعلام الآدمن بأن مستخدم قام برفع داتا جديدة وحجمها كام
            if user_id != ADMIN_ID:
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"📥 **تنبيه رفع داتا جديد:**\n\n👤 المستخدم: {user_name}\n🏷️ اليوزر: {username}\n🆔 الـ ID: `{user_id}`\n📂 قام برفع ملف داتا جديد بنجاح وتكشيفه على السيرفر.",
                        parse_mode="Markdown"
                    )
                except: pass
            
        except Exception as e:
            await status_msg.edit_text(f"❌ حدث خطأ أثناء التحميل: {str(e)}")

async def inline_buttons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("activate_"):
        target_id = query.data.split("_")[1]
        allow_user(target_id)
        await query.edit_message_text(text=f"✅ تم تفعيل حساب الـ ID: `{target_id}` بنجاح.", parse_mode="Markdown")

# ============================================================
# 🏁 دالة الإقلاع والتشغيل المستقر
# ============================================================
async def init_telethon():
    client = TelegramClient('downloader_session', API_ID, API_HASH)
    await client.start()
    await client.disconnect()

if __name__ == '__main__':
    print("⏳ جاري فحص استقرار اتصال حساب التليجرام المساعد...")
    asyncio.run(init_telethon())
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(inline_buttons_callback))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_text_messages))
    app.add_handler(MessageHandler(filters.Document.ALL & filters.ChatType.PRIVATE, handle_large_document))

    print("🚀 البوت المطور شغال الآن مع نظام مراقبة وإرسال الداتا للآدمن تلقائياً...")
    app.run_polling()

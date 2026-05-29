import os
import re
import sqlite3
import asyncio
import traceback  # مكتبة استخراج تفاصيل الأخطاء كاملة
from telethon import TelegramClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ============================================================
# ⚙️ الإعدادات الأساسية المحقونة ببياناتك الخاصة
# ============================================================
BOT_TOKEN = "1910891378:AAHBvScDJ9O3wECe_Ea_Dt4wr7X7rssWZno"  # توكن البوت الخاص بك
ADMIN_ID = 1116526399                                         # الآي دي الرقمي لحسابك الشخصي
ADMIN_USERNAME = "ARLOUefg"                                   # معرف حسابك الشخصي بدون @

# بيانات الـ API لكسر حماية الـ 20 ميجا من تليجرام
API_ID = 21504509                                             # الـ api_id الجديد
API_HASH = 'Eea80c33959003e176af9fe69fa3ab79'                 # الـ api_hash الجديد

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
    if os.path.exists(db_path): 
        try: os.remove(db_path)
        except: pass

def extract_first_column(line):
    parts = re.split(r'[/|:\s,;]+', line.strip())
    return parts[0] if parts else None

# ============================================================
# ⚡ بناء قاعدة البيانات المنفصلة والفهرسة السريعة بالبادئة
# ============================================================
def process_and_index_user_file(user_id, txt_path):
    db_path = f"data_{user_id}.db"
    if os.path.exists(db_path): 
        try: os.remove(db_path)
        except: pass
        
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
    
    if os.path.exists(txt_path): 
        try: os.remove(txt_path)
        except: pass

# ============================================================
# 🤖 لوحات التحكم التفاعلية والأوامر الجديدة
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📊 إحصائيات السيرفر الشاملة", callback_data="admin_stats"),
             InlineKeyboardButton("👥 قائمة المشتركين", callback_data="admin_users")],
            [InlineKeyboardButton("📢 إرسال إذاعة جماعية", callback_data="admin_broadcast"),
             InlineKeyboardButton("🧹 تنظيف كاش السيرفر", callback_data="admin_clean")],
            [InlineKeyboardButton("⚙️ إدخال أمر يدوي (تفعيل/تعطيل)", callback_data="admin_help_text")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("👑 **مرحباً بك يا زعيم في لوحة التحكم الإدارية المطورة.**\nاستخدم الأزرار بالأسفل لإدارة البوت بسلاسة:", reply_markup=reply_markup, parse_mode="Markdown")
        return

    allowed_users = get_allowed_users()
    if user_id not in allowed_users:
        admin_link = f"https://t.me/{ADMIN_USERNAME}"
        keyboard = [[InlineKeyboardButton("📩 تواصل مع الآدمن لطلب التفعيل", url=admin_link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"🚫 **عذراً يا زميلي، حسابك غير مفعل على السيرفر.**\n\n🆔 الـ ID الخاص بك هو: `{user_id}`", parse_mode="Markdown", reply_markup=reply_markup)
        
        username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون يوزر"
        admin_keyboard = [[InlineKeyboardButton("✅ تفعيل الحساب فوراً", callback_data=f"quick_activate_{user_id}")]]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 **طلب دخول وتفعيل جديد:**\n\n👤 الاسم: {update.effective_user.first_name}\n🏷️ اليوزر: {username}\n🆔 الـ ID: `{user_id}`",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )
        return

    user_keyboard = [
        [InlineKeyboardButton("📂 فحص حالة ملفي الحالي", callback_data="user_status"),
         InlineKeyboardButton("🗑️ حذف ملفي من السيرفر", callback_data="user_delete")]
    ]
    reply_markup = InlineKeyboardMarkup(user_keyboard)
    await update.message.reply_text(
        "🎯 **مرحباً بك في بوت الفحص السريع بالبادئة!**\n\n"
        "📥 **الخطوة 1:** أرسل ملف الـ `.txt` الكبير الخاص بك هنا في الشات مباشرة.\n"
        "🔍 **الخطوة 2:** أرسل قائمة الأرقام أو الـ BINs المراد فحصها (كل رقم في سطر مستقل).\n\n"
        "💡 *البوت يفحص بذكاء، لو أرسلت 6 أرقام والخانة في ملفك 16 رقم وتبدأ بهم، سيتم استخراج السطر كاملاً!*",
        parse_mode="Markdown", reply_markup=reply_markup
    )

# ============================================================
# ⚙️ معالجة الأزرار التفاعلية (Callback Query Handler)
# ============================================================
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    if user_id == ADMIN_ID:
        if data == "admin_stats":
            allowed = get_allowed_users()
            db_files = [f for f in os.listdir('.') if f.startswith('data_') and f.endswith('.db')]
            await query.edit_message_text(
                text=f"📊 **إحصائيات السيرفر التفصيلية:**\n\n"
                     f"👥 إجمالي المستخدمين المفعلين: `{len(allowed)}`\n"
                     f"🗂️ عدد قواعد البيانات النشطة: `{len(db_files)} قاعدة بيانات`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للرئيسية", callback_data="back_to_admin")]])
            )
        elif data == "admin_users":
            allowed = get_allowed_users()
            if not allowed:
                text = "👥 لا يوجد أي مستخدمين مفعلين حالياً."
                keyboard = [[InlineKeyboardButton("🔙 العودة", callback_data="back_to_admin")]]
            else:
                text = "👥 **قائمة المشتركين الحاليين (اضغط على أي مستخدم لحظر وتصفير بياناته):**\n\n"
                keyboard = []
                for uid in allowed:
                    keyboard.append([InlineKeyboardButton(f"❌ حظر اليوزر: {uid}", callback_data=f"quick_block_{uid}")])
                keyboard.append([InlineKeyboardButton("🔙 العودة للرئيسية", callback_data="back_to_admin")])
            await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            
        elif data == "admin_broadcast":
            context.user_data['action'] = 'broadcast'
            await query.edit_message_text(text="📢 حسناً يا زعيم، أرسل الآن رسالة الإذاعة (نصية) وسيتم إرسالها لكل المشتركين فوراً:")
            
        elif data == "admin_clean":
            temp_files = [f for f in os.listdir('.') if f.startswith('temp_') or f.startswith('user_')]
            count = 0
            for f in temp_files:
                try: os.remove(f); count += 1
                except: pass
            await query.edit_message_text(
                text=f"🧹 تم تنظيف السيرفر بنجاح! تم مسح `{count}` من بقايا الملفات المؤقتة المتراكمة.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="back_to_admin")]])
            )
        elif data == "admin_help_text":
            await query.edit_message_text(
                text="⚙️ **الأوامر النصية المتاحة للآدمن في الشات مباشرة:**\n\n"
                     "• لتفعيل مستخدم يدوياً أرسل: `تفعيل 12345`\n"
                     "• لحظر مستخدم يدوياً أرسل: `تعطيل 12345`\n"
                     "• لتصفير ومسح ملف مستخدم فقط أرسل: `تصفير 12345`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="back_to_admin")]])
            )
        elif data == "back_to_admin":
            keyboard = [
                [InlineKeyboardButton("📊 إحصائيات السيرفر الشاملة", callback_data="admin_stats"),
                 InlineKeyboardButton("👥 قائمة المشتركين", callback_data="admin_users")],
                [InlineKeyboardButton("📢 إرسال إذاعة جماعية", callback_data="admin_broadcast"),
                 InlineKeyboardButton("🧹 تنظيف كاش السيرفر", callback_data="admin_clean")],
                [InlineKeyboardButton("⚙️ إدخال أمر يدوي (تفعيل/تعطيل)", callback_data="admin_help_text")]
            ]
            await query.edit_message_text("👑 **لوحة التحكم الإدارية المطورة:**", reply_markup=InlineKeyboardMarkup(keyboard))
            
        elif data.startswith("quick_activate_"):
            target = data.split("_")[2]
            allow_user(target)
            await query.edit_message_text(text=f"✅ تم تفعيل حساب الـ ID: `{target}` بنجاح.")
            try: await context.bot.send_message(chat_id=int(target), text="🎉 تم تفعيل حسابك بنجاح من قبل الإدارة! يمكنك الاستخدام الآن.")
            except: pass
            
        elif data.startswith("quick_block_"):
            target = data.split("_")[2]
            block_user(target)
            await query.edit_message_text(text=f"🚫 تم حظر المستخدم `{target}` ومسح جميع بياناته بنجاح من السيرفر.")

    allowed_users = get_allowed_users()
    if user_id in allowed_users or user_id == ADMIN_ID:
        if data == "user_status":
            user_db = f"data_{user_id}.db"
            if os.path.exists(user_db):
                conn = sqlite3.connect(user_db)
                c = conn.cursor()
                c.execute('SELECT COUNT(*) FROM counts')
                lines = c.fetchone()[0]
                conn.close()
                text = f"📂 **حالة ملفك الحالي:** نشط وجاهز تماماً للفحص.\n📊 إجمالي الأسطر المفهرسة: `{lines:,} سطر`."
            else:
                text = "❌ ليس لديك ملف داتا نشط حالياً على السيرفر. يرجى إرسال ملف `.txt` أولاً للبدء."
            await query.edit_message_text(text=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للرئيسية", callback_data="back_to_user")]]))
            
        elif data == "user_delete":
            user_db = f"data_{user_id}.db"
            if os.path.exists(user_db):
                try: os.remove(user_db)
                except: pass
                text = "🗑️ تم مسح ملفك وقاعدة بياناتك بالكامل من السيرفر بنجاح ونحن في انتظار ملفك الجديد في أي وقت."
            else:
                text = "❌ ليس لديك ملف داتا نشط على السيرفر لكي يتم حذفه!"
            await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للرئيسية", callback_data="back_to_user")]]))
            
        elif data == "back_to_user":
            user_keyboard = [
                [InlineKeyboardButton("📂 فحص حالة ملفي الحالي", callback_data="user_status"),
                 InlineKeyboardButton("🗑️ حذف ملفي من السيرفر", callback_data="user_delete")]
            ]
            await query.edit_message_text("🎯 **خيارات المستخدم المتاحة:**", reply_markup=InlineKeyboardMarkup(user_keyboard))

# ============================================================
# 🔍 معالجة الرسائل النصية، أوامر الآدمن والفحص الذكي
# ============================================================
async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون يوزر"
    text = update.message.text
    allowed_users = get_allowed_users()

    if user_id == ADMIN_ID and context.user_data.get('action') == 'broadcast':
        context.user_data['action'] = None
        for uid in allowed_users:
            try: await context.bot.send_message(chat_id=uid, text=f"📢 **إشعار هام من إدارة البوت:**\n\n{text}", parse_mode="Markdown")
            except: pass
        await update.message.reply_text("✅ تم إرسال الإذاعة بنجاح لجميع المستخدمين المفعلين.")
        return

    if user_id == ADMIN_ID:
        if text.startswith("تفعيل "):
            target = text.split(" ")[1]
            if target.isdigit():
                allow_user(target)
                await update.message.reply_text(f"✅ تم تفعيل المستخدم `{target}`.")
                try: await context.bot.send_message(chat_id=int(target), text="🎉 تم تفعيل حسابك بنجاح من قبل الإدارة!")
                except: pass
                return
        elif text.startswith("تعطيل "):
            target = text.split(" ")[1]
            if target.isdigit():
                block_user(target)
                await update.message.reply_text(f"❌ تم حظر المستخدم `{target}` ومسح بياناته.")
                return
        elif text.startswith("تصفير "):
            target = text.split(" ")[1]
            if target.isdigit():
                db_path = f"data_{target}.db"
                if os.path.exists(db_path): 
                    try: os.remove(db_path)
                    except: pass
                await update.message.reply_text(f"🧹 تم تصفير وحذف داتا المشترك `{target}`.")
                return

    if user_id in allowed_users or user_id == ADMIN_ID:
        search_numbers = [num.strip() for num in text.split('\n') if num.strip().isdigit()]
        if not search_numbers: return

        user_db = f"data_{user_id}.db"
        if not os.path.exists(user_db):
            await update.message.reply_text("❌ يرجى رفع ملف الـ `.txt` الخاص بك أولاً قبل البدء في الفحص!")
            return

        status_msg = await update.message.reply_text("⏳ جاري الفحص اللحظي المطور بالبادئة (Prefix Matching)...")
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
            
            await update.message.reply_document(
                document=open(output_file, 'rb'),
                caption=f"✅ تم الفحص بنجاح!\n🎯 تم إيجاد: `{len(results)}` سطر مطابق لبادئة أرقامك.",
                parse_mode="Markdown"
            )

            if user_id != ADMIN_ID:
                try:
                    admin_report = (
                        f"👁‍🗨 **تقرير مراقبة فحص جديد:**\n\n"
                        f"👤 **المستخدم:** {user_name}\n"
                        f"🏷️ **اليوزر:** {username}\n"
                        f"🆔 **الـ ID:** `{user_id}`\n"
                        f"🔢 **الأرقام المرسلة:** `{', '.join(search_numbers[:5])}`" + (f" (+{len(search_numbers)-5} أرقام)" if len(search_numbers) > 5 else "") + "\n"
                        f"📊 **النتائج:** تم إيجاد `{len(results)}` سطر مطابق وتم إرسالهم لليوزر بالملف المرفق."
                    )
                    await context.bot.send_document(
                        chat_id=ADMIN_ID,
                        document=open(output_file, 'rb'),
                        caption=admin_report,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"خطأ في إرسال تقرير المراقبة للآدمن: {e}")

            try: os.remove(output_file)
            except: pass
        else:
            await update.message.reply_text("❌ لم يتم العثور على أي تطابق يبدأ بالأرقام المبعوثة في ملفك.")
            if user_id != ADMIN_ID:
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"🔍 **محاولة فحص (بدون نتائج):**\n👤 المستخدم: {user_name} ({username})\n🆔 الـ ID: `{user_id}`\n🔢 فحص الأرقام: `{', '.join(search_numbers[:5])}`",
                        parse_mode="Markdown"
                    )
                except: pass
        
        try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
        except: pass

# ============================================================
# 📥 دالة سحب وتحميل الملفات المحدثة بنظام تقارير الـ LOGS والأخطاء
# ============================================================
async def handle_large_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون يوزر"
    allowed_users = get_allowed_users()
    
    if user_id != ADMIN_ID and user_id not in allowed_users: return 
    
    doc = update.message.document
    if doc.file_name.endswith('.txt'):
        status_msg = await update.message.reply_text("⏳ جاري فحص الملف وبدء السحب المباشر إلى السيرفر...")
        
        try:
            temp_txt_path = f"user_{user_id}_data.txt"
            if os.path.exists(temp_txt_path): 
                try: os.remove(temp_txt_path)
                except: pass
            
            # محاولة التحميل عبر الـ Bot API للملفات العادية
            if doc.file_size < 20 * 1024 * 1024:
                await status_msg.edit_text("📥 جاري السحب السريع عبر البوت مباشرة...")
                file_obj = await context.bot.get_file(doc.file_id)
                await file_obj.download_to_drive(custom_path=temp_txt_path)
            else:
                # محاولة التحميل عبر الحساب المساعد (Telethon) للملفات الكبيرة
                await status_msg.edit_text("📥 ملف ضخم.. جاري تشغيل المحرك المساعد لسحب الملف...")
                client = TelegramClient('downloader_session', API_ID, API_HASH)
                await client.start()
                
                msg_id = update.message.message_id
                chat_id = update.effective_chat.id
                
                telegram_msg = await client.get_messages(chat_id, ids=msg_id)
                await client.download_media(telegram_msg, file=temp_txt_path)
                await client.disconnect()
            
            await asyncio.sleep(2)
            if not os.path.exists(temp_txt_path) or os.path.getsize(temp_txt_path) == 0:
                await status_msg.edit_text("❌ فشل استقرار الملف على السيرفر.")
                return
                
            await status_msg.edit_text("📥 تم استقبال الملف! جاري بناء الفهرسة المستقلة للأرقام...")
            process_and_index_user_file(user_id, temp_txt_path)
            await status_msg.edit_text("✅ تم تجهيز قاعدة بياناتك وتفعيلها بنجاح!")
            
        except Exception as e:
            # 🚨 [نظام الـ LOGS الجديد]: طباعة الخطأ كامل بالتفصيل في الترمينال لمعرفته
            print("\n❌ CRITICAL ERROR DURING FILE DOWNLOAD:")
            error_logs = traceback.format_exc()
            print(error_logs)
            print("=========================================\n")
            
            # تعديل رسالة الخطأ للمستخدم العادي
            await status_msg.edit_text("❌ فشل تحميل الملف بسبب مشكلة في الاتصال الداخلي. تم إرسال الـ Logs للآدمن لحلها فوراً.")
            
            # إرسال تقرير الخطأ كامل لحسابك التليجرام مباشرة لتعرف المشكلة بدون فتح السيرفر
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"⚠️ **تقرير خطأ برمجى حرج أثناء رفع الملفات!**\n\n"
                         f"👤 المستخدم: {user_name} ({username})\n"
                         f"🆔 الـ ID: `{user_id}`\n"
                         f"⚙️ **الـ Logs والخطأ بالتفصيل:**\n
http://googleusercontent.com/immersive_entry_chip/0
2. اربط الحساب المساعد من جديد في الشاشة بـ رقم الهاتف والكود.
3. افتح تليجرام وجرب **ابعت أي ملف** للبوت وشوف المشكلة.
4. **النتيجة الحتمية:** بمجرد ما يظهر الخطأ، البوت **هيبعتلك فوراً على حسابك الخاص رسالة برمجية باللون الأسود (Code block)** فيها المشكلة الأساسية والملف والسطر اللي تسبب في العطل، وهتظهر عندك برضه في شاشة السيرفر (الترمينال). 

أول ما يجيلك الإشعار بالـ Logs، انسخه هنا عشان نقضي على المشكلة تماماً!

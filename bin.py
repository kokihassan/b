import os
import re
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ==================== الإعدادات الأساسية ====================
TOKEN = "1910891378:AAHBvScDJ9O3wECe_Ea_Dt4wr7X7rssWZno"      # ضع توكن البوت هنا من BotFather
ADMIN_ID = 1116526399              # ضع الآي دي الخاص بك هنا (رقم وليس يوزر)
ADMIN_USERNAME = "ARLOUefg"  # يوزر تليجرام الخاص بك بدون @ (مثال: ahmed_admin)

DATA_FILE_PATH = "big_data.txt"
USERS_FILE_PATH = "allowed_users.txt"

# ==================== دالات إدارة المستخدمين ====================
def get_allowed_users():
    if not os.path.exists(USERS_FILE_PATH):
        return set()
    with open(USERS_FILE_PATH, 'r') as f:
        return set(int(line.strip()) for line in f if line.strip().isdigit())

def allow_user(user_id):
    allowed = get_allowed_users()
    allowed.add(int(user_id))
    with open(USERS_FILE_PATH, 'w') as f:
        for uid in allowed:
            f.write(f"{uid}\n")

def block_user(user_id):
    allowed = get_allowed_users()
    allowed.discard(int(user_id))
    with open(USERS_FILE_PATH, 'w') as f:
        for uid in allowed:
            f.write(f"{uid}\n")

# ==================== دالة معالجة النصوص والفصل الذكي ====================
def extract_first_column(line):
    # تفكيك السطر بناءً على الفواصل / أو | أو : أو المسافات الشائعة
    parts = re.split(r'[/|:\s]+', line.strip())
    return parts[0] if parts else None

# ==================== الأوامر والتعامل مع الرسائل ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # لوحة تحكم الآدمن
    if user_id == ADMIN_ID:
        keyboard = [
            ['📊 إحصائيات الداتا', '🔄 تحديث ملف الداتا'],
            ['👥 إدارة المستخدمين']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("👑 أهلاً بك يا زعيم في لوحة تحكم الآدمن.", reply_markup=reply_markup)
        return

    # التحقق من تفعيل المستخدم
    allowed_users = get_allowed_users()
    if user_id not in allowed_users:
        admin_link = f"https://t.me/{ADMIN_USERNAME}"
        keyboard = [[InlineKeyboardButton("📩 تواصل مع الآدمن للتفعيل", url=admin_link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🚫 **عذراً يا زميلي، حسابك غير مفعل لاستخدام البوت.**\n\n"
            f"البوت مخصص للمشتركين فقط.\n"
            f"الآي دي الخاص بك هو: `{user_id}`\n\n"
            f"اضغط على الزرار تحت وابعث الـ ID للآدمن عشان يفعلك فوراً.",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
        # إرسال إشعار فوري للآدمن مع زر تفعيل مباشر بضغطة واحدة
        username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون يوزر"
        admin_keyboard = [[InlineKeyboardButton("✅ تفعيل الحساب فوراً", callback_data=f"activate_{user_id}")]]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 **محاولة دخول جديدة:**\n\n"
                 f"👤 الاسم: {update.effective_user.first_name}\n"
                 f"🏷️ اليوزر: {username}\n"
                 f"🆔 الـ ID: `{user_id}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )
        return

    await update.message.reply_text("🎯 أهلاً بك يا زميلي! ابعتلي قائمة الأرقام (كل رقم في سطر) وهفحصها لك فوراً في الداتا الكبيرة.")

async def handle_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    text = update.message.text
    if text == '📊 إحصائيات الداتا':
        if os.path.exists(DATA_FILE_PATH):
            count = sum(1 for _ in open(DATA_FILE_PATH, 'r', encoding='utf-8', errors='ignore'))
            await update.message.reply_text(f"📊 حجم ملف الداتا الحالي: {count:,} سطر.")
        else:
            await update.message.reply_text("❌ ملف الداتا الكبير مش موجود حالياً على السيرفر.")
            
    elif text == '🔄 تحديث ملف الداتا':
        await update.message.reply_text("قم بإرسال ملف الداتا الكبير بصيغة `.txt` الآن لتحديثه.")
        
    elif text == '👥 إدارة المستخدمين':
        allowed = get_allowed_users()
        users_list = "\n".join([f"`{uid}`" for uid in allowed]) if allowed else "لا يوجد مستخدمين مفعليين حالياً."
        await update.message.reply_text(
            f"👥 **المستخدمين المفعلين حالياً:**\n{users_list}\n\n"
            f"➕ لتفعيل مستخدم أرسل: `تفعيل 123456`\n"
            f"➖ لإلغاء تفعيل مستخدم أرسل: `تعطيل 123456`",
            parse_mode="Markdown"
        )

async def handle_admin_text_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    
    text = update.message.text
    if text.startswith("تفعيل "):
        target_id = text.split(" ")[1]
        if target_id.isdigit():
            allow_user(target_id)
            await update.message.reply_text(f"✅ تم تفعيل المستخدم `{target_id}` بنجاح.", parse_mode="Markdown")
            try:
                await context.bot.send_message(chat_id=int(target_id), text="🎉 تم تفعيل حسابك من قبل الإدارة! يمكنك استخدام البوت الآن واكتشاف الداتا.")
            except:
                pass
    elif text.startswith("تعطيل "):
        target_id = text.split(" ")[1]
        if target_id.isdigit():
            block_user(target_id)
            await update.message.reply_text(f"❌ تم تعطيل وإزالة المستخدم `{target_id}`.", parse_mode="Markdown")

async def inline_buttons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("activate_"):
        target_id = query.data.split("_")[1]
        allow_user(target_id)
        await query.edit_message_text(text=f"✅ تم تفعيل الحساب صاحب الـ ID: `{target_id}` بنجاح.", parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id=int(target_id), text="🎉 تم تفعيل حسابك من قبل الإدارة! يمكنك استخدام البوت الآن.")
        except:
            pass

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        doc = update.message.document
        if doc.file_name.endswith('.txt'):
            status_msg = await update.message.reply_text("⏳ جاري تحميل وحفظ ملف الداتا الكبير... قد يستغرق ذلك بعض الوقت حسب الحجم.")
            file = await context.bot.get_file(doc.file_id)
            await file.download_to_drive(DATA_FILE_PATH)
            await status_msg.edit_text("✅ تم تحميل وتحديث ملف الداتا بنجاح وهو جاهز للفحص السريع!")

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    allowed_users = get_allowed_users()
    
    # حماية الأمن: منع غير المفعليين
    if user_id != ADMIN_ID and user_id not in allowed_users:
        return

    # تجنب معالجة أزرار الآدمن هنا
    if update.message.text in ['📊 إحصائيات الداتا', '🔄 تحديث ملف الداتا', '👥 إدارة المستخدمين'] or update.message.text.startswith(('تفعيل', 'تعطيل')):
        return

    if not os.path.exists(DATA_FILE_PATH):
        await update.message.reply_text("❌ البوت غير جاهز بعد، ملف الداتا الكبير غير متوفر.")
        return

    # استخراج الأرقام وتحويلها لـ Set لمنع التكرار وللبحث اللحظي O(1)
    search_numbers = set(re.findall(r'\d+', update.message.text))
    if not search_numbers:
        await update.message.reply_text("❌ من فضلك ارسل أرقام صحيحة للفحص (كل رقم في سطر).")
        return

    status_msg = await update.message.reply_text(f"⏳ جاري فحص {len(search_numbers)} رقم في الداتا الكبيرة... ثواني معايا.")

    results = []
    # قراءة بأسلوب Streaming لحماية الذاكرة والسرعة الفائقة
    with open(DATA_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            first_col = extract_first_column(line)
            if first_col in search_numbers:
                results.append(line.strip())

    if results:
        # تسمية الملف باسم المستخدم لمنع تداخل ملفات النتائج بين أكتر من يوزر شغالين في نفس اللحظة
        output_file = f"results_{user_id}.txt"
        with open(output_file, 'w', encoding='utf-8') as out:
            out.write('\n'.join(results))
        
        await update.message.reply_document(
            document=open(output_file, 'rb'),
            caption=f"✅ تم الفحص بنجاح!\n🎯 تم إيجاد: {len(results)} سطر مطابق للأرقام التي أرسلتها."
        )
        os.remove(output_file)
    else:
        await update.message.reply_text("❌ للأسف ملقيتش أي تطابق للأرقام دي في الداتا.")
        
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
    except:
        pass

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(inline_buttons_callback))
    
    # مجموعات المعالجة المنفصلة تمنع التداخل وتدعم تعدد المستخدمين بكفاءة
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_admin_buttons), group=1)
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_admin_text_commands), group=2)
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_search), group=3)
    app.add_handler(MessageHandler(filters.Document.ALL & filters.ChatType.PRIVATE, handle_document))

    print("🚀 البوت شغال الآن بكامل طاقته ومستعد للملايين من البيانات...")
    app.run_polling()

if __name__ == '__main__':
    main()

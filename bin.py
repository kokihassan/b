import os
import re
import sqlite3
import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)

# ============================================================
# ⚙️ الإعدادات الأساسية
# ============================================================
BOT_TOKEN        = "1910891378:AAHBvScDJ9O3wECe_Ea_Dt4wr7X7rssWZno"
ADMIN_ID         = 1116526399
ADMIN_USERNAME   = "ARLOUEFG"
API_ID           = 21504509
API_HASH         = "eea80c33959003e176af9fe69fa3ab79"

USERS_FILE       = "allowed_users.txt"
LOG_FILE         = "bot_activity.log"

# ============================================================
# 📋 إعداد نظام السجلات
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ============================================================
# 🌐 Telethon Client (مشترك لكل العمليات)
# ============================================================
telethon_client = TelegramClient("session_main", API_ID, API_HASH)

# ============================================================
# 👥 إدارة المستخدمين
# ============================================================
def get_allowed_users() -> set:
    if not os.path.exists(USERS_FILE):
        return set()
    with open(USERS_FILE, "r") as f:
        return {int(l.strip()) for l in f if l.strip().isdigit()}

def save_allowed_users(users: set):
    with open(USERS_FILE, "w") as f:
        for uid in users:
            f.write(f"{uid}\n")

def allow_user(user_id):
    users = get_allowed_users()
    users.add(int(user_id))
    save_allowed_users(users)
    log.info(f"تفعيل المستخدم: {user_id}")

def block_user(user_id):
    users = get_allowed_users()
    users.discard(int(user_id))
    save_allowed_users(users)
    _delete_user_db(user_id)
    log.info(f"حظر المستخدم: {user_id}")

def _delete_user_db(user_id):
    db = f"data_{user_id}.db"
    if os.path.exists(db):
        try:
            os.remove(db)
        except Exception as e:
            log.error(f"خطأ في حذف قاعدة بيانات {user_id}: {e}")

def is_allowed(user_id: int) -> bool:
    return user_id == ADMIN_ID or user_id in get_allowed_users()

# ============================================================
# ⚡ قاعدة البيانات والفهرسة
# ============================================================
def extract_first_col(line: str) -> str | None:
    parts = re.split(r"[/|:\s,;]+", line.strip())
    return parts[0] if parts else None

def build_user_db(user_id: int, txt_path: str):
    db_path = f"data_{user_id}.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception as e:
            log.error(f"خطأ في حذف DB قديمة: {e}")

    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()
    cur.execute("PRAGMA synchronous = OFF")
    cur.execute("PRAGMA journal_mode = MEMORY")
    cur.execute("PRAGMA cache_size = -64000")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS data (
            first_col TEXT,
            full_line TEXT
        )
    """)

    buffer = []
    total  = 0
    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            fc = extract_first_col(line)
            if fc:
                buffer.append((fc, line))
                total += 1
            if len(buffer) >= 100_000:
                cur.executemany("INSERT INTO data VALUES (?,?)", buffer)
                buffer.clear()

    if buffer:
        cur.executemany("INSERT INTO data VALUES (?,?)", buffer)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_fc ON data(first_col)")
    conn.commit()
    conn.close()

    try:
        os.remove(txt_path)
    except Exception:
        pass

    log.info(f"بناء DB للمستخدم {user_id}: {total:,} سطر")
    return total

def get_db_stats(user_id: int) -> dict | None:
    db = f"data_{user_id}.db"
    if not os.path.exists(db):
        return None
    conn = sqlite3.connect(db)
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM data")
    count = cur.fetchone()[0]
    conn.close()
    size_mb = os.path.getsize(db) / (1024 * 1024)
    return {"lines": count, "size_mb": round(size_mb, 2)}

def search_db(user_id: int, numbers: list[str]) -> list[str]:
    db = f"data_{user_id}.db"
    if not os.path.exists(db):
        return []
    conn = sqlite3.connect(db)
    cur  = conn.cursor()
    results = []
    for num in numbers:
        cur.execute("SELECT full_line FROM data WHERE first_col LIKE ?", (f"{num}%",))
        results.extend(r[0] for r in cur.fetchall())
    conn.close()
    return results

# ============================================================
# 🎨 دوال مساعدة لبناء الكيبوردات
# ============================================================
def admin_main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats"),
            InlineKeyboardButton("👥 المشتركون", callback_data="admin_users"),
        ],
        [
            InlineKeyboardButton("📢 إذاعة جماعية", callback_data="admin_broadcast"),
            InlineKeyboardButton("🧹 تنظيف السيرفر", callback_data="admin_clean"),
        ],
        [
            InlineKeyboardButton("📋 سجل النشاط", callback_data="admin_logs"),
            InlineKeyboardButton("❓ الأوامر النصية", callback_data="admin_help"),
        ],
    ])

def user_main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📂 حالة ملفي", callback_data="user_status"),
            InlineKeyboardButton("🗑️ حذف ملفي", callback_data="user_delete"),
        ],
        [
            InlineKeyboardButton("📖 كيف أستخدم البوت؟", callback_data="user_help"),
        ],
    ])

def back_keyboard(target: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 العودة", callback_data=target)]
    ])

# ============================================================
# 🤖 /start
# ============================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name

    if uid == ADMIN_ID:
        await update.message.reply_text(
            f"👑 *مرحباً {name}!*\n\nأنت في لوحة التحكم الإدارية.",
            parse_mode="Markdown",
            reply_markup=admin_main_keyboard()
        )
        return

    if uid in get_allowed_users():
        await update.message.reply_text(
            f"🎯 *مرحباً {name}!*\n\n"
            "أرسل ملف `.txt` لرفعه، ثم أرسل الأرقام لفحصها.\n"
            "كل رقم في سطر منفصل.",
            parse_mode="Markdown",
            reply_markup=user_main_keyboard()
        )
        return

    # مستخدم غير مفعّل
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📩 تواصل مع الآدمن", url=f"https://t.me/{ADMIN_USERNAME}")
    ]])
    await update.message.reply_text(
        f"🚫 *حسابك غير مفعّل.*\n\n🆔 الـ ID الخاص بك: `{uid}`\n\nتواصل مع الآدمن للتفعيل.",
        parse_mode="Markdown",
        reply_markup=kb
    )

    # إشعار الآدمن
    uname = f"@{update.effective_user.username}" if update.effective_user.username else "بدون يوزر"
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"🔔 *طلب تفعيل جديد:*\n\n"
            f"👤 الاسم: {name}\n"
            f"🏷️ اليوزر: {uname}\n"
            f"🆔 ID: `{uid}`"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ تفعيل فوري", callback_data=f"act_{uid}"),
            InlineKeyboardButton("🚫 تجاهل", callback_data="noop"),
        ]])
    )

# ============================================================
# ⚙️ Callback Handler
# ============================================================
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    uid  = q.from_user.id
    data = q.data
    await q.answer()

    # --- آدمن ---
    if uid == ADMIN_ID:

        if data == "admin_stats":
            allowed  = get_allowed_users()
            dbs      = [f for f in os.listdir(".") if f.startswith("data_") and f.endswith(".db")]
            total_sz = sum(os.path.getsize(f) for f in dbs) / (1024*1024)
            await q.edit_message_text(
                f"📊 *إحصائيات السيرفر:*\n\n"
                f"👥 المشتركون المفعّلون: `{len(allowed)}`\n"
                f"🗂️ قواعد البيانات: `{len(dbs)}`\n"
                f"💾 الحجم الكلي للبيانات: `{total_sz:.1f} MB`\n"
                f"🕐 وقت الاستعلام: `{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
                parse_mode="Markdown",
                reply_markup=back_keyboard("back_admin")
            )

        elif data == "admin_users":
            allowed = get_allowed_users()
            if not allowed:
                await q.edit_message_text(
                    "👥 لا يوجد مشتركون مفعّلون حالياً.",
                    reply_markup=back_keyboard("back_admin")
                )
                return
            rows = []
            for u in sorted(allowed):
                stats = get_db_stats(u)
                label = f"🗂️ {u}" if stats else f"⭕ {u}"
                rows.append([InlineKeyboardButton(f"❌ حظر {label}", callback_data=f"block_{u}")])
            rows.append([InlineKeyboardButton("🔙 العودة", callback_data="back_admin")])
            await q.edit_message_text(
                f"👥 *المشتركون ({len(allowed)}):*\n_(🗂️ = لديه ملف | ⭕ = بدون ملف)_",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(rows)
            )

        elif data == "admin_broadcast":
            context.user_data["action"] = "broadcast"
            await q.edit_message_text("📢 أرسل رسالة الإذاعة الآن (نص أو صورة أو ملف):")

        elif data == "admin_clean":
            removed = 0
            for f in os.listdir("."):
                if f.startswith(("temp_", "user_")) and not f.endswith(".db"):
                    try:
                        os.remove(f)
                        removed += 1
                    except Exception:
                        pass
            await q.edit_message_text(
                f"🧹 تم تنظيف `{removed}` ملف مؤقت.",
                parse_mode="Markdown",
                reply_markup=back_keyboard("back_admin")
            )

        elif data == "admin_logs":
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r", encoding="utf-8") as lf:
                    lines = lf.readlines()
                last = "".join(lines[-20:]) if lines else "السجل فارغ."
                await q.edit_message_text(
                    f"📋 *آخر 20 سطر من السجل:*\n\n```\n{last[:3000]}\n```",
                    parse_mode="Markdown",
                    reply_markup=back_keyboard("back_admin")
                )
            else:
                await q.edit_message_text("لا يوجد ملف سجل بعد.", reply_markup=back_keyboard("back_admin"))

        elif data == "admin_help":
            await q.edit_message_text(
                "⚙️ *الأوامر النصية المتاحة:*\n\n"
                "• `تفعيل 12345` — تفعيل مستخدم\n"
                "• `تعطيل 12345` — حظر مستخدم ومسح بياناته\n"
                "• `تصفير 12345` — مسح ملف المستخدم فقط\n"
                "• `معلومات 12345` — عرض إحصائيات مستخدم\n"
                "• `قائمة` — عرض كل المشتركين",
                parse_mode="Markdown",
                reply_markup=back_keyboard("back_admin")
            )

        elif data == "back_admin":
            await q.edit_message_text(
                "👑 *لوحة التحكم الإدارية:*",
                parse_mode="Markdown",
                reply_markup=admin_main_keyboard()
            )

        elif data.startswith("act_"):
            target = int(data.split("_")[1])
            allow_user(target)
            await q.edit_message_text(f"✅ تم تفعيل المستخدم `{target}`.", parse_mode="Markdown")
            try:
                await context.bot.send_message(
                    target,
                    "🎉 *تم تفعيل حسابك!* يمكنك استخدام البوت الآن.\n\nأرسل /start للبدء.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        elif data.startswith("block_"):
            target = data.split("_")[1]
            block_user(target)
            await q.edit_message_text(
                f"🚫 تم حظر المستخدم `{target}` ومسح بياناته.",
                parse_mode="Markdown",
                reply_markup=back_keyboard("back_admin")
            )

        elif data == "noop":
            await q.edit_message_text("تم التجاهل.")

    # --- مستخدم مفعّل ---
    if is_allowed(uid):

        if data == "user_status":
            stats = get_db_stats(uid)
            if stats:
                text = (
                    f"📂 *حالة ملفك:* نشط ✅\n\n"
                    f"📊 الأسطر: `{stats['lines']:,}`\n"
                    f"💾 الحجم: `{stats['size_mb']} MB`"
                )
            else:
                text = "❌ لا يوجد ملف مرفوع حالياً. أرسل ملف `.txt` للبدء."
            await q.edit_message_text(text, parse_mode="Markdown", reply_markup=back_keyboard("back_user"))

        elif data == "user_delete":
            _delete_user_db(uid)
            await q.edit_message_text(
                "🗑️ تم مسح ملفك بنجاح.",
                reply_markup=back_keyboard("back_user")
            )

        elif data == "user_help":
            await q.edit_message_text(
                "📖 *طريقة الاستخدام:*\n\n"
                "1️⃣ أرسل ملف `.txt` (مهما كان حجمه).\n"
                "2️⃣ انتظر رسالة تأكيد البناء.\n"
                "3️⃣ أرسل الأرقام المراد فحصها (كل رقم في سطر).\n"
                "4️⃣ ستصلك النتائج كملف `.txt`.\n\n"
                "💡 *مثال:* لو الملف يحتوي أرقام 16 خانة وأرسلت 6 أرقام كبادئة، سيُعيد كل الأسطر التي تبدأ بها.",
                parse_mode="Markdown",
                reply_markup=back_keyboard("back_user")
            )

        elif data == "back_user":
            await q.edit_message_text(
                "🎯 *القائمة الرئيسية:*",
                parse_mode="Markdown",
                reply_markup=user_main_keyboard()
            )

# ============================================================
# 💬 معالجة الرسائل النصية
# ============================================================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text.strip()

    # --- إذاعة الآدمن ---
    if uid == ADMIN_ID and context.user_data.get("action") == "broadcast":
        context.user_data["action"] = None
        allowed = get_allowed_users()
        success = 0
        for u in allowed:
            try:
                await context.bot.send_message(
                    u,
                    f"📢 *إشعار من الإدارة:*\n\n{text}",
                    parse_mode="Markdown"
                )
                success += 1
            except Exception:
                pass
        await update.message.reply_text(f"✅ تم الإرسال لـ {success}/{len(allowed)} مشترك.")
        return

    # --- أوامر الآدمن النصية ---
    if uid == ADMIN_ID:
        parts = text.split()

        if parts[0] == "تفعيل" and len(parts) == 2 and parts[1].isdigit():
            allow_user(parts[1])
            await update.message.reply_text(f"✅ تم تفعيل `{parts[1]}`.", parse_mode="Markdown")
            try:
                await context.bot.send_message(int(parts[1]), "🎉 تم تفعيل حسابك! أرسل /start للبدء.")
            except Exception:
                pass
            return

        if parts[0] == "تعطيل" and len(parts) == 2 and parts[1].isdigit():
            block_user(parts[1])
            await update.message.reply_text(f"🚫 تم حظر `{parts[1]}`.", parse_mode="Markdown")
            return

        if parts[0] == "تصفير" and len(parts) == 2 and parts[1].isdigit():
            _delete_user_db(parts[1])
            await update.message.reply_text(f"🧹 تم تصفير بيانات `{parts[1]}`.", parse_mode="Markdown")
            return

        if parts[0] == "معلومات" and len(parts) == 2 and parts[1].isdigit():
            target = int(parts[1])
            stats = get_db_stats(target)
            active = "✅ مفعّل" if target in get_allowed_users() else "❌ غير مفعّل"
            if stats:
                await update.message.reply_text(
                    f"📋 *معلومات المستخدم {target}:*\n\n"
                    f"الحالة: {active}\n"
                    f"الأسطر: `{stats['lines']:,}`\n"
                    f"الحجم: `{stats['size_mb']} MB`",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    f"📋 المستخدم `{target}`: {active} | لا يوجد ملف.",
                    parse_mode="Markdown"
                )
            return

        if text == "قائمة":
            allowed = get_allowed_users()
            if not allowed:
                await update.message.reply_text("لا يوجد مشتركون.")
            else:
                msg = "👥 *المشتركون:*\n" + "\n".join(f"• `{u}`" for u in sorted(allowed))
                await update.message.reply_text(msg, parse_mode="Markdown")
            return

    # --- فحص الأرقام ---
    if not is_allowed(uid):
        return

    numbers = [ln.strip() for ln in text.split("\n") if ln.strip().isdigit()]
    if not numbers:
        return

    if not os.path.exists(f"data_{uid}.db"):
        await update.message.reply_text("❌ أرسل ملف `.txt` أولاً ثم ابدأ الفحص.")
        return

    status = await update.message.reply_text(f"⏳ جاري فحص `{len(numbers)}` رقم...")

    results = search_db(uid, numbers)

    if results:
        out_path = f"results_{uid}.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(results))

        with open(out_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                caption=(
                    f"✅ *نتائج الفحص:*\n\n"
                    f"🔢 أرقام مُفحوصة: `{len(numbers)}`\n"
                    f"🎯 أسطر مطابقة: `{len(results):,}`"
                ),
                parse_mode="Markdown"
            )

        try:
            os.remove(out_path)
        except Exception:
            pass

        log.info(f"فحص ناجح | uid={uid} | أرقام={len(numbers)} | نتائج={len(results)}")
    else:
        await update.message.reply_text(
            f"❌ لم يُعثر على نتائج للأرقام المرسلة.\n"
            f"_(تأكد أن الأرقام موجودة كبادئة في ملفك)_",
            parse_mode="Markdown"
        )
        log.info(f"فحص بلا نتائج | uid={uid} | أرقام={numbers[:5]}")

    try:
        await context.bot.delete_message(update.effective_chat.id, status.message_id)
    except Exception:
        pass

# ============================================================
# 📥 معالجة رفع الملفات
# ============================================================
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name
    uname = f"@{update.effective_user.username}" if update.effective_user.username else "بدون يوزر"

    if not is_allowed(uid):
        return

    doc = update.message.document
    if not doc.file_name.endswith(".txt"):
        await update.message.reply_text("⚠️ يُقبل فقط ملفات `.txt`.")
        return

    status = await update.message.reply_text("⏳ جاري تحميل الملف...")

    temp_path = f"temp_{uid}.txt"

    try:
        if not telethon_client.is_connected():
            await telethon_client.connect()

        tg_msg = await telethon_client.get_messages(
            update.effective_chat.id,
            ids=update.message.message_id
        )
        await telethon_client.download_media(tg_msg, file=temp_path)

        # انتظار اكتمال الملف
        for _ in range(15):
            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                break
            await asyncio.sleep(3)
        else:
            await status.edit_text("❌ فشل التحميل. حاول مرة أخرى.")
            return

        await status.edit_text("📥 تم التحميل. جاري بناء الفهرسة...")

        total = await asyncio.to_thread(build_user_db, uid, temp_path)

        await status.edit_text(
            f"✅ *تم بنجاح!*\n\n"
            f"📊 الأسطر المفهرسة: `{total:,}`\n"
            f"🚀 يمكنك الآن إرسال الأرقام للفحص.",
            parse_mode="Markdown"
        )

        log.info(f"رفع ملف | uid={uid} | أسطر={total:,}")

        if uid != ADMIN_ID:
            await context.bot.send_message(
                ADMIN_ID,
                f"📥 *رفع ملف جديد:*\n\n"
                f"👤 {name} ({uname})\n"
                f"🆔 `{uid}`\n"
                f"📊 أسطر: `{total:,}`",
                parse_mode="Markdown"
            )

    except Exception as e:
        log.error(f"خطأ في رفع الملف uid={uid}: {e}")
        await status.edit_text(f"❌ خطأ: `{str(e)[:200]}`", parse_mode="Markdown")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

# ============================================================
# 🏁 تشغيل البوت
# ============================================================
async def post_init(app: Application):
    """تشغيل Telethon بعد بدء التطبيق"""
    if not telethon_client.is_connected():
        await telethon_client.start()
    log.info("✅ Telethon متصل وجاهز.")

async def post_shutdown(app: Application):
    """إغلاق Telethon عند إيقاف البوت"""
    if telethon_client.is_connected():
        await telethon_client.disconnect()
    log.info("🔴 Telethon قُطع الاتصال.")

if __name__ == "__main__":
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
        handle_text
    ))
    app.add_handler(MessageHandler(
        filters.Document.ALL & filters.ChatType.PRIVATE,
        handle_document
    ))

    log.info("🚀 البوت يعمل الآن...")
    app.run_polling(drop_pending_updates=True)

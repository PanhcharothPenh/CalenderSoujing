import os
import datetime
import logging
import asyncio
import threading
import urllib.request
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Set
import uuid
import pytz

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from google_calendar import GoogleCalendarManager, find_json_credentials

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global instances
calendar_mgr = GoogleCalendarManager()
sent_reminders: Set[str] = set()

def get_main_keyboard(is_admin_user=False) -> ReplyKeyboardMarkup:
    """Generate permanent Khmer Telegram keyboard buttons."""
    if is_admin_user:
        keyboard = [
            [KeyboardButton("📅 Event ថ្ងៃនេះ"), KeyboardButton("📆 Event ៧ថ្ងៃខាងមុខ")],
            [KeyboardButton("📊 តារាងពិន្ទុ"), KeyboardButton("📢 ផ្សាយតារាងពិន្ទុ")],
            [KeyboardButton("🔔 ចុះឈ្មោះទទួលសារ"), KeyboardButton("🔕 លុបការចុះឈ្មោះ")],
            [KeyboardButton("ℹ️ ការណែនាំ")]
        ]
    else:
        keyboard = [
            [KeyboardButton("📅 Event ថ្ងៃនេះ"), KeyboardButton("📆 Event ៧ថ្ងៃខាងមុខ")],
            [KeyboardButton("📊 តារាងពិន្ទុ"), KeyboardButton("🔔 ចុះឈ្មោះទទួលសារ")],
            [KeyboardButton("🔕 លុបការចុះឈ្មោះ"), KeyboardButton("ℹ️ ការណែនាំ")]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Lightweight HTTP handler for Render/Cloud free Web Service health checks."""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK - Google Calendar Telegram Bot is running 24/7!")

    def log_message(self, format, *args):
        # Suppress noisy HTTP GET access logs
        pass

def start_health_server():
    """Start background HTTP server for Render/Cloud web service health check."""
    port = int(os.getenv("PORT", 8080))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Health check HTTP server started on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Error starting health check HTTP server: {e}")

def start_keep_alive():
    """Background thread to self-ping HTTP server every 3 minutes to keep Render Free Web Service active 24/7."""
    port = int(os.getenv("PORT", 8080))
    url = f"http://127.0.0.1:{port}/"
    time.sleep(10)  # Wait for initial HTTP server startup
    while True:
        try:
            time.sleep(180)  # Ping every 3 minutes
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                pass
            logger.info("Self-ping keep-alive successful.")
        except Exception as e:
            logger.debug(f"Keep-alive ping exception: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with auto-subscription."""
    chat_id = update.effective_chat.id
    is_new = config.add_subscriber(chat_id)
    
    status_text = (
        "🎉 <b>អ្នកបានចុះឈ្មោះទទួលការជូនដំណឹងដោយស្វ័យប្រវត្តិរួចរាល់ហើយ!</b>"
        if is_new else
        "✅ <b>អ្នកកំពុងស្ថិតក្នុងបញ្ជីទទួលការជូនដំណឹងស្រាប់!</b>"
    )

    welcome_text = (
        f"👋 <b>ជម្រាបសួរ! ខ្ញុំជា Telegram Bot ជូនដំណឹងពី Google Calendar</b>\n\n"
        f"{status_text}\n"
        f"🆔 <b>Chat ID របស់អ្នក:</b> <code>{chat_id}</code>\n\n"
        f"<b>👇 សូមចុចប៊ូតុងខាងក្រោមដើម្បីប្រើប្រាស់៖</b>"
    )
    await update.message.reply_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop or /unsubscribe command."""
    chat_id = update.effective_chat.id
    removed = config.remove_subscriber(chat_id)
    if removed:
        await update.message.reply_text(
            "🔕 <b>អ្នកបានលុបការចុះឈ្មោះទទួលសារជូនដំណឹងរួចរាល់ហើយ!</b>\n"
            "ប្រសិនបើចង់ចុះឈ្មោះសារជាថ្មី សូមចុចប៊ូតុង 🔔 ចុះឈ្មោះទទួលសារ",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "ℹ️ អ្នកមិនទាន់បានចុះឈ្មោះទទួលសារនៅឡើយទេ។ ចុចប៊ូតុង 🔔 ចុះឈ្មោះទទួលសារ ដើម្បីចុះឈ្មោះ។",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = (
        "ℹ️ <b>ការណែនាំប្រើប្រាស់ Bot:</b>\n\n"
        "• 📅 Event ថ្ងៃនេះ - បង្ហាញកាលវិភាគថ្ងៃនេះ\n"
        "• 📆 Event ៧ថ្ងៃខាងមុខ - បង្ហាញកាលវិភាគ ៧ថ្ងៃ\n"
        "• 📊 តារាងពិន្ទុ - មើលតារាងពិន្ទុប្រចាំខែចុងក្រោយ\n"
        "• 🔔 ចុះឈ្មោះទទួលសារ - ចុះឈ្មោះទទួលសាររំលឹក\n"
        "• 🔕 លុបការចុះឈ្មោះ - ឈប់ទទួលសារ\n"
        "• 📊 ស្ថានភាពប្រព័ន្ធ (/status) - ពិនិត្យស្ថានភាព Bot\n\n"
        "👑 <b>សម្រាប់ Admin:</b>\n"
        "• <code>/broadcast [សារ/រូប/ឯកសារ]</code> - ផ្សាយដំណឹង/តារាងពិន្ទុទៅកាន់ Subscribers ទាំងអស់\n"
    )
    await update.message.reply_text(
        help_text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

async def score_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /score command or 📊 តារាងពិន្ទុ button."""
    if not update.message:
        return
    chat_id = update.message.chat_id
    score_data = config.get_latest_score()
    reply_markup = get_main_keyboard()

    if not score_data:
        empty_msg = (
            "📊 <b>តារាងពិន្ទុប្រចាំខែ (Monthly Score Report)</b>\n\n"
            "ℹ️ បច្ចុប្បន្នមិនទាន់មានការបង្ហោះតារាងពិន្ទុថ្មីនៅឡើយទេ។\n"
            "សូមរង់ចាំការជូនដំណឹងជាផ្លូវការ ឬសួរលោកគ្រូ/អ្នកគ្រូ។"
        )
        await update.message.reply_text(empty_msg, parse_mode="HTML", reply_markup=reply_markup)
        return

    stype = score_data.get("type")
    if stype == "photo":
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=score_data.get("file_id"),
            caption=score_data.get("caption", "📊 <b>តារាងពិន្ទុប្រចាំខែ</b>"),
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    elif stype == "document":
        await context.bot.send_document(
            chat_id=chat_id,
            document=score_data.get("file_id"),
            caption=score_data.get("caption", "📊 <b>តារាងពិន្ទុប្រចាំខែ</b>"),
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    elif stype == "text":
        await update.message.reply_text(
            score_data.get("text", "📊 <b>តារាងពិន្ទុប្រចាំខែ</b>"),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=reply_markup
        )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast and /announce command for admins."""
    if not update.message:
        return
    chat_id = update.message.chat_id
    reply_markup = get_main_keyboard()

    if not config.is_admin(chat_id):
        await update.message.reply_text(
            "⛔ <b>អ្នកមិនមានសិទ្ធិប្រើប្រាស់មុខងារផ្សាយដំណឹងនេះទេ!</b>\n\n"
            "មុខងារ <code>/broadcast</code> ត្រូវបានកំណត់សម្រាប់តែ <b>Administrator</b> ប៉ុណ្ណោះ។",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        return

    subscribers = config.load_subscribers()
    if not subscribers:
        await update.message.reply_text(
            "⚠️ <b>មិនទាន់មាន Subscribers ណាមួយបានចុះឈ្មោះនៅឡើយទេ!</b>",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        return

    tz = pytz.timezone(config.TIMEZONE)
    now_str = datetime.datetime.now(tz).strftime('%d/%m/%Y %I:%M %p')

    # Parse arguments
    args_text = " ".join(context.args) if context.args else ""
    caption = update.message.caption or ""
    photos = update.message.photo
    document = update.message.document
    reply_to = update.message.reply_to_message

    # Clean command prefix if sent in caption
    if caption:
        for cmd in ["/broadcast", "/announce", "/score_broadcast", "/post_score", "📢 ផ្សាយដំណឹង"]:
            if caption.lower().startswith(cmd.lower()):
                caption = caption[len(cmd):].strip()
                break

    broadcast_payload = args_text or caption

    if not broadcast_payload and not photos and not document and not reply_to:
        help_broadcast = (
            "ℹ️ <b>ការណែនាំអំពីការផ្សាយដំណឹង / តារាងពិន្ទុ (/broadcast):</b>\n\n"
            "1️⃣ <b>ផ្ញើរូបភាព ឬ File PDF តារាងពិន្ទុ:</b>\n"
            "   • ជ្រើសរើសរូបភាព ឬ File រួចដាក់ Caption: <code>/broadcast [ព័ត៌មានបន្ថែម]</code>\n\n"
            "2️⃣ <b>ផ្ញើសារជាអក្សរជូនដំណឹង:</b>\n"
            "   • វាយ: <code>/broadcast [ខ្លឹមសារសារ]</code>\n\n"
            "3️⃣ <b>Reply លើសារចាស់:</b>\n"
            "   • ចុច Reply លើរូបភាព ឬ File ណាមួយ រួចវាយ: <code>/broadcast</code>\n\n"
            "<i>* សារ ឬតារាងពិន្ទុនឹងត្រូវផ្ញើជូនសមាជិក (Subscribers) ទាំងអស់ភ្លាមៗ!</i>"
        )
        await update.message.reply_text(help_broadcast, parse_mode="HTML", reply_markup=reply_markup)
        return

    sent_count = 0
    fail_count = 0

    # 1. Direct Photo
    if photos:
        file_id = photos[-1].file_id
        header = "📢 <b>តារាងពិន្ទុប្រចាំខែ (Monthly Score Report)</b> 📊\n"
        final_caption = f"{header}\n{broadcast_payload}\n\n🗓️ <i>{now_str}</i>" if broadcast_payload else f"{header}\nសូមពិនិត្យមើលតារាងពិន្ទុខាងលើ!\n\n🗓️ <i>{now_str}</i>"

        for sub_id in subscribers:
            try:
                await context.bot.send_photo(chat_id=sub_id, photo=file_id, caption=final_caption, parse_mode="HTML")
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to broadcast photo to {sub_id}: {e}")
                fail_count += 1

        config.save_latest_score({
            "type": "photo",
            "file_id": file_id,
            "caption": final_caption,
            "date": now_str,
            "sender_id": chat_id
        })

        report = (
            "✅ <b>បានផ្សាយដំណឹង/តារាងពិន្ទុ (រូបភាព) ជោគជ័យ!</b>\n\n"
            f"👥 អ្នកទទួលបាន: <b>{sent_count}</b> នាក់\n"
            f"⚠️ បរាជ័យ: <b>{fail_count}</b> នាក់\n"
            f"🕒 កាលបរិច្ឆេទ: <b>{now_str}</b>"
        )
        await update.message.reply_text(report, parse_mode="HTML", reply_markup=reply_markup)
        return

    # 2. Direct Document
    elif document:
        file_id = document.file_id
        file_name = document.file_name or "Monthly_Score.pdf"
        header = "📢 <b>តារាងពិន្ទុប្រចាំខែ (Monthly Score Report)</b> 📊\n"
        final_caption = f"{header}\n📄 ឯកសារ: <code>{file_name}</code>\n\n{broadcast_payload}\n\n🗓️ <i>{now_str}</i>" if broadcast_payload else f"{header}\n📄 ឯកសារ: <code>{file_name}</code>\n\nសូមទាញយកឯកសារតារាងពិន្ទុខាងលើដើម្បីពិនិត្យមើល!\n\n🗓️ <i>{now_str}</i>"

        for sub_id in subscribers:
            try:
                await context.bot.send_document(chat_id=sub_id, document=file_id, caption=final_caption, parse_mode="HTML")
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to broadcast document to {sub_id}: {e}")
                fail_count += 1

        config.save_latest_score({
            "type": "document",
            "file_id": file_id,
            "file_name": file_name,
            "caption": final_caption,
            "date": now_str,
            "sender_id": chat_id
        })

        report = (
            "✅ <b>បានផ្សាយដំណឹង/តារាងពិន្ទុ (ឯកសារ) ជោគជ័យ!</b>\n\n"
            f"📄 ឯកសារ: <code>{file_name}</code>\n"
            f"👥 អ្នកទទួលបាន: <b>{sent_count}</b> នាក់\n"
            f"⚠️ បរាជ័យ: <b>{fail_count}</b> នាក់\n"
            f"🕒 កាលបរិច្ឆេទ: <b>{now_str}</b>"
        )
        await update.message.reply_text(report, parse_mode="HTML", reply_markup=reply_markup)
        return

    # 3. Reply to existing message
    elif reply_to:
        reply_photo = reply_to.photo
        reply_doc = reply_to.document
        reply_cap = reply_to.caption or ""
        reply_txt = reply_to.text or ""

        if reply_photo:
            file_id = reply_photo[-1].file_id
            content = broadcast_payload or reply_cap or "សូមពិនិត្យមើលតារាងពិន្ទុខាងលើ!"
            final_caption = f"📢 <b>តារាងពិន្ទុប្រចាំខែ (Monthly Score Report)</b> 📊\n\n{content}\n\n🗓️ <i>{now_str}</i>"
            for sub_id in subscribers:
                try:
                    await context.bot.send_photo(chat_id=sub_id, photo=file_id, caption=final_caption, parse_mode="HTML")
                    sent_count += 1
                except Exception as e:
                    fail_count += 1
            config.save_latest_score({"type": "photo", "file_id": file_id, "caption": final_caption, "date": now_str, "sender_id": chat_id})

        elif reply_doc:
            file_id = reply_doc.file_id
            file_name = reply_doc.file_name or "Monthly_Score.pdf"
            content = broadcast_payload or reply_cap or "សូមទាញយកឯកសារតារាងពិន្ទុខាងលើដើម្បីពិនិត្យមើល!"
            final_caption = f"📢 <b>តារាងពិន្ទុប្រចាំខែ (Monthly Score Report)</b> 📊\n📄 ឯកសារ: <code>{file_name}</code>\n\n{content}\n\n🗓️ <i>{now_str}</i>"
            for sub_id in subscribers:
                try:
                    await context.bot.send_document(chat_id=sub_id, document=file_id, caption=final_caption, parse_mode="HTML")
                    sent_count += 1
                except Exception as e:
                    fail_count += 1
            config.save_latest_score({"type": "document", "file_id": file_id, "file_name": file_name, "caption": final_caption, "date": now_str, "sender_id": chat_id})

        else:
            content = broadcast_payload or reply_txt
            final_text = f"📢 <b>សេចក្តីជូនដំណឹង / តារាងពិន្ទុប្រចាំខែ</b> 📊\n\n{content}\n\n🗓️ <i>{now_str}</i>"
            for sub_id in subscribers:
                try:
                    await context.bot.send_message(chat_id=sub_id, text=final_text, parse_mode="HTML", disable_web_page_preview=True)
                    sent_count += 1
                except Exception as e:
                    fail_count += 1
            config.save_latest_score({"type": "text", "text": final_text, "date": now_str, "sender_id": chat_id})

        report = (
            "✅ <b>បានផ្សាយដំណឹង/តារាងពិន្ទុជោគជ័យ!</b>\n\n"
            f"👥 អ្នកទទួលបាន: <b>{sent_count}</b> នាក់\n"
            f"⚠️ បរាជ័យ: <b>{fail_count}</b> នាក់\n"
            f"🕒 កាលបរិច្ឆេទ: <b>{now_str}</b>"
        )
        await update.message.reply_text(report, parse_mode="HTML", reply_markup=reply_markup)
        return

    # 4. Text broadcast
    else:
        final_text = (
            "📢 <b>សេចក្តីជូនដំណឹង / តារាងពិន្ទុប្រចាំខែ</b> 📊\n\n"
            f"{broadcast_payload}\n\n"
            f"🗓️ <i>{now_str}</i>"
        )
        for sub_id in subscribers:
            try:
                await context.bot.send_message(chat_id=sub_id, text=final_text, parse_mode="HTML", disable_web_page_preview=True)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to broadcast text to {sub_id}: {e}")
                fail_count += 1

        config.save_latest_score({
            "type": "text",
            "text": final_text,
            "date": now_str,
            "sender_id": chat_id
        })

        report = (
            "✅ <b>បានផ្សាយដំណឹងជាអក្សរជោគជ័យ!</b>\n\n"
            f"👥 អ្នកទទួលបាន: <b>{sent_count}</b> នាក់\n"
            f"⚠️ បរាជ័យ: <b>{fail_count}</b> នាក់\n"
            f"🕒 កាលបរិច្ឆេទ: <b>{now_str}</b>"
        )
        await update.message.reply_text(report, parse_mode="HTML", reply_markup=reply_markup)
        return

async def handle_media_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Intercept media uploads. If Admin, provide 1-click broadcast confirmation."""
    if not update.message:
        return
    chat_id = update.message.chat_id
    if not config.is_admin(chat_id):
        return

    caption = update.message.caption or ""
    photos = update.message.photo
    document = update.message.document

    # If explicit /broadcast caption used, trigger immediate broadcast
    if any(caption.lower().startswith(cmd) for cmd in ["/broadcast", "/announce", "/score_broadcast", "/post_score", "📢 ផ្សាយដំណឹង"]):
        await broadcast_command(update, context)
        return

    # Easy 1-Click: Admin sent photo or document without command
    bcast_key = str(uuid.uuid4())[:8]
    file_type = "photo" if photos else "document"
    file_id = photos[-1].file_id if photos else document.file_id
    file_name = document.file_name or "Monthly_Score.pdf" if document else None

    config.save_pending_broadcast(bcast_key, {
        "type": file_type,
        "file_id": file_id,
        "file_name": file_name,
        "caption": caption,
        "admin_id": chat_id
    })

    subscribers = config.load_subscribers()
    type_name = "រូបភាពតារាងពិន្ទុ (Photo)" if photos else f"ឯកសារ ({file_name})"
    confirm_text = (
        "📥 <b>បានទទួលឯកសារ/រូបភាពតារាងពិន្ទុ!</b>\n\n"
        f"📄 ប្រភេទ: <b>{type_name}</b>\n"
        f"👥 សិស្សទទួលសារ (Subscribers): <b>{len(subscribers)} នាក់</b>\n"
        f"💬 ចំណាំ (Caption): <i>{caption or 'គ្មាន'}</i>\n\n"
        "👇 <b>តើអ្នកចង់ផ្សាយដំណឹងនេះទៅកាន់សិស្សទាំងអស់ដែរឬទេ?</b>"
    )
    inline_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 ផ្សាយទៅកាន់សិស្សទាំងអស់", callback_data=f"bcast:{bcast_key}")],
        [InlineKeyboardButton("❌ បោះបង់", callback_data=f"cancel:{bcast_key}")]
    ])
    await update.message.reply_text(
        confirm_text,
        parse_mode="HTML",
        reply_markup=inline_kb
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 1-click broadcast confirmation or cancel."""
    query = update.callback_query
    if not query:
        return

    user_id = query.from_user.id
    if not config.is_admin(user_id):
        await query.answer("⛔ អ្នកមិនមានសិទ្ធិប្រើប្រាស់មុខងារនេះទេ!", show_alert=True)
        return

    data = query.data or ""
    if data.startswith("bcast:"):
        key = data.split(":", 1)[1]
        pending = config.get_pending_broadcast(key)
        if not pending:
            await query.answer("⚠️ ឯកសារនេះផុតកំណត់ ឬត្រូវបានផ្សាយរួចហើយ!", show_alert=True)
            return

        await query.answer("🚀 កំពុងផ្សាយដំណឹងទៅកាន់សិស្សទាំងអស់...")
        subscribers = config.load_subscribers()
        tz = pytz.timezone(config.TIMEZONE)
        now_str = datetime.datetime.now(tz).strftime('%d/%m/%Y %I:%M %p')

        b_type = pending.get("type")
        file_id = pending.get("file_id")
        file_name = pending.get("file_name", "Monthly_Score.pdf")
        user_caption = pending.get("caption", "").strip()

        header = "📢 <b>តារាងពិន្ទុប្រចាំខែ (Monthly Score Report)</b> 📊\n"
        final_caption = f"{header}\n{user_caption}\n\n🗓️ <i>{now_str}</i>" if user_caption else f"{header}\nសូមពិនិត្យមើលតារាងពិន្ទុខាងលើ!\n\n🗓️ <i>{now_str}</i>"

        sent_count = 0
        fail_count = 0

        if b_type == "photo":
            for sub_id in subscribers:
                try:
                    await context.bot.send_photo(chat_id=sub_id, photo=file_id, caption=final_caption, parse_mode="HTML")
                    sent_count += 1
                except Exception:
                    fail_count += 1
            config.save_latest_score({
                "type": "photo",
                "file_id": file_id,
                "caption": final_caption,
                "date": now_str,
                "sender_id": user_id
            })

        elif b_type == "document":
            doc_caption = f"{header}\n📄 ឯកសារ: <code>{file_name}</code>\n\n{user_caption or 'សូមទាញយកឯកសារតារាងពិន្ទុខាងលើ!'}\n\n🗓️ <i>{now_str}</i>"
            for sub_id in subscribers:
                try:
                    await context.bot.send_document(chat_id=sub_id, document=file_id, caption=doc_caption, parse_mode="HTML")
                    sent_count += 1
                except Exception:
                    fail_count += 1
            config.save_latest_score({
                "type": "document",
                "file_id": file_id,
                "file_name": file_name,
                "caption": doc_caption,
                "date": now_str,
                "sender_id": user_id
            })

        config.remove_pending_broadcast(key)

        report = (
            "✅ <b>បានផ្សាយដំណឹង/តារាងពិន្ទុជូនសិស្សទាំងអស់ជោគជ័យ!</b>\n\n"
            f"👥 អ្នកទទួលបាន: <b>{sent_count}</b> នាក់\n"
            f"⚠️ បរាជ័យ: <b>{fail_count}</b> នាក់\n"
            f"🕒 កាលបរិច្ឆេទ: <b>{now_str}</b>"
        )
        try:
            await query.edit_message_text(text=report, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(text=report, parse_mode="HTML")

    elif data.startswith("cancel:"):
        key = data.split(":", 1)[1]
        config.remove_pending_broadcast(key)
        await query.answer("បានបោះបង់!")
        try:
            await query.edit_message_text(text="❌ <b>បានបោះបង់ការផ្សាយដំណឹង។</b>", parse_mode="HTML")
        except Exception:
            pass

async def admin_prompt_score_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Guide admin on how to easily send score file."""
    if not update.message:
        return
    is_admin = config.is_admin(update.message.chat_id)
    if not is_admin:
        await update.message.reply_text(
            "⛔ <b>មុខងារនេះសម្រាប់តែ Administrator ប៉ុណ្ណោះ!</b>",
            parse_mode="HTML"
        )
        return
    prompt_msg = (
        "📤 <b>សូមផ្ញើរូបភាព ឬ File PDF តារាងពិន្ទុមកកាន់ទីនេះ៖</b>\n\n"
        "• អ្នកគ្រាន់តែផ្ញើ ឬ Forward រូបភាព ឬ File PDF ចូលក្នុង Chat នេះ (ដោយមិនបាច់វាយពាក្យអ្វីទាំងអស់)\n"
        "• រួច Bot នឹងបង្ហាញប៊ូតុង <code>[📢 ផ្សាយទៅកាន់សិស្សទាំងអស់]</code> ឱ្យចុចបញ្ជាក់ភ្លាមៗ! ⚡"
    )
    await update.message.reply_text(
        prompt_msg,
        parse_mode="HTML",
        reply_markup=get_main_keyboard(is_admin_user=True)
    )

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /today command."""
    try:
        events = calendar_mgr.get_today_events()
        msg = calendar_mgr.format_daily_schedule(events)
        await update.message.reply_text(
            msg,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Error fetching today events: {e}")
        await update.message.reply_text(
            f"❌ <b>មានបញ្ហាក្នុងការទាញយក Event:</b>\n<code>{e}</code>",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

async def upcoming_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /upcoming command."""
    try:
        events = calendar_mgr.get_upcoming_events(days=7)
        msg = calendar_mgr.format_upcoming_schedule(events)
        await update.message.reply_text(
            msg,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Error fetching upcoming events: {e}")
        await update.message.reply_text(
            f"❌ <b>មានបញ្ហាក្នុងការទាញយក Event:</b>\n<code>{e}</code>",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    missing = config.validate_config()
    has_json = bool(find_json_credentials())
    subscribers = config.load_subscribers()
    latest_score = config.get_latest_score()
    score_info = f"{latest_score.get('date', 'មិនទាន់មាន')} ({latest_score.get('type', 'none')})" if latest_score else "មិនទាន់មាន"

    try:
        events = calendar_mgr.get_today_events()
        status_msg = (
            "✅ <b>ប្រព័ន្ធដំណើរការជាប្រក្រតី! (System Status OK)</b>\n\n"
            "• 🔑 <b>Google Credentials:</b> " + ("ភ្ជាប់រួចរាល់ (Connected ✅)" if has_json else "មិនទាន់បានភ្ជាប់ ❌") + "\n"
            f"• 📅 <b>Calendar ID:</b> <code>{config.GOOGLE_CALENDAR_ID}</code>\n"
            f"• ⏰ <b>Timezone:</b> {config.TIMEZONE}\n"
            f"• 👥 <b>អ្នកចុះឈ្មោះទទួលសារ ({len(subscribers)}):</b> <code>{', '.join(subscribers) if subscribers else 'គ្មាន'}</code>\n"
            f"• 📊 <b>តារាងពិន្ទុចុងក្រោយ:</b> {score_info}\n"
            f"• ☀️ <b>Events ថ្ងៃនេះ:</b> {len(events)} Event\n"
        )
        await update.message.reply_text(
            status_msg,
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        status_msg = (
            "⚠️ <b>ស្ថានភាពប្រព័ន្ធ (System Status):</b>\n\n"
            "• 🔑 <b>Google Credentials:</b> " + ("ភ្ជាប់រួចរាល់ (Connected ✅)" if has_json else "មិនទាន់បានភ្ជាប់ ❌") + "\n"
            f"• ❌ <b>Error:</b> <code>{e}</code>\n"
        )
        await update.message.reply_text(
            status_msg,
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Flexible matching router for Telegram Keyboard Button clicks."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    
    if "Event ថ្ងៃនេះ" in text or "ថ្ងៃនេះ" in text:
        await today_command(update, context)
    elif "Event ៧ថ្ងៃ" in text or "៧ថ្ងៃ" in text or "ជិតមកដល់" in text:
        await upcoming_command(update, context)
    elif "ផ្សាយតារាងពិន្ទុ" in text:
        await admin_prompt_score_upload(update, context)
    elif "តារាងពិន្ទុ" in text or "ពិន្ទុ" in text:
        await score_command(update, context)
    elif "ចុះឈ្មោះទទួលសារ" in text or "ចុះឈ្មោះ" in text:
        await start_command(update, context)
    elif "លុបការចុះឈ្មោះ" in text or "លុប" in text:
        await stop_command(update, context)
    elif "ស្ថានភាព" in text or "status" in text.lower():
        await status_command(update, context)
    elif "ការណែនាំ" in text or "help" in text.lower():
        await help_command(update, context)

async def check_upcoming_reminders(bot):
    """Background task to check and send reminders for events starting soon to all subscribers."""
    subscribers = config.load_subscribers()
    if not subscribers:
        return

    try:
        tz = pytz.timezone(config.TIMEZONE)
        now = datetime.datetime.now(tz)
        reminder_window_start = now
        reminder_window_end = now + datetime.timedelta(minutes=config.REMINDER_MINUTES + 2)

        events = calendar_mgr.get_events_starting_between(reminder_window_start, reminder_window_end)
        
        for event in events:
            event_id = event.get('id')
            start = event.get('start', {})
            
            # Skip all-day events for exact minute reminders
            if 'dateTime' not in start:
                continue

            start_dt = datetime.datetime.fromisoformat(start['dateTime']).astimezone(tz)
            time_diff = (start_dt - now).total_seconds() / 60.0

            # Send reminder if start time is within [0, REMINDER_MINUTES]
            reminder_key = f"{event_id}_{start_dt.isoformat()}"
            if 0 <= time_diff <= config.REMINDER_MINUTES and reminder_key not in sent_reminders:
                msg = calendar_mgr.format_reminder_notification(event, int(round(time_diff)))
                
                # Send to all registered subscribers
                for chat_id in subscribers:
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=msg,
                            parse_mode="HTML",
                            disable_web_page_preview=True
                        )
                        logger.info(f"Sent reminder for event '{event.get('summary')}' to subscriber chat_id: {chat_id}")
                    except Exception as send_err:
                        logger.error(f"Failed to send reminder to chat_id {chat_id}: {send_err}")

                sent_reminders.add(reminder_key)

    except Exception as e:
        logger.error(f"Error in check_upcoming_reminders scheduler: {e}")

async def send_daily_summary(bot):
    """Background task to send daily summary of events to all subscribers."""
    subscribers = config.load_subscribers()
    if not subscribers:
        return

    try:
        events = calendar_mgr.get_today_events()
        tz = pytz.timezone(config.TIMEZONE)
        today_str = datetime.datetime.now(tz).strftime('%d/%m/%Y')
        msg = calendar_mgr.format_daily_schedule(events, today_str)

        for chat_id in subscribers:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=msg,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                logger.info(f"Sent daily summary notification to subscriber chat_id: {chat_id}")
            except Exception as send_err:
                logger.error(f"Failed to send daily summary to chat_id {chat_id}: {send_err}")

    except Exception as e:
        logger.error(f"Error sending daily summary: {e}")

async def post_init(application: Application):
    """Setup background tasks scheduler and bot commands menu after initialization."""
    bot = application.bot
    tz = pytz.timezone(config.TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    # Set Telegram Bot Commands menu
    commands = [
        BotCommand("start", "ចាប់ផ្តើម និងចុះឈ្មោះទទួលសារ (Start & Subscribe)"),
        BotCommand("today", "មើល Event ទាំងអស់សម្រាប់ថ្ងៃនេះ (Today's Events)"),
        BotCommand("upcoming", "មើល Event ៧ថ្ងៃខាងមុខ (Upcoming Events)"),
        BotCommand("score", "មើលតារាងពិន្ទុប្រចាំខែចុងក្រោយ (Monthly Score)"),
        BotCommand("broadcast", "ផ្សាយដំណឹង ឬផ្ញើតារាងពិន្ទុ (Admin Only)"),
        BotCommand("status", "ពិនិត្យស្ថានភាពប្រព័ន្ធ (Check Status)"),
        BotCommand("stop", "លុបការចុះឈ្មោះទទួលសារ (Unsubscribe)"),
        BotCommand("help", "ការណែនាំបន្ថែម (Help)"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Bot command menu set successfully.")
    except Exception as e:
        logger.error(f"Error setting bot commands: {e}")

    # Schedule reminder check every 1 minute
    scheduler.add_job(
        check_upcoming_reminders,
        'interval',
        minutes=1,
        args=[bot]
    )

    # Schedule daily summary
    summary_hour, summary_minute = map(int, config.DAILY_SUMMARY_TIME.split(':'))
    scheduler.add_job(
        send_daily_summary,
        CronTrigger(hour=summary_hour, minute=summary_minute, timezone=tz),
        args=[bot]
    )

    scheduler.start()
    logger.info("Scheduler started successfully for reminders and daily summary.")

def main():
    logger.info("==========================================")
    logger.info("Starting Google Calendar Telegram Bot...")
    logger.info(f"Timezone: {config.TIMEZONE}")
    logger.info(f"Calendar ID: {config.GOOGLE_CALENDAR_ID}")
    logger.info("==========================================")

    # Start HTTP Health Check Server in a background thread for Render Free Web Service
    threading.Thread(target=start_health_server, daemon=True).start()

    # Start self-ping keep-alive loop to prevent Render Free Web Service from going to sleep
    threading.Thread(target=start_keep_alive, daemon=True).start()

    missing = config.validate_config()
    if missing:
        logger.warning(
            "⚠️ Config validation warning:\nMissing parameters:\n - " + "\n - ".join(missing)
        )

    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        logger.error("❌ Error: TELEGRAM_BOT_TOKEN is not set in Environment Variables!")
        logger.error("Please add TELEGRAM_BOT_TOKEN in Environment Variables.")
        import time
        while True:
            time.sleep(60)

    # Build Application
    application = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Register Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("unsubscribe", stop_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("upcoming", upcoming_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("score", score_command))
    application.add_handler(CommandHandler("scores", score_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("announce", broadcast_command))

    # Register Media broadcast handler (Photos and Documents with /broadcast caption)
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_media_broadcast))

    # Register 1-Click Callback Query Handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # Register Keyboard Button Message Handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_click))

    logger.info("Starting Telegram Bot polling...")
    application.run_polling()

if __name__ == "__main__":
    main()

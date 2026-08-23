from http.server import BaseHTTPRequestHandler
import json
import asyncio
import os
import sys
import logging
import traceback
from typing import Set

# Ensure root project directory is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters

import config
from google_calendar import GoogleCalendarManager, find_json_credentials

logger = logging.getLogger(__name__)

# Global instances
calendar_mgr = GoogleCalendarManager()

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Generate permanent Khmer Telegram keyboard buttons."""
    keyboard = [
        [KeyboardButton("📅 Event ថ្ងៃនេះ"), KeyboardButton("📆 Event ៧ថ្ងៃខាងមុខ")],
        [KeyboardButton("🔔 ចុះឈ្មោះទទួលសារ"), KeyboardButton("🔕 លុបការចុះឈ្មោះ")],
        [KeyboardButton("📊 ស្ថានភាពប្រព័ន្ធ"), KeyboardButton("ℹ️ ការណែនាំ")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start_command(update: Update, context):
    """Handle /start command with auto-subscription."""
    chat_id = update.effective_chat.id
    is_new = config.add_subscriber(chat_id)
    
    status_text = (
        "🎉 <b>អ្នកបានចុះឈ្មោះទទួលការជូនដំណឹងដោយស្វ័យប្រវត្តិរួចរាល់ហើយ!</b>"
        if is_new else
        "✅ <b>អ្នកកំពុងស្ថិតក្នុងបញ្ជីទទួលការជូនដំណឹងស្រាប់!</b>"
    )

    welcome_text = (
        f"👋 <b>ជម្រាបសួរ! ខ្ញុំជា Telegram Bot ជូនដំណឹងពី Google Calendar (Vercel)</b>\n\n"
        f"{status_text}\n"
        f"🆔 <b>Chat ID របស់អ្នក:</b> <code>{chat_id}</code>\n\n"
        f"<b>👇 សូមចុចប៊ូតុងខាងក្រោមដើម្បីប្រើប្រាស់៖</b>"
    )
    await update.message.reply_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

async def stop_command(update: Update, context):
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

async def help_command(update: Update, context):
    """Handle /help command."""
    help_text = (
        "ℹ️ <b>ការណែនាំប្រើប្រាស់ Bot (Vercel Serverless):</b>\n\n"
        "• គ្រាន់តែចុច 🔔 ចុះឈ្មោះទទួលសារ អ្នកនឹងត្រូវបានចុះឈ្មោះដោយស្វ័យប្រវត្តិ ⚡\n"
        "• ជូនដំណឹងនៅពេលមាន Event ជិតដល់ម៉ោង។\n\n"
        "<b>ប៊ូតុងបញ្ជា៖</b>\n"
        "📅 Event ថ្ងៃនេះ - បង្ហាញ Event ថ្ងៃនេះ\n"
        "📆 Event ៧ថ្ងៃខាងមុខ - បង្ហាញ Event ៧ថ្ងៃខាងមុខ\n"
        "🔔 ចុះឈ្មោះទទួលសារ - ចុះឈ្មោះទទួលសាររំលឹក\n"
        "🔕 លុបការចុះឈ្មោះ - ឈប់ទទួលសារ\n"
        "📊 ស្ថានភាពប្រព័ន្ធ - ពិនិត្យស្ថានភាពប្រព័ន្ធ\n"
    )
    await update.message.reply_text(
        help_text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

async def today_command(update: Update, context):
    """Handle /today command."""
    try:
        events = calendar_mgr.get_today_events()
        if not events:
            await update.message.reply_text(
                "📅 <b>គ្មាន Event សម្រាប់ថ្ងៃនេះទេ!</b>",
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )
            return

        msg = f"☀️ <b>Event ទាំងអស់សម្រាប់ថ្ងៃនេះ ({len(events)} Event):</b>\n\n"
        for idx, event in enumerate(events, 1):
            msg += f"<b>{idx}.</b> {calendar_mgr.format_event_message(event)}\n"

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

async def upcoming_command(update: Update, context):
    """Handle /upcoming command."""
    try:
        events = calendar_mgr.get_upcoming_events(days=7)
        if not events:
            await update.message.reply_text(
                "📅 <b>គ្មាន Event ក្នុងរយៈពេល ៧ ថ្ងៃខាងមុខទេ!</b>",
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )
            return

        msg = f"📆 <b>Event ក្នុងរយៈពេល ៧ ថ្ងៃខាងមុខ ({len(events)} Event):</b>\n\n"
        for idx, event in enumerate(events, 1):
            msg += f"<b>{idx}.</b> {calendar_mgr.format_event_message(event)}\n"

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

async def status_command(update: Update, context):
    """Handle /status command."""
    has_json = bool(find_json_credentials())
    subscribers = config.load_subscribers()

    try:
        events = calendar_mgr.get_today_events()
        status_msg = (
            "✅ <b>ប្រព័ន្ធដំណើរការជាប្រក្រតី! (Vercel Serverless OK)</b>\n\n"
            "• 🔑 <b>Google Credentials:</b> " + ("ភ្ជាប់រួចរាល់ (Connected ✅)" if has_json else "មិនទាន់បានភ្ជាប់ ❌") + "\n"
            f"• 📅 <b>Calendar ID:</b> <code>{config.GOOGLE_CALENDAR_ID}</code>\n"
            f"• ⏰ <b>Timezone:</b> {config.TIMEZONE}\n"
            f"• 👥 <b>អ្នកចុះឈ្មោះទទួលសារ ({len(subscribers)}):</b> <code>{', '.join(subscribers) if subscribers else 'គ្មាន'}</code>\n"
            f"• ☀️ <b>Events ថ្ងៃនេះ:</b> {len(events)} Event\n"
        )
        await update.message.reply_text(
            status_msg,
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        status_msg = (
            "⚠️ <b>ស្ថានភាពប្រព័ន្ធ (Vercel Status):</b>\n\n"
            "• 🔑 <b>Google Credentials:</b> " + ("ភ្ជាប់រួចរាល់ (Connected ✅)" if has_json else "មិនទាន់បានភ្ជាប់ ❌") + "\n"
            f"• ❌ <b>Error:</b> <code>{e}</code>\n"
        )
        await update.message.reply_text(
            status_msg,
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

async def handle_button_click(update: Update, context):
    """Flexible matching router for Telegram Keyboard Button clicks."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    
    if "Event ថ្ងៃនេះ" in text or "ថ្ងៃនេះ" in text:
        await today_command(update, context)
    elif "Event ៧ថ្ងៃ" in text or "៧ថ្ងៃ" in text or "ជិតមកដល់" in text:
        await upcoming_command(update, context)
    elif "ចុះឈ្មោះទទួលសារ" in text or "ចុះឈ្មោះ" in text:
        await start_command(update, context)
    elif "លុបការចុះឈ្មោះ" in text or "លុប" in text:
        await stop_command(update, context)
    elif "ស្ថានភាព" in text or "status" in text.lower():
        await status_command(update, context)
    elif "ការណែនាំ" in text or "help" in text.lower():
        await help_command(update, context)

# Global Application instance
_telegram_app = None

async def get_telegram_app():
    global _telegram_app
    if _telegram_app is None:
        token = config.TELEGRAM_BOT_TOKEN
        _telegram_app = Application.builder().token(token).build()
        _telegram_app.add_handler(CommandHandler("start", start_command))
        _telegram_app.add_handler(CommandHandler("stop", stop_command))
        _telegram_app.add_handler(CommandHandler("unsubscribe", stop_command))
        _telegram_app.add_handler(CommandHandler("help", help_command))
        _telegram_app.add_handler(CommandHandler("today", today_command))
        _telegram_app.add_handler(CommandHandler("upcoming", upcoming_command))
        _telegram_app.add_handler(CommandHandler("status", status_command))
        _telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_click))
        await _telegram_app.initialize()
    return _telegram_app

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            host = self.headers.get('Host', 'jingbot.p2bkh.tech')
            if 'set_webhook' in self.path:
                webhook_url = f"https://{host}/"
                asyncio.run(self._set_webhook_url(webhook_url))
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                resp = f"<h2>✅ Telegram Webhook registered successfully!</h2><p>Webhook URL: <code>{webhook_url}</code></p>"
                self.wfile.write(resp.encode('utf-8'))
                return

            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"OK - Google Calendar Telegram Bot is running on Vercel Serverless Function!")
        except Exception as e:
            tb = traceback.format_exc()
            self.send_response(500)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            err_msg = f"Vercel Exception: {e}\n\nTraceback:\n{tb}"
            self.wfile.write(err_msg.encode('utf-8'))

    async def _set_webhook_url(self, url: str):
        app = await get_telegram_app()
        await app.bot.set_webhook(url=url)

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            update_data = json.loads(post_data.decode('utf-8'))
            asyncio.run(self._process_update(update_data))
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
        except Exception as e:
            logger.error(f"Error processing Vercel webhook update: {e}")
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

    async def _process_update(self, update_data: dict):
        app = await get_telegram_app()
        update = Update.de_json(update_data, app.bot)
        await app.process_update(update)

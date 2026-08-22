import os
import datetime
import logging
import asyncio
import threading
import urllib.request
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Set
import pytz

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
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

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Generate permanent Khmer Telegram keyboard buttons."""
    keyboard = [
        [KeyboardButton("📅 Event ថ្ងៃនេះ"), KeyboardButton("📆 Event ៧ថ្ងៃខាងមុខ")],
        [KeyboardButton("🔔 ចុះឈ្មោះទទួលសារ"), KeyboardButton("🔕 លុបការចុះឈ្មោះ")],
        [KeyboardButton("📊 ស្ថានភាពប្រព័ន្ធ"), KeyboardButton("ℹ️ ការណែនាំ")]
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
    """Background thread to self-ping HTTP server every 5 minutes to keep Render Free Web Service active 24/7."""
    port = int(os.getenv("PORT", 8080))
    url = f"http://127.0.0.1:{port}/"
    time.sleep(10)  # Wait for initial HTTP server startup
    while True:
        try:
            time.sleep(300)  # Ping every 5 minutes
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
        "• គ្រាន់តែចុច 🔔 ចុះឈ្មោះទទួលសារ អ្នកនឹងត្រូវបានចុះឈ្មោះដោយស្វ័យប្រវត្តិ ⚡\n"
        "• ជូនដំណឹងនៅពេលមាន Event ជិតដល់ម៉ោង (ឧ. ១៥នាទីមុន)។\n"
        "• ផ្ញើសារសង្ខេប Event សម្រាប់ថ្ងៃថ្មីរៀងរាល់ព្រឹក ម៉ោង ៧:០០ ព្រឹក។\n\n"
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

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def upcoming_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    missing = config.validate_config()
    has_json = bool(find_json_credentials())
    subscribers = config.load_subscribers()
    
    user_envs = [k for k in os.environ.keys() if not k.startswith("PATH") and not k.startswith("HOME") and not k.startswith("NIX") and not k.startswith("LC_")]

    try:
        events = calendar_mgr.get_today_events()
        status_msg = (
            "✅ <b>ប្រព័ន្ធដំណើរការជាប្រក្រតី!</b>\n\n"
            "• Google Credentials Detected: " + ("Yes ✅" if has_json else "No ❌") + "\n"
            f"• Calendar ID: <code>{config.GOOGLE_CALENDAR_ID}</code>\n"
            f"• Timezone: {config.TIMEZONE}\n"
            f"• Auto Subscribers ({len(subscribers)}): <code>{', '.join(subscribers) if subscribers else 'គ្មាន'}</code>\n"
            f"• Env Variables ({len(user_envs)}): <code>{', '.join(user_envs)}</code>\n"
            f"• Events ថ្ងៃនេះ: {len(events)} Event\n"
        )
        await update.message.reply_text(
            status_msg,
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        status_msg = (
            "⚠️ <b>ស្ថានភាពប្រព័ន្ធ (System Status):</b>\n\n"
            "• Google Credentials Detected: " + ("Yes ✅" if has_json else "No ❌") + "\n"
            f"• Environment Variables Found ({len(user_envs)}): <code>{', '.join(user_envs)}</code>\n"
            f"• Error: <code>{e}</code>\n"
        )
        await update.message.reply_text(
            status_msg,
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route Telegram Keyboard Button clicks to corresponding command handlers."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    
    if text == "📅 Event ថ្ងៃនេះ":
        await today_command(update, context)
    elif text == "📆 Event ៧ថ្ងៃខាងមុខ":
        await upcoming_command(update, context)
    elif text == "🔔 ចុះឈ្មោះទទួលសារ":
        await start_command(update, context)
    elif text == "🔕 លុបការចុះឈ្មោះ":
        await stop_command(update, context)
    elif text == "📊 ស្ថានភាពប្រព័ន្ធ":
        await status_command(update, context)
    elif text == "ℹ️ ការណែនាំ":
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
                event_details = calendar_mgr.format_event_message(event)
                msg = (
                    f"🔔 <b>[ការជូនដំណឹង] Event ជិតដល់ម៉ោងក្នុងពេល {int(time_diff)} នាទីទៀត!</b>\n\n"
                    f"{event_details}"
                )
                
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

        if not events:
            msg = f"☀️ <b>អរុណសួស្តី! ({today_str})</b>\n\n📅 ថ្ងៃនេះគ្មាន Event រៀបចំទុកទេ! រីករាយថ្ងៃថ្មី!"
        else:
            msg = f"☀️ <b>អរុណសួស្តី! នេះជា Event ទាំងអស់សម្រាប់ថ្ងៃនេះ ({today_str}):</b>\n\n"
            for idx, event in enumerate(events, 1):
                msg += f"<b>{idx}.</b> {calendar_mgr.format_event_message(event)}\n"

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

    # Register Keyboard Button Message Handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_click))

    logger.info("Starting Telegram Bot polling...")
    application.run_polling()

if __name__ == "__main__":
    main()

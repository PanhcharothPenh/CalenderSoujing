import os
import sys
import json
import asyncio
import logging
from flask import Flask, request, jsonify

# Ensure root project directory is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

app = Flask(__name__)
logger = logging.getLogger(__name__)

def get_main_keyboard():
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    keyboard = [
        [KeyboardButton("📅 Event ថ្ងៃនេះ"), KeyboardButton("📆 Event ៧ថ្ងៃខាងមុខ")],
        [KeyboardButton("🔔 ចុះឈ្មោះទទួលសារ"), KeyboardButton("🔕 លុបការចុះឈ្មោះ")],
        [KeyboardButton("📊 ស្ថានភាពប្រព័ន្ធ"), KeyboardButton("ℹ️ ការណែនាំ")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

@app.route("/", methods=["GET"])
@app.route("/api/index.py", methods=["GET"])
def home():
    return "OK - Google Calendar Telegram Bot on Vercel is READY!"

@app.route("/set_webhook", methods=["GET"])
@app.route("/api/index.py/set_webhook", methods=["GET"])
def set_webhook():
    host = request.headers.get("Host", "jingbot.p2bkh.tech")
    webhook_url = f"https://{host}/"
    
    from telegram.ext import Application
    import config
    
    async def _set():
        bot_app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        await bot_app.initialize()
        await bot_app.bot.set_webhook(url=webhook_url)

    try:
        asyncio.run(_set())
        return f"<h2>✅ Telegram Webhook registered successfully!</h2><p>Webhook URL: <code>{webhook_url}</code></p>"
    except Exception as e:
        return f"<h2>❌ Error setting webhook:</h2><p><code>{e}</code></p>", 500

@app.route("/", methods=["POST"])
@app.route("/api/index.py", methods=["POST"])
@app.route("/<path:path>", methods=["POST"])
def webhook(path=None):
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters
    import config
    from google_calendar import GoogleCalendarManager, find_json_credentials

    try:
        update_data = request.get_json(force=True, silent=True) or {}
        if not update_data:
            return jsonify({"status": "error", "message": "No JSON payload"}), 400

        calendar_mgr = GoogleCalendarManager()

        async def start_cmd(update, context):
            chat_id = update.effective_chat.id
            is_new = config.add_subscriber(chat_id)
            status_text = "🎉 <b>អ្នកបានចុះឈ្មោះទទួលការជូនដំណឹងដោយស្វ័យប្រវត្តិរួចរាល់ហើយ!</b>" if is_new else "✅ <b>អ្នកកំពុងស្ថិតក្នុងបញ្ជីទទួលការជូនដំណឹងស្រាប់!</b>"
            welcome_text = f"👋 <b>ជម្រាបសួរ! ខ្ញុំជា Telegram Bot ជូនដំណឹងពី Google Calendar (Vercel)</b>\n\n{status_text}\n🆔 <b>Chat ID របស់អ្នក:</b> <code>{chat_id}</code>\n\n<b>👇 សូមចុចប៊ូតុងខាងក្រោមដើម្បីប្រើប្រាស់៖</b>"
            await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=get_main_keyboard())

        async def stop_cmd(update, context):
            chat_id = update.effective_chat.id
            removed = config.remove_subscriber(chat_id)
            if removed:
                await update.message.reply_text("🔕 <b>អ្នកបានលុបការចុះឈ្មោះទទួលសារជូនដំណឹងរួចរាល់ហើយ!</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
            else:
                await update.message.reply_text("ℹ️ អ្នកមិនទាន់បានចុះឈ្មោះទទួលសារនៅឡើយទេ។", parse_mode="HTML", reply_markup=get_main_keyboard())

        async def help_cmd(update, context):
            help_text = "ℹ️ <b>ការណែនាំប្រើប្រាស់ Bot (Vercel Serverless):</b>\n\n• គ្រាន់តែចុច 🔔 ចុះឈ្មោះទទួលសារ អ្នកនឹងត្រូវបានចុះឈ្មោះដោយស្វ័យប្រវត្តិ ⚡\n"
            await update.message.reply_text(help_text, parse_mode="HTML", reply_markup=get_main_keyboard())

        async def today_cmd(update, context):
            events = calendar_mgr.get_today_events()
            if not events:
                await update.message.reply_text("📅 <b>គ្មាន Event សម្រាប់ថ្ងៃនេះទេ!</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
                return
            msg = f"☀️ <b>Event ទាំងអស់សម្រាប់ថ្ងៃនេះ ({len(events)} Event):</b>\n\n"
            for idx, event in enumerate(events, 1):
                msg += f"<b>{idx}.</b> {calendar_mgr.format_event_message(event)}\n"
            await update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True, reply_markup=get_main_keyboard())

        async def upcoming_cmd(update, context):
            events = calendar_mgr.get_upcoming_events(days=7)
            if not events:
                await update.message.reply_text("📅 <b>គ្មាន Event ក្នុងរយៈពេល ៧ ថ្ងៃខាងមុខទេ!</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
                return
            msg = f"📆 <b>Event ក្នុងរយៈពេល ៧ ថ្ងៃខាងមុខ ({len(events)} Event):</b>\n\n"
            for idx, event in enumerate(events, 1):
                msg += f"<b>{idx}.</b> {calendar_mgr.format_event_message(event)}\n"
            await update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True, reply_markup=get_main_keyboard())

        async def status_cmd(update, context):
            has_json = bool(find_json_credentials())
            subscribers = config.load_subscribers()
            events = calendar_mgr.get_today_events()
            status_msg = (
                "✅ <b>ប្រព័ន្ធដំណើរការជាប្រក្រតី! (Vercel Serverless OK)</b>\n\n"
                "• 🔑 <b>Google Credentials:</b> " + ("ភ្ជាប់រួចរាល់ (Connected ✅)" if has_json else "មិនទាន់បានភ្ជាប់ ❌") + "\n"
                f"• 📅 <b>Calendar ID:</b> <code>{config.GOOGLE_CALENDAR_ID}</code>\n"
                f"• ⏰ <b>Timezone:</b> {config.TIMEZONE}\n"
                f"• 👥 <b>អ្នកចុះឈ្មោះទទួលសារ ({len(subscribers)}):</b> <code>{', '.join(subscribers) if subscribers else 'គ្មាន'}</code>\n"
                f"• ☀️ <b>Events ថ្ងៃនេះ:</b> {len(events)} Event\n"
            )
            await update.message.reply_text(status_msg, parse_mode="HTML", reply_markup=get_main_keyboard())

        async def button_handler(update, context):
            if not update.message or not update.message.text:
                return
            text = update.message.text.strip()
            if "Event ថ្ងៃនេះ" in text or "ថ្ងៃនេះ" in text:
                await today_cmd(update, context)
            elif "Event ៧ថ្ងៃ" in text or "៧ថ្ងៃ" in text or "ជិតមកដល់" in text:
                await upcoming_cmd(update, context)
            elif "ចុះឈ្មោះទទួលសារ" in text or "ចុះឈ្មោះ" in text:
                await start_cmd(update, context)
            elif "លុបការចុះឈ្មោះ" in text or "លុប" in text:
                await stop_cmd(update, context)
            elif "ស្ថានភាព" in text or "status" in text.lower():
                await status_cmd(update, context)
            elif "ការណែនាំ" in text or "help" in text.lower():
                await help_cmd(update, context)

        async def _run():
            bot_app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
            bot_app.add_handler(CommandHandler("start", start_cmd))
            bot_app.add_handler(CommandHandler("stop", stop_cmd))
            bot_app.add_handler(CommandHandler("unsubscribe", stop_cmd))
            bot_app.add_handler(CommandHandler("help", help_cmd))
            bot_app.add_handler(CommandHandler("today", today_cmd))
            bot_app.add_handler(CommandHandler("upcoming", upcoming_cmd))
            bot_app.add_handler(CommandHandler("status", status_cmd))
            bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))

            await bot_app.initialize()
            await bot_app.start()
            update = Update.de_json(update_data, bot_app.bot)
            await bot_app.process_update(update)
            await bot_app.stop()
            await bot_app.shutdown()

        asyncio.run(_run())
        return jsonify({"status": "ok"})

    except Exception as e:
        logger.error(f"Error in webhook endpoint: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

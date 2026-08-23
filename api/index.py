from http.server import BaseHTTPRequestHandler
import json
import asyncio
import os
import sys
import logging
import traceback

# Ensure root project directory is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

logger = logging.getLogger(__name__)

def get_main_keyboard():
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    keyboard = [
        [KeyboardButton("📅 Event ថ្ងៃនេះ"), KeyboardButton("📆 Event ៧ថ្ងៃខាងមុខ")],
        [KeyboardButton("🔔 ចុះឈ្មោះទទួលសារ"), KeyboardButton("🔕 លុបការចុះឈ្មោះ")],
        [KeyboardButton("📊 ស្ថានភាពប្រព័ន្ធ"), KeyboardButton("ℹ️ ការណែនាំ")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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
        from telegram.ext import Application
        import config
        app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
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
        from telegram import Update
        from telegram.ext import Application, CommandHandler, MessageHandler, filters
        import config
        from google_calendar import GoogleCalendarManager, find_json_credentials

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

        app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start_cmd))
        app.add_handler(CommandHandler("stop", stop_cmd))
        app.add_handler(CommandHandler("unsubscribe", stop_cmd))
        app.add_handler(CommandHandler("help", help_cmd))
        app.add_handler(CommandHandler("today", today_cmd))
        app.add_handler(CommandHandler("upcoming", upcoming_cmd))
        app.add_handler(CommandHandler("status", status_cmd))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))

        await app.initialize()
        update = Update.de_json(update_data, app.bot)
        await app.process_update(update)

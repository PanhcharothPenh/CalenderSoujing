import os
import sys
import json
import asyncio
import logging
import traceback
import datetime
import pytz
from flask import Flask, request, jsonify

# Ensure root project directory is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Global cache to prevent duplicate reminder notifications
sent_reminders = set()

def get_main_keyboard():
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    keyboard = [
        [KeyboardButton("📅 Event ថ្ងៃនេះ"), KeyboardButton("📆 Event ៧ថ្ងៃខាងមុខ")],
        [KeyboardButton("🚗 ទីតាំងយានយន្ត"), KeyboardButton("📊 ស្ថានភាពប្រព័ន្ធ")],
        [KeyboardButton("🔔 ចុះឈ្មោះទទួលសារ"), KeyboardButton("🔕 លុបការចុះឈ្មោះ")],
        [KeyboardButton("ℹ️ ការណែនាំ")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

@app.route("/", methods=["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST"])
def catch_all(path=""):
    if request.method == "GET":
        host = request.headers.get("Host", "jingbot.p2bkh.tech")
        
        # Cron endpoint for automated 24/7 background event reminders
        if "cron" in request.path or "cron" in path:
            from telegram import Bot
            import config
            from google_calendar import GoogleCalendarManager

            bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            calendar_mgr = GoogleCalendarManager()
            subscribers = config.load_subscribers()

            async def process_cron():
                if not subscribers:
                    return "No subscribers"
                tz = pytz.timezone(config.TIMEZONE)
                now = datetime.datetime.now(tz)
                window_end = now + datetime.timedelta(minutes=config.REMINDER_MINUTES + 2)

                events = await asyncio.to_thread(calendar_mgr.get_events_starting_between, now, window_end)
                sent_count = 0

                for event in events:
                    event_id = event.get('id')
                    start = event.get('start', {})
                    if 'dateTime' not in start:
                        continue
                    
                    start_dt = datetime.datetime.fromisoformat(start['dateTime']).astimezone(tz)
                    time_diff = (start_dt - now).total_seconds() / 60.0
                    reminder_key = f"{event_id}_{start_dt.isoformat()}"

                    if 0 <= time_diff <= config.REMINDER_MINUTES and reminder_key not in sent_reminders:
                        event_details = calendar_mgr.format_event_message(event)
                        msg = f"🔔 <b>[ការជូនដំណឹង] Event ជិតដល់ម៉ោងក្នុងពេល {int(time_diff)} នាទីទៀត!</b>\n\n{event_details}"
                        for cid in subscribers:
                            try:
                                await bot.send_message(chat_id=cid, text=msg, parse_mode="HTML", disable_web_page_preview=True)
                                sent_count += 1
                            except Exception as send_err:
                                logger.error(f"Error sending reminder to {cid}: {send_err}")
                        sent_reminders.add(reminder_key)
                return f"Cron executed. Sent {sent_count} reminders."

            try:
                res_msg = asyncio.run(process_cron())
                return jsonify({"status": "ok", "message": res_msg})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        # Webhook setup endpoint
        if "set_webhook" in request.path or "set_webhook" in path:
            webhook_url = f"https://{host}/"
            from telegram import Bot
            import config
            
            async def _set():
                bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
                await bot.set_webhook(url=webhook_url)

            try:
                asyncio.run(_set())
                return f"<h2>✅ Telegram Webhook registered successfully!</h2><p>Webhook URL: <code>{webhook_url}</code></p>"
            except Exception as e:
                return f"<h2>❌ Error setting webhook:</h2><p><code>{e}</code></p>", 500

        return "OK - Google Calendar & ProTrack365 Telegram Bot is running on Vercel Serverless Function!"

    # POST handling for Telegram Webhook
    try:
        update_data = request.get_json(force=True, silent=True) or {}
        if "message" not in update_data:
            return jsonify({"status": "ok", "message": "No message in update"}), 200

        msg_data = update_data["message"]
        chat_id = msg_data.get("chat", {}).get("id")
        text = msg_data.get("text", "").strip()

        if not chat_id or not text:
            return jsonify({"status": "ok", "message": "No chat_id or text"}), 200

        from telegram import Bot
        import config
        from google_calendar import GoogleCalendarManager, find_json_credentials
        from protrack import ProTrackClient

        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        calendar_mgr = GoogleCalendarManager()
        protrack = ProTrackClient()

        async def process_message():
            reply_markup = get_main_keyboard()

            if "Event ថ្ងៃនេះ" in text or "ថ្ងៃនេះ" in text or text == "/today":
                events = await asyncio.to_thread(calendar_mgr.get_today_events)
                if not events:
                    await bot.send_message(
                        chat_id=chat_id,
                        text="📅 <b>គ្មាន Event សម្រាប់ថ្ងៃនេះទេ!</b>",
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                else:
                    msg = f"☀️ <b>Event ទាំងអស់សម្រាប់ថ្ងៃនេះ ({len(events)} Event):</b>\n\n"
                    for idx, event in enumerate(events, 1):
                        msg += f"<b>{idx}.</b> {calendar_mgr.format_event_message(event)}\n"
                    await bot.send_message(
                        chat_id=chat_id,
                        text=msg,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                        reply_markup=reply_markup
                    )

            elif "Event ៧ថ្ងៃ" in text or "៧ថ្ងៃ" in text or "ជិតមកដល់" in text or text == "/upcoming":
                events = await asyncio.to_thread(calendar_mgr.get_upcoming_events, 7)
                if not events:
                    await bot.send_message(
                        chat_id=chat_id,
                        text="📅 <b>គ្មាន Event ក្នុងរយៈពេល ៧ ថ្ងៃខាងមុខទេ!</b>",
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                else:
                    msg = f"📆 <b>Event ក្នុងរយៈពេល ៧ ថ្ងៃខាងមុខ ({len(events)} Event):</b>\n\n"
                    for idx, event in enumerate(events, 1):
                        msg += f"<b>{idx}.</b> {calendar_mgr.format_event_message(event)}\n"
                    await bot.send_message(
                        chat_id=chat_id,
                        text=msg,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                        reply_markup=reply_markup
                    )

            elif text.startswith("/set_imei") or text.startswith("/imei"):
                parts = text.split()
                if len(parts) > 1:
                    new_imei = parts[1].strip()
                    protrack.save_imei(new_imei)
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"✅ <b>បានកំណត់លេខ IMEI រួចរាល់:</b> <code>{new_imei}</code>\n\nសូមចុចប៊ូតុង 🚗 ទីតាំងយានយន្ត ដើម្បីពិនិត្យទីតាំង។",
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text="👉 <b>របៀបកំណត់ IMEI:</b>\n<code>/set_imei <លេខ IMEI 15ខ្ទង់></code>\n(ឧទាហរណ៍៖ <code>/set_imei 868340051234567</code>)",
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )

            elif "ទីតាំង" in text or "track" in text.lower() or text == "/track":
                parts = text.split()
                target_imei = parts[1].strip() if len(parts) > 1 and parts[1].isdigit() else None
                loc_data = await asyncio.to_thread(protrack.get_device_location, target_imei)
                loc_msg = protrack.format_location_message(loc_data)
                await bot.send_message(
                    chat_id=chat_id,
                    text=loc_msg,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                    disable_web_page_preview=False
                )

            elif "ស្ថានភាព" in text or "status" in text.lower() or text == "/status":
                has_json = bool(find_json_credentials())
                has_protrack = bool(config.PROTRACK_ACCOUNT and config.PROTRACK_PASSWORD)
                subscribers = config.load_subscribers()
                events = await asyncio.to_thread(calendar_mgr.get_today_events)
                status_msg = (
                    "✅ <b>ប្រព័ន្ធដំណើរការជាប្រក្រតី! (Vercel Serverless OK)</b>\n\n"
                    "• 🔑 <b>Google Credentials:</b> " + ("ភ្ជាប់រួចរាល់ (Connected ✅)" if has_json else "មិនទាន់បានភ្ជាប់ ❌") + "\n"
                    "• 🚗 <b>ProTrack365 GPS:</b> " + ("ភ្ជាប់រួចរាល់ (Connected ✅)" if has_protrack else "មិនទាន់កំណត់ (Not Configured ⚠️)") + "\n"
                    f"• 📅 <b>Calendar ID:</b> <code>{config.GOOGLE_CALENDAR_ID}</code>\n"
                    f"• ⏰ <b>Timezone:</b> {config.TIMEZONE}\n"
                    f"• 👥 <b>អ្នកចុះឈ្មោះទទួលសារ ({len(subscribers)}):</b> <code>{', '.join(subscribers) if subscribers else 'គ្មាន'}</code>\n"
                    f"• ☀️ <b>Events ថ្ងៃនេះ:</b> {len(events)} Event\n"
                )
                await bot.send_message(
                    chat_id=chat_id,
                    text=status_msg,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )

            elif "ចុះឈ្មោះ" in text or text == "/start":
                is_new = config.add_subscriber(chat_id)
                status_text = "🎉 <b>អ្នកបានចុះឈ្មោះទទួលការជូនដំណឹងដោយស្វ័យប្រវត្តិរួចរាល់ហើយ!</b>" if is_new else "✅ <b>អ្នកកំពុងស្ថិតក្នុងបញ្ជីទទួលការជូនដំណឹងស្រាប់!</b>"
                welcome_text = f"👋 <b>ជម្រាបសួរ! ខ្ញុំជា Telegram Bot ជូនដំណឹងពី Google Calendar & ProTrack365</b>\n\n{status_text}\n🆔 <b>Chat ID របស់អ្នក:</b> <code>{chat_id}</code>\n\n<b>👇 សូមចុចប៊ូតុងខាងក្រោមដើម្បីប្រើប្រាស់៖</b>"
                await bot.send_message(
                    chat_id=chat_id,
                    text=welcome_text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )

            elif "លុប" in text or text in ["/stop", "/unsubscribe"]:
                removed = config.remove_subscriber(chat_id)
                if removed:
                    await bot.send_message(
                        chat_id=chat_id,
                        text="🔕 <b>អ្នកបានលុបការចុះឈ្មោះទទួលសារជូនដំណឹងរួចរាល់ហើយ!</b>",
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text="ℹ️ អ្នកមិនទាន់បានចុះឈ្មោះទទួលសារនៅឡើយទេ។",
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )

            elif "ការណែនាំ" in text or "help" in text.lower() or text == "/help":
                help_text = (
                    "ℹ️ <b>ការណែនាំប្រើប្រាស់ Bot (Google Calendar & ProTrack365):</b>\n\n"
                    "• 📅 Event ថ្ងៃនេះ - បង្ហាញកាលវិភាគថ្ងៃនេះ\n"
                    "• 📆 Event ៧ថ្ងៃខាងមុខ - បង្ហាញកាលវិភាគ ៧ថ្ងៃ\n"
                    "• 🚗 ទីតាំងយានយន្ត - ពិនិត្យទីតាំង GPS និងល្បឿនឡាន/ម៉ូតូ (ProTrack365)\n"
                    "• 📊 ស្ថានភាពប្រព័ន្ធ - ពិនិត្យស្ថានភាព Bot\n"
                )
                await bot.send_message(
                    chat_id=chat_id,
                    text=help_text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )

        asyncio.run(process_message())
        return jsonify({"status": "ok"})

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Error in webhook endpoint: {e}\n{tb}")
        return jsonify({"status": "error", "message": str(e), "traceback": tb}), 200

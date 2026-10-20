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
        [KeyboardButton("📊 តារាងពិន្ទុ"), KeyboardButton("🔔 ចុះឈ្មោះទទួលសារ")],
        [KeyboardButton("🔕 លុបការចុះឈ្មោះ"), KeyboardButton("ℹ️ ការណែនាំ")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

@app.route("/", methods=["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST"])
def catch_all(path=""):
    if request.method == "GET":
        host = request.headers.get("Host", "jingbot.p2bkh.tech")
        
        request_uri = request.environ.get("REQUEST_URI", "")
        raw_uri = request.environ.get("RAW_URI", "")
        matched_path = request.headers.get("x-matched-path", "")
        invoke_path = request.headers.get("x-invoke-path", "")
        is_cron = (
            request.args.get("cron") is not None
            or "cron" in request_uri
            or "cron" in raw_uri
            or "cron" in request.url
            or "cron" in request.path
            or "cron" in path
            or "cron" in matched_path
            or "cron" in invoke_path
        )

        # Cron endpoint for automated 24/7 background event reminders
        if is_cron:
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
                window_end = now + datetime.timedelta(minutes=35)

                events = await asyncio.to_thread(calendar_mgr.get_events_starting_between, now, window_end)
                sent_count = 0

                for event in events:
                    event_id = event.get('id')
                    start = event.get('start', {})
                    if 'dateTime' not in start:
                        continue
                    
                    start_dt = datetime.datetime.fromisoformat(start['dateTime']).astimezone(tz)
                    time_diff = (start_dt - now).total_seconds() / 60.0

                    alert_type = None
                    if 25.0 <= time_diff <= 32.0:
                        alert_type = "30m"
                    elif 0.0 <= time_diff <= 17.0:
                        alert_type = "15m"

                    if alert_type:
                        reminder_key = f"{event_id}_{start_dt.isoformat()}_{alert_type}"
                        if reminder_key not in sent_reminders:
                            diff_mins = int(round(time_diff))
                            msg = calendar_mgr.format_reminder_notification(event, diff_mins)
                            for cid in subscribers:
                                try:
                                    await bot.send_message(chat_id=cid, text=msg, parse_mode="HTML", disable_web_page_preview=True)
                                    sent_count += 1
                                except Exception as send_err:
                                    logger.error(f"Error sending reminder to {cid}: {send_err}")
                            sent_reminders.add(reminder_key)

                # Daily summary at 07:00 AM
                current_time_str = now.strftime("%H:%M")
                daily_key = f"daily_summary_{now.strftime('%Y-%m-%d')}"
                if current_time_str == config.DAILY_SUMMARY_TIME and daily_key not in sent_reminders:
                    today_events = await asyncio.to_thread(calendar_mgr.get_today_events)
                    today_str = now.strftime('%d/%m/%Y')
                    msg = calendar_mgr.format_daily_schedule(today_events, today_str)

                    for cid in subscribers:
                        try:
                            await bot.send_message(
                                chat_id=cid,
                                text=msg,
                                parse_mode="HTML",
                                disable_web_page_preview=True
                            )
                            sent_count += 1
                        except Exception as send_err:
                            logger.error(f"Error sending daily summary to {cid}: {send_err}")

                    sent_reminders.add(daily_key)

                return f"Cron executed. Sent {sent_count} reminders."

            try:
                res_msg = asyncio.run(process_cron())
                return jsonify({"status": "ok", "message": res_msg})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        # Webhook setup endpoint
        is_set_webhook = (
            request.args.get("set_webhook") is not None
            or "set_webhook" in request_uri
            or "set_webhook" in raw_uri
            or "set_webhook" in request.url
            or "set_webhook" in request.path
            or "set_webhook" in path
            or "set_webhook" in matched_path
            or "set_webhook" in invoke_path
        )
        if is_set_webhook:
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

        return "OK - Google Calendar Telegram Bot is running on Vercel Serverless Function!"

    # POST handling for Telegram Webhook
    try:
        update_data = request.get_json(force=True, silent=True) or {}
        msg_data = update_data.get("message") or update_data.get("channel_post") or {}
        if not msg_data:
            return jsonify({"status": "ok", "message": "No message in update"}), 200

        chat_id = msg_data.get("chat", {}).get("id")
        text = msg_data.get("text", "").strip()
        caption = msg_data.get("caption", "").strip()
        photos = msg_data.get("photo", [])
        document = msg_data.get("document", None)
        reply_to = msg_data.get("reply_to_message", None)

        if not chat_id:
            return jsonify({"status": "ok", "message": "No chat_id"}), 200

        if not text and not caption and not photos and not document and not reply_to:
            return jsonify({"status": "ok", "message": "Unsupported update type"}), 200

        from telegram import Bot
        import config
        from google_calendar import GoogleCalendarManager, find_json_credentials

        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        calendar_mgr = GoogleCalendarManager()

        async def process_message():
            reply_markup = get_main_keyboard()

            # Check for broadcast commands (/broadcast, /announce, etc.)
            is_broadcast = False
            broadcast_payload = ""

            for source in [text, caption]:
                if not source:
                    continue
                s_lower = source.lower()
                for cmd in ["/broadcast", "/announce", "/score_broadcast", "/post_score", "📢 ផ្សាយដំណឹង"]:
                    if s_lower.startswith(cmd.lower()):
                        is_broadcast = True
                        broadcast_payload = source[len(cmd):].strip()
                        break
                if is_broadcast:
                    break

            if is_broadcast:
                if not config.is_admin(chat_id):
                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            "⛔ <b>អ្នកមិនមានសិទ្ធិប្រើប្រាស់មុខងារផ្សាយដំណឹងនេះទេ!</b>\n\n"
                            "មុខងារ <code>/broadcast</code> ត្រូវបានកំណត់សម្រាប់តែ <b>Administrator</b> ប៉ុណ្ណោះ។"
                        ),
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                    return

                subscribers = config.load_subscribers()
                if not subscribers:
                    await bot.send_message(
                        chat_id=chat_id,
                        text="⚠️ <b>មិនទាន់មាន Subscribers ណាមួយបានចុះឈ្មោះនៅឡើយទេ!</b>",
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                    return

                tz = pytz.timezone(config.TIMEZONE)
                now_str = datetime.datetime.now(tz).strftime('%d/%m/%Y %I:%M %p')

                # Guide if empty broadcast command
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
                    await bot.send_message(chat_id=chat_id, text=help_broadcast, parse_mode="HTML", reply_markup=reply_markup)
                    return

                sent_count = 0
                fail_count = 0

                # Case 1: Direct Photo broadcast
                if photos:
                    file_id = photos[-1]["file_id"]
                    header = "📢 <b>តារាងពិន្ទុប្រចាំខែ (Monthly Score Report)</b> 📊\n"
                    final_caption = f"{header}\n{broadcast_payload}\n\n🗓️ <i>{now_str}</i>" if broadcast_payload else f"{header}\nសូមពិនិត្យមើលតារាងពិន្ទុខាងលើ!\n\n🗓️ <i>{now_str}</i>"

                    for sub_id in subscribers:
                        try:
                            await bot.send_photo(chat_id=sub_id, photo=file_id, caption=final_caption, parse_mode="HTML")
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
                    await bot.send_message(chat_id=chat_id, text=report, parse_mode="HTML", reply_markup=reply_markup)
                    return

                # Case 2: Direct Document broadcast
                elif document:
                    file_id = document["file_id"]
                    file_name = document.get("file_name", "Monthly_Score.pdf")
                    header = "📢 <b>តារាងពិន្ទុប្រចាំខែ (Monthly Score Report)</b> 📊\n"
                    final_caption = f"{header}\n📄 ឯកសារ: <code>{file_name}</code>\n\n{broadcast_payload}\n\n🗓️ <i>{now_str}</i>" if broadcast_payload else f"{header}\n📄 ឯកសារ: <code>{file_name}</code>\n\nសូមទាញយកឯកសារតារាងពិន្ទុខាងលើដើម្បីពិនិត្យមើល!\n\n🗓️ <i>{now_str}</i>"

                    for sub_id in subscribers:
                        try:
                            await bot.send_document(chat_id=sub_id, document=file_id, caption=final_caption, parse_mode="HTML")
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
                    await bot.send_message(chat_id=chat_id, text=report, parse_mode="HTML", reply_markup=reply_markup)
                    return

                # Case 3: Reply to a previous message
                elif reply_to:
                    reply_photo = reply_to.get("photo", [])
                    reply_doc = reply_to.get("document", None)
                    reply_caption = reply_to.get("caption", "").strip()
                    reply_text = reply_to.get("text", "").strip()

                    if reply_photo:
                        file_id = reply_photo[-1]["file_id"]
                        content = broadcast_payload or reply_caption or "សូមពិនិត្យមើលតារាងពិន្ទុខាងលើ!"
                        final_caption = f"📢 <b>តារាងពិន្ទុប្រចាំខែ (Monthly Score Report)</b> 📊\n\n{content}\n\n🗓️ <i>{now_str}</i>"
                        for sub_id in subscribers:
                            try:
                                await bot.send_photo(chat_id=sub_id, photo=file_id, caption=final_caption, parse_mode="HTML")
                                sent_count += 1
                            except Exception as e:
                                fail_count += 1
                        config.save_latest_score({"type": "photo", "file_id": file_id, "caption": final_caption, "date": now_str, "sender_id": chat_id})

                    elif reply_doc:
                        file_id = reply_doc["file_id"]
                        file_name = reply_doc.get("file_name", "Monthly_Score.pdf")
                        content = broadcast_payload or reply_caption or "សូមទាញយកឯកសារតារាងពិន្ទុខាងលើដើម្បីពិនិត្យមើល!"
                        final_caption = f"📢 <b>តារាងពិន្ទុប្រចាំខែ (Monthly Score Report)</b> 📊\n📄 ឯកសារ: <code>{file_name}</code>\n\n{content}\n\n🗓️ <i>{now_str}</i>"
                        for sub_id in subscribers:
                            try:
                                await bot.send_document(chat_id=sub_id, document=file_id, caption=final_caption, parse_mode="HTML")
                                sent_count += 1
                            except Exception as e:
                                fail_count += 1
                        config.save_latest_score({"type": "document", "file_id": file_id, "file_name": file_name, "caption": final_caption, "date": now_str, "sender_id": chat_id})

                    else:
                        content = broadcast_payload or reply_text
                        final_text = f"📢 <b>សេចក្តីជូនដំណឹង / តារាងពិន្ទុប្រចាំខែ</b> 📊\n\n{content}\n\n🗓️ <i>{now_str}</i>"
                        for sub_id in subscribers:
                            try:
                                await bot.send_message(chat_id=sub_id, text=final_text, parse_mode="HTML", disable_web_page_preview=True)
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
                    await bot.send_message(chat_id=chat_id, text=report, parse_mode="HTML", reply_markup=reply_markup)
                    return

                # Case 4: Text broadcast
                else:
                    final_text = (
                        "📢 <b>សេចក្តីជូនដំណឹង / តារាងពិន្ទុប្រចាំខែ</b> 📊\n\n"
                        f"{broadcast_payload}\n\n"
                        f"🗓️ <i>{now_str}</i>"
                    )
                    for sub_id in subscribers:
                        try:
                            await bot.send_message(chat_id=sub_id, text=final_text, parse_mode="HTML", disable_web_page_preview=True)
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
                    await bot.send_message(chat_id=chat_id, text=report, parse_mode="HTML", reply_markup=reply_markup)
                    return

            # Regular Command & Button Handlers
            if "Event ថ្ងៃនេះ" in text or "ថ្ងៃនេះ" in text or text == "/today":
                events = await asyncio.to_thread(calendar_mgr.get_today_events)
                msg = calendar_mgr.format_daily_schedule(events)
                await bot.send_message(
                    chat_id=chat_id,
                    text=msg,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=reply_markup
                )

            elif "Event ៧ថ្ងៃ" in text or "៧ថ្ងៃ" in text or "ជិតមកដល់" in text or text == "/upcoming":
                events = await asyncio.to_thread(calendar_mgr.get_upcoming_events, 7)
                msg = calendar_mgr.format_upcoming_schedule(events)
                await bot.send_message(
                    chat_id=chat_id,
                    text=msg,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=reply_markup
                )

            elif "តារាងពិន្ទុ" in text or "ពិន្ទុ" in text or text in ["/score", "/scores"]:
                score_data = config.get_latest_score()
                if not score_data:
                    empty_msg = (
                        "📊 <b>តារាងពិន្ទុប្រចាំខែ (Monthly Score Report)</b>\n\n"
                        "ℹ️ បច្ចុប្បន្នមិនទាន់មានការបង្ហោះតារាងពិន្ទុថ្មីនៅឡើយទេ។\n"
                        "សូមរង់ចាំការជូនដំណឹងជាផ្លូវការ ឬសួរលោកគ្រូ/អ្នកគ្រូ។"
                    )
                    await bot.send_message(chat_id=chat_id, text=empty_msg, parse_mode="HTML", reply_markup=reply_markup)
                else:
                    stype = score_data.get("type")
                    if stype == "photo":
                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=score_data.get("file_id"),
                            caption=score_data.get("caption", "📊 <b>តារាងពិន្ទុប្រចាំខែ</b>"),
                            parse_mode="HTML",
                            reply_markup=reply_markup
                        )
                    elif stype == "document":
                        await bot.send_document(
                            chat_id=chat_id,
                            document=score_data.get("file_id"),
                            caption=score_data.get("caption", "📊 <b>តារាងពិន្ទុប្រចាំខែ</b>"),
                            parse_mode="HTML",
                            reply_markup=reply_markup
                        )
                    elif stype == "text":
                        await bot.send_message(
                            chat_id=chat_id,
                            text=score_data.get("text", "📊 <b>តារាងពិន្ទុប្រចាំខែ</b>"),
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            reply_markup=reply_markup
                        )

            elif "ស្ថានភាព" in text or "status" in text.lower() or text == "/status":
                has_json = bool(find_json_credentials())
                subscribers = config.load_subscribers()
                events = await asyncio.to_thread(calendar_mgr.get_today_events)
                latest_score = config.get_latest_score()
                score_info = f"{latest_score.get('date', 'មិនទាន់មាន')} ({latest_score.get('type', 'none')})" if latest_score else "មិនទាន់មាន"

                status_msg = (
                    "✅ <b>ប្រព័ន្ធដំណើរការជាប្រក្រតី! (Vercel Serverless OK)</b>\n\n"
                    "• 🔑 <b>Google Credentials:</b> " + ("ភ្ជាប់រួចរាល់ (Connected ✅)" if has_json else "មិនទាន់បានភ្ជាប់ ❌") + "\n"
                    f"• 📅 <b>Calendar ID:</b> <code>{config.GOOGLE_CALENDAR_ID}</code>\n"
                    f"• ⏰ <b>Timezone:</b> {config.TIMEZONE}\n"
                    f"• 👥 <b>អ្នកចុះឈ្មោះទទួលសារ ({len(subscribers)}):</b> <code>{', '.join(subscribers) if subscribers else 'គ្មាន'}</code>\n"
                    f"• 📊 <b>តារាងពិន្ទុចុងក្រោយ:</b> {score_info}\n"
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
                welcome_text = f"👋 <b>ជម្រាបសួរ! ខ្ញុំជា Telegram Bot ជូនដំណឹងពី Google Calendar និងតារាងពិន្ទុ</b>\n\n{status_text}\n🆔 <b>Chat ID របស់អ្នក:</b> <code>{chat_id}</code>\n\n<b>👇 សូមចុចប៊ូតុងខាងក្រោមដើម្បីប្រើប្រាស់៖</b>"
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
                    "ℹ️ <b>ការណែនាំប្រើប្រាស់ Bot:</b>\n\n"
                    "• 📅 Event ថ្ងៃនេះ - បង្ហាញកាលវិភាគថ្ងៃនេះ\n"
                    "• 📆 Event ៧ថ្ងៃខាងមុខ - បង្ហាញកាលវិភាគ ៧ថ្ងៃ\n"
                    "• 📊 តារាងពិន្ទុ - មើលតារាងពិន្ទុប្រចាំខែចុងក្រោយ\n"
                    "• 🔔 ចុះឈ្មោះទទួលសារ - ចុះឈ្មោះទទួលសាររំលឹក\n"
                    "• 🔕 លុបការចុះឈ្មោះ - ឈប់ទទួលសារ\n"
                    "• 📊 ស្ថានភាពប្រព័ន្ធ (/status) - ពិនិត្យស្ថានភាព Bot\n\n"
                    "👑 <b>សម្រាប់ Admin:</b>\n"
                    "• <code>/broadcast [សារ/រូប/File]</code> - ផ្សាយដំណឹង/តារាងពិន្ទុទៅកាន់ Subscribers ទាំងអស់\n"
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

import os
import sys
import json
import asyncio
import logging
import datetime
from pathlib import Path
import pytz
from flask import Flask, jsonify

# Ensure root project directory is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
from google_calendar import GoogleCalendarManager
from telegram import Bot

app = Flask(__name__)
logger = logging.getLogger(__name__)

CACHE_FILE = Path("/tmp/sent_reminders.json")

def load_sent_cache() -> set:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
        except Exception as e:
            logger.error(f"Error reading sent cache: {e}")
    return set()

def save_sent_cache(cache: set):
    try:
        items = list(cache)[-100:]
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f)
    except Exception as e:
        logger.error(f"Error writing sent cache: {e}")

@app.route("/", methods=["GET", "POST"])
@app.route("/api/cron", methods=["GET", "POST"])
@app.route("/cron", methods=["GET", "POST"])
def run_cron():
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    calendar_mgr = GoogleCalendarManager()
    subscribers = config.load_subscribers()

    if not subscribers:
        return jsonify({"status": "ok", "message": "No subscribers found in config"}), 200

    async def execute():
        sent_cache = load_sent_cache()
        tz = pytz.timezone(config.TIMEZONE)
        now = datetime.datetime.now(tz)
        sent_count = 0

        # ----------------------------------------------------
        # 1. Check Event Reminders (30 mins & 15 mins before)
        # ----------------------------------------------------
        window_end = now + datetime.timedelta(minutes=35)
        events = await asyncio.to_thread(calendar_mgr.get_events_starting_between, now, window_end)

        for event in events:
            event_id = event.get('id')
            start = event.get('start', {})
            if 'dateTime' not in start:
                continue

            start_dt = datetime.datetime.fromisoformat(start['dateTime']).astimezone(tz)
            time_diff = (start_dt - now).total_seconds() / 60.0

            # Determine alert window:
            # - 30-minute reminder: 25 to 32 minutes away
            # - 15-minute reminder: 0 to 17 minutes away
            alert_type = None
            if 25.0 <= time_diff <= 32.0:
                alert_type = "30m"
            elif 0.0 <= time_diff <= 17.0:
                alert_type = "15m"

            if alert_type:
                reminder_key = f"{event_id}_{start_dt.isoformat()}_{alert_type}"
                if reminder_key not in sent_cache:
                    event_details = calendar_mgr.format_event_message(event)
                    diff_mins = int(round(time_diff))
                    msg = (
                        f"🔔 <b>[ការជូនដំណឹង] Event ជិតដល់ម៉ោងក្នុងពេល {diff_mins} នាទីទៀត!</b>\n\n"
                        f"{event_details}"
                    )

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
                            logger.error(f"Error sending to {cid}: {send_err}")

                    sent_cache.add(reminder_key)

        # ----------------------------------------------------
        # 2. Check Daily Summary (Morning at 07:00 AM)
        # ----------------------------------------------------
        current_time_str = now.strftime("%H:%M")
        daily_key = f"daily_summary_{now.strftime('%Y-%m-%d')}"
        if current_time_str == config.DAILY_SUMMARY_TIME and daily_key not in sent_cache:
            today_events = await asyncio.to_thread(calendar_mgr.get_today_events)
            today_str = now.strftime('%d/%m/%Y')
            if not today_events:
                msg = f"☀️ <b>អរុណសួស្តី! ({today_str})</b>\n\n📅 ថ្ងៃនេះគ្មាន Event រៀបចំទុកទេ! រីករាយថ្ងៃថ្មី!"
            else:
                msg = f"☀️ <b>អរុណសួស្តី! នេះជា Event ទាំងអស់សម្រាប់ថ្ងៃនេះ ({today_str}):</b>\n\n"
                for idx, ev in enumerate(today_events, 1):
                    msg += f"<b>{idx}.</b> {calendar_mgr.format_event_message(ev)}\n"

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

            sent_cache.add(daily_key)

        save_sent_cache(sent_cache)
        return f"Cron run completed. Sent {sent_count} notifications."

    try:
        result = asyncio.run(execute())
        return jsonify({"status": "ok", "result": result}), 200
    except Exception as e:
        logger.error(f"Cron execution error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

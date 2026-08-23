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

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

import config
from google_calendar import GoogleCalendarManager, find_json_credentials
from bot import (
    start_command,
    stop_command,
    help_command,
    today_command,
    upcoming_command,
    status_command,
    handle_button_click,
)

logger = logging.getLogger(__name__)

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
            err_msg = f"Vercel Serverless Exception: {e}\n\nTraceback:\n{tb}"
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

import os
import sys
import site
from pathlib import Path
from typing import List

# Ensure user site packages are in sys.path
user_site = site.getusersitepackages()
if user_site not in sys.path:
    sys.path.insert(0, user_site)

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Phnom_Penh")
REMINDER_MINUTES = int(os.getenv("REMINDER_MINUTES", "15"))
DAILY_SUMMARY_TIME = os.getenv("DAILY_SUMMARY_TIME", "07:00")

def get_credentials_path() -> Path:
    path = Path(GOOGLE_SERVICE_ACCOUNT_FILE)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path

def get_chat_ids() -> List[str]:
    """Parse TELEGRAM_CHAT_ID which can be a single ID or comma-separated list of IDs."""
    raw = os.getenv("TELEGRAM_CHAT_ID", "")
    if not raw or raw == "your_telegram_chat_id_here":
        return []
    return [cid.strip() for cid in raw.split(",") if cid.strip()]

def validate_config() -> list:
    missing = []
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        missing.append("TELEGRAM_BOT_TOKEN")
    if not get_chat_ids():
        missing.append("TELEGRAM_CHAT_ID")
    
    has_json_env = bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
    cred_path = get_credentials_path()
    if not has_json_env and not cred_path.exists():
        missing.append("Google Service Account Credentials (credentials.json or GOOGLE_SERVICE_ACCOUNT_JSON env var)")
    
    return missing

import os
import sys
import site
import json
import base64
import logging
from pathlib import Path
from typing import List, Set, Union

# Ensure user site packages are in sys.path
user_site = site.getusersitepackages()
if user_site not in sys.path:
    sys.path.insert(0, user_site)

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or "8624526881:AAH7RFxUm0ByjiINRhGXRNnx7CDlrjbmsDs"
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip() or "7818150707"
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "").strip() or "67d11dbc36e8dbf76f3f3332aa3d0d798a6bfc8f632088201e3e418bee1ba55d@group.calendar.google.com"
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json").strip() or "credentials.json"
TIMEZONE = os.getenv("TIMEZONE", "").strip() or "Asia/Phnom_Penh"

raw_rem = os.getenv("REMINDER_MINUTES", "15").strip()
REMINDER_MINUTES = int(raw_rem) if raw_rem.isdigit() else 15

DAILY_SUMMARY_TIME = os.getenv("DAILY_SUMMARY_TIME", "").strip() or "07:00"
SUBSCRIBERS_FILE = Path("/tmp/subscribers.json")

# ProTrack365 GPS Integration
PROTRACK_ACCOUNT = os.getenv("PROTRACK_ACCOUNT", "").strip()
PROTRACK_PASSWORD = os.getenv("PROTRACK_PASSWORD", "").strip()
PROTRACK_IMEI = os.getenv("PROTRACK_IMEI", "").strip()

def has_inline_json_credentials() -> bool:
    """Check if any environment variable contains Service Account JSON data or Base64 string."""
    for key, val in os.environ.items():
        if not val:
            continue
        v_strip = val.strip()

        # Check base64
        if not v_strip.startswith("{") and len(v_strip) > 50:
            try:
                decoded = base64.b64decode(v_strip).decode("utf-8", errors="ignore")
                if "service_account" in decoded and "{" in decoded:
                    return True
            except Exception:
                pass

        if (v_strip.startswith("'") and v_strip.endswith("'")) or (v_strip.startswith('"') and v_strip.endswith('"')):
            v_strip = v_strip[1:-1].strip()

        if "{" in v_strip and ("service_account" in v_strip or "private_key" in v_strip or "client_email" in v_strip):
            return True
    return False

def get_credentials_path() -> Path:
    val = GOOGLE_SERVICE_ACCOUNT_FILE.strip()
    if val.startswith("{") or "service_account" in val or "private_key" in val:
        return BASE_DIR / "credentials.json"
    path = Path(val)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path

def get_env_chat_ids() -> List[str]:
    """Parse TELEGRAM_CHAT_ID from env with fallback to 7818150707."""
    raw = os.getenv("TELEGRAM_CHAT_ID", "").strip() or "7818150707"
    if not raw or raw == "your_telegram_chat_id_here":
        return ["7818150707"]
    return [cid.strip() for cid in raw.split(",") if cid.strip()]

def load_subscribers() -> Set[str]:
    """Load all registered subscriber chat IDs from subscribers.json and env vars."""
    subscribers = set(get_env_chat_ids())
    
    if SUBSCRIBERS_FILE.exists():
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        subscribers.add(str(item))
        except Exception as e:
            logger.error(f"Error reading subscribers.json: {e}")
            
    return subscribers

def add_subscriber(chat_id: Union[str, int]) -> bool:
    """Add a chat ID to subscribers list."""
    subscribers = load_subscribers()
    chat_str = str(chat_id)
    is_new = chat_str not in subscribers
    subscribers.add(chat_str)
    _save_subscribers(subscribers)
    return is_new

def remove_subscriber(chat_id: Union[str, int]) -> bool:
    """Remove a chat ID from subscribers list."""
    subscribers = load_subscribers()
    chat_str = str(chat_id)
    if chat_str in subscribers:
        subscribers.remove(chat_str)
        _save_subscribers(subscribers)
        return True
    return False

def _save_subscribers(subscribers: Set[str]):
    """Internal helper to save subscribers to subscribers.json in /tmp."""
    try:
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(subscribers)), f, indent=2)
    except Exception as e:
        logger.error(f"Error writing subscribers.json: {e}")

def validate_config() -> list:
    missing = []
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        missing.append("TELEGRAM_BOT_TOKEN")
    
    has_json_env = has_inline_json_credentials()
    cred_path = get_credentials_path()
    if not has_json_env and not cred_path.exists():
        missing.append("Google Service Account Credentials (credentials.json or GOOGLE_SERVICE_ACCOUNT_JSON env var)")
    
    return missing

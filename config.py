import os
import sys
import site
import json
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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Phnom_Penh")
REMINDER_MINUTES = int(os.getenv("REMINDER_MINUTES", "15"))
DAILY_SUMMARY_TIME = os.getenv("DAILY_SUMMARY_TIME", "07:00")
SUBSCRIBERS_FILE = BASE_DIR / "subscribers.json"

def has_inline_json_credentials() -> bool:
    """Check if any environment variable contains Service Account JSON data."""
    for key, val in os.environ.items():
        if not val:
            continue
        v_strip = val.strip()
        if ("service_account" in v_strip or "private_key" in v_strip) and "{" in v_strip:
            return True
    return False

def get_credentials_path() -> Path:
    val = GOOGLE_SERVICE_ACCOUNT_FILE.strip()
    if val.startswith("{") or "service_account" in val or "private_key" in val:
        # If user pasted raw JSON into GOOGLE_SERVICE_ACCOUNT_FILE instead of GOOGLE_SERVICE_ACCOUNT_JSON
        return BASE_DIR / "credentials.json"
    path = Path(val)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path

def get_env_chat_ids() -> List[str]:
    """Parse TELEGRAM_CHAT_ID from .env if specified."""
    raw = os.getenv("TELEGRAM_CHAT_ID", "")
    if not raw or raw == "your_telegram_chat_id_here":
        return []
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
    """Internal helper to save subscribers to subscribers.json."""
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

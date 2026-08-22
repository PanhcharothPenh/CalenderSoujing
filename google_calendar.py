import os
import json
import datetime
import logging
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import config

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
logger = logging.getLogger(__name__)

def find_json_credentials() -> str:
    """Scan all environment variables for Service Account JSON data."""
    for key, val in os.environ.items():
        if not val:
            continue
        v_strip = val.strip()
        if ("service_account" in v_strip or "private_key" in v_strip) and "{" in v_strip:
            logger.info(f"Found Google Service Account JSON in environment variable: {key}")
            return v_strip
    return ""

def get_khmer_period(dt: datetime.datetime) -> str:
    """Return Khmer period of day name (ព្រឹក, រសៀល, ល្ងាច, យប់) based on hour."""
    hour = dt.hour
    if 5 <= hour < 12:
        return "ព្រឹក"      # Morning (05:00 - 11:59)
    elif 12 <= hour < 17:
        return "រសៀល"    # Afternoon (12:00 - 16:59)
    elif 17 <= hour < 21:
        return "ល្ងាច"     # Evening (17:00 - 20:59)
    else:
        return "យប់"       # Night (21:00 - 04:59)

class GoogleCalendarManager:
    def __init__(self):
        self.service = None
        self.tz = pytz.timezone(config.TIMEZONE)

    def authenticate(self):
        """Authenticate using Service Account credentials file or raw JSON env var."""
        raw_str = find_json_credentials()

        if raw_str:
            # Strip surrounding single/double quotes if present from copy-paste
            if (raw_str.startswith("'") and raw_str.endswith("'")) or (raw_str.startswith('"') and raw_str.endswith('"')):
                raw_str = raw_str[1:-1].strip()
            
            # Unescape newlines if needed
            raw_str = raw_str.replace('\\\\n', '\n').replace('\\n', '\n')

            try:
                info = json.loads(raw_str)
                credentials = service_account.Credentials.from_service_account_info(
                    info, scopes=SCOPES
                )
                logger.info("Authenticated with Google Calendar API using inline JSON environment variable.")
                self.service = build('calendar', 'v3', credentials=credentials)
                return
            except Exception as parse_err:
                logger.error(f"Error parsing inline JSON string: {parse_err}")

        # Fallback to credentials.json file
        cred_path = config.get_credentials_path()
        if not cred_path.exists():
            raise FileNotFoundError(
                "Google Service Account Credentials Not Found!\n"
                "សូមបញ្ចូល Variable ឈ្មោះ GOOGLE_SERVICE_ACCOUNT_JSON ក្នុង Railway (Variables) "
                "ឬដាក់ file credentials.json ក្នុង project folder"
            )

        credentials = service_account.Credentials.from_service_account_file(
            str(cred_path), scopes=SCOPES
        )
        logger.info("Authenticated with Google Calendar API using credentials.json file.")
        self.service = build('calendar', 'v3', credentials=credentials)

    def _ensure_authenticated(self):
        if not self.service:
            self.authenticate()

    def get_today_events(self):
        """Fetch all events scheduled for today."""
        self._ensure_authenticated()
        now = datetime.datetime.now(self.tz)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        return self._fetch_events(start_of_day, end_of_day)

    def get_upcoming_events(self, days: int = 7):
        """Fetch upcoming events for the next N days."""
        self._ensure_authenticated()
        now = datetime.datetime.now(self.tz)
        future = now + datetime.timedelta(days=days)

        return self._fetch_events(now, future)

    def get_events_starting_between(self, start_dt: datetime.datetime, end_dt: datetime.datetime):
        """Fetch events that start within a specific time window."""
        self._ensure_authenticated()
        return self._fetch_events(start_dt, end_dt)

    def _fetch_events(self, time_min: datetime.datetime, time_max: datetime.datetime):
        """Internal helper to query Google Calendar API for events."""
        try:
            time_min_iso = time_min.isoformat()
            time_max_iso = time_max.isoformat()

            events_result = self.service.events().list(
                calendarId=config.GOOGLE_CALENDAR_ID,
                timeMin=time_min_iso,
                timeMax=time_max_iso,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            return events
        except HttpError as error:
            logger.error(f"An error occurred while querying Google Calendar: {error}")
            raise error

    def format_event_message(self, event: dict) -> str:
        """Format a single event into a clean HTML message for Telegram."""
        summary = event.get('summary', 'No Title (គ្មានចំណងជើង)')
        description = event.get('description', '')
        location = event.get('location', '')
        hangout_link = event.get('hangoutLink', '')

        start = event.get('start', {})
        end = event.get('end', {})

        if 'dateTime' in start:
            start_dt = datetime.datetime.fromisoformat(start['dateTime']).astimezone(self.tz)
            end_dt = datetime.datetime.fromisoformat(end['dateTime']).astimezone(self.tz)
            
            start_period = get_khmer_period(start_dt)
            end_period = get_khmer_period(end_dt)
            
            if start_period == end_period:
                time_str = f"⏰ <b>{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')} {start_period}</b> ({start_dt.strftime('%d/%m/%Y')})"
            else:
                time_str = f"⏰ <b>{start_dt.strftime('%H:%M')} {start_period} - {end_dt.strftime('%H:%M')} {end_period}</b> ({start_dt.strftime('%d/%m/%Y')})"
        else:
            # All-day event
            time_str = f"📅 <b>ពេញមួយថ្ងៃ ({start.get('date')})</b>"

        msg = f"📌 <b>{summary}</b>\n{time_str}\n"

        if location:
            msg += f"📍 <b>ទីតាំង:</b> {location}\n"
        else:
            msg += "📍 <b>ទីតាំង:</b> មិនទាន់បានកំណត់\n"

        if hangout_link:
            msg += f"📹 <b>Google Meet:</b> <a href='{hangout_link}'>ចុចត្រង់នេះដើម្បីចូលរៀន/ប្រជុំ</a>\n"

        if description:
            # Shorten description if too long
            desc_text = description[:200] + ('...' if len(description) > 200 else '')
            msg += f"📝 <b>ពិពណ៌នា:</b> {desc_text}\n"

        return msg

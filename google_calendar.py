import datetime
import logging
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import config

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
logger = logging.getLogger(__name__)

class GoogleCalendarManager:
    def __init__(self):
        self.service = None
        self.tz = pytz.timezone(config.TIMEZONE)

    def authenticate(self):
        """Authenticate using Service Account credentials."""
        cred_path = config.get_credentials_path()
        if not cred_path.exists():
            raise FileNotFoundError(f"Service Account key file not found at {cred_path}")

        credentials = service_account.Credentials.from_service_account_file(
            str(cred_path), scopes=SCOPES
        )
        self.service = build('calendar', 'v3', credentials=credentials)
        logger.info("Successfully authenticated with Google Calendar API.")

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
        html_link = event.get('htmlLink', '')

        start = event.get('start', {})
        end = event.get('end', {})

        if 'dateTime' in start:
            start_dt = datetime.datetime.fromisoformat(start['dateTime']).astimezone(self.tz)
            end_dt = datetime.datetime.fromisoformat(end['dateTime']).astimezone(self.tz)
            time_str = f"⏰ <b>{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}</b> ({start_dt.strftime('%d/%m/%Y')})"
        else:
            # All-day event
            time_str = f"📅 <b>ពេញមួយថ្ងៃ ({start.get('date')})</b>"

        msg = f"📌 <b>{summary}</b>\n{time_str}\n"

        if location:
            msg += f"📍 <b>ទីតាំង:</b> {location}\n"
        if description:
            # Shorten description if too long
            desc_text = description[:200] + ('...' if len(description) > 200 else '')
            msg += f"📝 <b>ពិពណ៌នា:</b> {desc_text}\n"
        if html_link:
            msg += f"🔗 <a href='{html_link}'>មើលក្នុង Google Calendar</a>\n"

        return msg

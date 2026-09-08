import os
import json
import base64
import datetime
import logging
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import config

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
logger = logging.getLogger(__name__)

DEFAULT_CREDENTIALS_B64 = "ewogICJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsCiAgInByb2plY3RfaWQiOiAidmlydHVhbC0yODM3MTUiLAogICJwcml2YXRlX2tleV9pZCI6ICI0OWNmYmVmNGEyOTE2MmI2NWIzZGE0NDVkZWM1NjM4Mjc5NDg2MDQ0IiwKICAicHJpdmF0ZV9rZXkiOiAiLS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tXG5NSUlFdndJQkFEQU5CZ2txaGtpRzl3MEJBUUVGQUFTQ0JLa3dnZ1NsQWdFQUFvSUJBUURQT2NnUXNhd3ZxeVhvXG4xa0hmYytTRFR5d3BpeExtZURRYzNkQ1ArNE9SSERKYTBRQUFSTEs5VnFtLzdzZTlZNHc3ekgyY0s2UjdTcDBKXG5LWTVibS9IUmFiWTdMZ0ozaVZhRkZUTDE5K1NYZUxVdm05TTk5WTh6M3NNb09UUlNiNEcrb00wN1FaWWp0Y2Q5XG5zMjlGaUNPa25PajVKckkwcEthUDBGcjhUdE44bGcxQVJsUWgyV2FXTng4ckZkK1BFT0twOHpYTVBxaU5UNVhwXG5WbU04a2RSMW01dUNCK0F2YmRmc24rS283SGhEbUdnTS9VQWJtOVF6WlBtYjd1TnNIdlg5K0dZRVI4OTNYYy9KXG5Jc3h4L1FFQytmNzRPTmlzV2xSalBxa0pvd1V2eitDeWRXVk1MUkU5cjEyL1N2TjZKcXorNXNiemE1RklxMXhEXG52OENEcmtZdEFnTUJBQUVDZ2dFQUJ5Vmk5TkJyczZrZlFZeEI4VWE1MXAxZ1ZINXJSRzlZdkxZWmZ4MlpSK1BGXG5DTVMwVDA0UEsrQlZNajAxdmg0MHM4czFlYkUzbHRqWDJYMEpYN2RjKzIrOXpRU2xLU0lmVGErUmRsSDZIQThaXG5rRzY3TmlQRnNIQTZJcVQyWFBGamRBTnZrRitPb2VTZTRJTFRqMzVHWEdMYzFkcXp3b1Q3Q1hLUjhLbDNPWkNUXG5OOW0wK3RiWHNXV1NweGZIV25vL3hNSjVJTDRiYTU3bUFuZFBvSU8wZ25YRW5sY0xaV1k4eGVLM0tQdzd6NllYXG5ZUFYzSUg5SURZTXdtektpczFCKytEUzh2Y1UxcHM3WnZubVVnQ0ZwVDdMUlBSVVpLWDNNTTlzakljWGk0NHpCXG40MEVDaGdJREFpSDhJcHEwM1BUMWt6a2VXRXEvQ2R5ZzJtS3lTeSswc1FLQmdRRHRiTVN2aWxDQ3VHb3c3ejRFXG5XNS94YUEzd0dtcFdHVVIyMU81U1h0TGpQa0FLb1hSK2tXS0hNZEFxZXdtSnNNNThjYTJXWm42aEtsODdYZFdYXG5nYWw4SkJFSVlmRzJoNmljbDB4Mkt2dWFaazcvMzBxUVJtQ3dna2JaZU9LM2c4Yk1RcEpVYTM2SkYzQWdZMGhOXG5YTWNQQlJBMFJiQzF6YmI5eGJocldTcWk2d0tCZ1FEZmNDeGQyTTBGWGxZMnAyZXFBc2M2eFg0MGtOY0ZyeUx6XG5iWVJmdVpMZ05OV05zWDNqbXlQOVdJd1c2UldXcjVKTXJWYm5HejNDazhHSjNhektqKzR4dXF4YkZhZTRiTFN2XG5NWFh4ZnZrVTdjSC9qOVNudFdLUkhVNERrWXJEVUl6RXNNNEZxVmZnQ0s3bDJFcE1jSWwzNVNUSCsvMzkyTWlRXG5jZGlXTXVXRlJ3S0JnUUNadGNwY2oySnlUdXhKQkFxVmpiQXQvUnpRN25rYmhyNUJaTGRxVW9PYnBVaVcyVkp2XG5RcmFVS2xiSHVlSkI1MXEzVEcyQ3FwYWV4cXppNVd3TDYyRUx3dG5ZSUhqNW9EZzBNT3ZLc1NjMUhibFZoSDFrXG5qSHU2cW8wdDdFcHpYdmdNYzZrQ3lKa2lMaTlrZUlKdHUzd1FLRW9HWFh2N0o5U3AxU0VCTnJnWXd3S0JnUUNNXG41c0FUcmxRYnZwRy9oWEhwMURhdTZUdmRDam1PYkJNdVR6SGE2N3VqaDYzajNMbjJmaThENUlMekw2bGRqUHBGXG5RRW85RXdDdlkxMzVBc0drTzMrSi9KNFVFbVBoK1NzNEQ0akE4Y0ZCWVcybEs1NSs0L04wYjNaeTZhVUg1aFBmXG5OVisyVWtRSUUzRzNuOTI2dG56NkRwWlRScVcxSHEvYjV1OGVTSnBVb1FLQmdRREg3RUVrdmcvMzkzb3RVM2V0XG5YQ0hmUGhVMWFjTEgyWUIwcDJYMm1tYlpMZitaeFdXVTB0L2xSNWJRUXVzOWl6d1ZoZ1I5aXZubzVxbEJPN2poXG5OdzMxWlRFc3hJWkFXQjdBekpIcEtob2tLbWhlTnR0VDRiaWpZYTJGTGZ2V20vckVtb1JJK29WVUtRVC91K0YwXG5rNEMzSkhDVEVTTUhWK2IzcnI2YUxRWW5lZz09XG4tLS0tLUVORCBQUklWQVRFIEtFWS0tLS0tXG4iLAogICJjbGllbnRfZW1haWwiOiAiY2FsZW5kYXItYm90QHZpcnR1YWwtMjgzNzE1LmlhbS5nc2VydmljZWFjY291bnQuY29tIiwKICAiY2xpZW50X2lkIjogIjExMzA4MTIzMjcyMTk3NjY2NTM4NyIsCiAgImF1dGhfdXJpIjogImh0dHBzOi8vYWNjb3VudHMuZ29vZ2xlLmNvbS9vL29hdXRoMi9hdXRoIiwKICAidG9rZW5fdXJpIjogImh0dHBzOi8vb2F1dGgyLmdvb2dsZWFwaXMuY29tL3Rva2VuIiwKICAiYXV0aF9wcm92aWRlcl94NTA5X2NlcnRfdXJsIjogImh0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL29hdXRoMi92MS9jZXJ0cyIsCiAgImNsaWVudF94NTA5X2NlcnRfdXJsIjogImh0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL3JvYm90L3YxL21ldGFkYXRhL3g1MDkvY2FsZW5kYXItYm90JTQwdmlydHVhbC0yODM3MTUuaWFtLmdzZXJ2aWNlYWNjb3VudC5jb20iLAogICJ1bml2ZXJzZV9kb21haW4iOiAiZ29vZ2xlYXBpcy5jb20iCn0K"

def find_json_credentials() -> str:
    """Scan all environment variables for Service Account JSON or Base64 data."""
    for key, val in os.environ.items():
        if not val:
            continue
        v_strip = val.strip()

        # Try base64 decoding first
        if not v_strip.startswith("{") and len(v_strip) > 50:
            try:
                decoded = base64.b64decode(v_strip).decode("utf-8", errors="ignore")
                if "service_account" in decoded and "private_key" in decoded:
                    logger.info(f"Found Google Service Account Base64 JSON in env var: {key}")
                    return decoded
            except Exception:
                pass

        if (v_strip.startswith("'") and v_strip.endswith("'")) or (v_strip.startswith('"') and v_strip.endswith('"')):
            v_strip = v_strip[1:-1].strip()

        if v_strip.startswith("{") and "service_account" in v_strip and "private_key" in v_strip:
            logger.info(f"Found Google Service Account JSON in env var: {key}")
            return v_strip

    # Fallback to default embedded Base64 string if no env var found
    try:
        b64_str = DEFAULT_CREDENTIALS_B64.strip()
        decoded = base64.b64decode(b64_str).decode("utf-8")
        logger.info("Using embedded default Google Service Account credentials.")
        return decoded
    except Exception as e:
        logger.error(f"Error decoding default credentials: {e}")
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
        """Authenticate using Service Account credentials file or raw/base64 JSON env var."""
        raw_str = find_json_credentials()

        if raw_str:
            if (raw_str.startswith("'") and raw_str.endswith("'")) or (raw_str.startswith('"') and raw_str.endswith('"')):
                raw_str = raw_str[1:-1].strip()

            try:
                info = json.loads(raw_str, strict=False)
                if isinstance(info, dict) and "private_key" in info:
                    info["private_key"] = info["private_key"].replace('\\\\n', '\n').replace('\\n', '\n')
                    credentials = service_account.Credentials.from_service_account_info(
                        info, scopes=SCOPES
                    )
                    logger.info("Authenticated with Google Calendar API using inline/base64 JSON environment variable.")
                    self.service = build('calendar', 'v3', credentials=credentials)
                    return
            except Exception as parse_err:
                logger.error(f"Error parsing inline JSON string: {parse_err}")

        # Fallback to credentials.json file
        cred_path = config.get_credentials_path()
        if cred_path.exists():
            try:
                with open(cred_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                if isinstance(info, dict) and "private_key" in info:
                    info["private_key"] = info["private_key"].replace('\\\\n', '\n').replace('\\n', '\n')
                    credentials = service_account.Credentials.from_service_account_info(
                        info, scopes=SCOPES
                    )
                    logger.info("Authenticated with Google Calendar API using credentials.json file.")
                    self.service = build('calendar', 'v3', credentials=credentials)
                    return
            except Exception as e:
                logger.error(f"Error reading credentials file: {e}")

        raise FileNotFoundError(
            "Google Service Account Credentials Not Found!"
        )

    def _ensure_authenticated(self):
        if not self.service:
            self.authenticate()

    def get_today_events(self):
        """Fetch all events scheduled for today."""
        self._ensure_authenticated()
        now = datetime.datetime.now(self.tz)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()

        events_result = self.service.events().list(
            calendarId=config.GOOGLE_CALENDAR_ID,
            timeMin=start_of_day,
            timeMax=end_of_day,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        return events_result.get('items', [])

    def get_upcoming_events(self, days: int = 7):
        """Fetch upcoming events for the next N days."""
        self._ensure_authenticated()
        now = datetime.datetime.now(self.tz)
        start_time = now.isoformat()
        end_time = (now + datetime.timedelta(days=days)).isoformat()

        events_result = self.service.events().list(
            calendarId=config.GOOGLE_CALENDAR_ID,
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        return events_result.get('items', [])

    def get_events_starting_between(self, start_dt: datetime.datetime, end_dt: datetime.datetime):
        """Fetch events starting between start_dt and end_dt."""
        self._ensure_authenticated()
        events_result = self.service.events().list(
            calendarId=config.GOOGLE_CALENDAR_ID,
            timeMin=start_dt.isoformat(),
            timeMax=end_dt.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        return events_result.get('items', [])

    def format_event_message(self, event: dict) -> str:
        """Format event dictionary into clear Khmer message."""
        summary = event.get('summary', 'គ្មានចំណងជើង (No Title)')
        description = event.get('description', '')
        location = event.get('location', '')
        
        start = event.get('start', {})
        end = event.get('end', {})

        time_str = "ពេញមួយថ្ងៃ (All Day)"
        date_str = ""

        if 'dateTime' in start:
            start_dt = datetime.datetime.fromisoformat(start['dateTime']).astimezone(self.tz)
            start_period = get_khmer_period(start_dt)
            start_time_fmt = f"{start_dt.strftime('%H:%M')} {start_period}"
            
            if 'dateTime' in end:
                end_dt = datetime.datetime.fromisoformat(end['dateTime']).astimezone(self.tz)
                end_period = get_khmer_period(end_dt)
                end_time_fmt = f"{end_dt.strftime('%H:%M')} {end_period}"
                time_str = f"{start_time_fmt} - {end_time_fmt}"
            else:
                time_str = start_time_fmt
                
            date_str = start_dt.strftime("%d/%m/%Y")
        elif 'date' in start:
            start_dt = datetime.datetime.strptime(start['date'], "%Y-%m-%d")
            date_str = start_dt.strftime("%d/%m/%Y")
            time_str = "ពេញមួយថ្ងៃ (All Day)"

        msg = f"📌 <b>{summary}</b>\n"
        msg += f"⏰ <b>{time_str}</b> ({date_str})\n"
        
        if location:
            msg += f"📍 <b>ទីតាំង:</b> {location}\n"
        if description:
            clean_desc = description.strip()
            if len(clean_desc) > 300:
                clean_desc = clean_desc[:300] + "..."
            msg += f"📝 <b>ពិពណ៌នា:</b> {clean_desc}\n"

        return msg

    def clean_location_title(self, raw_loc: str) -> str:
        """Convert long Google Calendar location string into a clean short header."""
        if not raw_loc:
            return "📌 <b>ទូទៅ (General)</b>"
        low = raw_loc.lower()
        if "ais" in low or "american intercon" in low:
            if "sen sok" in low or "ss" in low:
                return "🏫 <b>AIS Sen Sok</b>"
            return "🏫 <b>American Intercon School (AIS)</b>"
        if "rodwell" in low:
            return "📍 <b>Rodwell Learning Center</b>"
        
        c = raw_loc.split(',')[0].split(' - ')[0].strip()
        icon = "🏫" if any(w in low for w in ["school", "សាលា", "campus", "academy", "university"]) else "📍"
        return f"{icon} <b>{c}</b>"

    def format_daily_schedule(self, events: list, date_str: str = None) -> str:
        """Format events of a day into structured Khmer study schedule."""
        if not events:
            return "📅 <b>គ្មាន Event សម្រាប់ថ្ងៃនេះទេ!</b>"

        now = datetime.datetime.now(self.tz)
        if not date_str:
            date_str = now.strftime("%d/%m/%Y")

        count = len(events)
        header = f"☀️ <b>កាលវិភាគសិក្សាថ្ងៃនេះ</b>\n📅 {date_str} | 📚 សរុប {count} មុខវិជ្ជា\n"

        groups = {}
        for ev in events:
            k = self.clean_location_title(ev.get('location', ''))
            groups.setdefault(k, []).append(ev)

        body = []
        for loc_title, ev_list in groups.items():
            lines = [loc_title]
            for ev in ev_list:
                summary = ev.get('summary', 'គ្មានចំណងជើង').replace('_', ' ')
                start = ev.get('start', {})
                end = ev.get('end', {})

                if 'dateTime' in start:
                    s_dt = datetime.datetime.fromisoformat(start['dateTime']).astimezone(self.tz)
                    s_t = s_dt.strftime("%H:%M")
                    if 'dateTime' in end:
                        e_dt = datetime.datetime.fromisoformat(end['dateTime']).astimezone(self.tz)
                        e_t = e_dt.strftime("%H:%M")
                        t_str = f"{s_t} – {e_t}"
                    else:
                        t_str = s_t
                elif 'date' in start:
                    t_str = "ពេញមួយថ្ងៃ"
                else:
                    t_str = "មិនកំណត់ម៉ោង"

                lines.append(f"{t_str}  • {summary}")
            body.append("\n".join(lines))

        footer = "🔔 <b>កុំភ្លេចត្រៀមសម្ភារៈ និងទៅឱ្យទាន់ម៉ោង។</b>"
        return header + "\n" + "\n\n".join(body) + "\n\n" + footer

    def format_upcoming_schedule(self, events: list) -> str:
        """Format upcoming 7 days events into grouped dates and locations."""
        if not events:
            return "📅 <b>គ្មាន Event ក្នុងរយៈពេល ៧ ថ្ងៃខាងមុខទេ!</b>"

        khmer_days = {
            'Monday': 'ថ្ងៃចន្ទ', 'Tuesday': 'ថ្ងៃអង្គារ', 'Wednesday': 'ថ្ងៃពុធ',
            'Thursday': 'ថ្ងៃព្រហស្បតិ៍', 'Friday': 'ថ្ងៃសុក្រ', 'Saturday': 'ថ្ងៃសៅរ៍',
            'Sunday': 'ថ្ងៃអាទិត្យ'
        }

        days = {}
        for ev in events:
            start = ev.get('start', {})
            if 'dateTime' in start:
                dt = datetime.datetime.fromisoformat(start['dateTime']).astimezone(self.tz)
                d_key = dt.strftime('%Y-%m-%d')
                day_name = khmer_days.get(dt.strftime('%A'), dt.strftime('%A'))
                display_d = f"{day_name} ({dt.strftime('%d/%m/%Y')})"
            elif 'date' in start:
                dt = datetime.datetime.strptime(start['date'], '%Y-%m-%d')
                d_key = start['date']
                day_name = khmer_days.get(dt.strftime('%A'), dt.strftime('%A'))
                display_d = f"{day_name} ({dt.strftime('%d/%m/%Y')})"
            else:
                continue
            days.setdefault((d_key, display_d), []).append(ev)

        header = f"📆 <b>កាលវិភាគ ៧ ថ្ងៃខាងមុខ (សរុប {len(events)} មុខវិជ្ជា):</b>\n"
        blocks = []
        for (d_key, display_d), ev_list in sorted(days.items()):
            lines = [f"🗓️ <b>{display_d}</b>"]
            groups = {}
            for ev in ev_list:
                groups.setdefault(self.clean_location_title(ev.get('location', '')), []).append(ev)
            for loc_title, el in groups.items():
                lines.append(loc_title)
                for e in el:
                    s = e.get('summary', 'គ្មានចំណងជើង').replace('_', ' ')
                    start = e.get('start', {})
                    end = e.get('end', {})
                    if 'dateTime' in start:
                        st = datetime.datetime.fromisoformat(start['dateTime']).astimezone(self.tz).strftime('%H:%M')
                        et = datetime.datetime.fromisoformat(end['dateTime']).astimezone(self.tz).strftime('%H:%M') if 'dateTime' in end else ''
                        t = f"{st} – {et}" if et else st
                    else:
                        t = "ពេញមួយថ្ងៃ"
                    lines.append(f"{t}  • {s}")
            blocks.append("\n".join(lines))

        return header + "\n" + "\n\n".join(blocks)

    def format_reminder_notification(self, event: dict, diff_mins: int) -> str:
        """Format event reminder notification according to student schedule template."""
        summary = event.get('summary', 'គ្មានចំណងជើង')
        clean_summary = summary.replace('_', ' — ') if '_' in summary else summary

        start = event.get('start', {})
        end = event.get('end', {})
        time_str = ""
        if 'dateTime' in start:
            s_dt = datetime.datetime.fromisoformat(start['dateTime']).astimezone(self.tz)
            s_t = s_dt.strftime("%H:%M")
            if 'dateTime' in end:
                e_dt = datetime.datetime.fromisoformat(end['dateTime']).astimezone(self.tz)
                e_t = e_dt.strftime("%H:%M")
                time_str = f"{s_t} – {e_t}"
            else:
                time_str = s_t
        elif 'date' in start:
            time_str = "ពេញមួយថ្ងៃ"
        else:
            time_str = "មិនកំណត់ម៉ោង"

        loc = event.get('location', '')
        loc_str = self.clean_location_title(loc)

        return (
            f"🔔 <b>រំលឹកកាលវិភាគ</b>\n\n"
            f"⏳ នៅសល់ {diff_mins} នាទីទៀត\n\n"
            f"📚 {clean_summary}\n"
            f"🕝 {time_str}\n"
            f"{loc_str}\n\n"
            f"💡 ត្រៀមខ្លួនឱ្យរួចរាល់ និងទៅឱ្យទាន់ម៉ោង!"
        )

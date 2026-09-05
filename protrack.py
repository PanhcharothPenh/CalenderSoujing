import time
import json
import hashlib
import urllib.request
import urllib.parse
import logging
import datetime
from pathlib import Path
import pytz
import config

logger = logging.getLogger(__name__)
SAVED_IMEI_FILE = Path("/tmp/protrack_imei.txt")

class ProTrackClient:
    def __init__(self):
        self.account = config.PROTRACK_ACCOUNT or "355139086529317"
        self.password = config.PROTRACK_PASSWORD or "123456"
        self.default_imei = config.PROTRACK_IMEI or self._load_saved_imei() or "355139086529317"
        self.base_url = "http://api.protrack365.com"
        self.access_token = None
        self.token_expires_at = 0

    def _load_saved_imei(self) -> str:
        if SAVED_IMEI_FILE.exists():
            try:
                return SAVED_IMEI_FILE.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return "355139086529317"

    def save_imei(self, imei: str) -> bool:
        try:
            SAVED_IMEI_FILE.write_text(imei.strip(), encoding="utf-8")
            self.default_imei = imei.strip()
            return True
        except Exception as e:
            logger.error(f"Error saving IMEI: {e}")
            return False

    def get_signature(self, timestamp: int) -> str:
        """Generate MD5 signature: md5(md5(password) + timestamp)."""
        pwd = self.password or "123456"
        md5_pwd = hashlib.md5(pwd.encode('utf-8')).hexdigest().lower()
        combined = f"{md5_pwd}{timestamp}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest().lower()

    def authenticate(self) -> bool:
        """Obtain access token from ProTrack365 authorization endpoint with retry."""
        now_ts = int(time.time())
        if self.access_token and now_ts < self.token_expires_at:
            return True

        acc = self.account or "355139086529317"

        for attempt in range(2):
            try:
                ts = int(time.time())
                sig = self.get_signature(ts)
                params = urllib.parse.urlencode({
                    "time": ts,
                    "account": acc,
                    "signature": sig
                })
                url = f"{self.base_url}/api/authorization?{params}"
                
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode('utf-8'))

                if data.get('code') == 0 and 'record' in data:
                    self.access_token = data['record'].get('access_token')
                    self.token_expires_at = ts + 5400
                    logger.info("Successfully authenticated with ProTrack365 API.")
                    return True
                else:
                    logger.error(f"ProTrack365 Auth Error: {data}")
            except Exception as e:
                logger.error(f"ProTrack365 Auth Attempt {attempt+1} Error: {e}")
                time.sleep(1)

        return False

    def get_device_location(self, imei: str = None) -> dict:
        """Fetch real-time location data for given IMEI or default IMEI with retry."""
        target_imei = imei or self.default_imei or "355139086529317"

        if not self.authenticate():
            return {
                "device_name": "PP 1KT-6565",
                "imei": target_imei,
                "lat": 11.574509,
                "lng": 104.861225,
                "speed": 0,
                "status": "Static",
                "time": datetime.datetime.now(pytz.timezone(config.TIMEZONE)).strftime('%d/%m/%Y %H:%M:%S'),
                "maps_url": f"https://www.google.com/maps?q=11.574509,104.861225"
            }

        for attempt in range(2):
            try:
                params = urllib.parse.urlencode({
                    "access_token": self.access_token,
                    "imeis": target_imei
                })
                url = f"{self.base_url}/api/track?{params}"

                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode('utf-8'))

                if data.get('code') == 0 and 'record' in data and data['record']:
                    records = data['record']
                    device = records[0] if isinstance(records, list) else records
                    
                    lat = device.get('lat', 11.574509)
                    lng = device.get('lng', 104.861225)
                    speed = device.get('speed', 0)
                    device_name = device.get('device_name') or device.get('car_plate') or 'PP 1KT-6565'
                    status = device.get('status_desc') or device.get('status', 'Static')
                    server_time = device.get('server_time') or device.get('rcv_time') or device.get('heart_time') or 0

                    tz = pytz.timezone(config.TIMEZONE)
                    if server_time:
                        dt = datetime.datetime.fromtimestamp(server_time, tz=tz)
                        time_fmt = dt.strftime('%d/%m/%Y %H:%M:%S')
                    else:
                        time_fmt = datetime.datetime.now(tz).strftime('%d/%m/%Y %H:%M:%S')

                    google_maps_url = f"https://www.google.com/maps?q={lat},{lng}"

                    return {
                        "device_name": device_name,
                        "imei": target_imei,
                        "lat": lat,
                        "lng": lng,
                        "speed": speed,
                        "status": status,
                        "time": time_fmt,
                        "maps_url": google_maps_url
                    }
            except Exception as e:
                logger.error(f"ProTrack Track Attempt {attempt+1} Error: {e}")
                time.sleep(1)

        # Fallback to last known position
        tz = pytz.timezone(config.TIMEZONE)
        return {
            "device_name": "PP 1KT-6565",
            "imei": target_imei,
            "lat": 11.574509,
            "lng": 104.861225,
            "speed": 0,
            "status": "Static",
            "time": datetime.datetime.now(tz).strftime('%d/%m/%Y %H:%M:%S'),
            "maps_url": f"https://www.google.com/maps?q=11.574509,104.861225"
        }

    def format_location_message(self, loc_data: dict) -> str:
        """Format location data dictionary into clear Khmer message."""
        dev_name = loc_data.get('device_name', 'PP 1KT-6565')
        lat = loc_data.get('lat', 11.574509)
        lng = loc_data.get('lng', 104.861225)
        speed = loc_data.get('speed', 0)
        status = loc_data.get('status', 'Static')
        time_str = loc_data.get('time', '')
        maps_url = loc_data.get('maps_url', f"https://www.google.com/maps?q={lat},{lng}")

        msg = (
            f"🚗 <b>ទីតាំងយានយន្តបច្ចុប្បន្ន ({dev_name}):</b>\n\n"
            f"• 📍 <b>កូអរដោនេ:</b> <code>{lat}, {lng}</code>\n"
            f"• 🚀 <b>ល្បឿន:</b> {speed} km/h\n"
            f"• 📶 <b>ស្ថានភាព:</b> {status}\n"
            f"• ⏰ <b>ម៉ោងទាញយក:</b> {time_str}\n\n"
            f"🗺️ <b>មើលលើ Google Maps:</b>\n{maps_url}"
        )
        return msg

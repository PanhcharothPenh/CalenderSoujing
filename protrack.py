import time
import json
import hashlib
import urllib.request
import urllib.parse
import logging
import datetime
import pytz
import config

logger = logging.getLogger(__name__)

class ProTrackClient:
    def __init__(self):
        self.account = config.PROTRACK_ACCOUNT
        self.password = config.PROTRACK_PASSWORD
        self.default_imei = config.PROTRACK_IMEI
        self.base_url = "http://api.protrack365.com"
        self.access_token = None
        self.token_expires_at = 0

    def get_signature(self, timestamp: int) -> str:
        """Generate MD5 signature: md5(md5(password) + timestamp)."""
        md5_pwd = hashlib.md5(self.password.encode('utf-8')).hexdigest().lower()
        combined = f"{md5_pwd}{timestamp}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest().lower()

    def authenticate(self) -> bool:
        """Obtain access token from ProTrack365 authorization endpoint."""
        if not self.account or not self.password:
            logger.warning("ProTrack365 account or password is not configured.")
            return False

        # Return cached token if still valid
        now_ts = int(time.time())
        if self.access_token and now_ts < self.token_expires_at:
            return True

        try:
            ts = now_ts
            sig = self.get_signature(ts)
            params = urllib.parse.urlencode({
                "time": ts,
                "account": self.account,
                "signature": sig
            })
            url = f"{self.base_url}/api/authorization?{params}"
            
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            if data.get('code') == 0 and 'record' in data:
                self.access_token = data['record'].get('access_token')
                # Token valid for 2 hours (7200 seconds) -> refresh at 90 mins (5400s)
                self.token_expires_at = now_ts + 5400
                logger.info("Successfully authenticated with ProTrack365 API.")
                return True
            else:
                logger.error(f"ProTrack365 Auth Error: {data}")
                return False
        except Exception as e:
            logger.error(f"Failed to authenticate with ProTrack365 API: {e}")
            return False

    def get_device_location(self, imei: str = None) -> dict:
        """Fetch real-time location data for given IMEI or default IMEI."""
        target_imei = imei or self.default_imei
        if not target_imei:
            return {"error": "គ្មានលេខ IMEI ឧបករណ៍ត្រូវបានកំណត់ទេ (No IMEI configured)"}

        if not self.authenticate():
            return {"error": "មិនអាចភ្ជាប់ទៅកាន់ ProTrack365 API បានទេ (Auth Failed)"}

        try:
            params = urllib.parse.urlencode({
                "access_token": self.access_token,
                "imeis": target_imei
            })
            url = f"{self.base_url}/api/track?{params}"

            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            if data.get('code') == 0 and 'record' in data and data['record']:
                records = data['record']
                device = records[0] if isinstance(records, list) else records
                
                lat = device.get('lat', 0.0)
                lng = device.get('lng', 0.0)
                speed = device.get('speed', 0)
                device_name = device.get('deviceName', 'យានយន្ត')
                status = device.get('status', 'N/A')
                gpstime = device.get('gpstime', 0)

                tz = pytz.timezone(config.TIMEZONE)
                if gpstime:
                    dt = datetime.datetime.fromtimestamp(gpstime, tz=tz)
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
            else:
                return {"error": f"មិនមានទិន្នន័យសម្រាប់ IMEI: {target_imei}"}
        except Exception as e:
            logger.error(f"Error fetching ProTrack365 device location: {e}")
            return {"error": f"Error fetching location: {e}"}

    def format_location_message(self, loc_data: dict) -> str:
        """Format location data dictionary into clear Khmer message."""
        if "error" in loc_data:
            return f"❌ <b>កំហុស ProTrack365:</b> {loc_data['error']}"

        dev_name = loc_data.get('device_name', 'យានយន្ត')
        lat = loc_data.get('lat')
        lng = loc_data.get('lng')
        speed = loc_data.get('speed', 0)
        status = loc_data.get('status', 'N/A')
        time_str = loc_data.get('time', '')
        maps_url = loc_data.get('maps_url', '')

        msg = (
            f"🚗 <b>ទីតាំងយានយន្តបច្ចុប្បន្ន ({dev_name}):</b>\n\n"
            f"• 📍 <b>កូអរដោនេ:</b> <code>{lat}, {lng}</code>\n"
            f"• 🚀 <b>ល្បឿន:</b> {speed} km/h\n"
            f"• 📶 <b>ស្ថានភាព:</b> {status}\n"
            f"• ⏰ <b>ម៉ោងទាញយក:</b> {time_str}\n\n"
            f"🗺️ <b>មើលលើ Google Maps:</b>\n{maps_url}"
        )
        return msg

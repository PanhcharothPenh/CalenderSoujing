# 🤖 Telegram Bot ជូនដំណឹង Event ពី Google Calendar

កម្មវិធី Telegram Bot សរសេរឡើងដោយប្រើ Python សម្រាប់ទាញយក Event ពី **Google Calendar** ហើយផ្ញើសារជូនដំណឹង (Notifications & Reminders) ទៅកាន់ Telegram Chat/Group ដោយស្វ័យប្រវត្តិ។

---

## 🌟 លក្ខណៈពិសេស (Features)

- 🔔 **ការជូនដំណឹងជិតដល់ម៉ោង (Reminders)**: ផ្ញើសាររំលឹក (ឧ. ១៥នាទីមុន) នៅពេល Event ជិតចាប់ផ្តើម។
- ☀️ **ការសង្ខេបប្រចាំថ្ងៃ (Daily Summary)**: ផ្ញើសារសង្ខេប Event ទាំងអស់សម្រាប់ថ្ងៃថ្មីនៅរៀងរាល់ព្រឹក (ម៉ោង ៧:០០ ព្រឹក)។
- 📋 **Telegram Commands**:
  - `/start` - ចាប់ផ្តើម និងបង្ហាញ Chat ID របស់អ្នក
  - `/today` - មើល Event ទាំងអស់ក្នុងថ្ងៃនេះ
  - `/upcoming` - មើល Event ជិតមកដល់ក្នុងរយៈពេល ៧ ថ្ងៃ
  - `/status` - ពិនិត្យស្ថានភាព Connection ទៅ Google Calendar
  - `/help` - មើលការណែនាំ

---

## 🛠️ ការរៀបចំដំឡើង (Step-by-Step Setup Guide)

### ជំហានទី ១: បង្កើត Telegram Bot
1. បើកកម្មវិធី Telegram ហើយស្វែងរក `@BotFather`
2. ផ្ញើសារ `/newbot` រួចវាយបញ្ចូល ឈ្មោះ bot និង username របស់ bot
3. អ្នកនឹងទទួលបាន **HTTP API Token** (ឧទាហរណ៍: `123456789:ABCdefGHIjklmNOPqrstUVwxyz`)

### ជំហានទី ២: បង្កើត Google Service Account (Google Calendar API)
1. ចូលទៅកាន់ [Google Cloud Console](https://console.cloud.google.com/)
2. បង្កើត Project ថ្មី ឬជ្រើសរើស Project ដែលមានស្រាប់
3. ចូលទៅ **APIs & Services** > **Enable APIs and Services** > ស្វែងរក **Google Calendar API** រួចចុច **Enable**
4. ចូលទៅ **APIs & Services** > **Credentials** > ចុច **Create Credentials** > ជ្រើសរើស **Service Account**
5. បញ្ចូលឈ្មោះ Service Account រួចចុច **Create and Continue**
6. បន្ទាប់ពីបង្កើតរួច ចុចលើ Service Account នោះ > ចូលទៅ tab **Keys** > ចុច **Add Key** > **Create new key** > ជ្រើសរើសប្រភេទ **JSON** > ចុច **Create**
7. វានឹង Download file `.json` មកកុំព្យូទ័ររបស់អ្នក។ សូមប្តូរឈ្មោះ file នោះទៅជា `credentials.json` ហើយយកមកដាក់ក្នុង Folder គម្រោងនេះ។

### ជំហានទី ៣: Share Google Calendar ទៅកាន់ Service Account
1. បើក file `credentials.json` រួច copy អ៊ីមែលត្រង់ `client_email` (ឧទាហរណ៍: `my-bot@project-name.iam.gserviceaccount.com`)
2. បើក [Google Calendar](https://calendar.google.com/)
3. នៅផ្នែកខាងឆ្វេង ត្រង់ **My calendars** ចុចលើសញ្ញាចុច ៣ ជ្រុងក្បែរ Calendar របស់អ្នក > ជ្រើសរើស **Settings and sharing**
4. ត្រង់ផ្នែក **Share with specific people or groups** ចុច **Add people and groups**
5. បិទភ្ជាប់ (Paste) **Service Account Email** ដែលបាន copy អម្បាញ់មិញ
6. ត្រង់ Permissions ជ្រើសរើស **"See all event details"** ឬ **"Make changes to events"** រួចចុច **Send**

---

## 🚀 ការដំឡើង និង Run កម្មវិធី

### ១. ដំឡើង Python Packages
```bash
pip install -r requirements.txt
```

### ២. រៀបចំ File Configuration `.env`
ចម្លង file `.env.example` ទៅជា `.env`:
```bash
cp .env.example .env
```

កែប្រែព័ត៌មានក្នុង `.env`:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklmNOPqrstUVwxyz
TELEGRAM_CHAT_ID=123456789
GOOGLE_CALENDAR_ID=primary
GOOGLE_SERVICE_ACCOUNT_FILE=credentials.json
TIMEZONE=Asia/Phnom_Penh
REMINDER_MINUTES=15
DAILY_SUMMARY_TIME=07:00
```
*(ចំណាំ: ដើម្បីដឹង Telegram Chat ID របស់អ្នក អ្នកអាចរ៉ាន់ Bot រួចផ្ញើសារ `/start` ទៅកាន់ Bot នោះវានឹងបង្ហាញ Chat ID)*

### ៣. ចាប់ផ្តើម Run Bot
```bash
python bot.py
```

---

## 📁 រចនាសម្ព័ន្ធ Folder (Project Structure)

```
Calender_soujing/
├── bot.py                  # កម្មវិធី Telegram Bot ចម្បង និង Scheduler
├── google_calendar.py      # Module សម្រាប់ភ្ជាប់ និងទាញយកទិន្នន័យពី Google Calendar API
├── config.py               # Module គ្រប់គ្រង Environment variables
├── requirements.txt        # បញ្ជី Python Dependencies
├── .env.example            # គំរូ configuration
├── credentials.json        # Google Service Account Key (ទាញយកពី Google Cloud Console)
└── README.md               # សៀវភៅណែនាំ
```

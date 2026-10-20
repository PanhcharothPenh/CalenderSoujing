# Google Calendar & Score Notification Telegram Bot (Vercel Serverless)

A modern, fast Google Calendar & Monthly Score Announcement Telegram Bot built with Python, Telegram Webhook API, and Vercel Serverless Functions.

## 🌟 Features
- **Auto Subscription**: Users simply run `/start` or click the button to subscribe automatically.
- **📊 Monthly Score Table (តារាងពិន្ទុប្រចាំខែ)**: Subscribers can tap `📊 តារាងពិន្ទុ` or send `/score` at any time to view the latest monthly score table (photo, PDF/document, or text).
- **📢 Admin Broadcast & Announce**: Admins can broadcast monthly scores, photos, PDFs, or announcements to all subscribers using `/broadcast [caption]` or by replying to media with `/broadcast`.
- **Vercel Serverless Function**: Instant response time (<200ms) with zero server maintenance.
- **Custom Domain Webhook**: Integrated with `https://jingbot.p2bkh.tech/`.
- **Khmer Time Period Formatting**: Displays event times with Khmer indicators (`ព្រឹក`, `រសៀល`, `ល្ងាច`, `យប់`).
- **Interactive Khmer Telegram Buttons**: Easy navigation buttons:
  - `📅 Event ថ្ងៃនេះ`
  - `📆 Event ៧ថ្ងៃខាងមុខ`
  - `📊 តារាងពិន្ទុ`
  - `🔔 ចុះឈ្មោះទទួលសារ`
  - `🔕 លុបការចុះឈ្មោះ`
  - `ℹ️ ការណែនាំ`

## 👑 Admin Features (ផ្ញើតារាងពិន្ទុ ឬផ្សាយដំណឹង)
- **វិធីទី១ (ងាយស្រួលបំផុត - 1-Click):**
  - Admin គ្រាន់តែផ្ញើ ឬ Forward រូបភាព ឬ File PDF ចូលក្នុង Chat ជាមួយ Bot (មិនបាច់វាយពាក្យអ្វីទាំងអស់)។
  - Bot នឹងសួរភ្លាមៗជាមួយប៊ូតុង `[📢 ផ្សាយទៅកាន់សិស្សទាំងអស់]`។ ចុចតែ ១ ឃ្លីក រួចជាស្រេច!
- **វិធីទី២ (Command):**
  - `/broadcast <សារ>` ឬដាក់ Caption `/broadcast` លើរូបភាព ឬ Reply លើ File ចាស់។

## 🚀 Deployment on Vercel
1. Import repository `PanhcharothPenh/CalenderSoujing` into Vercel.
2. Configure Environment Variables:
   - `TELEGRAM_BOT_TOKEN`: Telegram bot token from @BotFather
   - `TELEGRAM_CHAT_ID` / `ADMIN_CHAT_ID`: Admin Telegram Chat ID(s)
   - `GOOGLE_CALENDAR_ID`: Calendar ID
   - `GOOGLE_SERVICE_ACCOUNT_JSON`: Service account JSON / Base64 string
3. Click **Deploy**.
4. Register Telegram Webhook URL to `https://jingbot.p2bkh.tech/set_webhook`.

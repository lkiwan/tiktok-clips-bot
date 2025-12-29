# TikTok Clips Bot

A Telegram bot that converts YouTube videos into TikTok-ready clips. Runs 100% FREE using GitHub Actions + Render.

## How It Works

```
You send YouTube link → Telegram Bot → GitHub Actions (processing) → Clips sent back to you
```

## Features

- Send YouTube link via Telegram
- Choose number of clips (1-5)
- Choose clip duration (30s, 45s, 60s)
- AI selects the best viral moments
- Generates vertical (9:16) TikTok format
- Adds subtitles automatically
- Sends clips with ready-to-copy captions + hashtags

## Setup Guide

### Step 1: Create Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Choose a name: `My TikTok Clips Bot`
4. Choose a username: `my_tiktok_clips_bot`
5. **Save the bot token** (looks like `123456789:ABCdefGHI...`)

### Step 2: Create GitHub Repository

1. Go to https://github.com/new
2. Create a new **private** repository named `tiktok-clips-bot`
3. Upload all files from this project to the repository

### Step 3: Add GitHub Secrets

Go to your repo → Settings → Secrets and variables → Actions → New repository secret

Add these secrets:

| Name | Value |
|------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from Step 1 |
| `GROQ_API_KEY` | (Optional) Get free key from https://console.groq.com |

### Step 4: Create GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Name: `tiktok-bot-trigger`
4. Select scopes: `repo` (full control)
5. Generate and **save the token**

### Step 5: Deploy Bot to Render

1. Go to https://render.com and sign up (free)
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Settings:
   - **Name:** tiktok-clips-bot
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r bot/requirements.txt`
   - **Start Command:** `cd bot && gunicorn app:app`

5. Add Environment Variables:
   - `TELEGRAM_BOT_TOKEN` = Your bot token
   - `GITHUB_TOKEN` = Your personal access token from Step 4
   - `GITHUB_REPO` = `yourusername/tiktok-clips-bot`

6. Click "Create Web Service"
7. Wait for deployment (2-3 minutes)
8. Copy the URL (like `https://tiktok-clips-bot.onrender.com`)

### Step 6: Set Telegram Webhook

Run this command (replace values):

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://<YOUR_RENDER_URL>/webhook"
```

Example:
```bash
curl "https://api.telegram.org/bot123456789:ABC.../setWebhook?url=https://tiktok-clips-bot.onrender.com/webhook"
```

You should see: `{"ok":true,"result":true,"description":"Webhook was set"}`

### Step 7: Keep Bot Alive (cron-job.org)

Render free tier sleeps after 15 minutes of inactivity.

1. Go to https://cron-job.org and sign up (free)
2. Create new cron job:
   - **URL:** `https://your-render-url.onrender.com/health`
   - **Schedule:** Every 10 minutes
3. Save and enable

## Usage

1. Open your bot in Telegram
2. Send `/start`
3. Send a YouTube link
4. Choose number of clips
5. Choose duration
6. Wait 10-20 minutes
7. Receive clips with captions!

## Free Tier Limits

| Service | Limit |
|---------|-------|
| Render | 750 hours/month (enough for 24/7) |
| GitHub Actions | 2,000 minutes/month (private repo) |
| Groq AI | 30 requests/minute (free tier) |
| cron-job.org | Unlimited pings |

**Estimated capacity:** ~30-50 videos per month

## Troubleshooting

### Bot not responding
- Check Render logs for errors
- Verify webhook is set correctly
- Make sure cron-job is running

### Processing takes too long
- Long videos (>30 min) take longer
- GitHub Actions has 6 hour max limit

### Clips not sending
- File might be too large (>50MB limit)
- Check Telegram bot token is correct

### No AI clip selection
- Add GROQ_API_KEY secret to GitHub
- Get free key from https://console.groq.com

## Project Structure

```
tiktok-clips-bot/
├── bot/
│   ├── app.py              # Telegram webhook server
│   └── requirements.txt    # Bot dependencies
├── scripts/
│   ├── process_video.py    # Main processing script
│   ├── downloader.py       # YouTube download
│   ├── transcriber.py      # Whisper transcription
│   ├── clip_selector.py    # AI clip selection
│   ├── clip_generator.py   # FFmpeg clip generation
│   └── telegram_sender.py  # Send to Telegram
├── .github/
│   └── workflows/
│       └── process_video.yml  # GitHub Action
├── requirements.txt        # Processing dependencies
├── render.yaml            # Render config
└── README.md              # This file
```

## Cost: $0

Everything runs on free tiers!

## License

MIT - Use freely!

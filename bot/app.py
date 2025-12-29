"""
TikTok Clips Bot - Telegram Webhook Server
Receives YouTube links and triggers GitHub Actions for processing
"""

import os
import re
import json
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# Configuration from environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO')  # format: username/repo

# User session storage (in production, use Redis)
user_sessions = {}

# Telegram API base URL
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_message(chat_id, text, reply_markup=None):
    """Send message to Telegram user"""
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)

    response = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)
    return response.json()


def send_typing(chat_id):
    """Send typing indicator"""
    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        'chat_id': chat_id,
        'action': 'typing'
    })


def is_youtube_url(text):
    """Check if text is a YouTube URL"""
    youtube_patterns = [
        r'(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(https?://)?(www\.)?youtu\.be/[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/shorts/[\w-]+'
    ]
    for pattern in youtube_patterns:
        if re.search(pattern, text):
            return True
    return False


def extract_youtube_url(text):
    """Extract YouTube URL from text"""
    patterns = [
        r'(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(https?://)?(www\.)?youtu\.be/[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/shorts/[\w-]+'
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            url = match.group()
            if not url.startswith('http'):
                url = 'https://' + url
            return url
    return None


def trigger_github_action(chat_id, youtube_url, num_clips, clip_duration):
    """Trigger GitHub Actions workflow via repository_dispatch"""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "GitHub not configured"

    url = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    payload = {
        'event_type': 'process_video',
        'client_payload': {
            'chat_id': str(chat_id),
            'youtube_url': youtube_url,
            'num_clips': num_clips,
            'clip_duration': clip_duration,
            'timestamp': datetime.now().isoformat()
        }
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 204:
        return True, "Workflow triggered"
    else:
        return False, f"Error: {response.status_code} - {response.text}"


def handle_message(message):
    """Process incoming Telegram message"""
    chat_id = message['chat']['id']
    user_name = message['from'].get('first_name', 'there')
    text = message.get('text', '')

    # Initialize session if needed
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {'state': 'idle'}

    session = user_sessions[chat_id]

    # Handle /start command
    if text == '/start':
        session['state'] = 'idle'
        send_message(chat_id, f"""
<b>Welcome {user_name}!</b>

I turn YouTube videos into TikTok-ready clips.

<b>How to use:</b>
1. Send me a YouTube link
2. Choose number of clips (1-5)
3. Choose clip duration (30s, 45s, 60s)
4. Wait for processing (~10-20 min)
5. Get clips with captions + hashtags!

<b>Commands:</b>
/start - Show this message
/status - Check if processing
/help - Get help

Send me a YouTube link to start!
        """)
        return

    # Handle /help command
    if text == '/help':
        send_message(chat_id, """
<b>Help</b>

<b>Supported links:</b>
- youtube.com/watch?v=...
- youtu.be/...
- youtube.com/shorts/...

<b>Processing time:</b>
- Short videos (< 10 min): ~5-10 min
- Medium videos (10-30 min): ~10-15 min
- Long videos (30+ min): ~15-25 min

<b>Tips:</b>
- Clips are optimized for TikTok (9:16)
- Includes auto-generated subtitles
- Captions and hashtags provided

<b>Issues?</b>
Just send another link to try again.
        """)
        return

    # Handle /status command
    if text == '/status':
        if session.get('processing'):
            send_message(chat_id, f"""
<b>Status: Processing</b>

Video: {session.get('youtube_url', 'Unknown')}
Clips: {session.get('num_clips', '?')}
Duration: {session.get('clip_duration', '?')}s

Started: {session.get('started_at', 'Unknown')}

Please wait, I'll notify you when ready!
            """)
        else:
            send_message(chat_id, "No video processing. Send me a YouTube link!")
        return

    # State machine for conversation flow
    state = session.get('state', 'idle')

    if state == 'idle':
        # Expecting YouTube URL
        if is_youtube_url(text):
            url = extract_youtube_url(text)
            session['youtube_url'] = url
            session['state'] = 'waiting_num_clips'

            send_message(chat_id,
                "<b>Got it!</b>\n\nHow many clips do you want?",
                reply_markup={
                    'keyboard': [
                        [{'text': '1'}, {'text': '2'}, {'text': '3'}],
                        [{'text': '4'}, {'text': '5'}]
                    ],
                    'resize_keyboard': True,
                    'one_time_keyboard': True
                }
            )
        else:
            send_message(chat_id, "Please send me a valid YouTube link.\n\nExample: https://youtube.com/watch?v=...")

    elif state == 'waiting_num_clips':
        # Expecting number of clips
        if text.isdigit() and 1 <= int(text) <= 5:
            session['num_clips'] = int(text)
            session['state'] = 'waiting_duration'

            send_message(chat_id,
                f"<b>{text} clips</b>\n\nMax duration per clip?",
                reply_markup={
                    'keyboard': [
                        [{'text': '30 seconds'}, {'text': '45 seconds'}],
                        [{'text': '60 seconds'}]
                    ],
                    'resize_keyboard': True,
                    'one_time_keyboard': True
                }
            )
        else:
            send_message(chat_id, "Please choose a number between 1 and 5")

    elif state == 'waiting_duration':
        # Expecting clip duration
        duration_map = {
            '30': 30, '30 seconds': 30, '30s': 30,
            '45': 45, '45 seconds': 45, '45s': 45,
            '60': 60, '60 seconds': 60, '60s': 60
        }

        duration = duration_map.get(text.lower())
        if duration:
            session['clip_duration'] = duration
            session['state'] = 'processing'
            session['processing'] = True
            session['started_at'] = datetime.now().strftime('%H:%M:%S')

            # Remove keyboard
            send_message(chat_id,
                f"""
<b>Starting processing!</b>

Video: {session['youtube_url']}
Clips: {session['num_clips']}
Duration: {duration}s each

This will take 10-20 minutes.
I'll send you the clips when ready!
                """,
                reply_markup={'remove_keyboard': True}
            )

            # Trigger GitHub Action
            success, message = trigger_github_action(
                chat_id,
                session['youtube_url'],
                session['num_clips'],
                session['clip_duration']
            )

            if success:
                send_message(chat_id, "Processing started! Please wait...")
            else:
                session['state'] = 'idle'
                session['processing'] = False
                send_message(chat_id, f"Error starting process: {message}\n\nPlease try again.")
        else:
            send_message(chat_id, "Please choose: 30, 45, or 60 seconds")


def handle_callback(callback_query):
    """Handle callback query from inline buttons"""
    chat_id = callback_query['message']['chat']['id']
    data = callback_query.get('data', '')

    # Answer callback to remove loading state
    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
        'callback_query_id': callback_query['id']
    })

    # Process callback data
    # (Add callback handling if needed)


@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'running',
        'bot': 'TikTok Clips Bot',
        'time': datetime.now().isoformat()
    })


@app.route('/health')
def health():
    """Health check for cron-job.org"""
    return 'OK', 200


@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram webhook endpoint"""
    try:
        update = request.get_json()

        if 'message' in update:
            handle_message(update['message'])
        elif 'callback_query' in update:
            handle_callback(update['callback_query'])

        return jsonify({'ok': True})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/notify', methods=['POST'])
def notify():
    """
    Endpoint for GitHub Actions to notify completion
    Called by the workflow when processing is done
    """
    try:
        data = request.get_json()
        chat_id = data.get('chat_id')
        status = data.get('status')

        if status == 'success':
            clips = data.get('clips', [])
            message = "<b>Your clips are ready!</b>\n\n"
            message += f"Generated {len(clips)} clips.\n"
            message += "Sending them now..."
            send_message(chat_id, message)

        elif status == 'error':
            error = data.get('error', 'Unknown error')
            send_message(chat_id, f"<b>Processing failed</b>\n\nError: {error}\n\nPlease try again.")

        # Reset session
        if chat_id in user_sessions:
            user_sessions[chat_id] = {'state': 'idle'}

        return jsonify({'ok': True})

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

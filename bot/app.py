"""
TikTok Clips Bot - Telegram Webhook Server
Supports HYBRID processing: Local PC (if online) or GitHub Actions (if offline)
"""

import os
import re
import json
import time
import requests
import threading
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# Configuration from environment variables
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO')  # format: username/repo
LOCAL_WAIT_SECONDS = int(os.environ.get('LOCAL_WAIT_SECONDS', 120))  # 2 minutes

# Telegram API base URL
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# User session storage
user_sessions = {}

# Job queue for hybrid processing
# Jobs wait here for local PC to pick up, or get sent to GitHub Actions
job_queue = {}  # job_id -> job_data


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


def generate_job_id():
    """Generate unique job ID"""
    return f"job_{int(time.time() * 1000)}"


def create_job(chat_id, youtube_url, num_clips, clip_duration):
    """Create a new processing job"""
    job_id = generate_job_id()
    job_queue[job_id] = {
        'job_id': job_id,
        'chat_id': str(chat_id),
        'youtube_url': youtube_url,
        'num_clips': num_clips,
        'clip_duration': clip_duration,
        'status': 'pending',  # pending, processing, completed, failed
        'created_at': time.time(),
        'processor': None,  # 'local' or 'github'
        'github_triggered': False
    }
    return job_id


def trigger_github_action(job_data):
    """Trigger GitHub Actions workflow"""
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
            'chat_id': job_data['chat_id'],
            'youtube_url': job_data['youtube_url'],
            'num_clips': job_data['num_clips'],
            'clip_duration': job_data['clip_duration'],
            'job_id': job_data['job_id']
        }
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 204:
        return True, "Workflow triggered"
    else:
        return False, f"Error: {response.status_code}"


def check_and_trigger_github(job_id):
    """Background task: Wait for local PC, then trigger GitHub if needed"""
    time.sleep(LOCAL_WAIT_SECONDS)

    if job_id not in job_queue:
        return

    job = job_queue[job_id]

    # If still pending (local PC didn't pick it up), trigger GitHub
    if job['status'] == 'pending' and not job['github_triggered']:
        job['github_triggered'] = True
        job['processor'] = 'github'

        send_message(
            job['chat_id'],
            "💻 Local PC not available. Using cloud processing..."
        )

        success, message = trigger_github_action(job)
        if success:
            job['status'] = 'processing'
            send_message(job['chat_id'], "☁️ Cloud processing started! Please wait 10-20 minutes.")
        else:
            job['status'] = 'failed'
            send_message(job['chat_id'], f"❌ Failed to start processing: {message}")


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
<b>Welcome {user_name}!</b> 🎬

I turn YouTube videos into TikTok-ready clips.

<b>How to use:</b>
1. Send me a YouTube link
2. Choose number of clips (1-5)
3. Choose clip duration
4. Wait for processing
5. Get clips with captions!

<b>Hybrid Mode:</b>
🖥️ If your PC is ON → Fast local processing
☁️ If your PC is OFF → Cloud processing

<b>Commands:</b>
/start - Show this message
/status - Check processing status
/help - Get help

Send me a YouTube link to start!
        """)
        return

    # Handle /help command
    if text == '/help':
        send_message(chat_id, """
<b>Help</b>

<b>Supported links:</b>
• youtube.com/watch?v=...
• youtu.be/...
• youtube.com/shorts/...

<b>Processing modes:</b>
🖥️ <b>Local</b> - When your PC is running the local script (faster)
☁️ <b>Cloud</b> - When PC is off, uses GitHub Actions

<b>Processing time:</b>
• Local: 2-10 minutes
• Cloud: 10-20 minutes

<b>Tips:</b>
• Keep your PC on for faster processing
• Clips are optimized for TikTok (9:16)
• Includes auto-generated subtitles
        """)
        return

    # Handle /status command
    if text == '/status':
        # Find user's jobs
        user_jobs = [j for j in job_queue.values() if j['chat_id'] == str(chat_id)]
        active_jobs = [j for j in user_jobs if j['status'] in ['pending', 'processing']]

        if active_jobs:
            job = active_jobs[-1]
            processor = job.get('processor', 'waiting')
            status_emoji = '⏳' if job['status'] == 'pending' else '🔄'
            send_message(chat_id, f"""
<b>{status_emoji} Job Status</b>

Status: {job['status'].upper()}
Processor: {processor}
URL: {job['youtube_url'][:50]}...
Clips: {job['num_clips']}
Duration: {job['clip_duration']}s

{'Waiting for local PC or cloud...' if job['status'] == 'pending' else 'Processing in progress...'}
            """)
        else:
            send_message(chat_id, "No active jobs. Send me a YouTube link!")
        return

    # State machine for conversation flow
    state = session.get('state', 'idle')

    if state == 'idle':
        if is_youtube_url(text):
            url = extract_youtube_url(text)
            session['youtube_url'] = url
            session['state'] = 'waiting_num_clips'

            send_message(chat_id,
                "✅ <b>Got it!</b>\n\nHow many clips do you want?",
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
        if text.isdigit() and 1 <= int(text) <= 5:
            session['num_clips'] = int(text)
            session['state'] = 'waiting_duration'

            send_message(chat_id,
                f"<b>{text} clips</b> ✓\n\nMax duration per clip?",
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
        duration_map = {
            '30': 30, '30 seconds': 30, '30s': 30,
            '45': 45, '45 seconds': 45, '45s': 45,
            '60': 60, '60 seconds': 60, '60s': 60
        }

        duration = duration_map.get(text.lower())
        if duration:
            session['clip_duration'] = duration
            session['state'] = 'waiting_processor'

            send_message(chat_id,
                f"<b>{duration}s per clip</b> ✓\n\nWhere to process?",
                reply_markup={
                    'keyboard': [
                        [{'text': '🖥️ Local PC (faster)'}],
                        [{'text': '☁️ Cloud (when PC off)'}],
                        [{'text': '🔄 Auto (local first, then cloud)'}]
                    ],
                    'resize_keyboard': True,
                    'one_time_keyboard': True
                }
            )
        else:
            send_message(chat_id, "Please choose: 30, 45, or 60 seconds")

    elif state == 'waiting_processor':
        processor_choice = None

        if 'local' in text.lower() or '🖥️' in text:
            processor_choice = 'local'
        elif 'cloud' in text.lower() or '☁️' in text:
            processor_choice = 'cloud'
        elif 'auto' in text.lower() or '🔄' in text:
            processor_choice = 'auto'

        if processor_choice:
            session['state'] = 'idle'

            # Create job with processor preference
            job_id = create_job(
                chat_id,
                session['youtube_url'],
                session['num_clips'],
                session['clip_duration']
            )

            job_queue[job_id]['processor_choice'] = processor_choice

            if processor_choice == 'local':
                send_message(chat_id, f"""
<b>🖥️ Local Processing Selected!</b>

📹 Video: {session['youtube_url'][:50]}...
✂️ Clips: {session['num_clips']}
⏱️ Duration: {session['clip_duration']}s each

<b>Waiting for your PC...</b>
Make sure local_processor.py is running!

Job ID: <code>{job_id}</code>
                """,
                    reply_markup={'remove_keyboard': True}
                )
                # No GitHub fallback for local-only

            elif processor_choice == 'cloud':
                job_queue[job_id]['github_triggered'] = True
                job_queue[job_id]['processor'] = 'github'

                send_message(chat_id, f"""
<b>☁️ Cloud Processing Selected!</b>

📹 Video: {session['youtube_url'][:50]}...
✂️ Clips: {session['num_clips']}
⏱️ Duration: {session['clip_duration']}s each

Starting cloud processing...
Please wait 10-20 minutes.

Job ID: <code>{job_id}</code>
                """,
                    reply_markup={'remove_keyboard': True}
                )

                # Trigger GitHub Actions immediately
                success, message = trigger_github_action(job_queue[job_id])
                if success:
                    job_queue[job_id]['status'] = 'processing'
                    send_message(chat_id, "☁️ Cloud processing started!")
                else:
                    job_queue[job_id]['status'] = 'failed'
                    send_message(chat_id, f"❌ Failed to start: {message}")

            else:  # auto
                send_message(chat_id, f"""
<b>🔄 Auto Mode Selected!</b>

📹 Video: {session['youtube_url'][:50]}...
✂️ Clips: {session['num_clips']}
⏱️ Duration: {session['clip_duration']}s each

<b>Checking for local PC...</b>
🖥️ If PC online → Local processing (faster)
☁️ If PC offline → Cloud in {LOCAL_WAIT_SECONDS // 60} min

Job ID: <code>{job_id}</code>
                """,
                    reply_markup={'remove_keyboard': True}
                )

                # Start background thread for auto mode
                thread = threading.Thread(target=check_and_trigger_github, args=(job_id,))
                thread.daemon = True
                thread.start()
        else:
            send_message(chat_id, "Please choose: Local PC, Cloud, or Auto")


# ============== API ENDPOINTS FOR LOCAL PC ==============

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'running',
        'bot': 'TikTok Clips Bot (Hybrid)',
        'pending_jobs': len([j for j in job_queue.values() if j['status'] == 'pending']),
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
        return jsonify({'ok': True})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/jobs/pending', methods=['GET'])
def get_pending_jobs():
    """
    API endpoint for local PC to get pending jobs
    Local PC polls this every 30 seconds
    """
    pending = [
        job for job in job_queue.values()
        if job['status'] == 'pending' and not job['github_triggered']
    ]
    return jsonify({
        'jobs': pending,
        'count': len(pending)
    })


@app.route('/api/jobs/<job_id>/claim', methods=['POST'])
def claim_job(job_id):
    """
    Local PC claims a job to process
    Prevents GitHub Actions from processing it
    """
    if job_id not in job_queue:
        return jsonify({'ok': False, 'error': 'Job not found'}), 404

    job = job_queue[job_id]

    if job['status'] != 'pending':
        return jsonify({'ok': False, 'error': 'Job already claimed'}), 400

    job['status'] = 'processing'
    job['processor'] = 'local'
    job['claimed_at'] = time.time()

    # Notify user
    send_message(
        job['chat_id'],
        "🖥️ <b>Local PC connected!</b>\nProcessing on your computer (faster)..."
    )

    return jsonify({
        'ok': True,
        'job': job
    })


@app.route('/api/jobs/<job_id>/complete', methods=['POST'])
def complete_job(job_id):
    """
    Mark job as completed
    Called by local PC after sending clips
    """
    if job_id not in job_queue:
        return jsonify({'ok': False, 'error': 'Job not found'}), 404

    job = job_queue[job_id]
    job['status'] = 'completed'
    job['completed_at'] = time.time()

    return jsonify({'ok': True})


@app.route('/api/jobs/<job_id>/fail', methods=['POST'])
def fail_job(job_id):
    """
    Mark job as failed
    Optionally fall back to GitHub Actions
    """
    if job_id not in job_queue:
        return jsonify({'ok': False, 'error': 'Job not found'}), 404

    data = request.get_json() or {}
    error = data.get('error', 'Unknown error')
    fallback = data.get('fallback_to_github', True)

    job = job_queue[job_id]

    if fallback and not job['github_triggered']:
        # Try GitHub Actions as fallback
        job['github_triggered'] = True
        job['processor'] = 'github'
        job['status'] = 'processing'

        send_message(
            job['chat_id'],
            f"⚠️ Local processing failed: {error}\n\n☁️ Falling back to cloud..."
        )

        trigger_github_action(job)
    else:
        job['status'] = 'failed'
        send_message(
            job['chat_id'],
            f"❌ Processing failed: {error}"
        )

    return jsonify({'ok': True})


@app.route('/api/jobs/<job_id>/progress', methods=['POST'])
def update_progress(job_id):
    """
    Update job progress (for status messages)
    """
    if job_id not in job_queue:
        return jsonify({'ok': False, 'error': 'Job not found'}), 404

    data = request.get_json() or {}
    message = data.get('message', '')

    job = job_queue[job_id]

    if message:
        send_message(job['chat_id'], message)

    return jsonify({'ok': True})


# ============== CLEANUP OLD JOBS ==============

def cleanup_old_jobs():
    """Remove jobs older than 1 hour"""
    current_time = time.time()
    old_jobs = [
        job_id for job_id, job in job_queue.items()
        if current_time - job['created_at'] > 3600  # 1 hour
    ]
    for job_id in old_jobs:
        del job_queue[job_id]


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

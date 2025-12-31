#!/usr/bin/env python3
"""
Enhanced Local Video Processor for TikTok Clips Bot
Run this on your PC to process videos with professional features:
- Face-aware smart cropping
- Karaoke-style subtitles
- Split-screen with satisfying backgrounds

Usage:
    python local_processor_enhanced.py

Requirements:
    pip install requests yt-dlp faster-whisper moviepy groq mediapipe pillow
    FFmpeg must be installed and in PATH
"""

import os
import sys
import time
import json
import tempfile
import subprocess
from pathlib import Path

# Fix SSL certificate issue on Windows
import certifi
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests

# ============== CONFIGURATION ==============
# Edit these settings:

BOT_URL = "https://tiktok-clips-bot.onrender.com"
TELEGRAM_BOT_TOKEN = "8221904241:AAHVjoAyBEOHLgZrkV1oDK11RuzNu52CKp4"
GROQ_API_KEY = ""  # Optional: Get free key from https://console.groq.com

POLL_INTERVAL = 30  # Check for jobs every 30 seconds

# Enhancement settings
ENABLE_FACE_TRACKING = True     # Smart cropping for panoramic videos
SUBTITLE_STYLE = 'karaoke'      # 'karaoke', 'highlight', 'box', 'simple'
ENABLE_SPLIT_SCREEN = True      # Add satisfying background (ENABLED by default)
SPLIT_LAYOUT = 'top_bottom'     # 'top_bottom', 'bottom_top', 'left_right'

# Get absolute path to satisfying videos folder
SCRIPT_DIR = Path(__file__).parent.absolute()
SATISFYING_FOLDER = str(SCRIPT_DIR / 'assets' / 'satisfying_videos')

# ===========================================


def log(message):
    """Print with timestamp"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def get_pending_jobs():
    """Get pending jobs from bot"""
    try:
        response = requests.get(f"{BOT_URL}/api/jobs/pending", timeout=10)
        if response.status_code == 200:
            return response.json().get('jobs', [])
    except Exception as e:
        log(f"Error getting jobs: {e}")
    return []


def claim_job(job_id):
    """Claim a job for local processing"""
    try:
        response = requests.post(f"{BOT_URL}/api/jobs/{job_id}/claim", timeout=10)
        if response.status_code == 200:
            return response.json().get('job')
    except Exception as e:
        log(f"Error claiming job: {e}")
    return None


def complete_job(job_id):
    """Mark job as completed"""
    try:
        requests.post(f"{BOT_URL}/api/jobs/{job_id}/complete", timeout=10)
    except:
        pass


def fail_job(job_id, error, fallback=True):
    """Mark job as failed"""
    try:
        requests.post(
            f"{BOT_URL}/api/jobs/{job_id}/fail",
            json={'error': str(error), 'fallback_to_github': fallback},
            timeout=10
        )
    except:
        pass


def update_progress(job_id, message):
    """Send progress update to user"""
    try:
        requests.post(
            f"{BOT_URL}/api/jobs/{job_id}/progress",
            json={'message': message},
            timeout=10
        )
    except:
        pass


def send_video_to_telegram(chat_id, video_path, caption):
    """Send video to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"

    with open(video_path, 'rb') as video_file:
        response = requests.post(
            url,
            data={
                'chat_id': chat_id,
                'caption': caption[:1024],
                'parse_mode': 'HTML',
                'supports_streaming': True
            },
            files={'video': (Path(video_path).name, video_file, 'video/mp4')},
            timeout=120
        )

    return response.json().get('ok', False)


def download_video(url, output_dir):
    """Download YouTube video using yt-dlp"""
    log("Downloading video...")

    info_cmd = ['yt-dlp', '--dump-json', '--no-download', url]
    result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)

    video_id = info['id']
    title = info.get('title', 'Unknown')
    duration = info.get('duration', 0)

    output_path = Path(output_dir) / f"{video_id}.mp4"

    download_cmd = [
        'yt-dlp',
        '-f', 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
        '--merge-output-format', 'mp4',
        '-o', str(output_path),
        '--no-playlist',
        url
    ]
    subprocess.run(download_cmd, check=True)

    return {
        'video_id': video_id,
        'title': title,
        'duration': duration,
        'video_path': str(output_path)
    }


def transcribe_video(video_path):
    """Transcribe video using faster-whisper"""
    log("Transcribing audio...")

    from faster_whisper import WhisperModel

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments_iter, info = model.transcribe(video_path, beam_size=5, word_timestamps=True)

    # Convert to list and extract word-level timestamps
    transcript_segments = []
    word_segments = []

    for segment in segments_iter:
        transcript_segments.append({
            'start': segment.start,
            'end': segment.end,
            'text': segment.text.strip()
        })

        # Extract words
        if hasattr(segment, 'words') and segment.words:
            for word in segment.words:
                word_segments.append({
                    'start': word.start,
                    'end': word.end,
                    'word': word.word.strip()
                })

    return {
        'segments': transcript_segments,
        'word_segments': word_segments,
        'duration': info.duration
    }


def select_clips_ai(transcript, video_info, num_clips, max_duration):
    """Select clips using Groq AI"""
    if not GROQ_API_KEY:
        return select_clips_simple(transcript, num_clips, max_duration)

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        total_duration = video_info.get('duration', 0)

        # Calculate skip times for intro/outro
        if total_duration < 300:
            skip_intro, skip_outro = 30, 30
        elif total_duration < 1200:
            skip_intro, skip_outro = 60, 60
        else:
            skip_intro, skip_outro = 90, 90

        # Filter segments to exclude intro/outro
        usable_start = skip_intro
        usable_end = total_duration - skip_outro

        segments_text = []
        for seg in transcript['segments'][:200]:
            if seg['start'] >= usable_start and seg['end'] <= usable_end:
                segments_text.append(f"[{seg['start']:.1f}s - {seg['end']:.1f}s]: {seg['text']}")

        prompt = f"""Find the {num_clips} BEST moments for TikTok clips from this transcript.

VIDEO: {video_info.get('title', 'Unknown')}
DURATION: {total_duration}s

IMPORTANT:
- AVOID the intro (first {skip_intro}s) and outro (last {skip_outro}s)
- Select clips between {usable_start}s and {usable_end}s only
- Each clip should be 45-60 seconds for TikTok monetization
- Focus on the most engaging, viral-worthy moments

TRANSCRIPT:
{chr(10).join(segments_text)}

Return JSON only:
{{"clips": [{{"start": <seconds>, "end": <seconds>, "description": "<caption>", "hashtags": ["tag1", "tag2"]}}]}}"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000
        )

        import re
        response_text = response.choices[0].message.content
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            result = json.loads(json_match.group())
            return result.get('clips', [])[:num_clips]
    except Exception as e:
        log(f"AI selection failed: {e}")

    return select_clips_simple(transcript, num_clips, max_duration)


def select_clips_simple(transcript, num_clips, max_duration):
    """Simple clip selection based on timing - avoids intro and outro"""
    segments = transcript['segments']
    if not segments:
        return []

    total_duration = segments[-1]['end']

    # Skip intro and outro (proportional to video length)
    # For short videos (<5min): skip 30s intro/outro
    # For medium videos (5-20min): skip 60s intro/outro
    # For long videos (>20min): skip 90s intro/outro
    if total_duration < 300:  # < 5 minutes
        skip_intro = 30
        skip_outro = 30
    elif total_duration < 1200:  # < 20 minutes
        skip_intro = 60
        skip_outro = 60
    else:  # > 20 minutes
        skip_intro = 90
        skip_outro = 90

    # Calculate usable range
    usable_start = min(skip_intro, total_duration * 0.1)  # Max 10% of video
    usable_end = max(total_duration - skip_outro, total_duration * 0.9)  # Min 90% of video
    usable_duration = usable_end - usable_start

    if usable_duration < max_duration:
        # Video too short, use full duration
        usable_start = 0
        usable_end = total_duration
        usable_duration = total_duration

    log(f"Skipping intro ({usable_start:.0f}s) and outro (after {usable_end:.0f}s)")

    clips = []
    spacing = usable_duration / (num_clips + 1)

    for i in range(num_clips):
        target_time = usable_start + spacing * (i + 1)

        # Find best segment in usable range
        usable_segments = [s for s in segments if s['start'] >= usable_start and s['end'] <= usable_end]
        if not usable_segments:
            usable_segments = segments

        best_segment = min(usable_segments, key=lambda s: abs(s['start'] - target_time))

        start = max(usable_start, best_segment['start'] - 5)
        end = min(usable_end, start + min(max_duration, 60))

        clip_text = ""
        for seg in segments:
            if seg['start'] >= start and seg['end'] <= end:
                clip_text += seg['text'] + " "

        clips.append({
            'start': start,
            'end': end,
            'description': clip_text[:80].strip() + "..." if len(clip_text) > 80 else clip_text.strip(),
            'hashtags': ['fyp', 'viral', 'trending', 'tiktok', 'foryou']
        })

    return clips


def generate_enhanced_clips(video_path, clips, transcript, output_dir, config=None):
    """Generate clips with enhanced features"""
    from scripts.enhanced import generate_enhanced_clips as gen_clips

    # Use provided config or fall back to defaults
    if config is None:
        config = {
            'enable_face_tracking': ENABLE_FACE_TRACKING,
            'subtitle_style': SUBTITLE_STYLE,
            'enable_split_screen': ENABLE_SPLIT_SCREEN,
            'split_layout': SPLIT_LAYOUT,
            'satisfying_folder': SATISFYING_FOLDER,
            'output_width': 1080,
            'output_height': 1920
        }

    return gen_clips(video_path, clips, transcript, output_dir, config)


def generate_clips_fallback(video_path, clips, transcript, output_dir):
    """Fallback clip generation without enhancements"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for i, clip in enumerate(clips, 1):
        output_path = output_dir / f"clip_{i:02d}.mp4"

        cmd = [
            'ffmpeg', '-y',
            '-ss', str(clip['start']),
            '-i', str(video_path),
            '-t', str(clip['end'] - clip['start']),
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            str(output_path)
        ]

        try:
            subprocess.run(cmd, capture_output=True, timeout=300)
            results.append({
                'success': True,
                'path': str(output_path),
                'description': clip.get('description', ''),
                'hashtags': clip.get('hashtags', ['fyp', 'viral'])
            })
        except:
            results.append({'success': False})

    return results


def process_job(job):
    """Process a single job with enhanced features"""
    job_id = job['job_id']
    chat_id = job['chat_id']
    youtube_url = job['youtube_url']
    num_clips = job['num_clips']
    clip_duration = job['clip_duration']

    # Get enhancement settings from job (or use defaults)
    enhancements = job.get('enhancements', {})
    log(f"Job enhancements from bot: {enhancements}")

    # Use job settings if provided, otherwise use defaults
    subtitle_style = enhancements.get('subtitle_style') or SUBTITLE_STYLE
    enable_split_screen = enhancements.get('split_screen') if 'split_screen' in enhancements else ENABLE_SPLIT_SCREEN
    enable_face_tracking = enhancements.get('face_tracking') if 'face_tracking' in enhancements else ENABLE_FACE_TRACKING

    log(f"Final settings: subtitles={subtitle_style}, split={enable_split_screen}, face={enable_face_tracking}")

    log(f"Processing job: {job_id}")
    log(f"URL: {youtube_url}")
    log(f"Clips: {num_clips}, Duration: {clip_duration}s")
    log(f"Features: Face tracking={enable_face_tracking}, Subtitles={subtitle_style}, Split={enable_split_screen}")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        try:
            # Step 1: Download
            update_progress(job_id, "Downloading video...")
            video_info = download_video(youtube_url, temp_path)
            log(f"Downloaded: {video_info['title']}")

            # Step 2: Transcribe
            update_progress(job_id, "Transcribing audio (with word timestamps)...")
            transcript = transcribe_video(video_info['video_path'])
            log(f"Transcribed: {len(transcript['segments'])} segments, {len(transcript.get('word_segments', []))} words")

            # Step 3: Select clips
            update_progress(job_id, "AI selecting best moments...")
            clips = select_clips_ai(transcript, video_info, num_clips, clip_duration)
            log(f"Selected: {len(clips)} clips")

            # Step 4: Generate clips with enhancements
            features_text = f"({subtitle_style} subtitles"
            if enable_face_tracking:
                features_text += ", face tracking"
            if enable_split_screen:
                features_text += ", split screen"
            features_text += ")"

            update_progress(job_id, f"Generating professional clips {features_text}...")
            output_dir = temp_path / "output"

            # Build config from job enhancements
            config = {
                'enable_face_tracking': enable_face_tracking,
                'subtitle_style': subtitle_style if subtitle_style != 'none' else None,
                'enable_split_screen': enable_split_screen,
                'split_layout': SPLIT_LAYOUT,
                'satisfying_folder': SATISFYING_FOLDER,
                'output_width': 1080,
                'output_height': 1920
            }

            try:
                generated_clips = generate_enhanced_clips(
                    video_info['video_path'], clips, transcript, output_dir, config
                )
            except Exception as e:
                log(f"Enhanced generation failed: {e}, using fallback")
                generated_clips = generate_clips_fallback(
                    video_info['video_path'], clips, transcript, output_dir
                )

            # Filter successful clips
            successful_clips = [c for c in generated_clips if c.get('success')]
            log(f"Generated: {len(successful_clips)} clips")

            # Step 5: Send to Telegram
            update_progress(job_id, f"Sending {len(successful_clips)} clips...")

            for i, clip in enumerate(successful_clips, 1):
                log(f"Sending clip {i}/{len(successful_clips)}...")

                hashtags = " ".join([f"#{tag}" for tag in clip.get('hashtags', ['fyp', 'viral'])])
                caption = f"{clip.get('description', '')}\n\n{hashtags}\n\nCopy and post to TikTok!"

                if 'features' in clip:
                    features = clip['features']
                    if features.get('subtitle_style') == 'karaoke':
                        caption += "\n🎤 Karaoke subtitles"
                    if features.get('split_screen'):
                        caption += "\n🎮 Split-screen"

                send_video_to_telegram(chat_id, clip['path'], caption)
                time.sleep(2)

            complete_job(job_id)
            log(f"Job {job_id} completed!")

            return True

        except Exception as e:
            log(f"Error processing job: {e}")
            import traceback
            traceback.print_exc()
            fail_job(job_id, str(e), fallback=True)
            return False


def main():
    """Main loop"""
    print("=" * 60)
    print("TikTok Clips Bot - Enhanced Local Processor")
    print("=" * 60)
    print(f"\nBot URL: {BOT_URL}")
    print(f"Poll interval: {POLL_INTERVAL}s")
    print(f"\nEnhancements:")
    print(f"  Face tracking: {'Enabled' if ENABLE_FACE_TRACKING else 'Disabled'}")
    print(f"  Subtitle style: {SUBTITLE_STYLE}")
    print(f"  Split screen: {'Enabled' if ENABLE_SPLIT_SCREEN else 'Disabled'}")
    print(f"  Groq AI: {'Enabled' if GROQ_API_KEY else 'Disabled (using simple selection)'}")
    print("\nWaiting for jobs...")
    print("Press Ctrl+C to stop\n")

    while True:
        try:
            jobs = get_pending_jobs()

            if jobs:
                log(f"Found {len(jobs)} pending job(s)")

                for job in jobs:
                    claimed_job = claim_job(job['job_id'])

                    if claimed_job:
                        log(f"Claimed job: {claimed_job['job_id']}")
                        process_job(claimed_job)
                    else:
                        log("Failed to claim job (might be taken)")

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\n\nStopping enhanced processor...")
            break
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()

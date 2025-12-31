#!/usr/bin/env python3
"""
Local Video Processor for TikTok Clips Bot
Run this on your PC to process videos locally with ENHANCED features:
- Karaoke-style subtitles
- Split-screen with satisfying backgrounds
- Face-aware cropping

Usage:
    python local_processor.py

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
# Change these settings:

BOT_URL = "https://tiktok-clips-bot.onrender.com"  # Your Render URL
TELEGRAM_BOT_TOKEN = "8221904241:AAHVjoAyBEOHLgZrkV1oDK11RuzNu52CKp4"  # Your bot token
GROQ_API_KEY = ""  # Optional: Get free key from https://console.groq.com

POLL_INTERVAL = 30  # Check for jobs every 30 seconds

# Enhancement settings (ENABLED by default!)
ENABLE_FACE_TRACKING = True     # Smart cropping for panoramic videos
SUBTITLE_STYLE = 'karaoke'      # 'karaoke', 'highlight', 'box', 'simple'
ENABLE_SPLIT_SCREEN = True      # Add satisfying background videos
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
            data = response.json()
            return data.get('jobs', [])
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

    # Get video info
    info_cmd = ['yt-dlp', '--dump-json', '--no-download', url]
    result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)

    video_id = info['id']
    title = info.get('title', 'Unknown')
    duration = info.get('duration', 0)

    output_path = Path(output_dir) / f"{video_id}.mp4"

    # Download
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
    """Transcribe video using faster-whisper with word-level timestamps for karaoke"""
    log("Transcribing audio (with word timestamps for karaoke)...")

    from faster_whisper import WhisperModel

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments_iter, info = model.transcribe(video_path, beam_size=5, word_timestamps=True)

    transcript_segments = []
    word_segments = []

    for segment in segments_iter:
        transcript_segments.append({
            'start': segment.start,
            'end': segment.end,
            'text': segment.text.strip()
        })

        # Extract word-level timestamps for karaoke subtitles
        if hasattr(segment, 'words') and segment.words:
            for word in segment.words:
                word_segments.append({
                    'start': word.start,
                    'end': word.end,
                    'word': word.word.strip()
                })

    log(f"Transcribed: {len(transcript_segments)} segments, {len(word_segments)} words")

    return {
        'segments': transcript_segments,
        'word_segments': word_segments,
        'duration': info.duration
    }


def select_clips_simple(transcript, num_clips, max_duration):
    """Simple clip selection - avoids intro and outro"""
    segments = transcript['segments']
    if not segments:
        return []

    total_duration = segments[-1]['end']

    # Skip intro and outro (proportional to video length)
    if total_duration < 300:  # < 5 minutes
        skip_intro, skip_outro = 30, 30
    elif total_duration < 1200:  # < 20 minutes
        skip_intro, skip_outro = 60, 60
    else:  # > 20 minutes
        skip_intro, skip_outro = 90, 90

    # Calculate usable range
    usable_start = min(skip_intro, total_duration * 0.1)
    usable_end = max(total_duration - skip_outro, total_duration * 0.9)
    usable_duration = usable_end - usable_start

    if usable_duration < max_duration:
        usable_start, usable_end = 0, total_duration
        usable_duration = total_duration

    log(f"Skipping intro ({usable_start:.0f}s) and outro (after {usable_end:.0f}s)")

    clips = []
    spacing = usable_duration / (num_clips + 1)

    for i in range(num_clips):
        target_time = usable_start + spacing * (i + 1)

        # Find segments in usable range
        usable_segments = [s for s in segments if s['start'] >= usable_start and s['end'] <= usable_end]
        if not usable_segments:
            usable_segments = segments

        best_segment = min(usable_segments, key=lambda s: abs(s['start'] - target_time))

        start = max(usable_start, best_segment['start'] - 5)
        end = min(usable_end, start + min(max_duration, 60))

        # Get text for caption
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


def select_clips_ai(transcript, video_info, num_clips, max_duration):
    """Select clips using Groq AI"""
    if not GROQ_API_KEY:
        return select_clips_simple(transcript, num_clips, max_duration)

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        segments_text = []
        for seg in transcript['segments'][:200]:
            segments_text.append(f"[{seg['start']:.1f}s - {seg['end']:.1f}s]: {seg['text']}")

        prompt = f"""Find the {num_clips} BEST moments for TikTok clips from this transcript.

VIDEO: {video_info.get('title', 'Unknown')}

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


def generate_srt(transcript, start_time, end_time, output_path):
    """Generate SRT subtitle file"""
    segments = transcript['segments']
    srt_entries = []
    index = 1

    for seg in segments:
        if seg['end'] < start_time or seg['start'] > end_time:
            continue

        seg_start = max(0, seg['start'] - start_time)
        seg_end = min(end_time - start_time, seg['end'] - start_time)

        hours_s, minutes_s = int(seg_start // 3600), int((seg_start % 3600) // 60)
        secs_s, ms_s = int(seg_start % 60), int((seg_start % 1) * 1000)

        hours_e, minutes_e = int(seg_end // 3600), int((seg_end % 3600) // 60)
        secs_e, ms_e = int(seg_end % 60), int((seg_end % 1) * 1000)

        start_str = f"{hours_s:02d}:{minutes_s:02d}:{secs_s:02d},{ms_s:03d}"
        end_str = f"{hours_e:02d}:{minutes_e:02d}:{secs_e:02d},{ms_e:03d}"

        if seg['text'].strip():
            srt_entries.append(f"{index}\n{start_str} --> {end_str}\n{seg['text'].strip()}\n")
            index += 1

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(srt_entries))


def create_clip(video_path, start, end, srt_path, output_path):
    """Create TikTok-ready clip with FFmpeg"""
    duration = end - start
    srt_escaped = str(srt_path).replace('\\', '/').replace(':', '\\:')

    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start),
        '-i', str(video_path),
        '-t', str(duration),
        '-vf', (
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"subtitles='{srt_escaped}':force_style='FontName=Arial,FontSize=22,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=3,Outline=2,Shadow=1,MarginV=80'"
        ),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return True
    except:
        pass

    # Fallback without subtitles
    cmd_simple = [
        'ffmpeg', '-y',
        '-ss', str(start),
        '-i', str(video_path),
        '-t', str(duration),
        '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-c:a', 'aac', '-b:a', '128k',
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd_simple, capture_output=True, text=True, timeout=300)
        return result.returncode == 0
    except:
        return False


def generate_enhanced_clips_wrapper(video_path, clips, transcript, output_dir, config):
    """Wrapper to generate clips with enhanced features (karaoke, split-screen)"""
    try:
        from scripts.enhanced import generate_enhanced_clips as gen_clips
        return gen_clips(video_path, clips, transcript, output_dir, config)
    except ImportError as e:
        log(f"Enhanced modules not available: {e}")
        log("Falling back to basic clip generation...")
        return generate_clips_basic(video_path, clips, transcript, output_dir)


def generate_clips_basic(video_path, clips, transcript, output_dir):
    """Basic clip generation (fallback if enhanced not available)"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, clip in enumerate(clips, 1):
        output_path = output_dir / f"clip_{i:02d}.mp4"
        srt_path = output_dir / f"clip_{i:02d}.srt"

        generate_srt(transcript, clip['start'], clip['end'], srt_path)

        if create_clip(video_path, clip['start'], clip['end'], srt_path, output_path):
            results.append({
                'success': True,
                'path': str(output_path),
                'description': clip.get('description', ''),
                'hashtags': clip.get('hashtags', ['fyp', 'viral']),
                'features': {'subtitle_style': 'basic', 'split_screen': False}
            })
        else:
            results.append({'success': False})

    return results


def process_job(job):
    """Process a single job with ENHANCED features (karaoke, split-screen)"""
    job_id = job['job_id']
    chat_id = job['chat_id']
    youtube_url = job['youtube_url']
    num_clips = job['num_clips']
    clip_duration = job['clip_duration']

    log(f"Processing job: {job_id}")
    log(f"URL: {youtube_url}")
    log(f"Clips: {num_clips}, Duration: {clip_duration}s")
    log(f"Features: subtitles={SUBTITLE_STYLE}, split_screen={ENABLE_SPLIT_SCREEN}, face={ENABLE_FACE_TRACKING}")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        try:
            # Step 1: Download
            update_progress(job_id, "Downloading video...")
            video_info = download_video(youtube_url, temp_path)
            log(f"Downloaded: {video_info['title']}")

            # Step 2: Transcribe (with word timestamps for karaoke)
            update_progress(job_id, "Transcribing audio (with word timestamps)...")
            transcript = transcribe_video(video_info['video_path'])

            # Step 3: Select clips (skipping intro/outro)
            update_progress(job_id, "AI selecting best moments...")
            clips = select_clips_ai(transcript, video_info, num_clips, clip_duration)
            log(f"Selected: {len(clips)} clips")

            # Step 4: Generate clips with ENHANCED features
            features_text = f"({SUBTITLE_STYLE} subtitles"
            if ENABLE_FACE_TRACKING:
                features_text += ", face tracking"
            if ENABLE_SPLIT_SCREEN:
                features_text += ", split screen"
            features_text += ")"

            update_progress(job_id, f"Generating professional clips {features_text}...")
            output_dir = temp_path / "output"

            # Build config for enhanced generation
            config = {
                'enable_face_tracking': ENABLE_FACE_TRACKING,
                'subtitle_style': SUBTITLE_STYLE,
                'enable_split_screen': ENABLE_SPLIT_SCREEN,
                'split_layout': SPLIT_LAYOUT,
                'satisfying_folder': SATISFYING_FOLDER,
                'output_width': 1080,
                'output_height': 1920
            }

            generated_clips = generate_enhanced_clips_wrapper(
                video_info['video_path'], clips, transcript, output_dir, config
            )

            # Filter successful clips
            successful_clips = [c for c in generated_clips if c.get('success')]
            log(f"Generated: {len(successful_clips)} clips successfully")

            # Step 5: Send to Telegram
            update_progress(job_id, f"Sending {len(successful_clips)} clips...")

            for i, clip in enumerate(successful_clips, 1):
                log(f"Sending clip {i}/{len(successful_clips)}...")

                hashtags = " ".join([f"#{tag}" for tag in clip.get('hashtags', ['fyp', 'viral'])])
                caption = f"{clip.get('description', '')}\n\n{hashtags}\n\nCopy and post to TikTok!"

                # Add feature badges
                if 'features' in clip:
                    features = clip['features']
                    if features.get('subtitle_style') == 'karaoke':
                        caption += "\n🎤 Karaoke subtitles"
                    if features.get('split_screen'):
                        caption += "\n🎮 Split-screen"

                send_video_to_telegram(chat_id, clip['path'], caption)
                time.sleep(2)

            # Done!
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
    print("TikTok Clips Bot - ENHANCED Local Processor")
    print("=" * 60)
    print(f"\nBot URL: {BOT_URL}")
    print(f"Poll interval: {POLL_INTERVAL}s")
    print(f"\nEnhanced Features:")
    print(f"  Subtitle style: {SUBTITLE_STYLE}")
    print(f"  Split screen: {'ENABLED' if ENABLE_SPLIT_SCREEN else 'Disabled'}")
    print(f"  Face tracking: {'Enabled' if ENABLE_FACE_TRACKING else 'Disabled'}")
    print(f"  Groq AI: {'Enabled' if GROQ_API_KEY else 'Disabled (using simple selection)'}")
    print(f"  Satisfying folder: {SATISFYING_FOLDER}")
    print("\nWaiting for jobs...")
    print("Press Ctrl+C to stop\n")

    while True:
        try:
            # Check for pending jobs
            jobs = get_pending_jobs()

            if jobs:
                log(f"Found {len(jobs)} pending job(s)")

                for job in jobs:
                    # Claim the job
                    claimed_job = claim_job(job['job_id'])

                    if claimed_job:
                        log(f"Claimed job: {claimed_job['job_id']}")
                        process_job(claimed_job)
                    else:
                        log("Failed to claim job (might be taken)")

            # Wait before next check
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\n\nStopping local processor...")
            break
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()

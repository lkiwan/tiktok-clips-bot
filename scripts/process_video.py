#!/usr/bin/env python3
"""
Main video processing script for GitHub Actions
Downloads YouTube video, transcribes, creates clips, sends to Telegram
"""

import os
import sys
import json
import argparse
import subprocess
import tempfile
import requests
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from downloader import download_video
from transcriber import transcribe_video
from clip_selector import select_best_clips
from clip_generator import generate_clips
from telegram_sender import send_clips_to_telegram


def send_status(chat_id, message):
    """Send status update to Telegram"""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        print(f"Status: {message}")
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            },
            timeout=10
        )
    except Exception as e:
        print(f"Failed to send status: {e}")


def main():
    parser = argparse.ArgumentParser(description='Process YouTube video into TikTok clips')
    parser.add_argument('--chat-id', required=True, help='Telegram chat ID')
    parser.add_argument('--url', required=True, help='YouTube URL')
    parser.add_argument('--num-clips', type=int, default=3, help='Number of clips to generate')
    parser.add_argument('--clip-duration', type=int, default=60, help='Max duration per clip in seconds')

    args = parser.parse_args()

    print(f"Processing video: {args.url}")
    print(f"Clips: {args.num_clips}, Duration: {args.clip_duration}s")

    # Create temp directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        try:
            # Step 1: Download video
            send_status(args.chat_id, "📥 Downloading video...")
            print("\n=== Step 1: Downloading ===")
            video_info = download_video(args.url, temp_path)
            print(f"Downloaded: {video_info['title']}")
            print(f"Duration: {video_info['duration']}s")

            # Step 2: Transcribe
            send_status(args.chat_id, "🎤 Transcribing audio...")
            print("\n=== Step 2: Transcribing ===")
            transcript = transcribe_video(video_info['video_path'])
            print(f"Transcribed: {len(transcript['segments'])} segments")

            # Step 3: Select best clips
            send_status(args.chat_id, "🧠 AI selecting best moments...")
            print("\n=== Step 3: Selecting clips ===")
            clips = select_best_clips(
                transcript,
                video_info,
                num_clips=args.num_clips,
                max_duration=args.clip_duration
            )
            print(f"Selected: {len(clips)} clips")

            # Step 4: Generate clips
            send_status(args.chat_id, "🎬 Generating clips with subtitles...")
            print("\n=== Step 4: Generating clips ===")
            output_dir = temp_path / "output"
            output_dir.mkdir(exist_ok=True)

            generated_clips = generate_clips(
                video_info['video_path'],
                clips,
                transcript,
                output_dir
            )
            print(f"Generated: {len(generated_clips)} clips")

            # Step 5: Send to Telegram
            send_status(args.chat_id, "📤 Sending clips to you...")
            print("\n=== Step 5: Sending to Telegram ===")
            send_clips_to_telegram(args.chat_id, generated_clips)
            print("All clips sent!")

            print("\n=== Processing Complete ===")

        except Exception as e:
            print(f"\nError: {e}")
            send_status(args.chat_id, f"❌ Error: {str(e)[:200]}")
            sys.exit(1)


if __name__ == '__main__':
    main()

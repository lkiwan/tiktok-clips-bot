"""
Send generated clips to Telegram
"""

import os
import time
import requests
from pathlib import Path


TELEGRAM_API = "https://api.telegram.org/bot{token}"


def send_clips_to_telegram(chat_id, clips):
    """
    Send all generated clips to Telegram chat

    Args:
        chat_id: Telegram chat ID
        clips: List of clip info dicts with path, description, hashtags
    """
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")

    api_base = TELEGRAM_API.format(token=token)

    for i, clip in enumerate(clips, 1):
        print(f"Sending clip {i}/{len(clips)}...")

        # Prepare caption with description and hashtags
        caption = format_caption(clip)

        # Send video
        success = send_video(api_base, chat_id, clip['path'], caption)

        if success:
            print(f"  Clip {i} sent successfully")
        else:
            print(f"  Clip {i} failed to send")

        # Small delay between sends to avoid rate limiting
        if i < len(clips):
            time.sleep(2)


def format_caption(clip):
    """Format caption with description and hashtags"""
    parts = []

    # Add description
    if clip.get('description'):
        parts.append(clip['description'])

    # Add blank line
    parts.append("")

    # Add hashtags
    hashtags = clip.get('hashtags', [])
    if hashtags:
        hashtag_text = " ".join([f"#{tag.lstrip('#')}" for tag in hashtags])
        parts.append(hashtag_text)

    # Add copy instruction
    parts.append("")
    parts.append("👆 Copy caption above and post to TikTok!")

    return "\n".join(parts)


def send_video(api_base, chat_id, video_path, caption):
    """Send video to Telegram"""
    video_path = Path(video_path)

    if not video_path.exists():
        print(f"Video not found: {video_path}")
        return False

    # Check file size (Telegram limit is 50MB for bots)
    file_size = video_path.stat().st_size
    if file_size > 50 * 1024 * 1024:
        print(f"Video too large: {file_size / 1024 / 1024:.1f}MB (max 50MB)")
        return False

    try:
        with open(video_path, 'rb') as video_file:
            response = requests.post(
                f"{api_base}/sendVideo",
                data={
                    'chat_id': chat_id,
                    'caption': caption[:1024],  # Telegram caption limit
                    'parse_mode': 'HTML',
                    'supports_streaming': True
                },
                files={
                    'video': (video_path.name, video_file, 'video/mp4')
                },
                timeout=120  # 2 minute timeout for upload
            )

            result = response.json()

            if not result.get('ok'):
                print(f"Telegram error: {result.get('description', 'Unknown error')}")
                return False

            return True

    except requests.exceptions.Timeout:
        print("Upload timeout")
        return False
    except Exception as e:
        print(f"Send failed: {e}")
        return False


def send_message(api_base, chat_id, text):
    """Send text message to Telegram"""
    try:
        response = requests.post(
            f"{api_base}/sendMessage",
            json={
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            },
            timeout=10
        )
        return response.json().get('ok', False)
    except:
        return False

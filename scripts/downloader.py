"""
YouTube video downloader using yt-dlp
"""

import subprocess
import json
from pathlib import Path


def download_video(url, output_dir):
    """
    Download YouTube video

    Args:
        url: YouTube URL
        output_dir: Directory to save video

    Returns:
        dict with video info
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # First, get video info
    info_cmd = [
        'yt-dlp',
        '--dump-json',
        '--no-download',
        url
    ]

    result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)

    video_id = info['id']
    title = info.get('title', 'Unknown')
    duration = info.get('duration', 0)

    # Download video (best quality under 1080p for faster processing)
    output_path = output_dir / f"{video_id}.mp4"

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
        'video_path': str(output_path),
        'channel': info.get('uploader', 'Unknown'),
        'description': info.get('description', '')[:500]
    }

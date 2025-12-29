"""
Video clip generator using FFmpeg
Creates TikTok-ready vertical videos with subtitles
"""

import subprocess
import json
from pathlib import Path


def generate_clips(video_path, clips, transcript, output_dir):
    """
    Generate video clips with subtitles

    Args:
        video_path: Path to source video
        clips: List of clip dicts with start, end, description, hashtags
        transcript: Full transcript with word timestamps
        output_dir: Directory to save clips

    Returns:
        List of generated clip info dicts
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated = []

    for i, clip in enumerate(clips, 1):
        print(f"Generating clip {i}/{len(clips)}...")

        output_path = output_dir / f"clip_{i:02d}.mp4"
        srt_path = output_dir / f"clip_{i:02d}.srt"

        # Generate SRT subtitles for this clip
        generate_srt(transcript, clip['start'], clip['end'], srt_path)

        # Generate clip with FFmpeg
        success = create_tiktok_clip(
            video_path,
            clip['start'],
            clip['end'],
            srt_path,
            output_path
        )

        if success:
            generated.append({
                'path': str(output_path),
                'clip_number': i,
                'start': clip['start'],
                'end': clip['end'],
                'duration': clip['end'] - clip['start'],
                'description': clip['description'],
                'hashtags': clip['hashtags'],
                'reason': clip.get('reason', '')
            })

    return generated


def generate_srt(transcript, start_time, end_time, output_path):
    """Generate SRT subtitle file for a clip segment"""
    segments = transcript['segments']
    srt_entries = []
    index = 1

    for seg in segments:
        # Check if segment falls within clip range
        if seg['end'] < start_time or seg['start'] > end_time:
            continue

        # Adjust times relative to clip start
        seg_start = max(0, seg['start'] - start_time)
        seg_end = min(end_time - start_time, seg['end'] - start_time)

        # Format time for SRT
        start_str = format_srt_time(seg_start)
        end_str = format_srt_time(seg_end)

        text = seg['text'].strip()
        if text:
            srt_entries.append(f"{index}\n{start_str} --> {end_str}\n{text}\n")
            index += 1

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(srt_entries))


def format_srt_time(seconds):
    """Convert seconds to SRT time format (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def create_tiktok_clip(input_path, start, end, srt_path, output_path):
    """
    Create a TikTok-ready clip with vertical format and subtitles

    Uses FFmpeg to:
    1. Cut the video segment
    2. Convert to 9:16 aspect ratio (1080x1920)
    3. Add subtitles
    """
    duration = end - start

    # FFmpeg command for TikTok format
    # - Crop/scale to 9:16
    # - Add subtitles with nice styling
    # - Fast encoding settings

    # Escape paths for FFmpeg
    srt_escaped = str(srt_path).replace('\\', '/').replace(':', '\\:')

    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output
        '-ss', str(start),  # Start time
        '-i', str(input_path),  # Input video
        '-t', str(duration),  # Duration
        '-vf', (
            # Scale and crop to 9:16 (TikTok format)
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            # Add subtitles with styling
            f"subtitles='{srt_escaped}':force_style='"
            "FontName=Arial,"
            "FontSize=22,"
            "PrimaryColour=&HFFFFFF,"
            "OutlineColour=&H000000,"
            "BorderStyle=3,"
            "Outline=2,"
            "Shadow=1,"
            "MarginV=80"
            "'"
        ),
        '-c:v', 'libx264',  # Video codec
        '-preset', 'fast',  # Encoding speed
        '-crf', '23',  # Quality (lower = better, 18-28 is good)
        '-c:a', 'aac',  # Audio codec
        '-b:a', '128k',  # Audio bitrate
        '-movflags', '+faststart',  # Web optimization
        str(output_path)
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per clip
        )

        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr[:500]}")
            # Try simpler command without subtitles
            return create_simple_clip(input_path, start, end, output_path)

        return True

    except subprocess.TimeoutExpired:
        print("FFmpeg timeout")
        return False
    except Exception as e:
        print(f"FFmpeg failed: {e}")
        return create_simple_clip(input_path, start, end, output_path)


def create_simple_clip(input_path, start, end, output_path):
    """Create a simple clip without subtitles (fallback)"""
    duration = end - start

    cmd = [
        'ffmpeg',
        '-y',
        '-ss', str(start),
        '-i', str(input_path),
        '-t', str(duration),
        '-vf', (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920"
        ),
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '128k',
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0
    except:
        return False

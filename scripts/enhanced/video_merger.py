"""
Video Merger for TikTok Clips Bot
Combines main content with satisfying background videos using FFmpeg
"""

import os
import random
import subprocess
from pathlib import Path


class VideoMerger:
    """Merges main content with satisfying background videos"""

    LAYOUT_TOP_BOTTOM = 'top_bottom'
    LAYOUT_BOTTOM_TOP = 'bottom_top'
    LAYOUT_LEFT_RIGHT = 'left_right'

    def __init__(self, config=None):
        """Initialize video merger"""
        self.config = config or {}

        self.output_width = self.config.get('output_width', 1080)
        self.output_height = self.config.get('output_height', 1920)
        self.layout = self.config.get('layout', self.LAYOUT_TOP_BOTTOM)
        self.main_ratio = self.config.get('main_ratio', 0.6)

        # Satisfying video library
        self.satisfying_folder = Path(self.config.get(
            'satisfying_folder',
            './assets/satisfying_videos'
        ))

    def get_satisfying_videos(self, category='any'):
        """Get list of available satisfying videos"""
        if not self.satisfying_folder.exists():
            return []

        video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
        videos = []

        for ext in video_extensions:
            videos.extend(self.satisfying_folder.glob(f'*{ext}'))

        # Filter by category if specified
        if category and category != 'any':
            videos = [v for v in videos if category.lower() in v.stem.lower()]

        return videos

    def select_random_satisfying(self, category='any'):
        """Select a random satisfying video"""
        videos = self.get_satisfying_videos(category)
        if videos:
            return random.choice(videos)
        return None

    def create_merged_clip(self, main_video, output_path, satisfying_video=None,
                          start_time=0, duration=None, category='any'):
        """
        Create a merged clip with satisfying background

        Args:
            main_video: Path to main video
            output_path: Output path
            satisfying_video: Path to satisfying video (auto-selects if None)
            start_time: Start time in main video
            duration: Duration to extract
            category: Satisfying video category

        Returns:
            dict: Result with success status
        """
        if satisfying_video is None:
            satisfying_video = self.select_random_satisfying(category)

        if satisfying_video is None:
            print("[WARNING] No satisfying videos available. Creating without split screen.")
            return self._create_simple_clip(main_video, output_path, start_time, duration)

        # Calculate dimensions
        if self.layout in [self.LAYOUT_TOP_BOTTOM, self.LAYOUT_BOTTOM_TOP]:
            main_height = int(self.output_height * self.main_ratio)
            sat_height = self.output_height - main_height
            main_width = self.output_width
            sat_width = self.output_width
        else:  # LEFT_RIGHT
            main_width = int(self.output_width * self.main_ratio)
            sat_width = self.output_width - main_width
            main_height = self.output_height
            sat_height = self.output_height

        # Build FFmpeg filter complex
        if self.layout == self.LAYOUT_TOP_BOTTOM:
            filter_complex = self._build_top_bottom_filter(
                main_width, main_height, sat_width, sat_height
            )
            vstack = True
        elif self.layout == self.LAYOUT_BOTTOM_TOP:
            filter_complex = self._build_bottom_top_filter(
                main_width, main_height, sat_width, sat_height
            )
            vstack = True
        else:
            filter_complex = self._build_left_right_filter(
                main_width, main_height, sat_width, sat_height
            )
            vstack = False

        # Build FFmpeg command
        cmd = ['ffmpeg', '-y']

        # Input: main video with time selection
        if start_time > 0:
            cmd.extend(['-ss', str(start_time)])
        cmd.extend(['-i', str(main_video)])

        if duration:
            cmd.extend(['-t', str(duration)])

        # Input: satisfying video (will loop if needed)
        cmd.extend(['-stream_loop', '-1', '-i', str(satisfying_video)])

        # Apply filter
        cmd.extend(['-filter_complex', filter_complex])

        # Map the output
        cmd.extend(['-map', '[v]', '-map', '0:a?'])

        # Encoding settings
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-shortest',  # Stop when shortest input ends
            str(output_path)
        ])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode != 0:
                print(f"FFmpeg error: {result.stderr[:500]}")
                return self._create_simple_clip(main_video, output_path, start_time, duration)

            return {
                'success': True,
                'output_path': str(output_path),
                'layout': self.layout,
                'satisfying_used': str(satisfying_video)
            }

        except subprocess.TimeoutExpired:
            print("FFmpeg timeout on merge")
            return self._create_simple_clip(main_video, output_path, start_time, duration)
        except Exception as e:
            print(f"Merge failed: {e}")
            return self._create_simple_clip(main_video, output_path, start_time, duration)

    def _build_top_bottom_filter(self, main_w, main_h, sat_w, sat_h):
        """Build filter for main on top, satisfying on bottom"""
        return (
            f"[0:v]scale={main_w}:{main_h}:force_original_aspect_ratio=increase,"
            f"crop={main_w}:{main_h}[main];"
            f"[1:v]scale={sat_w}:{sat_h}:force_original_aspect_ratio=increase,"
            f"crop={sat_w}:{sat_h},volume=0[sat];"
            f"[main][sat]vstack=inputs=2[v]"
        )

    def _build_bottom_top_filter(self, main_w, main_h, sat_w, sat_h):
        """Build filter for satisfying on top, main on bottom"""
        return (
            f"[0:v]scale={main_w}:{main_h}:force_original_aspect_ratio=increase,"
            f"crop={main_w}:{main_h}[main];"
            f"[1:v]scale={sat_w}:{sat_h}:force_original_aspect_ratio=increase,"
            f"crop={sat_w}:{sat_h},volume=0[sat];"
            f"[sat][main]vstack=inputs=2[v]"
        )

    def _build_left_right_filter(self, main_w, main_h, sat_w, sat_h):
        """Build filter for side by side"""
        return (
            f"[0:v]scale={main_w}:{main_h}:force_original_aspect_ratio=increase,"
            f"crop={main_w}:{main_h}[main];"
            f"[1:v]scale={sat_w}:{sat_h}:force_original_aspect_ratio=increase,"
            f"crop={sat_w}:{sat_h},volume=0[sat];"
            f"[main][sat]hstack=inputs=2[v]"
        )

    def _create_simple_clip(self, main_video, output_path, start_time=0, duration=None):
        """Fallback: create clip without split screen"""
        cmd = ['ffmpeg', '-y']

        if start_time > 0:
            cmd.extend(['-ss', str(start_time)])

        cmd.extend(['-i', str(main_video)])

        if duration:
            cmd.extend(['-t', str(duration)])

        cmd.extend([
            '-vf', f'scale={self.output_width}:{self.output_height}:force_original_aspect_ratio=increase,'
                   f'crop={self.output_width}:{self.output_height}',
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            str(output_path)
        ])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return {
                'success': result.returncode == 0,
                'output_path': str(output_path),
                'layout': 'none'
            }
        except:
            return {'success': False}


def get_satisfying_stats(folder_path='./assets/satisfying_videos'):
    """Get statistics about satisfying video library"""
    folder = Path(folder_path)

    if not folder.exists():
        return {'total': 0, 'categories': {}}

    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    videos = []

    for ext in video_extensions:
        videos.extend(folder.glob(f'*{ext}'))

    # Categorize
    categories = {
        'minecraft': 0,
        'subway_surfers': 0,
        'soap_cutting': 0,
        'slime': 0,
        'other': 0
    }

    for video in videos:
        name = video.stem.lower()
        if 'minecraft' in name or 'parkour' in name:
            categories['minecraft'] += 1
        elif 'subway' in name or 'surfer' in name:
            categories['subway_surfers'] += 1
        elif 'soap' in name or 'cutting' in name:
            categories['soap_cutting'] += 1
        elif 'slime' in name:
            categories['slime'] += 1
        else:
            categories['other'] += 1

    return {
        'total': len(videos),
        'categories': categories
    }

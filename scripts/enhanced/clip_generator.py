"""
Enhanced Clip Generator for TikTok Clips Bot
Creates professional TikTok clips with:
- Face-aware smart cropping
- Karaoke-style subtitles
- Split-screen with satisfying backgrounds
"""

import subprocess
from pathlib import Path

# Import enhanced modules
try:
    from .face_tracker import FaceTracker, get_smart_crop_filter
    FACE_TRACKING_AVAILABLE = True
except ImportError:
    FACE_TRACKING_AVAILABLE = False

try:
    from .subtitle_renderer import generate_ass_subtitles, get_ffmpeg_subtitle_filter, SubtitleStyle
    ASS_SUBTITLES_AVAILABLE = True
except ImportError:
    ASS_SUBTITLES_AVAILABLE = False

try:
    from .video_merger import VideoMerger
    MERGER_AVAILABLE = True
except ImportError:
    MERGER_AVAILABLE = False


class EnhancedClipGenerator:
    """Generates professional TikTok clips with all enhancements"""

    def __init__(self, config=None):
        """
        Initialize enhanced clip generator

        Args:
            config: Configuration dict with options:
                - enable_face_tracking: bool
                - subtitle_style: 'karaoke', 'highlight', 'box', 'simple'
                - enable_split_screen: bool
                - split_layout: 'top_bottom', 'bottom_top', 'left_right'
                - main_ratio: float (0.5-0.8)
                - satisfying_folder: str path
                - satisfying_category: 'any', 'minecraft', etc.
                - output_width: int
                - output_height: int
        """
        self.config = config or {}

        # Feature flags
        self.enable_face_tracking = self.config.get('enable_face_tracking', True) and FACE_TRACKING_AVAILABLE
        self.subtitle_style = self.config.get('subtitle_style', 'karaoke')
        self.enable_split_screen = self.config.get('enable_split_screen', False) and MERGER_AVAILABLE

        # Output settings
        self.output_width = self.config.get('output_width', 1080)
        self.output_height = self.config.get('output_height', 1920)

        # Initialize components
        if self.enable_face_tracking:
            self.face_tracker = FaceTracker()
        else:
            self.face_tracker = None

        if self.enable_split_screen:
            self.merger = VideoMerger({
                'layout': self.config.get('split_layout', 'top_bottom'),
                'main_ratio': self.config.get('main_ratio', 0.6),
                'satisfying_folder': self.config.get('satisfying_folder', './assets/satisfying_videos'),
                'output_width': self.output_width,
                'output_height': self.output_height
            })
        else:
            self.merger = None

    def generate_clip(self, video_path, clip_data, transcript, output_path):
        """
        Generate a single enhanced clip

        Args:
            video_path: Path to source video
            clip_data: Dict with start, end, description, hashtags
            transcript: Full transcript dict
            output_path: Output file path

        Returns:
            dict: Result with success status and clip info
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        start = clip_data['start']
        end = clip_data['end']
        duration = end - start

        print(f"  Generating enhanced clip: {start:.1f}s - {end:.1f}s")

        # Step 1: Get video filter (with face tracking if enabled)
        video_filter = self._get_video_filter(video_path, start, end)

        # Step 2: Generate subtitles
        subtitle_path = output_path.with_suffix('.ass')
        subtitle_filter = self._generate_subtitles(transcript, start, end, subtitle_path)

        # Combine filters
        if subtitle_filter:
            full_filter = f"{video_filter},{subtitle_filter}"
        else:
            full_filter = video_filter

        # Step 3: Generate clip (with or without split screen)
        if self.enable_split_screen and self.merger:
            # Create temp clip first, then merge
            temp_path = output_path.parent / f"temp_{output_path.name}"
            success = self._create_clip_ffmpeg(video_path, start, duration, full_filter, temp_path)

            if success:
                # Merge with satisfying video
                merge_result = self.merger.create_merged_clip(
                    temp_path,
                    output_path,
                    category=self.config.get('satisfying_category', 'any')
                )

                # Clean up temp file
                if temp_path.exists():
                    temp_path.unlink()

                if merge_result.get('success'):
                    return self._build_result(output_path, clip_data, duration, merge_result)
                else:
                    # Fallback: use temp as output
                    return self._build_result(temp_path, clip_data, duration, {'layout': 'none'})
            else:
                return {'success': False, 'error': 'Failed to create clip'}
        else:
            # Create clip directly
            success = self._create_clip_ffmpeg(video_path, start, duration, full_filter, output_path)

            if success:
                return self._build_result(output_path, clip_data, duration, {'layout': 'none'})
            else:
                # Try simple fallback
                return self._create_simple_clip(video_path, start, duration, output_path, clip_data)

    def _get_video_filter(self, video_path, start, end):
        """Get video filter with optional face tracking"""
        if self.enable_face_tracking and self.face_tracker:
            try:
                crop_info = self.face_tracker.get_crop_for_clip(
                    video_path, start, end, self.output_width / self.output_height
                )

                if crop_info.get('has_faces'):
                    print(f"    Face detected at {crop_info['face_center']}")
                    return f"{crop_info['ffmpeg_crop']},scale={self.output_width}:{self.output_height}"
            except Exception as e:
                print(f"    Face tracking failed: {e}")

        # Default center crop
        return (f"scale={self.output_width}:{self.output_height}:force_original_aspect_ratio=increase,"
                f"crop={self.output_width}:{self.output_height}")

    def _generate_subtitles(self, transcript, start, end, output_path):
        """Generate subtitles and return FFmpeg filter"""
        if not ASS_SUBTITLES_AVAILABLE:
            return self._generate_srt_subtitles(transcript, start, end, output_path.with_suffix('.srt'))

        try:
            # Use ASS subtitles with karaoke
            ass_path = generate_ass_subtitles(
                transcript, start, end, output_path,
                style=self.subtitle_style,
                config={
                    'primary_color': self.config.get('subtitle_color', '&HFFFFFF'),
                    'highlight_color': self.config.get('highlight_color', '&H00D7FF'),
                    'font_size': self.config.get('font_size', 48)
                }
            )
            return get_ffmpeg_subtitle_filter(ass_path)
        except Exception as e:
            print(f"    ASS subtitle generation failed: {e}")
            return self._generate_srt_subtitles(transcript, start, end, output_path.with_suffix('.srt'))

    def _generate_srt_subtitles(self, transcript, start, end, srt_path):
        """Fallback: generate SRT subtitles"""
        segments = transcript.get('segments', [])
        srt_entries = []
        index = 1

        for seg in segments:
            if seg['end'] < start or seg['start'] > end:
                continue

            seg_start = max(0, seg['start'] - start)
            seg_end = min(end - start, seg['end'] - start)

            # Format time
            def fmt(s):
                h, m = int(s // 3600), int((s % 3600) // 60)
                sec, ms = int(s % 60), int((s % 1) * 1000)
                return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

            text = seg['text'].strip()
            if text:
                srt_entries.append(f"{index}\n{fmt(seg_start)} --> {fmt(seg_end)}\n{text}\n")
                index += 1

        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(srt_entries))

        srt_escaped = str(srt_path).replace('\\', '/').replace(':', '\\:')
        return (f"subtitles='{srt_escaped}':force_style='"
                "FontName=Arial,FontSize=22,PrimaryColour=&HFFFFFF,"
                "OutlineColour=&H000000,BorderStyle=3,Outline=2,Shadow=1,MarginV=80'")

    def _create_clip_ffmpeg(self, video_path, start, duration, video_filter, output_path):
        """Create clip using FFmpeg"""
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-i', str(video_path),
            '-t', str(duration),
            '-vf', video_filter,
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return result.returncode == 0
        except Exception as e:
            print(f"    FFmpeg error: {e}")
            return False

    def _create_simple_clip(self, video_path, start, duration, output_path, clip_data):
        """Create simple clip without enhancements"""
        cmd = [
            'ffmpeg', '-y',
            '-ss', str(start),
            '-i', str(video_path),
            '-t', str(duration),
            '-vf', f'scale={self.output_width}:{self.output_height}:force_original_aspect_ratio=increase,'
                   f'crop={self.output_width}:{self.output_height}',
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                return self._build_result(output_path, clip_data, duration, {'layout': 'none'})
        except:
            pass

        return {'success': False, 'error': 'Failed to create clip'}

    def _build_result(self, output_path, clip_data, duration, merge_info):
        """Build result dict"""
        return {
            'success': True,
            'path': str(output_path),
            'duration': duration,
            'start': clip_data['start'],
            'end': clip_data['end'],
            'description': clip_data.get('description', ''),
            'hashtags': clip_data.get('hashtags', ['fyp', 'viral']),
            'features': {
                'face_tracking': self.enable_face_tracking,
                'subtitle_style': self.subtitle_style,
                'split_screen': merge_info.get('layout', 'none') != 'none'
            }
        }


def generate_enhanced_clips(video_path, clips, transcript, output_dir, config=None):
    """
    Generate multiple enhanced clips

    Args:
        video_path: Path to source video
        clips: List of clip dicts
        transcript: Full transcript
        output_dir: Output directory
        config: Enhancement configuration

    Returns:
        list: Results for each clip
    """
    generator = EnhancedClipGenerator(config)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for i, clip in enumerate(clips, 1):
        print(f"\nGenerating clip {i}/{len(clips)}...")

        output_path = output_dir / f"clip_{i:02d}.mp4"

        try:
            result = generator.generate_clip(video_path, clip, transcript, output_path)
            results.append(result)

            if result.get('success'):
                print(f"  [OK] Clip {i} created")
            else:
                print(f"  [ERROR] Clip {i} failed: {result.get('error')}")
        except Exception as e:
            print(f"  [ERROR] Clip {i} exception: {e}")
            results.append({'success': False, 'error': str(e)})

    return results

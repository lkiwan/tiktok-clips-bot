"""
Enhanced TikTok Clips Bot Modules
Professional video generation with:
- Face-aware smart cropping
- Karaoke-style subtitles
- Split-screen with satisfying backgrounds
- Copyright avoidance
"""

from .clip_generator import EnhancedClipGenerator, generate_enhanced_clips

try:
    from .face_tracker import FaceTracker, get_smart_crop_filter
except ImportError:
    FaceTracker = None
    get_smart_crop_filter = None

try:
    from .subtitle_renderer import generate_ass_subtitles, SubtitleStyle
except ImportError:
    generate_ass_subtitles = None
    SubtitleStyle = None

try:
    from .video_merger import VideoMerger, get_satisfying_stats
except ImportError:
    VideoMerger = None
    get_satisfying_stats = None

try:
    from .copyright_avoider import CopyrightAvoider, quick_copyright_protect, get_safe_modifications
except ImportError:
    CopyrightAvoider = None
    quick_copyright_protect = None
    get_safe_modifications = None

__all__ = [
    'EnhancedClipGenerator',
    'generate_enhanced_clips',
    'FaceTracker',
    'get_smart_crop_filter',
    'generate_ass_subtitles',
    'SubtitleStyle',
    'VideoMerger',
    'get_satisfying_stats',
    'CopyrightAvoider',
    'quick_copyright_protect',
    'get_safe_modifications'
]

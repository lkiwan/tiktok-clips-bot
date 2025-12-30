"""
Configuration for Enhanced TikTok Clips Bot
Edit these settings to customize video generation
"""

# ============== ENHANCEMENT SETTINGS ==============

# Face Tracking (smart cropping for panoramic videos)
ENABLE_FACE_TRACKING = True  # Set to False if mediapipe not installed

# Subtitle Style
# Options: 'karaoke', 'highlight', 'box', 'simple'
# - karaoke: Words highlight as spoken (like MrBeast)
# - highlight: Current word highlighted
# - box: Text with background box
# - simple: Basic white text
SUBTITLE_STYLE = 'karaoke'

# Split Screen (satisfying background videos)
ENABLE_SPLIT_SCREEN = False  # Enable for Minecraft parkour, etc.
SPLIT_LAYOUT = 'top_bottom'  # 'top_bottom', 'bottom_top', 'left_right'
MAIN_RATIO = 0.6  # Main content takes 60% of screen
SATISFYING_FOLDER = './assets/satisfying_videos'
SATISFYING_CATEGORY = 'any'  # 'any', 'minecraft', 'subway_surfers', 'soap_cutting', 'slime'

# Video Output
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
VIDEO_FPS = 30
VIDEO_CRF = 23  # Quality (lower = better, 18-28 is good range)

# Subtitle Styling
FONT_NAME = 'Arial'
FONT_SIZE = 48
PRIMARY_COLOR = '&HFFFFFF'  # White (BGR format for ASS)
HIGHLIGHT_COLOR = '&H00D7FF'  # Gold
OUTLINE_COLOR = '&H000000'  # Black

# ============== TELEGRAM BOT SETTINGS ==============
# (These are also in local_processor.py)

BOT_URL = "https://tiktok-clips-bot.onrender.com"
POLL_INTERVAL = 30  # seconds


def get_enhancement_config():
    """Get configuration dict for enhanced generator"""
    return {
        'enable_face_tracking': ENABLE_FACE_TRACKING,
        'subtitle_style': SUBTITLE_STYLE,
        'enable_split_screen': ENABLE_SPLIT_SCREEN,
        'split_layout': SPLIT_LAYOUT,
        'main_ratio': MAIN_RATIO,
        'satisfying_folder': SATISFYING_FOLDER,
        'satisfying_category': SATISFYING_CATEGORY,
        'output_width': OUTPUT_WIDTH,
        'output_height': OUTPUT_HEIGHT,
        'font_size': FONT_SIZE,
        'subtitle_color': PRIMARY_COLOR,
        'highlight_color': HIGHLIGHT_COLOR
    }

"""
Enhanced Subtitle Renderer for TikTok Clips Bot
Generates karaoke-style and animated subtitles using FFmpeg ASS format
"""

import os
from pathlib import Path


class SubtitleStyle:
    """Subtitle style constants"""
    KARAOKE = 'karaoke'
    HIGHLIGHT = 'highlight'
    SIMPLE = 'simple'
    BOX = 'box'


def generate_ass_subtitles(transcript, start_time, end_time, output_path, style='karaoke', config=None):
    """
    Generate ASS subtitle file with karaoke or highlight effects

    Args:
        transcript: Transcript dict with segments and word_segments
        start_time: Clip start time
        end_time: Clip end time
        output_path: Output ASS file path
        style: Subtitle style (karaoke, highlight, simple, box)
        config: Style configuration

    Returns:
        str: Path to generated ASS file
    """
    config = config or {}

    # Default colors
    primary_color = config.get('primary_color', '&HFFFFFF')  # White
    highlight_color = config.get('highlight_color', '&H00D7FF')  # Gold (BGR format)
    outline_color = config.get('outline_color', '&H000000')  # Black
    font_name = config.get('font', 'Arial')
    font_size = config.get('font_size', 48)

    # ASS header
    ass_content = f"""[Script Info]
Title: TikTok Clip Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},&H80000000,1,0,0,0,100,100,0,0,1,3,1,2,40,40,120,1
Style: Highlight,{font_name},{int(font_size * 1.1)},{highlight_color},&H000000FF,{outline_color},&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,40,40,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Get word segments if available, otherwise use regular segments
    word_segments = transcript.get('word_segments', [])
    segments = transcript.get('segments', [])

    if style == SubtitleStyle.KARAOKE and word_segments:
        # Karaoke style with word-level timing
        ass_content += generate_karaoke_events(word_segments, start_time, end_time)
    elif style == SubtitleStyle.HIGHLIGHT and word_segments:
        # Highlight current word
        ass_content += generate_highlight_events(word_segments, start_time, end_time)
    elif style == SubtitleStyle.BOX:
        # Text with background box
        ass_content += generate_box_events(segments, start_time, end_time)
    else:
        # Simple subtitles
        ass_content += generate_simple_events(segments, start_time, end_time)

    # Write ASS file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)

    return str(output_path)


def format_ass_time(seconds):
    """Convert seconds to ASS time format (H:MM:SS.cc)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


def generate_karaoke_events(word_segments, start_time, end_time):
    """Generate karaoke-style events with word-by-word highlighting"""
    events = ""

    # Group words into phrases (max 4-5 words per line)
    max_words = 4
    phrases = []
    current_phrase = []

    for word in word_segments:
        if word['start'] < start_time or word['end'] > end_time:
            continue

        current_phrase.append({
            'word': word['word'],
            'start': word['start'] - start_time,
            'end': word['end'] - start_time
        })

        if len(current_phrase) >= max_words:
            phrases.append(current_phrase)
            current_phrase = []

    if current_phrase:
        phrases.append(current_phrase)

    # Generate events for each phrase
    for phrase in phrases:
        if not phrase:
            continue

        phrase_start = phrase[0]['start']
        phrase_end = phrase[-1]['end']

        start_str = format_ass_time(phrase_start)
        end_str = format_ass_time(phrase_end)

        # Build karaoke text with timing tags
        karaoke_text = ""
        for word in phrase:
            word_duration = int((word['end'] - word['start']) * 100)  # in centiseconds
            karaoke_text += f"{{\\kf{word_duration}}}{word['word']} "

        events += f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{karaoke_text.strip()}\n"

    return events


def generate_highlight_events(word_segments, start_time, end_time):
    """Generate events that highlight the current word"""
    events = ""

    # Group into phrases
    max_words = 4
    phrases = []
    current_phrase = []

    for word in word_segments:
        if word['start'] < start_time or word['end'] > end_time:
            continue

        current_phrase.append({
            'word': word['word'],
            'start': word['start'] - start_time,
            'end': word['end'] - start_time
        })

        if len(current_phrase) >= max_words:
            phrases.append(current_phrase)
            current_phrase = []

    if current_phrase:
        phrases.append(current_phrase)

    # For each phrase, create multiple events showing progression
    for phrase in phrases:
        if not phrase:
            continue

        phrase_text = " ".join([w['word'] for w in phrase])

        for i, word in enumerate(phrase):
            # Show phrase with current word highlighted
            start_str = format_ass_time(word['start'])
            end_str = format_ass_time(word['end'])

            # Build text with highlight on current word
            highlighted_text = ""
            for j, w in enumerate(phrase):
                if j == i:
                    # Current word - use highlight style
                    highlighted_text += f"{{\\rHighlight}}{w['word']}{{\\rDefault}} "
                else:
                    highlighted_text += f"{w['word']} "

            events += f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{highlighted_text.strip()}\n"

    return events


def generate_box_events(segments, start_time, end_time):
    """Generate events with background box"""
    events = ""

    for seg in segments:
        if seg['end'] < start_time or seg['start'] > end_time:
            continue

        seg_start = max(0, seg['start'] - start_time)
        seg_end = min(end_time - start_time, seg['end'] - start_time)

        start_str = format_ass_time(seg_start)
        end_str = format_ass_time(seg_end)

        text = seg['text'].strip()
        if text:
            # Add background box using \bord and \shad
            boxed_text = f"{{\\bord4\\3c&H000000&\\3a&H40&}}{text}"
            events += f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{boxed_text}\n"

    return events


def generate_simple_events(segments, start_time, end_time):
    """Generate simple subtitle events"""
    events = ""

    for seg in segments:
        if seg['end'] < start_time or seg['start'] > end_time:
            continue

        seg_start = max(0, seg['start'] - start_time)
        seg_end = min(end_time - start_time, seg['end'] - start_time)

        start_str = format_ass_time(seg_start)
        end_str = format_ass_time(seg_end)

        text = seg['text'].strip()
        if text:
            events += f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}\n"

    return events


def get_ffmpeg_subtitle_filter(ass_path, style='karaoke'):
    """
    Get FFmpeg filter for ASS subtitles

    Args:
        ass_path: Path to ASS file
        style: Subtitle style (affects filter parameters)

    Returns:
        str: FFmpeg subtitle filter
    """
    # Escape path for FFmpeg
    escaped_path = str(ass_path).replace('\\', '/').replace(':', '\\:')
    return f"ass='{escaped_path}'"

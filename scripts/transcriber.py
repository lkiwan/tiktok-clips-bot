"""
Video transcription using faster-whisper
"""

from faster_whisper import WhisperModel


def transcribe_video(video_path, model_size="base", language=None):
    """
    Transcribe video audio using Whisper

    Args:
        video_path: Path to video file
        model_size: Whisper model size (tiny, base, small, medium)
        language: Language code or None for auto-detect

    Returns:
        dict with transcript and segments
    """
    print(f"Loading Whisper model: {model_size}")

    # Use CPU with int8 for GitHub Actions
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print("Transcribing...")
    segments, info = model.transcribe(
        video_path,
        language=language,
        beam_size=5,
        word_timestamps=True
    )

    # Convert segments to list
    transcript_segments = []
    full_text = []

    for segment in segments:
        seg_data = {
            'start': segment.start,
            'end': segment.end,
            'text': segment.text.strip(),
            'words': []
        }

        # Add word-level timestamps if available
        if segment.words:
            for word in segment.words:
                seg_data['words'].append({
                    'word': word.word,
                    'start': word.start,
                    'end': word.end
                })

        transcript_segments.append(seg_data)
        full_text.append(segment.text.strip())

    return {
        'segments': transcript_segments,
        'full_text': ' '.join(full_text),
        'language': info.language,
        'duration': info.duration
    }

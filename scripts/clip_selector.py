"""
AI-powered clip selection using Groq API (free tier)
Falls back to simple algorithm if API unavailable
"""

import os
import json
import re
from groq import Groq


def select_best_clips(transcript, video_info, num_clips=3, max_duration=60):
    """
    Select the best clips from transcript using AI

    Args:
        transcript: Transcript dict with segments
        video_info: Video metadata
        num_clips: Number of clips to select
        max_duration: Maximum duration per clip in seconds

    Returns:
        List of clip dicts with start, end, description, hashtags
    """
    groq_key = os.environ.get('GROQ_API_KEY')

    if groq_key:
        try:
            return select_clips_with_ai(transcript, video_info, num_clips, max_duration, groq_key)
        except Exception as e:
            print(f"AI selection failed: {e}")
            print("Falling back to simple selection...")

    return select_clips_simple(transcript, num_clips, max_duration)


def select_clips_with_ai(transcript, video_info, num_clips, max_duration, api_key):
    """Select clips using Groq AI"""
    client = Groq(api_key=api_key)

    # Prepare transcript for AI (limit to avoid token limits)
    segments_text = []
    for i, seg in enumerate(transcript['segments']):
        segments_text.append(f"[{seg['start']:.1f}s - {seg['end']:.1f}s]: {seg['text']}")

    full_transcript = "\n".join(segments_text[:200])  # Limit segments

    prompt = f"""You are a TikTok content expert. Analyze this transcript and find the {num_clips} BEST moments for viral TikTok clips.

VIDEO TITLE: {video_info['title']}

TRANSCRIPT:
{full_transcript}

Find {num_clips} clips that are:
- Engaging, funny, controversial, or emotionally powerful
- Self-contained (make sense without context)
- Between 15-{max_duration} seconds long
- Perfect for TikTok's short attention span

For each clip, respond in this EXACT JSON format:
{{
  "clips": [
    {{
      "start": <start_time_in_seconds>,
      "end": <end_time_in_seconds>,
      "reason": "<why this moment is viral-worthy>",
      "description": "<catchy TikTok caption, max 100 chars>",
      "hashtags": ["hashtag1", "hashtag2", "hashtag3", "fyp", "viral"]
    }}
  ]
}}

ONLY respond with valid JSON. No other text."""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",  # Fast and free
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000
    )

    # Parse response
    response_text = response.choices[0].message.content.strip()

    # Try to extract JSON
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        result = json.loads(json_match.group())
        clips = result.get('clips', [])

        # Validate and adjust clips
        validated_clips = []
        for clip in clips[:num_clips]:
            start = float(clip.get('start', 0))
            end = float(clip.get('end', start + 30))

            # Ensure valid duration
            if end - start > max_duration:
                end = start + max_duration
            if end - start < 10:
                end = start + 30

            validated_clips.append({
                'start': start,
                'end': end,
                'reason': clip.get('reason', 'Engaging content'),
                'description': clip.get('description', 'Check this out!')[:100],
                'hashtags': clip.get('hashtags', ['fyp', 'viral', 'tiktok'])[:7]
            })

        return validated_clips

    raise ValueError("Could not parse AI response")


def select_clips_simple(transcript, num_clips, max_duration):
    """
    Simple clip selection without AI
    Selects evenly spaced segments from the video
    """
    segments = transcript['segments']

    if not segments:
        return []

    total_duration = segments[-1]['end']
    clips = []

    # Calculate spacing
    spacing = total_duration / (num_clips + 1)

    for i in range(num_clips):
        target_time = spacing * (i + 1)

        # Find segment closest to target time
        best_segment = min(segments, key=lambda s: abs(s['start'] - target_time))

        start = max(0, best_segment['start'] - 5)
        end = min(total_duration, start + min(max_duration, 45))

        # Get text for this section
        clip_text = ""
        for seg in segments:
            if seg['start'] >= start and seg['end'] <= end:
                clip_text += seg['text'] + " "

        clips.append({
            'start': start,
            'end': end,
            'reason': 'Selected based on video timing',
            'description': clip_text[:80].strip() + "..." if len(clip_text) > 80 else clip_text.strip(),
            'hashtags': ['fyp', 'viral', 'trending', 'tiktok', 'foryou']
        })

    return clips

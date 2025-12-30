"""
Copyright Avoider for TikTok Clips Bot
Helps avoid copyright detection through various audio/video modifications
"""

import subprocess
import random
from pathlib import Path


class CopyrightAvoider:
    """Applies modifications to avoid copyright detection on TikTok"""

    # Modification levels
    LEVEL_MINIMAL = 'minimal'      # Subtle changes only
    LEVEL_MODERATE = 'moderate'    # Noticeable but acceptable
    LEVEL_AGGRESSIVE = 'aggressive'  # Strong modifications

    def __init__(self, config=None):
        """Initialize copyright avoider"""
        self.config = config or {}
        self.level = self.config.get('level', self.LEVEL_MODERATE)

    def process_video(self, input_path, output_path, modifications=None):
        """
        Apply copyright-avoiding modifications to video

        Args:
            input_path: Path to input video
            output_path: Path for output video
            modifications: List of modifications to apply, or None for auto

        Returns:
            dict: Result with success status and applied modifications
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if modifications is None:
            modifications = self._get_auto_modifications()

        # Build FFmpeg filters
        audio_filters = []
        video_filters = []
        applied = []

        for mod in modifications:
            if mod == 'pitch_shift':
                # Shift pitch slightly (makes audio fingerprint different)
                shift = self._get_pitch_shift()
                audio_filters.append(f"asetrate=44100*{shift},aresample=44100")
                applied.append(f'pitch_shift_{shift:.3f}')

            elif mod == 'tempo_change':
                # Slightly speed up or slow down
                tempo = self._get_tempo_change()
                audio_filters.append(f"atempo={tempo}")
                applied.append(f'tempo_{tempo:.3f}')

            elif mod == 'eq_adjust':
                # Subtle EQ changes
                audio_filters.append("equalizer=f=1000:width_type=o:width=2:g=2")
                applied.append('eq_adjust')

            elif mod == 'add_reverb':
                # Add subtle room reverb
                audio_filters.append("aecho=0.8:0.88:6:0.4")
                applied.append('reverb')

            elif mod == 'mirror':
                # Mirror video horizontally
                video_filters.append("hflip")
                applied.append('mirror')

            elif mod == 'zoom':
                # Subtle zoom in (102-105%)
                zoom = random.uniform(1.02, 1.05)
                video_filters.append(
                    f"scale=iw*{zoom}:ih*{zoom},"
                    f"crop=iw/{zoom}:ih/{zoom}"
                )
                applied.append(f'zoom_{zoom:.3f}')

            elif mod == 'color_shift':
                # Slight color temperature shift
                hue_shift = random.uniform(-5, 5)
                video_filters.append(f"hue=h={hue_shift}")
                applied.append('color_shift')

            elif mod == 'brightness':
                # Subtle brightness adjustment
                brightness = random.uniform(-0.03, 0.03)
                video_filters.append(f"eq=brightness={brightness}")
                applied.append('brightness')

            elif mod == 'border':
                # Add thin border/frame
                video_filters.append(
                    "pad=iw+20:ih+20:10:10:color=black"
                )
                applied.append('border')

            elif mod == 'noise':
                # Add very subtle noise
                video_filters.append("noise=alls=3:allf=t")
                applied.append('noise')

        # Build FFmpeg command
        cmd = ['ffmpeg', '-y', '-i', str(input_path)]

        # Combine filters
        filter_complex = []

        if video_filters:
            filter_complex.append(','.join(video_filters))

        if audio_filters:
            cmd.extend(['-af', ','.join(audio_filters)])

        if filter_complex:
            cmd.extend(['-vf', ','.join(filter_complex)])

        # Output settings
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            str(output_path)
        ])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                return {
                    'success': True,
                    'output_path': str(output_path),
                    'modifications': applied
                }
            else:
                print(f"FFmpeg error: {result.stderr[:500]}")
                return {'success': False, 'error': result.stderr[:200]}

        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Processing timeout'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _get_auto_modifications(self):
        """Get automatic modifications based on level"""
        if self.level == self.LEVEL_MINIMAL:
            # Very subtle - just pitch and brightness
            mods = ['pitch_shift', 'brightness']
        elif self.level == self.LEVEL_MODERATE:
            # Balanced - audio and visual tweaks
            mods = ['pitch_shift', 'tempo_change', 'zoom', 'color_shift']
        else:  # AGGRESSIVE
            # Strong modifications
            mods = ['pitch_shift', 'tempo_change', 'eq_adjust',
                    'mirror', 'zoom', 'color_shift', 'border']

        return mods

    def _get_pitch_shift(self):
        """Get pitch shift value based on level"""
        if self.level == self.LEVEL_MINIMAL:
            return random.uniform(0.98, 1.02)  # +/- 2%
        elif self.level == self.LEVEL_MODERATE:
            return random.uniform(0.95, 1.05)  # +/- 5%
        else:
            return random.uniform(0.92, 1.08)  # +/- 8%

    def _get_tempo_change(self):
        """Get tempo change value based on level"""
        if self.level == self.LEVEL_MINIMAL:
            return random.uniform(0.98, 1.02)  # +/- 2%
        elif self.level == self.LEVEL_MODERATE:
            return random.uniform(0.95, 1.05)  # +/- 5%
        else:
            return random.uniform(0.92, 1.08)  # +/- 8%

    def apply_audio_only(self, input_path, output_path, modifications=None):
        """Apply modifications to audio only (faster for testing)"""
        if modifications is None:
            modifications = ['pitch_shift', 'tempo_change']

        audio_filters = []

        for mod in modifications:
            if mod == 'pitch_shift':
                shift = self._get_pitch_shift()
                audio_filters.append(f"asetrate=44100*{shift},aresample=44100")
            elif mod == 'tempo_change':
                tempo = self._get_tempo_change()
                audio_filters.append(f"atempo={tempo}")
            elif mod == 'eq_adjust':
                audio_filters.append("equalizer=f=1000:width_type=o:width=2:g=2")
            elif mod == 'add_reverb':
                audio_filters.append("aecho=0.8:0.88:6:0.4")

        if not audio_filters:
            return {'success': False, 'error': 'No audio modifications'}

        cmd = [
            'ffmpeg', '-y',
            '-i', str(input_path),
            '-af', ','.join(audio_filters),
            '-c:v', 'copy',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return {'success': result.returncode == 0}
        except:
            return {'success': False}


def get_safe_modifications(content_type='podcast'):
    """
    Get recommended modifications based on content type

    Args:
        content_type: 'podcast', 'music', 'movie', 'gameplay'

    Returns:
        list: Recommended modifications
    """
    if content_type == 'podcast':
        # Podcasts usually safe - minimal changes
        return ['pitch_shift', 'brightness']

    elif content_type == 'music':
        # Music needs more aggressive audio changes
        return ['pitch_shift', 'tempo_change', 'eq_adjust', 'zoom']

    elif content_type == 'movie':
        # Movies need visual changes
        return ['pitch_shift', 'mirror', 'zoom', 'color_shift', 'border']

    elif content_type == 'gameplay':
        # Gameplay usually safe
        return ['brightness', 'color_shift']

    else:
        # Default moderate
        return ['pitch_shift', 'tempo_change', 'zoom']


def quick_copyright_protect(input_path, output_path, level='moderate'):
    """
    Quick function to apply copyright protection

    Args:
        input_path: Input video path
        output_path: Output video path
        level: 'minimal', 'moderate', or 'aggressive'

    Returns:
        dict: Result with success status
    """
    avoider = CopyrightAvoider({'level': level})
    return avoider.process_video(input_path, output_path)

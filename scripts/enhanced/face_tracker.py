"""
Face Tracker Module for TikTok Clips Bot
Detects and tracks faces for intelligent video cropping
Uses MediaPipe for fast, accurate face detection
"""

import cv2
import numpy as np

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    print("[WARNING] MediaPipe not installed. Face tracking disabled.")
    print("Install with: pip install mediapipe")


class FaceTracker:
    """Tracks faces in video for smart cropping"""

    def __init__(self, config=None):
        """Initialize face tracker"""
        self.config = config or {}
        self.enabled = MEDIAPIPE_AVAILABLE

        if self.enabled:
            self.mp_face_detection = mp.solutions.face_detection
            self.min_detection_confidence = self.config.get('min_confidence', 0.5)
            self.model_selection = self.config.get('model', 1)

        self.smoothing_factor = self.config.get('smoothing', 0.3)
        self.last_crop_center = None

    def get_crop_for_clip(self, video_path, start_time, end_time, target_aspect=9/16):
        """
        Get optimal crop parameters for a clip segment

        Args:
            video_path: Path to video
            start_time: Clip start in seconds
            end_time: Clip end in seconds
            target_aspect: Target aspect ratio (width/height)

        Returns:
            dict: Crop parameters for FFmpeg
        """
        if not self.enabled:
            return {'has_faces': False, 'use_center_crop': True}

        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            return {'has_faces': False, 'use_center_crop': True}

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        start_frame = int(start_time * fps)
        end_frame = int(end_time * fps)
        sample_frames = min(10, end_frame - start_frame)
        sample_interval = max(1, (end_frame - start_frame) // sample_frames)

        face_centers = []

        with self.mp_face_detection.FaceDetection(
            model_selection=self.model_selection,
            min_detection_confidence=self.min_detection_confidence
        ) as face_detection:

            for frame_idx in range(start_frame, end_frame, sample_interval):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()

                if not ret:
                    continue

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_detection.process(rgb_frame)

                if results.detections:
                    for detection in results.detections:
                        bbox = detection.location_data.relative_bounding_box
                        center_x = bbox.xmin + bbox.width / 2
                        center_y = bbox.ymin + bbox.height / 2
                        face_centers.append((center_x, center_y))

        cap.release()

        # Calculate average face position
        if face_centers:
            avg_x = sum(c[0] for c in face_centers) / len(face_centers)
            avg_y = sum(c[1] for c in face_centers) / len(face_centers)
            face_center = (avg_x, avg_y)
            has_faces = True
        else:
            face_center = (0.5, 0.5)
            has_faces = False

        # Calculate crop for FFmpeg
        crop_params = self._calculate_ffmpeg_crop(width, height, target_aspect, face_center)

        return {
            'has_faces': has_faces,
            'face_center': face_center,
            'num_faces_detected': len(face_centers),
            'crop_x': crop_params['x'],
            'crop_y': crop_params['y'],
            'crop_width': crop_params['w'],
            'crop_height': crop_params['h'],
            'original_width': width,
            'original_height': height,
            'ffmpeg_crop': crop_params['ffmpeg_filter']
        }

    def _calculate_ffmpeg_crop(self, width, height, target_aspect, face_center):
        """Calculate FFmpeg crop filter parameters"""
        current_aspect = width / height

        if current_aspect > target_aspect:
            # Landscape video, crop width
            crop_h = height
            crop_w = int(height * target_aspect)

            # Position based on face center
            center_x = int(face_center[0] * width)
            x = center_x - crop_w // 2

            # Clamp to bounds
            x = max(0, min(x, width - crop_w))
            y = 0
        else:
            # Portrait or square
            crop_w = width
            crop_h = int(width / target_aspect)

            center_y = int(face_center[1] * height)
            y = center_y - crop_h // 2

            y = max(0, min(y, height - crop_h))
            x = 0

        # FFmpeg crop filter: crop=w:h:x:y
        ffmpeg_filter = f"crop={crop_w}:{crop_h}:{x}:{y}"

        return {
            'x': x,
            'y': y,
            'w': crop_w,
            'h': crop_h,
            'ffmpeg_filter': ffmpeg_filter
        }


def get_smart_crop_filter(video_path, start_time, end_time, output_width=1080, output_height=1920):
    """
    Convenience function to get FFmpeg filter for smart cropping

    Args:
        video_path: Path to source video
        start_time: Clip start time
        end_time: Clip end time
        output_width: Target width
        output_height: Target height

    Returns:
        str: FFmpeg video filter string
    """
    tracker = FaceTracker()
    target_aspect = output_width / output_height

    crop_info = tracker.get_crop_for_clip(video_path, start_time, end_time, target_aspect)

    if crop_info.get('has_faces'):
        # Use face-centered crop then scale
        return f"{crop_info['ffmpeg_crop']},scale={output_width}:{output_height}"
    else:
        # Standard center crop
        return f"scale={output_width}:{output_height}:force_original_aspect_ratio=increase,crop={output_width}:{output_height}"

"""
Smart Face Tracking & Centering Module for AI Viral Shorts Maker.
Uses MediaPipe and OpenCV to detect faces in widescreen 16:9 footage,
computes speaker focal centers, and crops dynamic 9:16 vertical shorts (1080x1920)
keeping the active speaker perfectly centered in the frame.
"""

import os
import sys
import json
import shutil
import urllib.request
import subprocess
import uuid
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks import python

# Ensure workspace root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.subtitle_generator import get_optimal_video_encoder

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_full_range/float16/1/blaze_face_full_range.tflite"
MODEL_PATH = "models/blaze_face_full_range.tflite"

DEFAULT_FFMPEG_TIMEOUT = int(os.environ.get("FFMPEG_TIMEOUT_SEC", "300"))
DEFAULT_FFMPEG_PRESET = os.environ.get("FFMPEG_PRESET", "fast")

# Global singleton face tracker instance & lock
_TRACKER_INSTANCE: Optional["SmartFaceTracker"] = None
_TRACKER_LOCK = threading.Lock()


def get_face_tracker() -> "SmartFaceTracker":
    """Thread-safe singleton getter for SmartFaceTracker."""
    global _TRACKER_INSTANCE
    with _TRACKER_LOCK:
        if _TRACKER_INSTANCE is None:
            _TRACKER_INSTANCE = SmartFaceTracker()
        return _TRACKER_INSTANCE


def ensure_face_model_exists() -> str:
    """Ensures MediaPipe full-range face detection model is downloaded."""
    os.makedirs(os.path.dirname(os.path.abspath(MODEL_PATH)), exist_ok=True)
    if not os.path.exists(MODEL_PATH) or os.path.getsize(MODEL_PATH) == 0:
        print(f"[*] Downloading MediaPipe face detector model to {MODEL_PATH}...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print(f"[SUCCESS] Model downloaded ({os.path.getsize(MODEL_PATH):,} bytes).")
    return MODEL_PATH


class SmartFaceTracker:
    def __init__(self, model_path: Optional[str] = None, min_confidence: float = 0.35):
        m_path = model_path or ensure_face_model_exists()
        base_options = python.BaseOptions(model_asset_path=m_path)
        options = vision.FaceDetectorOptions(base_options=base_options, min_detection_confidence=min_confidence)
        self.detector = vision.FaceDetector.create_from_options(options)

    def detect_faces_in_frame(self, frame_bgr: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detects all faces in a BGR video frame.
        Returns list of dicts with 'center_x', 'center_y', 'width', 'height', 'area' (normalized 0-1).
        """
        h, w, _ = frame_bgr.shape
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        res = self.detector.detect(mp_img)

        faces = []
        for det in res.detections:
            bb = det.bounding_box
            cx = (bb.origin_x + bb.width / 2.0) / float(w)
            cy = (bb.origin_y + bb.height / 2.0) / float(h)
            nw = bb.width / float(w)
            nh = bb.height / float(h)
            faces.append({
                "center_x": cx,
                "center_y": cy,
                "width": nw,
                "height": nh,
                "area": nw * nh
            })
        return faces

    def analyze_clip_focal_x(
        self,
        video_path: str,
        start_sec: float,
        end_sec: float,
        speaker_mode: str = "auto",
        probe_interval_sec: float = 0.5
    ) -> Dict[str, Any]:
        """
        Fast-probes the video slice to determine the optimal horizontal crop center (0.0 to 1.0).
        Extracts a lightweight temporary subclip first to avoid slow random seeks.
        """
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise RuntimeError("ffmpeg not found in PATH.")

        probe_id = uuid.uuid4().hex[:8]
        temp_subclip = os.path.join("temp", f"probe_{probe_id}.mp4")
        os.makedirs("temp", exist_ok=True)

        # Fast stream slice with FFmpeg
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", str(start_sec),
            "-to", str(end_sec),
            "-i", str(video_path),
            "-c", "copy",
            temp_subclip
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=60)
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"FFmpeg probe subclip timed out after 60s for {video_path}")

        detected_positions = []
        src_w = 1920
        src_h = 1080
        cap = cv2.VideoCapture(temp_subclip)
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
            src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
            step = max(1, int(round(fps * probe_interval_sec)))
            frame_idx = 0

            print(f"[*] Probing facial positions with MediaPipe across {end_sec - start_sec:.2f}s clip...")

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                if frame_idx % step == 0:
                    faces = self.detect_faces_in_frame(frame)
                    if faces:
                        if speaker_mode == "left":
                            target = min(faces, key=lambda f: f["center_x"])
                        elif speaker_mode == "right":
                            target = max(faces, key=lambda f: f["center_x"])
                        else:
                            target = max(faces, key=lambda f: f["area"])
                        detected_positions.append(target["center_x"])

                frame_idx += 1
        finally:
            cap.release()
            if os.path.exists(temp_subclip):
                try:
                    os.remove(temp_subclip)
                except Exception:
                    pass

        if detected_positions:
            # Use median to reject transient outlier movements or brief head turns
            optimal_focal_x = float(np.median(detected_positions))
            min_x = float(np.min(detected_positions))
            max_x = float(np.max(detected_positions))
            faces_found = len(detected_positions)
        else:
            # Default to center if no face detected (e.g. b-roll scenery)
            optimal_focal_x = 0.5
            min_x = 0.5
            max_x = 0.5
            faces_found = 0

        print(f"[+] Face Tracking Analysis:")
        print(f"    - Probes with Faces : {faces_found}")
        print(f"    - Median Focal X    : {optimal_focal_x:.3f} ({optimal_focal_x * 100:.1f}% from left edge)")
        print(f"    - Face Range X      : [{min_x:.3f}, {max_x:.3f}]")

        return {
            "optimal_focal_x": optimal_focal_x,
            "min_x": min_x,
            "max_x": max_x,
            "faces_found": faces_found,
            "src_w": src_w,
            "src_h": src_h
        }


def render_face_tracked_short(
    video_path: str,
    start_sec: float,
    end_sec: float,
    output_path: str,
    speaker_mode: str = "auto",
    target_width: int = 1080,
    target_height: int = 1920,
    captions_ass_path: Optional[str] = None,
    normalize_audio: bool = True,
    preset: Optional[str] = None,
    timeout: int = DEFAULT_FFMPEG_TIMEOUT
) -> Dict[str, Any]:
    """
    Renders a vertical 9:16 short with smart face centering and broadcast-quality audio.
    Optionally burns animated karaoke captions simultaneously in a single FFmpeg pass.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found in PATH.")

    tracker = get_face_tracker()
    analysis = tracker.analyze_clip_focal_x(
        video_path=video_path,
        start_sec=start_sec,
        end_sec=end_sec,
        speaker_mode=speaker_mode
    )

    focal_x = analysis["optimal_focal_x"]
    src_w = analysis["src_w"]
    src_h = analysis["src_h"]

    # Calculate 9:16 crop window dimensions
    # crop_w in 16:9 = src_h * (9 / 16)
    crop_w = int(round(src_h * (target_width / target_height)))
    focal_pixel_x = int(round(focal_x * src_w))

    if speaker_mode == "split_stack":
        # 2-speaker vertical split: Left speaker on top 50%, Right speaker on bottom 50%
        if captions_ass_path and os.path.exists(captions_ass_path):
            safe_ass = str(Path(captions_ass_path).resolve().as_posix()).replace(":", r"\:")
            filter_str = (
                f"[0:v]crop=w=iw/2:h=ih:x=0:y=0,scale={target_width}:{target_height // 2}:flags=lanczos[top];"
                f"[0:v]crop=w=iw/2:h=ih:x=iw/2:y=0,scale={target_width}:{target_height // 2}:flags=lanczos[bottom];"
                f"[top][bottom]vstack,ass='{safe_ass}'[outv]"
            )
            print(f"[*] Burning captions and split-stack crop in single FFmpeg pass...")
        else:
            filter_str = (
                f"[0:v]crop=w=iw/2:h=ih:x=0:y=0,scale={target_width}:{target_height // 2}:flags=lanczos[top];"
                f"[0:v]crop=w=iw/2:h=ih:x=iw/2:y=0,scale={target_width}:{target_height // 2}:flags=lanczos[bottom];"
                f"[top][bottom]vstack[outv]"
            )
        video_filter_args = ["-filter_complex", filter_str, "-map", "[outv]", "-map", "0:a?"]
    else:
        # Build crop filter with clamped X coordinates
        crop_filter = (
            f"crop=w=trunc(ih*9/16/2)*2:h=ih:"
            f"x='clip({focal_pixel_x}-ow/2,0,iw-ow)':y=0,"
            f"scale={target_width}:{target_height}:flags=lanczos"
        )
        if captions_ass_path and os.path.exists(captions_ass_path):
            safe_ass = str(Path(captions_ass_path).resolve().as_posix()).replace(":", r"\:")
            filter_str = f"{crop_filter},ass='{safe_ass}'"
            print(f"[*] Burning captions and face-centered crop in single FFmpeg pass...")
        else:
            filter_str = crop_filter
        video_filter_args = ["-vf", filter_str]

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    ffmpeg_preset = preset or DEFAULT_FFMPEG_PRESET

    audio_filters = []
    if normalize_audio:
        # Standard EBU R128 loudness normalization for modern social reels
        audio_filters.extend(["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"])

    optimal_enc = get_optimal_video_encoder()

    cmd = [
        ffmpeg_bin, "-y",
        "-ss", str(start_sec),
        "-to", str(end_sec),
        "-i", str(video_path),
        *video_filter_args,
        *optimal_enc["flags"],
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        *audio_filters,
        "-movflags", "+faststart",
        str(output_path)
    ]

    print(f"[*] Rendering Smart Face-Tracked 9:16 Video -> {output_path} (mode={speaker_mode}, enc={optimal_enc['name']}, loudnorm={normalize_audio})")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"FFmpeg render timed out after {timeout} seconds on {output_path}")

    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg face-tracked render failed: {res.stderr}")

    file_size = os.path.getsize(output_path)
    print(f"[SUCCESS] Face-Tracked 9:16 Short rendered: {output_path} ({file_size:,} bytes)")

    return {
        "output_path": output_path,
        "focal_x": round(focal_x, 3),
        "focal_pixel_x": focal_pixel_x,
        "speaker_mode": speaker_mode,
        "duration": round(end_sec - start_sec, 2),
        "resolution": f"{target_width}x{target_height}",
        "file_size_bytes": file_size
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Smart Face Tracking & Centering for Vertical Shorts")
    parser.add_argument("--video", type=str, required=True, help="Path to source 16:9 video MP4")
    parser.add_argument("--start", type=float, required=True, help="Start time in seconds")
    parser.add_argument("--end", type=float, required=True, help="End time in seconds")
    parser.add_argument("--speaker-mode", type=str, default="auto", choices=["auto", "largest", "left", "right"], help="Speaker selection mode")
    parser.add_argument("--captions", type=str, default=None, help="Optional ASS captions file to burn")
    parser.add_argument("--output", type=str, default=None, help="Output MP4 path")

    args = parser.parse_args()

    out_file = args.output
    if not out_file:
        base = Path(args.video).stem
        out_file = f"output/{base}_smart_centered_9x16.mp4"

    print("=" * 60)
    print(" BABY STEP 7: SMART FACE TRACKING & CENTERING")
    print("=" * 60)

    try:
        result = render_face_tracked_short(
            video_path=args.video,
            start_sec=args.start,
            end_sec=args.end,
            output_path=out_file,
            speaker_mode=args.speaker_mode,
            captions_ass_path=args.captions
        )

        print("\n" + "=" * 60)
        print(" BABY STEP 7 RENDER RESULTS")
        print("=" * 60)
        for k, v in result.items():
            print(f"  {k:20}: {v}")
        print("=" * 60)
        print("[SUCCESS] Baby Step 7 completed successfully.")
    except Exception as ex:
        print(f"\n[ERROR] Step 7 failed: {ex}", file=sys.stderr)
        sys.exit(1)

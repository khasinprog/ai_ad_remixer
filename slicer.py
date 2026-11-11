"""
Puzzle Slicer module.
Splits source video into puzzle clips according to scene timestamps using FFmpeg.
Guarantees a minimum clip duration of 3.0 seconds for Gemini Omni / AI Video Gen compatibility.
"""

import os
import re
import subprocess
from typing import Any, Dict, List

MIN_PUZZLE_DURATION = 3.0  # Gemini Omni requires min 3.0s video


def get_video_duration(video_path: str) -> float:
    """Get exact duration of video in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 60.0


def slice_video_to_puzzles(video_path: str, scenes: List[Dict[str, Any]], output_dir: str) -> List[Dict[str, Any]]:
    """Cuts source video into individual puzzle clips based on start_second and end_second.
    Enforces minimum 3.0s duration per clip so clips can be edited in Gemini Omni.
    
    Args:
        video_path: Source MP4 video file.
        scenes: List of scene dicts with 'detik_mulai', 'detik_selesai', 'scene'.
        output_dir: Directory where puzzle clips will be saved.
        
    Returns:
        List of puzzle metadata dicts with clip paths.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file tidak ditemukan: {video_path}")

    os.makedirs(output_dir, exist_ok=True)
    video_duration = get_video_duration(video_path)
    results = []

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    clean_prefix = re.sub(r"[^\w-]", "_", base_name)[:18].strip("_") or "video"

    for item in scenes:
        scene_idx = item.get("scene", 1)
        raw_start = float(item.get("detik_mulai", 0))
        raw_end = float(item.get("detik_selesai", raw_start + MIN_PUZZLE_DURATION))

        start_sec = max(0.0, raw_start)
        end_sec = max(start_sec + 0.5, raw_end)

        # Enforce minimum 3.0 seconds duration for Gemini Omni compatibility
        if (end_sec - start_sec) < MIN_PUZZLE_DURATION:
            end_sec = start_sec + MIN_PUZZLE_DURATION
            if end_sec > video_duration:
                end_sec = video_duration
                start_sec = max(0.0, end_sec - MIN_PUZZLE_DURATION)

        duration = max(0.5, end_sec - start_sec)
        if video_duration >= MIN_PUZZLE_DURATION and duration < MIN_PUZZLE_DURATION:
            duration = MIN_PUZZLE_DURATION

        clip_name = f"puzzle_{clean_prefix}_sc{scene_idx:02d}_{int(start_sec)}s-{int(end_sec)}s.mp4"
        clip_path = os.path.join(output_dir, clip_name)
        thumb_name = f"puzzle_{clean_prefix}_sc{scene_idx:02d}.jpg"
        thumb_path = os.path.join(output_dir, thumb_name)

        # Cut video clip using ultrafast FFmpeg
        cmd_cut = [
            "ffmpeg", "-y",
            "-ss", str(round(start_sec, 2)),
            "-to", str(round(end_sec, 2)),
            "-i", video_path,
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            clip_path
        ]
        subprocess.run(cmd_cut, capture_output=True, check=True)

        # Generate thumbnail frame
        cmd_thumb = [
            "ffmpeg", "-y",
            "-ss", str(round(start_sec + 0.1, 2)),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            thumb_path
        ]
        subprocess.run(cmd_thumb, capture_output=True)

        results.append({
            "source_video": base_name,
            "scene": scene_idx,
            "filename": clip_name,
            "clip_path": clip_path,
            "thumb_path": thumb_path if os.path.exists(thumb_path) else None,
            "start_second": round(start_sec, 2),
            "end_second": round(end_sec, 2),
            "duration": round(duration, 2),
            "peran": item.get("peran", ""),
            "aksi_visual": item.get("aksi_visual", ""),
            "skrip_suara": item.get("skrip_suara", ""),
            "ada_produk": item.get("ada_produk", False),
            "ada_wajah": item.get("ada_wajah", False),
            "kategori_visual": item.get("kategori_visual", "Universal Demo"),
            "omni_action": item.get("omni_action", "Bisa Dipakai Langsung"),
            "product_relation": item.get("product_relation", "same"),
            "rekomendasi_edit_omni": item.get("rekomendasi_edit_omni", ""),
        })

    return results


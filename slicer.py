"""
Puzzle Slicer module.
Splits source video into puzzle clips according to scene timestamps using FFmpeg.
"""

import os
import re
import subprocess
from typing import Any, Dict, List


def slice_video_to_puzzles(video_path: str, scenes: List[Dict[str, Any]], output_dir: str) -> List[Dict[str, Any]]:
    """Cuts source video into individual puzzle clips based on start_second and end_second.
    
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
    results = []

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    clean_prefix = re.sub(r"[^\w-]", "_", base_name)[:18].strip("_") or "video"

    for item in scenes:
        scene_idx = item.get("scene", 1)
        start_sec = float(item.get("detik_mulai", 0))
        end_sec = float(item.get("detik_selesai", start_sec + 3))
        duration = max(0.5, end_sec - start_sec)

        clip_name = f"puzzle_{clean_prefix}_sc{scene_idx:02d}_{int(start_sec)}s-{int(end_sec)}s.mp4"
        clip_path = os.path.join(output_dir, clip_name)
        thumb_name = f"puzzle_{clean_prefix}_sc{scene_idx:02d}.jpg"
        thumb_path = os.path.join(output_dir, thumb_name)

        # Cut video clip using ultrafast FFmpeg
        cmd_cut = [
            "ffmpeg", "-y",
            "-ss", str(start_sec),
            "-to", str(end_sec),
            "-i", video_path,
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            clip_path
        ]
        subprocess.run(cmd_cut, capture_output=True, check=True)

        # Generate thumbnail frame
        cmd_thumb = [
            "ffmpeg", "-y",
            "-ss", str(start_sec + 0.1),
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
            "start_second": start_sec,
            "end_second": end_sec,
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


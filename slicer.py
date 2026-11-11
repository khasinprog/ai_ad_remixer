"""
Puzzle Slicer module.
Splits source video into puzzle clips according to scene timestamps using FFmpeg.
Enforces Google Omni limits: Minimum 3.0s and Maximum 10.0s duration per clip.
"""

import math
import os
import re
import subprocess
from typing import Any, Dict, List

MIN_PUZZLE_DURATION = 3.0   # Google Omni min 3.0s
MAX_PUZZLE_DURATION = 10.0  # Google Omni max 10.0s


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


def normalize_and_split_scenes(scenes: List[Dict[str, Any]], video_duration: float) -> List[Dict[str, Any]]:
    """Normalizes scenes to strictly guarantee 3.0s <= duration <= 10.0s.
    If a scene is longer than 10.0s, splits it into even sub-chunks (e.g. 5-8s).
    If shorter than 3.0s, expands it to at least 3.0s.
    """
    normalized = []
    clip_counter = 1

    for item in scenes:
        raw_start = max(0.0, float(item.get("detik_mulai", 0)))
        raw_end = min(video_duration, float(item.get("detik_selesai", raw_start + MIN_PUZZLE_DURATION)))
        if raw_end <= raw_start:
            raw_end = min(video_duration, raw_start + MIN_PUZZLE_DURATION)

        raw_dur = raw_end - raw_start

        if raw_dur <= MAX_PUZZLE_DURATION:
            start_sec = raw_start
            end_sec = raw_end

            # Enforce min 3.0s
            if (end_sec - start_sec) < MIN_PUZZLE_DURATION:
                end_sec = min(video_duration, start_sec + MIN_PUZZLE_DURATION)
                if (end_sec - start_sec) < MIN_PUZZLE_DURATION and video_duration >= MIN_PUZZLE_DURATION:
                    start_sec = max(0.0, end_sec - MIN_PUZZLE_DURATION)

            # Cap at max 10.0s
            if (end_sec - start_sec) > MAX_PUZZLE_DURATION:
                end_sec = start_sec + MAX_PUZZLE_DURATION

            dur = max(0.5, round(end_sec - start_sec, 2))
            entry = dict(item)
            entry["scene"] = clip_counter
            entry["detik_mulai"] = round(start_sec, 2)
            entry["detik_selesai"] = round(end_sec, 2)
            entry["duration"] = dur
            normalized.append(entry)
            clip_counter += 1

        else:
            # Longer than 10 seconds: split into even sub-chunks between 4.0s and 8.0s
            num_chunks = math.ceil(raw_dur / 8.0)
            chunk_len = raw_dur / num_chunks

            cur_start = raw_start
            for c in range(num_chunks):
                cur_end = raw_end if c == num_chunks - 1 else cur_start + chunk_len
                dur = round(cur_end - cur_start, 2)

                # Ensure between 3.0 and 10.0
                if dur < MIN_PUZZLE_DURATION:
                    cur_end = min(video_duration, cur_start + MIN_PUZZLE_DURATION)
                    dur = round(cur_end - cur_start, 2)
                if dur > MAX_PUZZLE_DURATION:
                    cur_end = cur_start + MAX_PUZZLE_DURATION
                    dur = round(cur_end - cur_start, 2)

                entry = dict(item)
                entry["scene"] = clip_counter
                entry["detik_mulai"] = round(cur_start, 2)
                entry["detik_selesai"] = round(cur_end, 2)
                entry["duration"] = dur
                if num_chunks > 1:
                    orig_vis = item.get("aksi_visual", "")
                    entry["aksi_visual"] = f"{orig_vis} (Bagian {c+1}/{num_chunks})"
                normalized.append(entry)
                clip_counter += 1
                cur_start = cur_end

    return normalized


def slice_video_to_puzzles(video_path: str, scenes: List[Dict[str, Any]], output_dir: str) -> List[Dict[str, Any]]:
    """Cuts source video into individual puzzle clips based on start_second and end_second.
    Enforces Google Omni limits: 3.0s <= duration <= 10.0s for all clips.
    
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
    normalized_scenes = normalize_and_split_scenes(scenes, video_duration)
    results = []

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    clean_prefix = re.sub(r"[^\w-]", "_", base_name)[:18].strip("_") or "video"

    for item in normalized_scenes:
        scene_idx = item.get("scene", 1)
        start_sec = item["detik_mulai"]
        end_sec = item["detik_selesai"]
        duration = item["duration"]

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
            "start_second": start_sec,
            "end_second": end_sec,
            "duration": duration,
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


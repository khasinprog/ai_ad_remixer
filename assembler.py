"""
Ad Assembler module.
Generates voiceover per scene, adjusts video speed (tempo sync), and concatenates final ad video.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List

def get_edge_tts_cmd() -> List[str]:
    """Returns the portable command to invoke edge-tts across Windows, Mac, and Linux."""
    # Priority 1: sys.executable -m edge_tts (always matches current python environment)
    return [sys.executable, "-m", "edge_tts"]


def get_media_duration(file_path: str) -> float:
    """Returns duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    res = subprocess.check_output(cmd).decode().strip()
    return float(res)


def generate_tts_audio(text: str, voice: str, output_path: str) -> float:
    """Generates speech audio for text and returns duration in seconds."""
    cmd = get_edge_tts_cmd() + ["--voice", voice, "--text", text, "--write-media", output_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return get_media_duration(output_path)


def assemble_ad(
    scenes: List[Dict[str, Any]],
    voice: str = "id-ID-ArdiNeural",
    output_path: str = "downloads/final_ad.mp4",
    progress_callback=None
) -> Dict[str, Any]:
    """Assembles new ad from script and puzzle clips with speed-ramping tempo sync.
    
    Args:
        scenes: List of scene objects with:
            - 'script': text voiceover for this scene
            - 'clip_path': path to the puzzle video clip
        voice: edge-tts voice name (e.g. 'id-ID-ArdiNeural' or 'id-ID-GadisNeural')
        output_path: Target MP4 path
        progress_callback: Optional progress reporter
        
    Returns:
        Dict with status, output file, and scene statistics.
    """
    if not scenes:
        raise ValueError("Daftar scene kosong. Masukkan minimal 1 scene.")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix="ad_assemble_")
    synced_clips = []

    try:
        total_scenes = len(scenes)
        for idx, sc in enumerate(scenes, 1):
            script_text = sc.get("script", "").strip()
            clip_path = sc.get("clip_path")

            if not clip_path or not os.path.exists(clip_path):
                raise FileNotFoundError(f"Puzzle clip scene {idx} tidak ditemukan: {clip_path}")

            if progress_callback:
                progress_callback(f"Memproses Scene {idx}/{total_scenes}: Generate voice & tempo sync...")

            # 1. Generate Voiceover TTS
            audio_path = os.path.join(temp_dir, f"vo_scene_{idx:02d}.mp3")
            if script_text:
                audio_dur = generate_tts_audio(script_text, voice, audio_path)
            else:
                # If no script, keep original video duration
                audio_dur = get_media_duration(clip_path)
                audio_path = None

            video_dur = get_media_duration(clip_path)

            # 2. Compute Speed Factor
            # pts_factor = audio_dur / video_dur
            # When video is sped up, pts_factor < 1.0 (e.g. 0.8)
            # When slowed down, pts_factor > 1.0 (e.g. 1.25)
            pts_factor = (audio_dur / video_dur) if video_dur > 0 else 1.0
            # Guard against extreme speed distortion (cap between 0.4x and 2.5x)
            pts_factor = max(0.4, min(2.5, pts_factor))

            synced_clip_path = os.path.join(temp_dir, f"synced_scene_{idx:02d}.mp4")

            if audio_path and os.path.exists(audio_path):
                cmd_sync = [
                    "ffmpeg", "-y",
                    "-i", clip_path,
                    "-i", audio_path,
                    "-filter_complex", f"[0:v]setpts={pts_factor:.4f}*PTS,scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v]",
                    "-map", "[v]", "-map", "1:a",
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                    "-shortest",
                    synced_clip_path
                ]
            else:
                cmd_sync = [
                    "ffmpeg", "-y",
                    "-i", clip_path,
                    "-filter_complex", "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v]",
                    "-map", "[v]",
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-an",
                    synced_clip_path
                ]

            subprocess.run(cmd_sync, capture_output=True, check=True)
            synced_clips.append(synced_clip_path)

        # 3. Concatenate all synced clips into final MP4
        if progress_callback:
            progress_callback("Menggabungkan seluruh scene menjadi satu video final...")

        concat_list_path = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_list_path, "w") as f:
            for p in synced_clips:
                f.write(f"file '{p}'\n")

        cmd_concat = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list_path,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart",
            output_path
        ]
        subprocess.run(cmd_concat, capture_output=True, check=True)

        final_duration = get_media_duration(output_path)
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)

        return {
            "success": True,
            "output_path": output_path,
            "filename": os.path.basename(output_path),
            "total_scenes": total_scenes,
            "duration": round(final_duration, 2),
            "size_mb": round(file_size_mb, 2)
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

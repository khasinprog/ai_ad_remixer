"""
Gemini Video Analyzer module.
Deconstructs competitor ad videos into voice scripts, visual scene descriptions, and Omni edit prompts.
"""

import json
import os
import re
import time
from typing import Any, Dict
from google import genai

# Load API Key from environment or .env file
def get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                for line in f:
                    if line.startswith("GEMINI_API_KEY="):
                        key = line.strip().split("=", 1)[1].strip()
                        break
    if not key:
        raise ValueError("GEMINI_API_KEY belum diset. Silakan masukkan di file .env")
    return key


def analyze_video(video_path: str, progress_callback=None) -> Dict[str, Any]:
    """Uploads video to Gemini and extracts structured scene & audio breakdown.
    
    Args:
        video_path: Path to local video MP4.
        progress_callback: Optional callback for status strings.
        
    Returns:
        Dict of parsed video analysis.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file tidak ditemukan: {video_path}")

    api_key = get_api_key()
    client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})

    if progress_callback:
        progress_callback("Mengunggah video ke Gemini File API...")

    video_file = client.files.upload(file=video_path)

    if progress_callback:
        progress_callback("Menunggu Gemini memproses frame & audio video...")

    # Wait for file to be active
    while video_file.state.name == "PROCESSING":
        time.sleep(4)
        video_file = client.files.get(name=video_file.name)

    if video_file.state.name != "ACTIVE":
        raise RuntimeError(f"Gagal memproses video di Gemini: status {video_file.state.name}")

    if progress_callback:
        progress_callback("Menganalisis skrip suara, breakdown visual, dan hook iklan...")

    prompt = """
Kamu adalah Direktur Kreatif Video Iklan TikTok & Meta Ads (Direct Response Marketing Specialist).
Analisis video kompetitor ini secara presisi dan mendalam.

Keluarkan hasil analisis HANYA dalam format JSON valid di dalam blok ```json ... ``` dengan struktur persis seperti ini:
{
  "hook": {
    "durasi_detik": 3,
    "aksi_visual": "Deskripsi aksi visual di 3 detik pertama",
    "skrip_suara": "Kalimat pembuka hook yang diucapkan",
    "teknik_psikologi": "Alasan kenapa hook ini membuat orang berhenti scroll"
  },
  "transkrip_lengkap": "Seluruh transkrip kata demi kata dari awal sampai akhir video",
  "breakdown_scene": [
    {
      "scene": 1,
      "detik_mulai": 0,
      "detik_selesai": 5,
      "peran": "Hook / Problem / Solusi / Demo Produk / Social Proof / Call To Action",
      "aksi_visual": "Aksi apa yang terlihat di kamera",
      "skrip_suara": "Kalimat yang diucapkan di detik ini"
    }
  ],
  "formula_winning_iklan": [
    "Poin keunggulan formula 1",
    "Poin keunggulan formula 2"
  ]
}
"""

    # Try primary models with graceful fallback on high demand
    models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]
    response = None
    last_err = None

    for m in models_to_try:
        try:
            if progress_callback:
                progress_callback(f"Menganalisis skrip suara, visual, dan hook iklan dengan model {m}...")
            response = client.models.generate_content(
                model=m,
                contents=[video_file, prompt]
            )
            if response and response.text:
                break
        except Exception as e:
            last_err = e
            time.sleep(2)
            continue

    if not response or not response.text:
        raise RuntimeError(f"Semua model Gemini sedang sibuk atau error: {last_err}")

    raw_text = response.text.strip()

    # Extract JSON from markdown fences if present
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
    clean_json_str = json_match.group(1) if json_match else raw_text

    try:
        data = json.loads(clean_json_str)
    except Exception as e:
        # Fallback if raw text has leading/trailing characters
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1:
            data = json.loads(raw_text[start : end + 1])
        else:
            raise ValueError(f"Gagal mem-parsing JSON dari Gemini: {e}")

    return data


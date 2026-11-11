"""
AI Scene Matcher & Omni Prompt Generator module.
Matches user-crafted improvement scenes (Persona, Angle, Offer) with available puzzle clips,
and generates camera angle / visual improvement prompts for Omni / AI video generation.
"""

import json
import os
import re
import time
from typing import Any, Dict, List
from google import genai
from pydantic import BaseModel, Field

# Load API Key
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
        raise ValueError("GEMINI_API_KEY belum diset. Silakan periksa file .env")
    return key


class MatchedScene(BaseModel):
    scene_name: str = Field(description="Nama scene (Hook, Problem, Solusi, Demo, CTA, dll.)")
    voice_script: str = Field(description="Skrip suara improvement pengguna")
    visual_intent: str = Field(description="Arah visual yang diinginkan pengguna")
    selected_puzzle_filename: str = Field(description="Nama file klip puzzle terpilih dari Library yang paling cocok")
    match_reason: str = Field(description="Alasan singkat kecocokan visual puzzle dengan skrip pengguna")
    omni_camera_prompt: str = Field(description="Prompt instruksi edit / re-generate kamera Omni agar lebih eye-catching (ganti angle, cinematic camera movement, lighting, dll.)")


class MatchPlan(BaseModel):
    matched_scenes: List[MatchedScene]


MATCHER_SYSTEM_PROMPT = """
Anda adalah AI Video Editor & Creative Director spesialis Iklan TikTok / Meta Ads (Direct Response Video).
Tugas Anda:
1. Membaca rancangan scene improvement yang dibuat pengguna (Persona, Angle, Offer, dan Skrip Suara).
2. Memindai daftar kepingan klip puzzle video mentah (Puzzle Library) yang tersedia.
3. Mencocokkan SATU kepingan puzzle yang paling relevan untuk setiap scene pengguna.
4. Membuatkan PROMPT EDIT KAMERA OMNI (AI Video Gen) untuk setiap scene, difokuskan pada:
   - Mengubah angle kamera agar lebih eye-catching & dramatis (misal: Dutch angle, low-angle hero shot, macro close-up, fast zoom-in).
   - Memperkuat elemen visual utama produk/masalah.
   - Instruksi pencahayaan sinematik dan gerakan kamera yang dinamis.
"""


def match_scenes_with_ai(
    user_scenes: List[Dict[str, str]],
    library_puzzles: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Intelligently matches user scenes with puzzle library using Gemini.
    
    Args:
        user_scenes: List of dicts with 'scene_name', 'visual_intent', 'voice_script'.
        library_puzzles: List of puzzle dicts from PUZZLES_META_FILE.
        
    Returns:
        List of matched scene dicts with puzzle references and Omni prompts.
    """
    if not user_scenes:
        return []

    if not library_puzzles:
        raise ValueError("Perpustakaan puzzle masih kosong. Silakan download & potong video TikTok bahan terlebih dahulu.")

    api_key = get_api_key()
    client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})

    # Prepare compact library representation for prompt
    compact_lib = []
    for p in library_puzzles:
        compact_lib.append({
            "filename": p.get("filename"),
            "source": p.get("source_video", "TikTok Video"),
            "peran": p.get("peran", "Ad Clip"),
            "kategori_visual": p.get("kategori_visual", "Universal Demo"),
            "ada_produk": p.get("ada_produk", False),
            "ada_wajah": p.get("ada_wajah", False),
            "omni_action": p.get("omni_action", "Bisa Dipakai Langsung"),
            "aksi_visual": p.get("aksi_visual", ""),
            "skrip_asli": p.get("skrip_suara", ""),
            "durasi": p.get("duration", 3.0),
        })

    prompt_content = f"""
Koleksi Kepingan Puzzle yang Tersedia (Puzzle Library):
{json.dumps(compact_lib, indent=2, ensure_ascii=False)}

Daftar Scene & Skrip Improvement yang Diinginkan Pengguna:
{json.dumps(user_scenes, indent=2, ensure_ascii=False)}

Instruksi:
- Untuk setiap scene dari pengguna, pilih 'selected_puzzle_filename' yang HANYA berasal dari daftar Puzzle Library di atas.
- Tuliskan 'match_reason' yang menjelaskan mengapa aksi visual klip tersebut cocok dengan skrip pengguna.
- Tuliskan 'omni_camera_prompt' dalam bahasa Inggris yang kaya visual dan spesifik (camera angle, movement, focal length, aesthetic, dynamic visual hooks).
"""

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    last_err = None

    for m in models_to_try:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=m,
                    contents=[MATCHER_SYSTEM_PROMPT, prompt_content],
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=MatchPlan,
                    ),
                )
                data = json.loads(response.text)
                plan = MatchPlan(**data)
                return [s.model_dump() for s in plan.matched_scenes]
            except Exception as e:
                last_err = e
                time.sleep(2 * (attempt + 1))
                continue

    raise RuntimeError(f"Gagal mencocokkan scene dengan Gemini: {last_err}")


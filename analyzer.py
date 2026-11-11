"""
Gemini Video Analyzer module.
Deconstructs competitor ad videos into voice scripts, visual scene descriptions,
and intelligent Omni edit prompts (supporting Same Product vs Different Product replacement).
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
        raise ValueError("GEMINI_API_KEY belum diset. Silakan periksa file .env")
    return key


def analyze_video(
    video_path: str,
    product_relation: str = "different",
    my_product_name: str = "Dohero Black",
    my_packaging_desc: str = "Botol spray hitam matte 100ml dengan tutup kuning",
    my_talent_desc: str = "Pria Indonesia usia 25 tahun, kasual ramah dan antusias",
    progress_callback=None
) -> Dict[str, Any]:
    """Uploads video to Gemini and extracts structured scene & audio breakdown with product swap awareness.
    
    Args:
        video_path: Path to local video MP4.
        product_relation: 'same' (produk kita) or 'different' (produk kompetitor lain).
        my_product_name: Brand/product name of user's product.
        my_packaging_desc: Physical appearance of user's bottle/packaging.
        my_talent_desc: Description of replacement talent/face.
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

    is_diff = (product_relation.lower() == "different")
    relation_desc = "PRODUK BERBEDA (Merek Kompetitor Lain - Perlu Swap Kemasan/Wajah)" if is_diff else "PRODUK SAMA (Brand/Kemasan Kita Sendiri)"

    prompt = f"""
Kamu adalah Direktur Kreatif Video Iklan TikTok & Meta Ads (Direct Response Marketing Specialist).
Analisis video ini secara presisi dan mendalam untuk keperluan reverse-engineering dan remixing iklan.

INFORMASI BRAND PENGGUNA:
- Status Video Sumber: {relation_desc}
- Nama Produk Pengguna: {my_product_name or 'Produk Penghitam Motor'}
- Karakter Fisik Kemasan Baru: {my_packaging_desc or 'Botol spray hitam matte'}
- Karakter Model/Talent Pengganti: {my_talent_desc or 'Pria Indonesia usia muda berpenampilan kasual ramah'}

TUGAS UTAMA DETEKSI PER SCENE:
Untuk setiap scene dalam `breakdown_scene`, lakukan klasifikasi visual dengan sangat teliti:
1. `ada_produk`: (boolean: true/false) Apakah di scene ini terlihat botol/kaleng/kemasan produk (baik merek kompetitor seperti V-MAX, Spray, dsb, maupun produk apapun)? Jika produk fisik terlihat/dipegang/disemprotkan, WAJIB set true!
2. `ada_wajah`: (boolean: true/false) Apakah di scene ini terlihat wajah orang / kreator / talent? Jika ada orang berbicara atau wajahnya tampak, WAJIB set true!
3. `kategori_visual`: Pilih salah satu:
   - "Universal Demo": Adegan demo netral TANPA wajah orang dan TANPA botol/kemasan bermerek (contoh: close-up spakbor motor kusam, tangan mengusap kain microfiber pada plafon, foam bereaksi melarutkan kotoran, air deras mengguyur permukaan). Klip ini 100% AMAN dipakai langsung untuk produk apapun tanpa perlu diedit!
   - "Product Shot": Adegan yang menonjolkan botol/kemasan produk.
   - "Talent Shot": Adegan orang/kreator berbicara atau berekspresi ke kamera.
   - "Hybrid": Adegan orang/talent memegang botol produk sekaligus.
4. `omni_action`:
   - Jika "Universal Demo": "Aman Dipakai Langsung (Universal B-Roll)"
   - Jika `ada_produk` bernilai true dan Status Video adalah 'PRODUK BERBEDA': "Ganti Kemasan (Product Swap Omni)"
   - Jika `ada_wajah` bernilai true dan Status Video adalah 'PRODUK BERBEDA': "Ganti Wajah/Talent (Face Swap Omni)"
   - Jika keduanya bernilai true dan 'PRODUK BERBEDA': "Ganti Kemasan & Wajah (Omni Hybrid Swap)"
   - Jika Status Video adalah 'PRODUK SAMA': "Aman Dipakai Langsung"
5. `rekomendasi_edit_omni`:
   - Jika Universal Demo / Aman Dipakai Langsung: Tuliskan: "Aman dipakai langsung tanpa edit. (Opsional poles saturasi/transisi jika diperlukan)".
   - Jika ada kemasan & produk berbeda: berikan instruksi spesifik Gemini Omni Video Inpainting untuk mengganti kemasan kompetitor dengan '{my_product_name}' berbentuk '{my_packaging_desc}', pertahankan posisi genggaman tangan dan bayangan.
   - Jika ada wajah & produk berbeda: berikan instruksi spesifik Gemini Omni Face Swap untuk mengganti wajah talent dengan '{my_talent_desc}', sesuaikan ekspresi dan artikulasi mulut.

Keluarkan hasil analisis HANYA dalam format JSON valid di dalam blok ```json ... ``` dengan struktur persis seperti ini:
{{
  "product_relation": "{'different' if is_diff else 'same'}",
  "hook": {{
    "durasi_detik": 3,
    "aksi_visual": "Deskripsi aksi visual di 3 detik pertama",
    "skrip_suara": "Kalimat pembuka hook yang diucapkan",
    "teknik_psikologi": "Alasan kenapa hook ini membuat orang berhenti scroll"
  }},
  "transkrip_lengkap": "Seluruh transkrip kata demi kata dari awal sampai akhir video",
  "breakdown_scene": [
    {{
      "scene": 1,
      "detik_mulai": 0,
      "detik_selesai": 5,
      "peran": "Hook / Problem / Solusi / Demo Produk / Social Proof / Call To Action",
      "aksi_visual": "Aksi apa yang terlihat di kamera",
      "skrip_suara": "Kalimat yang diucapkan di detik ini",
      "ada_produk": true,
      "ada_wajah": true,
      "kategori_visual": "Universal Demo / Product Shot / Talent Shot / Hybrid",
      "omni_action": "Bisa Dipakai Langsung / Ganti Kemasan / Ganti Wajah",
      "rekomendasi_edit_omni": "Prompt detail untuk Gemini Omni..."
    }}
  ],
  "formula_winning_iklan": [
    "Poin keunggulan formula 1",
    "Poin keunggulan formula 2"
  ]
}}
"""

    models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]
    response = None
    last_err = None

    for m in models_to_try:
        try:
            if progress_callback:
                progress_callback(f"Menganalisis skrip suara, deteksi produk & wajah dengan {m}...")
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
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1:
            data = json.loads(raw_text[start : end + 1])
        else:
            raise ValueError(f"Gagal mem-parsing JSON dari Gemini: {e}")

    # Inject metadata into result
    data["product_relation"] = "different" if is_diff else "same"
    data["my_product_name"] = my_product_name
    data["my_packaging_desc"] = my_packaging_desc
    data["my_talent_desc"] = my_talent_desc

    return data

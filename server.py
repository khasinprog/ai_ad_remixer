#!/usr/bin/env python3
"""
AI Video Ad Studio & Remixer Web Server.
Pure Python backend orchestrating TikTok downloader, Gemini multimodal analysis,
FFmpeg puzzle slicer, edge-tts voiceover, and dynamic tempo sync.
"""

import json
import os
import re
import sys
import time
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
PUZZLES_DIR = os.path.join(BASE_DIR, "puzzles")
STATIC_DIR = os.path.join(BASE_DIR, "static")
ANALYSIS_FILE = os.path.join(BASE_DIR, "analysis_result.json")
PUZZLES_META_FILE = os.path.join(PUZZLES_DIR, "puzzles_meta.json")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(PUZZLES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Import local engines
from downloader import fetch_tiktok_data, download_stream, sanitize_filename
from analyzer import analyze_video
from slicer import slice_video_to_puzzles
from assembler import assemble_ad
from matcher import match_scenes_with_ai

OMNI_DIR = os.path.join(DOWNLOADS_DIR, "omni")
os.makedirs(OMNI_DIR, exist_ok=True)

PORT = 5055


class AdStudioHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Override to keep logs neat
        sys.stderr.write(f"[{self.log_date_time_string()}] {self.command} {self.path} - {format % args}\n")

    def send_json(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. Serve Home page
        if path == "/" or path == "/index.html":
            index_path = os.path.join(STATIC_DIR, "index.html")
            if os.path.exists(index_path):
                with open(index_path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404, "index.html not found")
            return

        # 2. Get current analysis if exists
        elif path == "/api/get-current-analysis":
            if os.path.exists(ANALYSIS_FILE):
                try:
                    with open(ANALYSIS_FILE, "r") as f:
                        raw = f.read()
                    clean = re.sub(r"^```(?:json)?\s*", "", raw.strip())
                    clean = re.sub(r"\s*```$", "", clean)
                    data = json.loads(clean)
                    self.send_json(200, {"success": True, "data": data})
                    return
                except Exception as e:
                    self.send_json(200, {"success": False, "error": str(e)})
                    return
            self.send_json(200, {"success": False, "message": "No analysis yet"})
            return

        # 3. List available puzzle clips
        elif path == "/api/puzzles":
            puzzles = []
            if os.path.exists(PUZZLES_META_FILE):
                try:
                    with open(PUZZLES_META_FILE, "r") as f:
                        puzzles = json.load(f)
                except Exception:
                    puzzles = []

            # Ensure paths resolve properly on any OS (Windows/Mac/Linux)
            for p in puzzles:
                filename = p.get("filename")
                if filename:
                    p["clip_path"] = os.path.join(PUZZLES_DIR, filename)
                    thumb_path = p.get("thumb_path")
                    if not thumb_path or not os.path.exists(thumb_path):
                        base_stem = os.path.splitext(filename)[0]
                        candidate = os.path.join(PUZZLES_DIR, f"{base_stem}.jpg")
                        if os.path.exists(candidate):
                            p["thumb_path"] = candidate

                p["clip_url"] = f"/api/media?path={urllib.parse.quote(p.get('clip_path', ''))}"
                if p.get("thumb_path") and os.path.exists(p.get("thumb_path")):
                    p["thumb_url"] = f"/api/media?path={urllib.parse.quote(p.get('thumb_path', ''))}"
                else:
                    p["thumb_url"] = ""

            self.send_json(200, {"success": True, "puzzles": puzzles})
            return

        # 4. Stream local media files (MP4, JPG, MP3) with Range support
        elif path == "/api/media":
            params = urllib.parse.parse_qs(parsed.query)
            file_path = params.get("path", [None])[0]
            if not file_path or not os.path.exists(file_path):
                self.send_error(404, "File not found")
                return

            ext = os.path.splitext(file_path)[1].lower()
            content_type = "application/octet-stream"
            if ext == ".mp4":
                content_type = "video/mp4"
            elif ext in (".jpg", ".jpeg"):
                content_type = "image/jpeg"
            elif ext == ".png":
                content_type = "image/png"
            elif ext == ".mp3":
                content_type = "audio/mpeg"

            file_size = os.path.getsize(file_path)
            range_header = self.headers.get("Range")

            if range_header:
                # Handle Byte-Range requests for smooth video scrubbing
                try:
                    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
                    start = int(range_match.group(1))
                    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                    length = end - start + 1

                    self.send_response(206)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()

                    with open(file_path, "rb") as f:
                        f.seek(start)
                        self.wfile.write(f.read(length))
                    return
                except Exception:
                    pass

            # Full file response
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()

            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            return

        # 5. List local videos in downloads folder
        elif path == "/api/local-videos":
            files = []
            if os.path.exists(DOWNLOADS_DIR):
                for f in os.listdir(DOWNLOADS_DIR):
                    if f.lower().endswith(".mp4") and not f.startswith("iklan_baru_"):
                        full_p = os.path.join(DOWNLOADS_DIR, f)
                        files.append({
                            "name": f,
                            "path": full_p,
                            "size_mb": round(os.path.getsize(full_p) / (1024 * 1024), 2),
                            "modified": os.path.getmtime(full_p)
                        })
            files.sort(key=lambda x: x["modified"], reverse=True)
            self.send_json(200, {"success": True, "videos": files})
            return

        else:
            self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))

        # 0. Upload local video file (Binary stream)
        if path == "/api/upload":
            raw_filename = self.headers.get("X-Filename", "uploaded_video.mp4")
            filename = urllib.parse.unquote(raw_filename)
            filename = re.sub(r"[^\w\.-]", "_", filename)
            if not filename.lower().endswith(".mp4"):
                filename += ".mp4"
            target_path = os.path.join(DOWNLOADS_DIR, filename)

            try:
                with open(target_path, "wb") as f:
                    remaining = length
                    chunk_size = 64 * 1024
                    while remaining > 0:
                        read_bytes = min(chunk_size, remaining)
                        chunk = self.rfile.read(read_bytes)
                        if not chunk:
                            break
                        f.write(chunk)
                        remaining -= len(chunk)

                self.send_json(200, {"success": True, "filename": filename, "video_path": target_path})
            except Exception as e:
                self.send_json(500, {"success": False, "error": str(e)})
            return

        # 0.1 Upload Omni Video Clip (Binary stream)
        if path == "/api/upload-omni":
            try:
                os.makedirs(OMNI_DIR, exist_ok=True)
                raw_filename = self.headers.get("X-Filename", "omni_clip.mp4")
                scene_idx = self.headers.get("X-Scene-Idx", "01")
                filename = urllib.parse.unquote(raw_filename)
                filename = re.sub(r"[^\w\.-]", "_", filename)
                if not filename.lower().endswith(".mp4"):
                    filename += ".mp4"
                target_filename = f"omni_sc{scene_idx}_{int(time.time())}_{filename}"
                target_path = os.path.join(OMNI_DIR, target_filename)

                with open(target_path, "wb") as f:
                    remaining = length
                    chunk_size = 64 * 1024
                    while remaining > 0:
                        read_bytes = min(chunk_size, remaining)
                        chunk = self.rfile.read(read_bytes)
                        if not chunk:
                            break
                        f.write(chunk)
                        remaining -= len(chunk)

                media_url = f"/api/media?path={urllib.parse.quote(target_path)}"
                self.send_json(200, {
                    "success": True,
                    "filename": target_filename,
                    "clip_path": target_path,
                    "clip_url": media_url
                })
            except Exception as e:
                self.send_json(500, {"success": False, "error": str(e)})
            return

        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        # 1. Reverse-engineer video with Gemini
        if path == "/api/analyze":
            url = payload.get("url", "").strip()
            video_path = payload.get("video_path", "").strip()
            product_relation = payload.get("product_relation", "different").strip()
            my_product_name = payload.get("my_product_name", "Dohero Black").strip()
            my_packaging_desc = payload.get("my_packaging_desc", "Botol spray hitam matte 100ml").strip()
            my_talent_desc = payload.get("my_talent_desc", "Pria Indonesia usia 25 tahun kasual ramah").strip()

            if not url and not video_path:
                self.send_json(400, {"success": False, "error": "URL TikTok atau file video tidak boleh kosong"})
                return

            try:
                if video_path and os.path.exists(video_path):
                    target_video_path = video_path
                else:
                    tt_data = fetch_tiktok_data(url)
                    video_url = tt_data["video"]["no_watermark_hd"] or tt_data["video"]["no_watermark"]
                    clean_title = sanitize_filename(tt_data.get("title", "tiktok_video"))
                    target_video_path = os.path.join(DOWNLOADS_DIR, f"{clean_title}_{tt_data['id']}_no_watermark.mp4")

                    if not os.path.exists(target_video_path):
                        download_stream(video_url, target_video_path)

                analysis = analyze_video(
                    target_video_path,
                    product_relation=product_relation,
                    my_product_name=my_product_name,
                    my_packaging_desc=my_packaging_desc,
                    my_talent_desc=my_talent_desc
                )

                with open(ANALYSIS_FILE, "w") as f:
                    json.dump(analysis, f, indent=2)

                self.send_json(200, {"success": True, "data": analysis, "video_path": target_video_path})
            except Exception as e:
                self.send_json(500, {"success": False, "error": str(e)})
            return

        # 2. Slice video into puzzle clips
        elif path == "/api/slice":
            scenes = payload.get("scenes", [])
            video_path = payload.get("video_path")

            if not video_path or not os.path.exists(video_path):
                # Fallback to any downloaded mp4 file in downloads/
                mp4s = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.endswith(".mp4")]
                if mp4s:
                    video_path = mp4s[0]
                else:
                    self.send_json(400, {"success": False, "error": "Video sumber belum diunduh."})
                    return

            try:
                results = slice_video_to_puzzles(video_path, scenes, PUZZLES_DIR)

                # Replace mode: update library by replacing previous puzzles of this video
                existing_puzzles = []
                if os.path.exists(PUZZLES_META_FILE):
                    try:
                        with open(PUZZLES_META_FILE, "r", encoding="utf-8") as f:
                            existing_puzzles = json.load(f)
                    except Exception:
                        existing_puzzles = []

                base_name = os.path.splitext(os.path.basename(video_path))[0]
                new_existing = []
                for p in existing_puzzles:
                    if p.get("source_video") == base_name:
                        old_clip = p.get("clip_path")
                        old_thumb = p.get("thumb_path")
                        if old_clip and os.path.exists(old_clip):
                            try: os.remove(old_clip)
                            except Exception: pass
                        if old_thumb and os.path.exists(old_thumb):
                            try: os.remove(old_thumb)
                            except Exception: pass
                    else:
                        new_existing.append(p)

                new_existing.extend(results)
                existing_puzzles = new_existing

                with open(PUZZLES_META_FILE, "w", encoding="utf-8") as f:
                    json.dump(existing_puzzles, f, indent=2, ensure_ascii=False)

                self.send_json(200, {
                    "success": True,
                    "count": len(results),
                    "total_puzzles": len(existing_puzzles)
                })
            except Exception as e:
                self.send_json(500, {"success": False, "error": str(e)})
            return

        # 3. Assemble new ad (Voiceover + Speed-ramp tempo sync + Concat)
        elif path == "/api/assemble":
            scenes = payload.get("scenes", [])
            voice = payload.get("voice", "id-ID-ArdiNeural")
            output_ad_path = os.path.join(DOWNLOADS_DIR, "iklan_baru_final.mp4")

            try:
                res = assemble_ad(scenes=scenes, voice=voice, output_path=output_ad_path)
                res["video_url"] = f"/api/media?path={urllib.parse.quote(output_ad_path)}"
                self.send_json(200, res)
            except Exception as e:
                self.send_json(500, {"success": False, "error": str(e)})
            return

        # 4. Batch Download TikTok Videos
        elif path == "/api/batch-download-tiktok":
            urls = payload.get("urls", [])
            if not urls:
                self.send_json(400, {"success": False, "error": "Daftar URL TikTok tidak boleh kosong"})
                return

            results_summary = []
            new_puzzles_total = 0

            # Load existing puzzles
            existing_puzzles = []
            if os.path.exists(PUZZLES_META_FILE):
                try:
                    with open(PUZZLES_META_FILE, "r") as f:
                        existing_puzzles = json.load(f)
                except Exception:
                    existing_puzzles = []

            existing_files = {p.get("filename") for p in existing_puzzles}

            for u in urls:
                u = u.strip()
                if not u:
                    continue
                try:
                    print(f"\n[Batch TikTok] Mengambil data video: {u}")
                    tt_data = fetch_tiktok_data(u)
                    
                    video_info = tt_data.get("video") or {}
                    video_url = video_info.get("no_watermark_hd") or video_info.get("no_watermark")
                    if not video_url:
                        if tt_data.get("is_image_slide"):
                            raise ValueError("Konten ini berupa slideshow foto, bukan video MP4.")
                        raise ValueError("Link video tanpa watermark tidak ditemukan dari API.")

                    clean_title = sanitize_filename(tt_data.get("title", "tiktok_video"))
                    target_video_path = os.path.join(DOWNLOADS_DIR, f"{clean_title}_{tt_data['id']}_no_watermark.mp4")

                    if not os.path.exists(target_video_path):
                        print(f"[Batch TikTok] Mengunduh MP4 ke: {target_video_path}")
                        download_stream(video_url, target_video_path)
                    else:
                        print(f"[Batch TikTok] File video sudah tersimpan di: {target_video_path}")

                    # Extract scenes with Gemini
                    print(f"[Batch TikTok] Menganalisis potongan scene dengan Gemini...")
                    analysis = analyze_video(target_video_path)
                    scenes = analysis.get("breakdown_scene", [])
                    print(f"[Batch TikTok] Ditemukan {len(scenes)} scene. Memotong jadi klip puzzle...")

                    # Slice video into puzzles (minimum 3.0s enforced)
                    cut_puzzles = slice_video_to_puzzles(target_video_path, scenes, PUZZLES_DIR)
                    base_name = os.path.splitext(os.path.basename(target_video_path))[0]
                    
                    # Replace previous puzzles belonging to this video
                    new_existing = []
                    for p in existing_puzzles:
                        if p.get("source_video") == base_name:
                            old_clip = p.get("clip_path")
                            old_thumb = p.get("thumb_path")
                            if old_clip and os.path.exists(old_clip):
                                try: os.remove(old_clip)
                                except Exception: pass
                            if old_thumb and os.path.exists(old_thumb):
                                try: os.remove(old_thumb)
                                except Exception: pass
                        else:
                            new_existing.append(p)

                    new_existing.extend(cut_puzzles)
                    existing_puzzles = new_existing
                    new_puzzles_total += len(cut_puzzles)

                    print(f"[Batch TikTok] ✅ Berhasil memproses & replace puzzle: {clean_title} ({len(cut_puzzles)} klip puzzle >= 3 detik)")
                    results_summary.append({
                        "url": u,
                        "title": tt_data.get("title", clean_title),
                        "success": True,
                        "scenes_cut": len(cut_puzzles),
                        "new_added": len(cut_puzzles)
                    })
                except Exception as err:
                    print(f"[Batch TikTok ERROR] ❌ Gagal memproses {u}: {err}")
                    results_summary.append({
                        "url": u,
                        "success": False,
                        "error": str(err)
                    })

            # Save updated puzzles
            with open(PUZZLES_META_FILE, "w") as f:
                json.dump(existing_puzzles, f, indent=2)

            self.send_json(200, {
                "success": True,
                "summary": results_summary,
                "new_puzzles_added": new_puzzles_total,
                "total_puzzles": len(existing_puzzles)
            })
            return

        # 5. AI Auto-Match Improvement Scenes with Puzzle Library
        elif path == "/api/match-scenes":
            user_scenes = payload.get("scenes", [])
            if not user_scenes:
                self.send_json(400, {"success": False, "error": "Daftar scene pengguna tidak boleh kosong"})
                return

            # Load available puzzles
            puzzles = []
            if os.path.exists(PUZZLES_META_FILE):
                try:
                    with open(PUZZLES_META_FILE, "r") as f:
                        puzzles = json.load(f)
                except Exception:
                    puzzles = []

            if not puzzles:
                self.send_json(400, {
                    "success": False,
                    "error": "Perpustakaan puzzle masih kosong. Masukkan dan potong video TikTok bahan terlebih dahulu."
                })
                return

            try:
                matched_results = match_scenes_with_ai(user_scenes, puzzles)
                puzzle_by_fn = {p.get("filename"): p for p in puzzles}

                # Enrich matched results with actual file paths and media URLs
                plan = []
                for m in matched_results:
                    fn = m.get("selected_puzzle_filename")
                    p_info = puzzle_by_fn.get(fn, {})
                    clip_path = p_info.get("clip_path") or os.path.join(PUZZLES_DIR, fn)
                    thumb_path = p_info.get("thumb_path")
                    if not thumb_path or not os.path.exists(thumb_path):
                        base_stem = os.path.splitext(fn)[0]
                        candidate = os.path.join(PUZZLES_DIR, f"{base_stem}.jpg")
                        if os.path.exists(candidate):
                            thumb_path = candidate

                    plan.append({
                        "scene_name": m.get("scene_name"),
                        "voice_script": m.get("voice_script"),
                        "visual_intent": m.get("visual_intent"),
                        "selected_puzzle_filename": fn,
                        "clip_path": clip_path,
                        "clip_url": f"/api/media?path={urllib.parse.quote(clip_path)}",
                        "thumb_url": f"/api/media?path={urllib.parse.quote(thumb_path)}" if thumb_path and os.path.exists(thumb_path) else "",
                        "match_reason": m.get("match_reason"),
                        "omni_camera_prompt": m.get("omni_camera_prompt"),
                        "is_omni": False,
                        "omni_clip_path": "",
                        "omni_clip_url": ""
                    })

                self.send_json(200, {"success": True, "plan": plan})
            except Exception as e:
                self.send_json(500, {"success": False, "error": str(e)})
            return

        else:
            self.send_error(404, "Endpoint not found")


def run_server(port=PORT):
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, AdStudioHandler)
    print("\n" + "=" * 55)
    print(f"🎬 AI Video Ad Studio & Remixer Siap Digunakan!")
    print(f"👉 Buka browser di: http://localhost:{port}")
    print("=" * 55 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nMematikan server...")
        httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run_server(port)

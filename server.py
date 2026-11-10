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
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

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
                    thumb_name = f"puzzle_scene_{p.get('scene', 1):02d}.jpg"
                    p["thumb_path"] = os.path.join(PUZZLES_DIR, thumb_name)

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

        else:
            self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        # 1. Reverse-engineer video with Gemini
        if path == "/api/analyze":
            url = payload.get("url", "").strip()
            if not url:
                self.send_json(400, {"success": False, "error": "URL TikTok tidak boleh kosong"})
                return

            try:
                # Check if we already have this video downloaded locally
                # Fetch metadata from TikTok
                tt_data = fetch_tiktok_data(url)
                video_url = tt_data["video"]["no_watermark_hd"] or tt_data["video"]["no_watermark"]
                clean_title = sanitize_filename(tt_data.get("title", "tiktok_video"))
                target_video_path = os.path.join(DOWNLOADS_DIR, f"{clean_title}_{tt_data['id']}_no_watermark.mp4")

                # Download if not present
                if not os.path.exists(target_video_path):
                    download_stream(video_url, target_video_path)

                # Analyze with Gemini
                analysis = analyze_video(target_video_path)

                # Cache analysis
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
                with open(PUZZLES_META_FILE, "w") as f:
                    json.dump(results, f, indent=2)

                self.send_json(200, {"success": True, "count": len(results)})
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

        else:
            self.send_error(404, "Endpoint not found")


def run_server(port=PORT):
    server_address = ("", port)
    httpd = HTTPServer(server_address, AdStudioHandler)
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

"""
Core TikTok Downloader module.
Provides functions to fetch video metadata and download media streams without watermark.
"""

import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Optional

TIKWM_API_URL = "https://www.tikwm.com/api/"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
}


def sanitize_filename(filename: str, max_length: int = 60) -> str:
    """Sanitize string to be used safely as filename."""
    # Replace invalid filename characters
    clean = re.sub(r'[\\/*?:"<>|#\n\r\t]', "_", filename).strip()
    if not clean:
        clean = "tiktok_media"
    return clean[:max_length]


def resolve_tiktok_url(url: str) -> str:
    """Resolve shortened TikTok URL to full URL if needed."""
    try:
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.geturl()
    except Exception:
        return url


def fetch_tiktok_data(tiktok_url: str) -> Dict[str, Any]:
    """Fetch video metadata from TikWM API with retry and redirect resolution.
    
    Args:
        tiktok_url: URL to TikTok video or photo post.
        
    Returns:
        Dict containing parsed metadata and media URLs.
    """
    cleaned_url = tiktok_url.strip()
    if not cleaned_url:
        raise ValueError("URL TikTok tidak boleh kosong.")

    # Try fetching with original URL first, then resolved URL if needed
    urls_to_try = [cleaned_url]
    if "vt.tiktok.com" in cleaned_url or "vm.tiktok.com" in cleaned_url:
        resolved = resolve_tiktok_url(cleaned_url)
        if resolved != cleaned_url:
            urls_to_try.append(resolved)

    last_error = None
    data = None

    for target_url in urls_to_try:
        for attempt in range(2):
            api_endpoint = f"{TIKWM_API_URL}?url={urllib.parse.quote(target_url)}&hd=1"
            req = urllib.request.Request(api_endpoint, headers=DEFAULT_HEADERS)
            try:
                with urllib.request.urlopen(req, timeout=20) as response:
                    res_body = response.read().decode("utf-8")
                    data = json.loads(res_body)
                    if data.get("code") == 0 and data.get("data"):
                        break
                    else:
                        last_error = data.get("msg", "API tidak mengembalikan data video")
            except Exception as e:
                last_error = str(e)
            
            import time
            time.sleep(1)

        if data and data.get("code") == 0 and data.get("data"):
            break

    if not data or data.get("code") != 0 or not data.get("data"):
        raise ValueError(f"Gagal mengambil video TikTok: {last_error or 'Pastikan link valid dan video bersifat publik'}")

    info = data.get("data", {})
    if not info:
        raise ValueError("Data video tidak ditemukan dalam respons API.")

    author = info.get("author", {})
    music_info = info.get("music_info", {})
    images = info.get("images") or []

    # Format result structure
    result = {
        "id": info.get("id"),
        "title": info.get("title") or "TikTok Video",
        "duration": info.get("duration", 0),
        "cover": info.get("cover"),
        "origin_cover": info.get("origin_cover") or info.get("cover"),
        "author": {
            "id": author.get("id"),
            "unique_id": author.get("unique_id", "creator"),
            "nickname": author.get("nickname", "Creator"),
            "avatar": author.get("avatar"),
        },
        "stats": {
            "plays": info.get("play_count", 0),
            "likes": info.get("digg_count", 0),
            "comments": info.get("comment_count", 0),
            "shares": info.get("share_count", 0),
            "downloads": info.get("download_count", 0),
        },
        "video": {
            "no_watermark": info.get("play"),
            "no_watermark_hd": info.get("hdplay") or info.get("play"),
            "with_watermark": info.get("wmplay"),
            "size": info.get("size", 0),
            "wm_size": info.get("wm_size", 0),
        },
        "music": {
            "url": info.get("music"),
            "title": music_info.get("title") or "Original Sound",
            "author": music_info.get("author") or author.get("nickname"),
        },
        "is_image_slide": bool(images),
        "images": images,
    }

    return result


def download_stream(url: str, output_path: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> str:
    """Download binary content from URL and save to output_path.
    
    Args:
        url: Direct media URL.
        output_path: Path where file should be saved.
        progress_callback: Optional callback receiving (bytes_read, total_bytes).
        
    Returns:
        The output path of the saved file.
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.tiktok.com/",
        },
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with urllib.request.urlopen(req, timeout=30) as response, open(output_path, "wb") as out_file:
        total_size = int(response.headers.get("Content-Length", 0))
        bytes_read = 0
        chunk_size = 64 * 1024  # 64 KB chunks

        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            out_file.write(chunk)
            bytes_read += len(chunk)
            if progress_callback:
                progress_callback(bytes_read, total_size)

    return output_path


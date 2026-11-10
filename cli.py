#!/usr/bin/env python3
"""
CLI TikTok Downloader tool.
Usage:
    python3 cli.py <tiktok_url> [--audio] [--watermark] [--output-dir DIR]
"""

import argparse
import os
import sys
import time

from downloader import download_stream, fetch_tiktok_data, sanitize_filename


def progress_bar(bytes_read: int, total_bytes: int):
    if total_bytes > 0:
        percent = (bytes_read / total_bytes) * 100
        bar_len = 30
        filled = int(bar_len * bytes_read // total_bytes)
        bar = "=" * filled + "-" * (bar_len - filled)
        mb_read = bytes_read / (1024 * 1024)
        mb_total = total_bytes / (1024 * 1024)
        sys.stdout.write(f"\r  Mengunduh: [{bar}] {percent:5.1f}% ({mb_read:.2f}/{mb_total:.2f} MB)")
    else:
        mb_read = bytes_read / (1024 * 1024)
        sys.stdout.write(f"\r  Mengunduh: {mb_read:.2f} MB")
    sys.stdout.flush()


def main():
    default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
    parser = argparse.ArgumentParser(description="Download TikTok Video tanpa watermark.")
    parser.add_argument("url", help="URL video TikTok (contoh: https://vt.tiktok.com/ZSpD4MSJL/)")
    parser.add_argument("--audio", action="store_true", help="Download audio MP3 saja")
    parser.add_argument("--watermark", action="store_true", help="Download video dengan watermark")
    parser.add_argument("--outdir", default=default_dir, help=f"Folder tujuan penyimpanan file (default: {default_dir})")
    args = parser.parse_args()

    print(f"\n[1/3] Mengambil informasi video dari: {args.url} ...")
    try:
        data = fetch_tiktok_data(args.url)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    print(f"\n--- Informasi Video ---")
    print(f"📌 Judul     : {data.get('title')}")
    print(f"👤 Creator   : {data['author']['nickname']} (@{data['author']['unique_id']})")
    print(f"⏱️ Durasi    : {data.get('duration')} detik")
    print(f"❤️ Likes     : {data['stats']['likes']:,}")
    print(f"💬 Comments  : {data['stats']['comments']:,}")
    print(f"🔄 Shares    : {data['stats']['shares']:,}")
    print("------------------------\n")

    os.makedirs(args.outdir, exist_ok=True)
    clean_title = sanitize_filename(data.get("title") or "tiktok_video")

    if data.get("is_image_slide"):
        print(f"📸 Postingan ini berupa slide foto ({len(data['images'])} gambar).")
        for idx, img_url in enumerate(data["images"], 1):
            filename = f"{data['author']['unique_id']}_{data['id']}_slide_{idx}.jpg"
            target_path = os.path.join(args.outdir, filename)
            print(f"Mengunduh gambar {idx}/{len(data['images'])}: {filename} ...")
            download_stream(img_url, target_path)
        print(f"\n✅ Semua gambar berhasil diunduh ke folder: {args.outdir}")
        return

    if args.audio:
        media_url = data["music"]["url"]
        filename = f"{clean_title}_{data['id']}_audio.mp3"
        print(f"[2/3] Memulai download audio MP3: {filename}")
    elif args.watermark:
        media_url = data["video"]["with_watermark"]
        filename = f"{clean_title}_{data['id']}_watermark.mp4"
        print(f"[2/3] Memulai download video (dengan watermark): {filename}")
    else:
        media_url = data["video"]["no_watermark_hd"] or data["video"]["no_watermark"]
        filename = f"{clean_title}_{data['id']}_no_watermark.mp4"
        print(f"[2/3] Memulai download video (TANPA watermark): {filename}")

    if not media_url:
        print("❌ URL media tidak tersedia untuk opsi yang dipilih.")
        sys.exit(1)

    target_path = os.path.join(args.outdir, filename)

    try:
        t0 = time.time()
        download_stream(media_url, target_path, progress_callback=progress_bar)
        print("\n\n[3/3] ✅ Berhasil diunduh!")
        print(f"📂 Lokasi file: {os.path.abspath(target_path)}")
        file_size_mb = os.path.getsize(target_path) / (1024 * 1024)
        print(f"📦 Ukuran file: {file_size_mb:.2f} MB (waktu: {time.time() - t0:.1f} detik)")
    except Exception as e:
        print(f"\n❌ Gagal saat mengunduh: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

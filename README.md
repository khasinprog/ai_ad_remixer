# 🎬 AI Video Ad Studio & Competitor Remixer

Aplikasi cerdas untuk **membedah video iklan kompetitor (TikTok / Reels / FB Ads)**, memotongnya menjadi kepingan klip puzzle, mengekstrak skrip & breakdown visual dengan **Gemini Multimodal AI**, serta merakit video iklan baru lengkap dengan **AI Voiceover** dan **Dynamic Tempo Sync (Speed Ramping)**.

Aplikasi ini **100% Cross-Platform** dan siap dijalankan baik di **Mac, Windows, maupun Linux**!

---

## 🪟 Panduan Menjalankan di Windows (Setelah di-Pull dari Git)

### 1. Prasyarat di Laptop Windows
Pastikan laptop Windows Anda sudah terpasang:
1. **Python 3.10+**: Download dari [python.org](https://www.python.org/downloads/) *(PENTING: Centang **"Add Python to PATH"** saat install)*.
2. **FFmpeg**: Buka PowerShell / Terminal di Windows, lalu jalankan:
   ```powershell
   winget install Gyan.FFmpeg
   ```
   *(Atau download `ffmpeg.exe` lalu masukkan foldernya ke Environment Variables PATH).*

---

### 2. Langkah Setup di Windows

1. **Clone / Tarik repo dari Git:**
   ```cmd
   git clone <url_repo_anda>
   cd ai_ad_remixer
   ```

2. **Buat file `.env`:**
   Salin `.env.example` menjadi `.env`, lalu isi API Key Anda:
   ```cmd
   copy .env.example .env
   ```
   Buka file `.env` dan masukkan:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

3. **Jalankan Aplikasi:**
   Cukup **klik dua kali (double click) file `run.bat`**!
   
   File `run.bat` akan secara otomatis:
   - Membuat virtual environment (`venv`) di Windows.
   - Menginstall library `requirements.txt`.
   - Menjalankan server lokal.
   - Otomatis membuka browser di **http://localhost:5055**.

---

## 🍎 Cara Menjalankan di Mac / Linux

Cukup jalankan script launcher:
```bash
./run.sh
```
Atau:
```bash
python3 server.py 5055
```
Lalu buka browser di: **http://localhost:5055**

---

## 🐙 Panduan Git (Push dari Mac -> Pull di Windows)

### Dari Mac Anda Sekarang:
```bash
cd /Users/a1/.gemini/antigravity/scratch/ai_ad_remixer
git init
git add .
git commit -m "Initial commit: AI Video Ad Studio & Remixer"
git branch -M main
git remote add origin <URL_REPOSITORY_GITHUB_ANDA>
git push -u origin main
```

*(Catatan: `.env` sudah otomatis diabaikan oleh `.gitignore` agar API Key Anda aman dari publik).*

### Di Laptop Windows Anda:
```cmd
git clone <URL_REPOSITORY_GITHUB_ANDA>
cd ai_ad_remixer
copy .env.example .env
:: Isi API key di file .env
run.bat
```

---

## 📁 Struktur File Proyek
```text
ai_ad_remixer/
├── run.bat                  # 🚀 Launcher 1-klik untuk WINDOWS
├── run.sh                   # 🚀 Launcher 1-klik untuk MAC / LINUX
├── server.py                # Web server backend (Pure Python, port 5055)
├── analyzer.py              # Engine Gemini 2.5 (Reverse Engineering & Omni Prompts)
├── slicer.py                # Engine FFmpeg (Slices video into puzzle clips)
├── assembler.py             # Engine Voiceover (TTS) & Dynamic Speed Ramping
├── downloader.py            # Modul pengunduh video TikTok tanpa watermark
├── cli.py                   # Tool CLI terminal
├── requirements.txt         # Daftar dependency python
├── .env.example             # Template API Key
├── .gitignore               # Menjaga keamanan API key & file besar
│
├── static/
│   └── index.html           # UI Interaktif (Tailwind CSS, 3 Tab: Reverse, Puzzle, Studio)
├── puzzles/                 # Folder kepingan puzzle klip video
└── downloads/               # Folder video unduhan & iklan final
```

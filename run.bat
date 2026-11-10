@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo   AI Video Ad Studio ^& Remixer - Windows Launcher
echo ==========================================================

:: 1. Cek apakah Python terpasang
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak ditemukan di sistem Windows Anda!
    echo Silakan install Python 3.10+ dari https://www.python.org/downloads/
    echo Pastikan centang "Add Python to PATH" saat menginstall.
    pause
    exit /b 1
)

:: 2. Cek apakah FFmpeg terpasang
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [PERINGATAN] FFmpeg belum terpasang atau belum masuk PATH!
    echo Anda bisa install cepat dengan perintah:
    echo   winget install Gyan.FFmpeg
    echo atau download ffmpeg.exe dan taruh di folder sistem.
    echo.
)

:: 3. Buat / Gunakan Virtual Environment (venv) jika ada
if not exist "venv" (
    echo [INFO] Membuat virtual environment baru (venv)...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo [INFO] Menginstall library yang dibutuhkan...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

:: 4. Buka Browser otomatis
start http://localhost:5055

:: 5. Jalankan Web Server
echo ==========================================================
echo   Server sedang berjalan di http://localhost:5055
echo   Tekan Ctrl + C untuk mematikan server.
echo ==========================================================
python server.py 5055

pause


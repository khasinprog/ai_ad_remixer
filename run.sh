#!/usr/bin/env bash
# Script peluncur aplikasi AI Video Ad Studio & Remixer (Mac / Linux)
cd "$(dirname "$0")"

# Cari Python yang memiliki virtual environment atau python3 sistem
if [ -f "/Users/a1/.gemini/antigravity/scratch/code_video_editor/venv/bin/python3" ]; then
  PYTHON_BIN="/Users/a1/.gemini/antigravity/scratch/code_video_editor/venv/bin/python3"
elif [ -f "./venv/bin/python3" ]; then
  PYTHON_BIN="./venv/bin/python3"
else
  PYTHON_BIN="python3"
fi

echo "=========================================================="
echo "🚀 Menjalankan AI Video Ad Studio & Remixer..."
echo "📂 Lokasi: $(pwd)"
echo "🌐 URL: http://localhost:5055"
echo "=========================================================="

"$PYTHON_BIN" server.py 5055

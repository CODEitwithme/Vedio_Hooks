"""
Production Runner for VedioHooks AI Web Application.
Launches the FastAPI server with Uvicorn on http://127.0.0.1:8000.
"""

import sys
import os
from pathlib import Path

# Fix Windows console UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add workspace to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.db import init_db
import uvicorn

if __name__ == "__main__":
    init_db()
    print("=" * 70)
    print("  [*] VedioHooks AI - Viral Shorts Maker is starting...")
    print("  [+] Web Dashboard : http://127.0.0.1:8000")
    print("  [+] API Docs (Swagger): http://127.0.0.1:8000/docs")
    print("  [+] Engine         : Faster-Whisper + MediaPipe + FFmpeg (SIMD)")
    print("=" * 70)
    uvicorn.run("src.server:app", host="127.0.0.1", port=8000, reload=False, log_level="info")

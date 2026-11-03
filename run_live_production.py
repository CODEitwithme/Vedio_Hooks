"""
VedioHooks AI - 1-Click Live Production Launcher with Free Public HTTPS Tunnel
Starts FastAPI Server + 24/7 Autonomous Scheduler and exposes it to the world
via an encrypted Cloudflare Tunnel with zero configuration required.
"""

import os
import sys

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import time
import re
import signal
import subprocess
import urllib.request
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
TOOLS_DIR = ROOT_DIR / "tools"
CLOUDFLARED_EXE = TOOLS_DIR / "cloudflared.exe"
LIVE_URL_FILE = ROOT_DIR / "LIVE_URL.txt"

def ensure_cloudflared() -> str:
    if not CLOUDFLARED_EXE.exists() or CLOUDFLARED_EXE.stat().st_size < 1000000:
        print("[*] Downloading Cloudflare Tunnel engine...")
        download_script = TOOLS_DIR / "download_cloudflared.py"
        subprocess.run([sys.executable, str(download_script)], check=True)
    return str(CLOUDFLARED_EXE)

def stop_existing_port_8000():
    """Kill any existing process on port 8000 to ensure fresh code execution."""
    if sys.platform == "win32":
        try:
            cmd = "powershell -Command \"Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }\""
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)
        except Exception:
            pass

def wait_for_server(url: str = "http://127.0.0.1:8000/api/system/stats", timeout: float = 25.0) -> bool:
    start_time = time.time()
    print("[*] Starting VedioHooks AI FastAPI server & 24/7 autonomous scheduler...")
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VedioHooks-Launcher/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    print("=" * 72)
    print(" [*] VEDIOHOOKS AI - 1-CLICK LIVE PRODUCTION LAUNCHER")
    print("=" * 72)

    cf_exe = ensure_cloudflared()

    # 1. Clean up stale port 8000
    stop_existing_port_8000()

    # 2. Start Uvicorn Server in background
    server_cmd = [
        sys.executable,
        "-m", "uvicorn",
        "src.server:app",
        "--host", "127.0.0.1",
        "--port", "8000"
    ]
    server_proc = subprocess.Popen(
        server_cmd,
        cwd=str(ROOT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # 3. Wait for server readiness
    if not wait_for_server():
        print("[-] Error: VedioHooks AI server failed to initialize on port 8000.")
        server_proc.terminate()
        sys.exit(1)

    print("[+] Local FastAPI server & autonomous background scheduler are active!")

    # 4. Start Cloudflare Tunnel
    print("[*] Establishing encrypted Cloudflare Tunnel to the internet...")
    cf_cmd = [
        cf_exe,
        "tunnel",
        "--url", "http://127.0.0.1:8000",
        "--no-autoupdate"
    ]

    cf_proc = subprocess.Popen(
        cf_cmd,
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    tunnel_url = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    # Read output until public URL is obtained
    for line in cf_proc.stdout:
        match = url_pattern.search(line)
        if match:
            tunnel_url = match.group(0)
            break

    if not tunnel_url:
        print("[-] Could not establish Cloudflare Tunnel.")
        cf_proc.terminate()
        server_proc.terminate()
        sys.exit(1)

    # Save active URL to file
    with open(LIVE_URL_FILE, "w", encoding="utf-8") as f:
        f.write(tunnel_url.strip() + "\n")

    print("\n" + "=" * 72)
    print(" [+] YOUR VEDIOHOOKS AI FACTORY IS LIVE AND ACCESSIBLE WORLDWIDE!")
    print("=" * 72)
    print(f" [>] Public HTTPS URL:    {tunnel_url}")
    print(f" [>] Local Dashboard:     http://localhost:8000")
    print(f" [>] Interactive API:     {tunnel_url}/docs")
    print(f" [>] System Telemetry:    {tunnel_url}/api/system/stats")
    print("=" * 72)
    print(" [*] Anyone with this link can use the app from any device or phone.")
    print(" [*] Running 24/7 in background. Press Ctrl+C in this window to stop.\n")

    # Keep running until Ctrl+C
    def cleanup(signum, frame):
        print("\n[*] Shutting down live tunnel and server...")
        cf_proc.terminate()
        server_proc.terminate()
        if LIVE_URL_FILE.exists():
            try:
                LIVE_URL_FILE.unlink()
            except Exception:
                pass
        print("[+] Everything stopped cleanly. Goodbye!")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        cleanup(None, None)

if __name__ == "__main__":
    main()

"""
VedioHooks AI - 1-Click Live Production Launcher with Free Public HTTPS Tunnel
Starts FastAPI Server + 24/7 Autonomous Scheduler and exposes it to the world
via an encrypted Cloudflare Tunnel with zero configuration required.
"""

import os
import sys
import socket

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

def get_local_ip() -> str:
    """Returns local LAN IP (e.g. 192.168.x.x) for phone on same Wi-Fi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

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
    local_ip = get_local_ip()

    # 1. Clean up stale port 8000
    stop_existing_port_8000()

    # 2. Start Uvicorn Server on 0.0.0.0 (all interfaces) so LAN & tunnel both work
    server_cmd = [
        sys.executable,
        "-m", "uvicorn",
        "src.server:app",
        "--host", "0.0.0.0",
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

    # Drain remaining output in background thread to prevent buffer deadlock
    import threading
    def drain_pipe():
        try:
            for _ in cf_proc.stdout:
                pass
        except Exception:
            pass
    threading.Thread(target=drain_pipe, daemon=True).start()

    if not tunnel_url:
        print("[-] Could not establish Cloudflare Tunnel.")
        cf_proc.terminate()
        server_proc.terminate()
        sys.exit(1)

    # Save active URLs to file
    with open(LIVE_URL_FILE, "w", encoding="utf-8") as f:
        f.write(f"PUBLIC_URL={tunnel_url}\n")
        f.write(f"WIFI_URL=http://{local_ip}:8000\n")
        f.write(f"LOCAL_URL=http://localhost:8000\n")

    # Automatically keep OPEN_ON_MOBILE.html QR code in sync
    mobile_html_file = ROOT_DIR / "OPEN_ON_MOBILE.html"
    if mobile_html_file.exists():
        try:
            import urllib.parse
            html_content = mobile_html_file.read_text(encoding="utf-8")
            html_content = re.sub(r"https%3A%2F%2F[a-zA-Z0-9-]+\.trycloudflare\.com", urllib.parse.quote(tunnel_url, safe=''), html_content)
            html_content = re.sub(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", tunnel_url, html_content)
            mobile_html_file.write_text(html_content, encoding="utf-8")
        except Exception:
            pass

    print("\n" + "=" * 72)
    print(" [+] YOUR VEDIOHOOKS AI FACTORY IS LIVE AND READY FOR MOBILE & WEB!")
    print("=" * 72)
    print(f" [>] Public HTTPS (Any Phone / Mobile Data):")
    print(f"     {tunnel_url}")
    print()
    print(f" [>] Local Wi-Fi (Phones on Same Wi-Fi):")
    print(f"     http://{local_ip}:8000")
    print()
    print(f" [>] PC Local Dashboard:")
    print(f"     http://localhost:8000")
    print("=" * 72)
    print(" [*] Running 24/7 in background. Press Ctrl+C to stop.\n")

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

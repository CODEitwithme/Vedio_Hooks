import os
import sys
import urllib.request
import subprocess

TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
EXE_PATH = os.path.join(TOOLS_DIR, "cloudflared.exe")
DOWNLOAD_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"

def download_cloudflared():
    if os.path.exists(EXE_PATH) and os.path.getsize(EXE_PATH) > 1000000:
        print(f"[*] cloudflared.exe already downloaded at {EXE_PATH}")
    else:
        print(f"[*] Downloading cloudflared.exe from {DOWNLOAD_URL} ...")
        urllib.request.urlretrieve(DOWNLOAD_URL, EXE_PATH)
        print(f"[+] Download complete! Saved to {EXE_PATH}")

    try:
        res = subprocess.run([EXE_PATH, "--version"], capture_output=True, text=True, check=True)
        print(f"[+] Verification: {res.stdout.strip()}")
    except Exception as e:
        print(f"[-] Error running cloudflared: {e}")
        sys.exit(1)

if __name__ == "__main__":
    download_cloudflared()

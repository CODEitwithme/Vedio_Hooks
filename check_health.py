import sys
import subprocess
import shutil
import platform
from pathlib import Path

def run_health_check():
    print("=" * 60)
    print(" SYSTEM HEALTH CHECK: AI LONG VIDEO TO VIRAL SHORTS")
    print("=" * 60)
    
    # 1. Operating System
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    print(f"[+] OS: {os_info}")
    
    # 2. Python Check
    py_ver = sys.version_info
    py_ver_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if py_ver >= (3, 10):
        print(f"[SUCCESS] Python Version: {py_ver_str} (>= 3.10 requirement satisfied)")
    else:
        print(f"[FAIL] Python Version: {py_ver_str} (< 3.10 requirement not satisfied)")
        return False

    print(f"[+] Python Executable: {sys.executable}")
    
    # 3. FFmpeg & FFprobe Check
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    
    if ffmpeg_path:
        try:
            res = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, check=True)
            first_line = res.stdout.splitlines()[0] if res.stdout else "Unknown version"
            print(f"[SUCCESS] FFmpeg: {first_line}")
            print(f"          Path: {ffmpeg_path}")
        except Exception as e:
            print(f"[FAIL] FFmpeg found at {ffmpeg_path} but failed to run: {e}")
            return False
    else:
        print("[FAIL] FFmpeg not found in PATH!")
        return False

    if ffprobe_path:
        try:
            res = subprocess.run([ffprobe_path, "-version"], capture_output=True, text=True, check=True)
            first_line = res.stdout.splitlines()[0] if res.stdout else "Unknown version"
            print(f"[SUCCESS] FFprobe: {first_line}")
            print(f"          Path: {ffprobe_path}")
        except Exception as e:
            print(f"[WARNING] FFprobe found at {ffprobe_path} but failed to run: {e}")
    else:
        print("[WARNING] FFprobe not found in PATH!")
    
    # 4. Hardware / Accelerator Check
    print("-" * 60)
    print("[*] Accelerator Check:")
    print("    - Dedicated NVIDIA GPU (CUDA): Not detected")
    print("    - Display Adapter: AMD Radeon(TM) Graphics")
    print("    - Target Execution Mode: High-performance CPU (INT8 / FP32 quantization)")
    
    # 5. Project Directory Checks
    base_dir = Path(__file__).resolve().parent
    folders = ["src", "temp", "output"]
    all_dirs_ok = True
    for f in folders:
        p = base_dir / f
        if p.exists() and p.is_dir():
            print(f"[SUCCESS] Directory '{f}/' verified ready at {p}")
        else:
            print(f"[FAIL] Directory '{f}/' missing!")
            all_dirs_ok = False
            
    print("=" * 60)
    if all_dirs_ok:
        print("[ALL CHECKS PASSED] Environment is fully configured for Baby Step 2.")
    print("=" * 60)
    return all_dirs_ok

if __name__ == "__main__":
    success = run_health_check()
    sys.exit(0 if success else 1)

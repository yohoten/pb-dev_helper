r"""Setup 32-bit embeddable Python worker for PB Dev Helper.

Downloads python-embed-win32.zip if needed, extracts it, copies the worker script,
and configures the _pth file.

Usage:
    python scripts/setup_worker.py
"""

import os
import sys
import zipfile
import shutil
import urllib.request

PYTHON_VERSION = "3.12.8"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-win32.zip"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
WORKER_DIR = os.path.join(PROJECT_DIR, "dist", "worker")


def download(url: str, dest: str) -> bool:
    print(f"Downloading: {url}")
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False


def setup():
    os.makedirs(WORKER_DIR, exist_ok=True)

    # 1. Download embeddable Python
    zip_path = os.path.join(WORKER_DIR, "python-embed-win32.zip")
    if not os.path.exists(zip_path):
        if not download(PYTHON_URL, zip_path):
            print("ERROR: Could not download 32-bit Python.")
            print(f"Please download manually from: {PYTHON_URL}")
            print(f"And extract to: {WORKER_DIR}")
            sys.exit(1)

    # 2. Extract
    if not os.path.exists(os.path.join(WORKER_DIR, "python.exe")):
        print(f"Extracting to: {WORKER_DIR}")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(WORKER_DIR)
        print("Extraction complete.")

    # 3. Copy worker script
    worker_src = os.path.join(SCRIPT_DIR, "orca_worker.py")
    worker_dst = os.path.join(WORKER_DIR, "orca_worker.py")
    shutil.copy2(worker_src, worker_dst)
    print(f"Copied: {worker_dst}")

    # 4. Configure _pth file
    pth_path = os.path.join(WORKER_DIR, f"python{PYTHON_VERSION[:3]}._pth")
    if os.path.exists(pth_path):
        content = ""
        with open(pth_path, "r") as f:
            content = f.read()
        # Uncomment 'import site' if commented
        if "#import site" in content:
            content = content.replace("#import site", "import site")
            with open(pth_path, "w") as f:
                f.write(content)
            print(f"Updated: {pth_path}")

    # 5. Verify
    python_exe = os.path.join(WORKER_DIR, "python.exe")
    if os.path.exists(python_exe):
        print(f"\nWorker setup complete!")
        print(f"32-bit Python: {python_exe}")
        print(f"Worker script: {worker_dst}")
        print(f"\nIn PB Dev Helper Settings tab, set Worker Python to:")
        print(f"  {python_exe}")
    else:
        print("ERROR: python.exe not found after extraction.")


if __name__ == "__main__":
    setup()

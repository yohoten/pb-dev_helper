"""Build standalone executable using PyInstaller.

Usage: python build_exe.py

Output: dist/PBDevHelper/main.exe + bundled data files
"""

import os
import shutil
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, "dist", "PBDevHelper")
SPEC_FILE = os.path.join(PROJECT_DIR, "pbdev.spec")

# UPX configuration
UPX_PATH = r"H:\UPX\upx.exe"


def check_upx():
    """Check if UPX is available and return path."""
    if os.path.exists(UPX_PATH):
        print(f"✅ UPX found: {UPX_PATH}")
        try:
            result = subprocess.run([UPX_PATH, "--version"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                print(f"   Version: {version}")
                return UPX_PATH
        except Exception as e:
            print(f"⚠️ UPX check failed: {e}")
    
    # Fallback to system PATH
    try:
        result = subprocess.run(["upx", "--version"], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ UPX found in system PATH")
            return "upx"
    except Exception:
        pass
    
    print("❌ UPX not found. Build will proceed without compression.")
    print("   Download UPX from: https://github.com/upx/upx/releases")
    return None


def create_spec(upx_path=None):
    """Generate PyInstaller spec file."""
    data_files = [
        ("dist/worker/*", "dist/worker"),      # 32-bit Python worker
        ("tools/pbpicker/*", "tools/pbpicker"), # PB Picker runtime
    ]
    datas_str = ",\n        ".join(f'("{s}", "{d}")' for s, d in data_files)
    
    upx_dir = os.path.dirname(upx_path) if upx_path and os.path.isabs(upx_path) else ""
    
    # Prepare icon path - use absolute path directly in spec file
    icon_path = os.path.join(PROJECT_DIR, "pb-dev-helper.ico")
    icon_expr = f"r'{icon_path}'" if os.path.exists(icon_path) else "'NONE'"

    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hidden_imports = []
for pkg in ['gui', 'orca', 'models', 'utils', 'scripts']:
    hidden_imports.extend(collect_submodules(pkg))

a = Analysis(
    ['main.py'],
    pathex=[r'{PROJECT_DIR}'],
    binaries=[],
    datas=[
        {datas_str},
    ],
    hiddenimports=hidden_imports + ['tkinter', 'tkinter.ttk', 'tkinter.filedialog',
                                     'tkinter.messagebox', 'tkinter.simpledialog'],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PBDevHelper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx={bool(upx_path)},
    upx_exclude=[],
    upx_dir=r'{upx_dir}',
    runtime_tmpdir=None,
    console=False,  # GUI mode, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon={icon_expr},
)
"""
    with open(SPEC_FILE, "w", encoding="utf-8") as f:
        f.write(spec_content)
    return SPEC_FILE


def clean_build_dirs():
    """Clean previous build artifacts."""
    dirs_to_clean = [
        os.path.join(PROJECT_DIR, "build"),
        DIST_DIR,
    ]
    for dir_path in dirs_to_clean:
        if os.path.exists(dir_path):
            print(f"🗑 Cleaning: {dir_path}")
            shutil.rmtree(dir_path, ignore_errors=True)


def get_folder_size(path):
    """Get folder size in MB."""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total_size += os.path.getsize(fp)
    return total_size / (1024 * 1024)


def build():
    print("=" * 60)
    print("🔨 PBDevHelper - Build Process")
    print("=" * 60)
    
    # Step 1: Check UPX
    print("\n📦 Step 1/4: Checking UPX...")
    upx_path = check_upx()
    
    # Step 2: Clean previous builds
    print("\n🧹 Step 2/4: Cleaning build directories...")
    clean_build_dirs()
    
    # Step 3: Generate spec file
    print("\n📝 Step 3/4: Generating .spec file...")
    spec = create_spec(upx_path)
    print(f"   Spec: {spec}")
    
    # Step 4: Run PyInstaller
    print("\n🚀 Step 4/4: Running PyInstaller...")
    try:
        subprocess.run(
            ["pyinstaller", "--clean", "--noconfirm", spec],
            cwd=PROJECT_DIR,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build failed with exit code {e.returncode}")
        sys.exit(1)
    
    # Post-build summary
    print("\n" + "=" * 60)
    print("✅ Build Complete!")
    print("=" * 60)
    
    # PyInstaller outputs to dist/ root by default (not dist/PBDevHelper/)
    exe_path = os.path.join(PROJECT_DIR, "dist", "PBDevHelper.exe")
    
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        
        print(f"\n📁 Output Directory: {os.path.join(PROJECT_DIR, 'dist')}")
        print(f"🎯 Executable: PBDevHelper.exe ({size_mb:.2f} MB)")
        
        if upx_path:
            print(f"   └─ Compressed with UPX ✅")
        else:
            print(f"   └─ No compression applied ⚠️")
        
        print(f"\n🚀 Run: {exe_path}")
        print("\n💡 Tips:")
        print("   - Ensure dist/worker/python.exe (32-bit) exists")
        print("   - Ensure tools/pbpicker/pb_picker.exe exists")
        print("   - Test on a clean Windows environment before deployment")
    else:
        print(f"\n❌ Executable not found: {exe_path}")
        print("   Check build logs for errors.")
        sys.exit(1)


if __name__ == "__main__":
    build()

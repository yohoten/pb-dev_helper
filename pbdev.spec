# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hidden_imports = []
for pkg in ['gui', 'orca', 'models', 'utils', 'scripts']:
    hidden_imports.extend(collect_submodules(pkg))

a = Analysis(
    ['main.py'],
    pathex=[r'F:\（8）Desktop\Files\Script_plugin\pb-dev-helper'],
    binaries=[],
    datas=[
        ("dist/worker/*", "dist/worker"),
        ("tools/pbpicker/*", "tools/pbpicker"),
    ],
    hiddenimports=hidden_imports + ['tkinter', 'tkinter.ttk', 'tkinter.filedialog',
                                     'tkinter.messagebox', 'tkinter.simpledialog'],
    hookspath=[],
    hooksconfig={},
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
    upx=True,
    upx_exclude=[],
    upx_dir=r'H:\UPX',
    runtime_tmpdir=None,
    console=False,  # GUI mode, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'F:\（8）Desktop\Files\Script_plugin\pb-dev-helper\pb-dev-helper.ico',
)

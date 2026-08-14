# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Python packages (recursive copy)
        ('gui', 'gui'),
        ('models', 'models'),
        ('orca', 'orca'),
        ('scripts', 'scripts'),
        ('utils', 'utils'),
        
        # Configuration file
        ('pbdev_config.json', '.'),
        
        # External tools directory (PBPicker and dependencies)
        ('tools', 'tools'),
    ],
    hiddenimports=[
        # Tkinter modules
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.simpledialog',
        
        # Standard library modules (explicitly included for safety)
        'json',
        'subprocess',
        'threading',
        'socket',
        'struct',
        'time',
        'os',
        'sys',
        'logging',
        'dataclasses',
        're',
        'ctypes',
        'ctypes.wintypes',
        'collections.abc',
        'argparse',
        'shutil',
        'pathlib',
        'typing',
        
        # Project-specific modules (ensure all are discovered)
        'gui.app',
        'gui.widgets',
        'gui.settings_tab',
        'gui.browse_tab',
        'gui.import_tab',
        'models.config',
        'models.enums',
        'orca.rpc_client',
        'orca.json_rpc',
        'orca.session',
        'utils.log',
        'utils.pb_path',
        'utils.pbt_parser',
        'scripts.orca_worker',
        'scripts.setup_worker',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'test',
        'unittest',
        'doctest',
        'pydoc',
        'pdb',
        'profile',
        'cProfile',
    ],
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
    runtime_tmpdir=None,
    console=False,  # Set to False for GUI-only application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='pb-dev-helper.ico',  # Application icon
)

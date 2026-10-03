# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

# Resolve main.py from the repository root, not from packaging/.
PROJECT_ROOT = Path(SPECPATH).resolve().parent
ENTRY = str(PROJECT_ROOT / 'main.py')
VERSION_FILE = str(PROJECT_ROOT / 'packaging' / 'version_info.txt')

hiddenimports = collect_submodules('PySide6.QtMultimedia')

a = Analysis(
    [ENTRY],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Junba_KTV_MultiTrack_v1.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    version=VERSION_FILE,
)

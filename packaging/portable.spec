# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

# PyInstaller executes a .spec relative to the directory that contains the spec.
# Resolve the real repository root explicitly so GitHub Actions can always find main.py.
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
    [],
    exclude_binaries=True,
    name='Junba_KTV_MultiTrack_v1.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    version=VERSION_FILE,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Junba_KTV_MultiTrack_v1.0_Portable',
)

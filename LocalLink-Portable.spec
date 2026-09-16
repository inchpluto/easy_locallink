# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['desktop_entry.py'],
    pathex=[],
    binaries=[],
    datas=[('locallink\\static', 'locallink\\static'), ('assets\\locallink.ico', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
import sys
sys.path.insert(0, SPECPATH)
from packaging_runtime import fix_windows_runtime
a.binaries = fix_windows_runtime(a.binaries)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LocalLink-Portable',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\locallink.ico'],
)

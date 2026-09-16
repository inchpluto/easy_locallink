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
    pyz, a.scripts, [], exclude_binaries=True, name='LocalLink-2.4.4',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    console=False, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon=['assets\\locallink.ico'],
)
coll = COLLECT(
    exe, a.binaries, a.datas, strip=False, upx=True, upx_exclude=[],
    name='LocalLink-2.4.4',
)

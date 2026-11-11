# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['../animlightify.py', '../gui.py', '../tdetect.py', '../../tagfile.py', '../../utils.py'],
    pathex=[],
    binaries=[],
    datas=[('../VERSION', '.'), ('../res/logo.ico', 'res')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Animlightify',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    hide_console='hide-late',
    icon=['../res/logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='animlightify',
)

# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Weblint desktop app (native window via pywebview).

Build locally:
  pip install -r requirements-desktop.txt pyinstaller
  pyinstaller weblint.spec

Output:
  Windows/Linux: dist/weblint(.exe)
  macOS:         dist/Weblint.app  (and dist/weblint)
"""
import os
import sys

block_cipher = None
root = os.path.abspath(SPECPATH)
icon_ico = os.path.join(root, 'static', 'weblint.ico')
icon_icns = os.path.join(root, 'static', 'weblint.icns')

a = Analysis(
    ['desktop.py'],
    pathex=[root],
    binaries=[],
    datas=[
        (os.path.join(root, 'templates'), 'templates'),
        (os.path.join(root, 'static'), 'static'),
    ],
    hiddenimports=[
        'flask_sqlalchemy',
        'flask_login',
        'sqlalchemy.sql.default_comparator',
        'webview',
        'webview.platforms',
        # Platform backends (only the matching one is used at runtime).
        'webview.platforms.winforms',
        'webview.platforms.edgechromium',
        'webview.platforms.cocoa',
        'webview.platforms.gtk',
    ],
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

# Windowed build: no console flash on Windows/macOS double-click.
# Errors are written to data/weblint.log by desktop.py.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='weblint',
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
    # Embedded .exe icon (Windows Explorer / taskbar when frozen).
    icon=icon_ico if os.path.isfile(icon_ico) else None,
)

# Proper double-clickable bundle on macOS (hides the Terminal).
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='Weblint.app',
        icon=icon_icns if os.path.isfile(icon_icns) else None,
        bundle_identifier='com.photoncody.weblint',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'CFBundleName': 'Weblint',
            'CFBundleDisplayName': 'Weblint',
        },
    )

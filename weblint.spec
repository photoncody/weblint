# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Weblint standalone binaries.

Build locally:
  pip install -r requirements.txt pyinstaller
  pyinstaller weblint.spec

Output lands in dist/weblint (or dist/weblint.exe on Windows).
"""
import os

block_cipher = None
root = os.path.abspath(SPECPATH)

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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

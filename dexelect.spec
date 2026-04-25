# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files

# customtkinter bundles its own assets (themes, fonts, icons) that must be
# included explicitly — PyInstaller won't find them via import analysis alone.
ctk_datas = collect_data_files('customtkinter')

datas = [
    ('config',         'config'),
    ('data',           'data'),
    ('assets/sprites', 'assets/sprites'),
] + ctk_datas

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['customtkinter', 'PIL._tkinter_finder'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='dexelect',
    debug=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='dexelect',
)

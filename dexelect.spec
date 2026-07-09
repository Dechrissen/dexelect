# -*- mode: python ; coding: utf-8 -*-
import os

datas = [
    ('config',         'config'),
    ('data',           'data'),
    ('assets/sprites', 'assets/sprites'),
    ('assets/icons',   'assets/icons'),
    ('assets/logo',    'assets/logo'),
    ('ui/gui/help.md',             'ui/gui'),
    ('ui/gui/tooltips.yaml',       'ui/gui'),
    ('ui/gui/export_template.txt', 'ui/gui'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['PIL._tkinter_finder'],
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
    icon='assets/icons/dexelect.ico',
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

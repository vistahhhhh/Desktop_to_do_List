# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec 文件 - 桌面待办小应用（onedir 模式，启动更快）"""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('app图标.ico', '.')],
    hiddenimports=[
        'sqlalchemy.dialects.sqlite',
        'PyQt5.sip',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtNetwork',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'pillow',
        'tkinter', '_tkinter', 'unittest', 'pytest',
        'IPython', 'notebook', 'sphinx',
        'setuptools', 'pkg_resources', 'distutils',
        'xml.etree', 'xmlrpc', 'pydoc', 'doctest',
        'argparse', 'pdb', 'profile', 'pstats',
        'PyQt5.QtSvg', 'PyQt5.QtXml',
        'PyQt5.QtTest', 'PyQt5.QtMultimedia', 'PyQt5.QtWebEngine',
        'PyQt5.QtWebEngineWidgets', 'PyQt5.QtQuick', 'PyQt5.QtQml',
        'PyQt5.QtBluetooth', 'PyQt5.QtNfc', 'PyQt5.QtSensors',
        'PyQt5.QtSerialPort', 'PyQt5.QtSql', 'PyQt5.QtHelp',
        'PyQt5.QtDesigner', 'PyQt5.QtOpenGL', 'PyQt5.QtPositioning',
        'PyQt5.QtLocation', 'PyQt5.QtWebSockets', 'PyQt5.QtWebChannel',
        'PyQt5.QtPrintSupport',
    ],
    noarchive=False,
    optimize=2,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='桌面待办',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='app图标.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='桌面待办',
)

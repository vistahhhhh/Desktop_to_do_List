# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec 文件 - 桌面待办（纯净 venv 版，极致精简）"""

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
        # ---------- 科学计算 / 数据 ----------
        'matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'pillow',

        # ---------- 开发 / 测试工具 ----------
        'tkinter', '_tkinter', 'unittest', 'pytest',
        'IPython', 'notebook', 'sphinx',
        'setuptools', 'pkg_resources', 'distutils',
        'xml.etree', 'xmlrpc', 'pydoc', 'doctest',
        'argparse', 'pdb', 'profile', 'pstats',

        # ---------- 不需要的 PyQt5 模块 ----------
        'PyQt5.QtSvg', 'PyQt5.QtXml',
        'PyQt5.QtTest', 'PyQt5.QtMultimedia', 'PyQt5.QtWebEngine',
        'PyQt5.QtWebEngineWidgets', 'PyQt5.QtQuick', 'PyQt5.QtQml',
        'PyQt5.QtBluetooth', 'PyQt5.QtNfc', 'PyQt5.QtSensors',
        'PyQt5.QtSerialPort', 'PyQt5.QtSql', 'PyQt5.QtHelp',
        'PyQt5.QtDesigner', 'PyQt5.QtOpenGL', 'PyQt5.QtPositioning',
        'PyQt5.QtLocation', 'PyQt5.QtWebSockets', 'PyQt5.QtWebChannel',
        'PyQt5.QtPrintSupport', 'PyQt5.QtPdf', 'PyQt5.QtQmlModels',
        'PyQt5.QtDBus', 'PyQt5.QtVirtualKeyboard',
        'PyQt5.QtRemoteObjects',
        'PyQt5.QtTextToSpeech', 'PyQt5.QtChart',
        'PyQt5.QtDataVisualization', 'PyQt5.Qt3DCore',
        'PyQt5.Qt3DRender', 'PyQt5.Qt3DInput', 'PyQt5.Qt3DExtras',
    ],
    noarchive=False,
    optimize=2,
    cipher=block_cipher,
)

# ---------- 二进制过滤：排除不需要的大体积 DLL ----------
_exclude_dlls = {
    'opengl32sw.dll',       # 软件 OpenGL 渲染后备
    'libGLESv2.dll',        # OpenGL ES
    'd3dcompiler_47.dll',   # DirectX 编译器
    'libEGL.dll',           # EGL
}

a.binaries = [
    (name, path, typ)
    for name, path, typ in a.binaries
    if Path(path).name.lower() not in {x.lower() for x in _exclude_dlls}
]

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
    name='桌面待办_venv',
)

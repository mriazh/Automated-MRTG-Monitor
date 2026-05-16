# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file untuk MRTG Live Monitor.
Mode: ONEFILE — Semua library dibundel ke dalam satu file .exe.
Build command:  pyinstaller mrtg_monitor.spec
"""

import os

block_cipher = None

PROJECT_DIR = os.path.abspath('.')

a = Analysis(
    ['mrtg_monitor.py'],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=[
        # Bundle file konfigurasi contoh dan graph title
        ('GRAPH-TITLE-MRTG.txt', '.'),
        ('.env.example', '.'),
    ],
    hiddenimports=[
        'helpers',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.common.by',
        'selenium.webdriver.common.keys',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'webdriver_manager',
        'webdriver_manager.chrome',
        'ntplib',
        'dotenv',
        'requests',
        'certifi',
        'urllib3',
        'charset_normalizer',
        'idna',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude modul besar yang tidak dipakai agar ukuran exe lebih kecil
        'matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'Pillow',
        'tkinter', '_tkinter',
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets',
        'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DInput',
        'PySide6.QtBluetooth', 'PySide6.QtDBus', 'PySide6.QtDesigner',
        'PySide6.QtHelp', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
        'PySide6.QtNetwork', 'PySide6.QtNfc', 'PySide6.QtOpenGL',
        'PySide6.QtPositioning', 'PySide6.QtPrintSupport',
        'PySide6.QtRemoteObjects', 'PySide6.QtScxml', 'PySide6.QtSensors',
        'PySide6.QtSerialPort', 'PySide6.QtSql', 'PySide6.QtSvg',
        'PySide6.QtTest', 'PySide6.QtWebChannel', 'PySide6.QtWebEngine',
        'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebSockets', 'PySide6.QtXml',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ONEFILE mode — semua dibundel ke satu file .exe
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MRTG-Live-Monitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,  # True agar log tetap terlihat di terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

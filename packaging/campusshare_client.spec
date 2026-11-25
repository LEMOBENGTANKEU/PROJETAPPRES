# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CampusShare Flet desktop client.

Build from repository root:
  python -m PyInstaller packaging/campusshare_client.spec --noconfirm
"""

from pathlib import Path

block_cipher = None
root = Path(SPECPATH).resolve().parent

datas = [
    (str(root / "assets"), "assets"),
    (str(root / "config"), "config"),
]
# Include backend schema/docs only if needed at runtime; client does not require backend package.

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "flet",
        "flet_desktop",
        "websockets",
        "services.webrtc_media_service",
        "aiortc",
        "av",
        "cv2",
        "mss",
        "numpy",
        "sounddevice",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["backend", "tests"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CampusShare",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CampusShare",
)

# PyInstaller spec for CrateSort beta packaging.
# Build from the _dev directory with:
#   pyinstaller packaging/CrateSort.spec --noconfirm --clean

import os

from PyInstaller.utils.hooks import collect_data_files

ROOT = os.path.abspath(os.path.join(os.path.dirname(SPEC), '..'))

block_cipher = None

a = Analysis(
    [os.path.join(ROOT, 'packaging', 'run_app.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'cratesort', 'assets'), 'cratesort/assets'),
        *collect_data_files('imageio_ffmpeg'),
    ],
    hiddenimports=[
        'PyQt6.QtSvgWidgets',
        'PyQt6.QtSvg',
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        # Spawned by the library scan in a separate process — make sure the
        # worker entry point and its deps are in the bundle.
        'cratesort.src.core.parallel_tag_reader',
        'cratesort.src.core.scan_worker_proc',
        # Spawned by audio playback in a separate process (freeze-proofing
        # against a stalling drive, same reasoning as the scan worker above).
        # Only the worker entry point needs listing — it's the one reached
        # via a runtime string import that PyInstaller's static analysis
        # misses; playback_worker.py itself is a normal top-level import
        # from playback_controller.py, already followed automatically.
        'cratesort.src.core.playback_worker_proc',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CrateSort',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, 'cratesort', 'assets', 'icons', 'app', 'CrateSort.icns'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CrateSort',
)

app = BUNDLE(
    coll,
    name='CrateSort.app',
    icon=os.path.join(ROOT, 'cratesort', 'assets', 'icons', 'app', 'CrateSort.icns'),
    bundle_identifier='com.jwbc.cratesort',
    info_plist={
        'CFBundleName': 'CrateSort',
        'CFBundleDisplayName': 'CrateSort',
        'CFBundleShortVersionString': '0.1.5',
        'CFBundleVersion': '0.1.5',
        'NSHumanReadableCopyright': 'Copyright © 2026 JWBC, LLC. All rights reserved.',
        'NSHighResolutionCapable': True,
    },
)

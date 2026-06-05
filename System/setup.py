#!/usr/bin/env python3
"""
System/setup.py — py2app build recipe for SIFTA.app (Alice, desktop v0.1+).

Reproducible recipe for the bundle that already ships at System/dist/SIFTA.app
(id com.anton.sifta, SIFTA 0.1.0, min macOS 12, camera/mic TCC strings). Until
now the recipe only lived as prose in SIFTA_APP_README.md; this file commits it
so the .app + .dmg rebuild the same way every time (no double-spend of a body).

Run on macOS, from the System/ directory:

    cd /Users/ioanganton/Music/ANTON_SIFTA/System
    python3 -m pip install py2app
    python3 setup.py py2app          # -> System/dist/SIFTA.app

Then wrap it into a distributable disk image:

    ./build_sifta_dmg.sh             # -> System/dist/SIFTA.dmg

Models are intentionally NOT bundled. The living organism pulls its weights
locally via ollama; the app stays ~90 MB and the swimmers stay on the host
hardware they are bound to.
"""
from setuptools import setup

APP = ["sifta_app.py"]

# The pywebview HTML surface ships beside the binary.
DATA_FILES = [
    "sifta_app_ui.html",
]

# Matches the shipped Info.plist exactly so rebuilds do not drift.
PLIST = {
    "CFBundleName": "SIFTA",
    "CFBundleDisplayName": "SIFTA",
    "CFBundleIdentifier": "com.anton.sifta",
    "CFBundleVersion": "0.1.0",
    "CFBundleShortVersionString": "0.1.0",
    "LSMinimumSystemVersion": "12.0",
    "NSHighResolutionCapable": True,
    # macOS shows these strings when Alice asks for the camera / microphone.
    "NSCameraUsageDescription": "SIFTA reads the camera when you explicitly enable it.",
    "NSMicrophoneUsageDescription": "SIFTA listens when you explicitly enable it.",
    "NSHumanReadableCopyright": "(c) 2026 Ioan Anton. SIFTA / Alice.",
}

OPTIONS = {
    "argv_emulation": False,
    "plist": PLIST,
    # py2app's modulegraph follows imports from sifta_app.py automatically.
    # This list only covers modules it cannot see statically (lazy / dynamic
    # imports). If a launch fails with ModuleNotFoundError, add the named
    # module here and rebuild — that is the normal py2app tightening loop.
    "includes": [
        "webview",
        "swarm_tool_router",
        "swarm_terminal_organ",
        "swarm_file_organ",
        "swarm_web_organ",
        "swarm_stgm_billing",
        "swarm_tab_consciousness",
        "swarm_doctor_mailbox",
    ],
    # Heavy ML deps the deterministic v0.1 surface does not import. Alice loads
    # her cortex (gemma4) at runtime through ollama, not from the bundle. If a
    # build ever needs one of these, delete it from this list and rebuild.
    "excludes": [
        "torch",
        "tensorflow",
        "mlx",
        "mlx_vlm",
        "transformers",
        "tkinter",
        "matplotlib",
    ],
}

setup(
    app=APP,
    name="SIFTA",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)

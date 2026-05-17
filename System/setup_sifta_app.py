"""
setup_sifta_app.py — py2app bundler for SIFTA v0.1.

Produces /Users/ioanganton/Music/ANTON_SIFTA/System/dist/SIFTA.app
that you can double-click. Unsigned (no notarization) so it'll show
the "downloaded from internet" Gatekeeper prompt on first launch —
right-click → Open once, then it's trusted.

Install once:
    pip3 install py2app

Build:
    cd /Users/ioanganton/Music/ANTON_SIFTA/System
    python3 setup_sifta_app.py py2app

Result:
    dist/SIFTA.app  — drag to /Applications or double-click in place.

To rebuild after editing sifta_app.py:
    rm -rf build dist
    python3 setup_sifta_app.py py2app
"""

import importlib.util
import sys
from pathlib import Path

from setuptools import setup

SYSTEM_DIR = Path(__file__).resolve().parent
REPO_ROOT = SYSTEM_DIR.parent
for path in (REPO_ROOT, SYSTEM_DIR):
    path_s = str(path)
    if path_s not in sys.path:
        sys.path.insert(0, path_s)

APP = [str(SYSTEM_DIR / "sifta_app.py")]
DATA_FILES = [str(SYSTEM_DIR / "sifta_app_ui.html")]

# Pull in the SIFTA modules sifta_app actually imports at runtime.
# Adding others is optional — they'll be picked up if the app imports
# them, but explicit listing prevents py2app from missing them.
CORE_MODULES = [
    # sifta_app.py inserts System/ into sys.path, so the py2app bundle
    # includes concrete organ modules by their top-level runtime names.
    "swarm_tool_router",
    "swarm_stgm_billing",
    "swarm_gemini_brain",
    "sifta_inference_defaults",
    "stgm_economy",
    "swarm_stigmergic_economy",
    "swarm_stgm_economy_body_audit",
    "swarm_terminal_organ",
    "swarm_file_organ",
    "swarm_web_organ",
    "swarm_tab_consciousness",
    "swarm_doctor_mailbox",
    "swarm_unified_log",
    "swarm_ledger_repair",
    "swarm_kernel_process_table",
    "swarm_skill_library",
    "swarm_skill_validator",
]


def _module_exists(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


INCLUDES = sorted({name for name in CORE_MODULES if _module_exists(name)})
PACKAGES = [name for name in ("webview",) if _module_exists(name)]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": None,                 # add 'sifta.icns' here when you have one
    "plist": {
        "CFBundleName": "SIFTA",
        "CFBundleDisplayName": "SIFTA",
        "CFBundleIdentifier": "com.anton.sifta",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        # Microphone / camera prompts only fire if SIFTA uses them; harmless to list.
        "NSCameraUsageDescription": "SIFTA reads the camera when you explicitly enable it.",
        "NSMicrophoneUsageDescription": "SIFTA listens when you explicitly enable it.",
    },
    "includes": INCLUDES,
    # Don't bundle pywebview's bottle server unless needed; small win.
    "excludes": ["System", "Kernel", "matplotlib", "numpy", "scipy", "tkinter"],
    "resources": DATA_FILES,
    # Bundle pywebview + pyobjc subpackages explicitly so py2app doesn't miss them.
    "packages": PACKAGES,
}

if __name__ == "__main__":
    setup(
        app=APP,
        data_files=DATA_FILES,
        options={"py2app": OPTIONS},
        setup_requires=["py2app"],
    )

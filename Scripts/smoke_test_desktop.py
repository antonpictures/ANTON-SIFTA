import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QThread
from pathlib import Path

# Add repo to python path
REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# CI environment overrides — must be set BEFORE any imports that read them.
# 1. Skip Alice's PortAudio microphone (which hangs in AUHAL on headless CI).
os.environ.setdefault("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", "1")
# 2. Use NullBackend for TTS so no 'say' subprocess is spawned.
os.environ.setdefault("SIFTA_VOICE_BACKEND", "null")
# 3. Skip Alice's boot-delay silent announcement.
os.environ.setdefault("SIFTA_ALICE_UNIFIED_BOOT_SILENT", "1")
# 4. Disable swarm mesh threads so no asyncio WebSocket worker runs.
os.environ.setdefault("SIFTA_DISABLE_MESH", "1")

from sifta_os_desktop import SiftaDesktop

def run_smoke_test():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    desktop = SiftaDesktop()
    desktop.show()

    # 1. Open Finance
    QTimer.singleShot(500,  lambda: print("[SMOKE] Opening Finance..."))
    QTimer.singleShot(600,  lambda: desktop.spawn_native_widget("Finance", "Applications/sifta_finance.py", "FinanceDashboard"))

    # 2. Open NLE
    QTimer.singleShot(1200, lambda: print("[SMOKE] Opening NLE..."))
    QTimer.singleShot(1300, lambda: desktop._trigger_manifest_app("SIFTA NLE"))

    # 3. Open File Navigator
    QTimer.singleShot(1900, lambda: print("[SMOKE] Opening File Navigator..."))
    QTimer.singleShot(2000, lambda: desktop._trigger_manifest_app("SIFTA File Navigator"))

    # 4. Open Alice (full widget lifecycle — GCI, TTS worker, child organs)
    QTimer.singleShot(2500, lambda: print("[SMOKE] Opening Alice..."))
    QTimer.singleShot(2600, lambda: desktop._trigger_manifest_app("Alice"))

    # 5. Clean Shutdown
    QTimer.singleShot(4000, lambda: print("[SMOKE] Initiating Clean Teardown..."))
    QTimer.singleShot(4200, desktop.close)
    QTimer.singleShot(5500, app.quit)  # 1.3s after close for thread teardown

    print("[SMOKE] Booting Mermaid OS Desktop...")

    # Drain any remaining mesh workers before app.exec() fully exits.
    def _pre_quit_drain():
        try:
            from System.global_cognitive_interface import drain_all_mesh_workers
            drain_all_mesh_workers(timeout_ms=2000)
        except Exception:
            pass

    app.aboutToQuit.connect(_pre_quit_drain)
    app.exec()

    print("[SMOKE] Clean exit.")
    sys.exit(0)

if __name__ == "__main__":
    run_smoke_test()

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from Applications.sifta_nle import NLEWindow
from sifta_os_desktop import _load_widget_class

_app = QApplication.instance()
if _app is None:
    _app = QApplication(sys.argv)

def test_nle_initialization():
    """Ensure the NLE Window instantiates properly and loads the base swarm variables."""
    widget = NLEWindow()
    
    assert widget.canvas is not None
    assert widget.canvas.rhythm_density == 80
    assert widget.canvas.chroma_density == 40
    assert widget.canvas.cut_threshold == 0.65


def test_desktop_loader_accepts_file_nle_module_path():
    assert _load_widget_class("Applications/sifta_nle.py", "NLEWindow").__name__ == "NLEWindow"


def test_desktop_loader_rejects_dotted_side_channel():
    try:
        _load_widget_class("Applications.sifta_nle", "NLEWindow")
    except RuntimeError as exc:
        assert "Applications/apps_manifest.json" in str(exc)
    else:
        raise AssertionError("dotted module path should not bypass the manifest entrypoint")

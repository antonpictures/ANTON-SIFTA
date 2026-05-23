import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from Applications.sifta_file_manager_widget import FileNavigatorWidget

_app = QApplication.instance()
if _app is None:
    _app = QApplication(sys.argv)

def test_file_navigator_initialization():
    """Ensure the File Navigator instantiates properly and dual panes are wired."""
    widget = FileNavigatorWidget()
    
    assert widget.left is not None
    assert widget.right is not None
    assert widget.left.current_dir() == str(REPO)
    assert widget.right.current_dir() == str(Path.home())
    
    # Test swapping
    widget._swap()
    assert widget.left.current_dir() == str(Path.home())
    assert widget.right.current_dir() == str(REPO)

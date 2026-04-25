import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from Applications.sifta_finance import FinanceDashboard

_app = QApplication.instance()
if _app is None:
    _app = QApplication(sys.argv)

def test_finance_dashboard_initialization():
    """Ensure the Finance Dashboard instantiates properly and tabs are wired."""
    widget = FinanceDashboard()
    
    assert widget.tabs is not None
    assert widget.tabs.count() == 3
    assert widget.portfolio_tab is not None
    assert widget.market_tab is not None
    assert widget.warren_tab is not None

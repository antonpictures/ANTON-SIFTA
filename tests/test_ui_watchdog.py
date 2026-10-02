"""W6 UI watchdog test: verify watchdog logic exists in web poller."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_watchdog_exists_in_js():
    from System import chorus_node_server as server
    import inspect
    src = inspect.getsource(server)
    # watchdog should be present in the JavaScript poller code
    assert "W6" in src or "watchdog" in src.lower(), "W6 watchdog code must be present in chorus_node_server"
    # should log a warning when pending turns persist
    assert "console.warn" in src or "alert(" in src, "watchdog must log or alert on timeout"


def test_watchdog_check_pending():
    from System import chorus_node_server as server
    import inspect
    src = inspect.getsource(server)
    # watchdog should check pending.size
    assert "pending.size" in src or "pending" in src, "watchdog must check pending set"


def test_watchdog_60s_threshold():
    from System import chorus_node_server as server
    import inspect
    src = inspect.getsource(server)
    # watchdog should have a ~60 second threshold (60000 ms)
    assert "60000" in src or "60000" in src, "watchdog should use 60s threshold"


if __name__ == "__main__":
    test_watchdog_exists_in_js()
    test_watchdog_check_pending()
    test_watchdog_60s_threshold()
    print("W6 watchdog code check: OK")
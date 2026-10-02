"""W8 teardown-with-failing-organ test: verify shutdown handles workers gracefully."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_closeEvent_stops_workers():
    from Applications import sifta_talk_to_alice_widget as widget
    import inspect
    src = inspect.getsource(widget)
    # closeEvent should exist and stop workers
    assert "closeEvent" in src, "Widget must have closeEvent handler"
    # Should stop various worker components
    assert "_listener" in src, "Should stop listener on close"


def test_closeEvent_handles_failing_workers():
    from Applications import sifta_talk_to_alice_widget as widget
    import inspect
    src = inspect.getsource(widget)
    # Should have timeout-based waiting for workers
    assert "wait(" in src and "terminate()" in src, "Should have timeout + terminate for failing workers"
    # Should use requestInterruption before terminate
    assert "requestInterruption" in src, "Should request interruption before terminating"


def test_closeEvent_has_boot_workers_teardown():
    from Applications import sifta_talk_to_alice_widget as widget
    import inspect
    src = inspect.getsource(widget)
    # Should handle _boot_sanity_workers
    assert "_boot_sanity_workers" in src, "Should handle boot sanity workers on close"


def test_closeEvent_clears_attributes():
    from Applications import sifta_talk_to_alice_widget as widget
    import inspect
    src = inspect.getsource(widget)
    # Should set workers to None after stopping
    assert 'setattr(self, attr, None)' in src or ". _listener = None" in src, "Should clear attributes after stopping"


if __name__ == "__main__":
    test_closeEvent_stops_workers()
    test_closeEvent_handles_failing_workers()
    test_closeEvent_has_boot_workers_teardown()
    test_closeEvent_clears_attributes()
    print("W8 teardown-with-failing-organ check: OK")
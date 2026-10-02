"""W7 deadline-abort test: verify brain watchdog timeout exists and has proper contract."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_watchdog_function_exists():
    from Applications import sifta_talk_to_alice_widget as widget
    assert hasattr(widget, "_brain_no_token_watchdog_s"), "Must have watchdog function"


def test_watchdog_returns_float():
    from Applications import sifta_talk_to_alice_widget as widget
    timeout = widget._brain_no_token_watchdog_s()
    assert isinstance(timeout, float), "Watchdog must return a float"
    assert timeout > 0, "Watchdog must return positive timeout"


def test_watchdog_respects_env():
    from Applications import sifta_talk_to_alice_widget as widget
    import os
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SIFTA_STATE_DIR"] = tmpdir
        os.environ["SIFTA_BRAIN_NO_TOKEN_TIMEOUT_S"] = "123.45"
        try:
            timeout = widget._brain_no_token_watchdog_s()
            assert timeout == 123.45, f"Env should override, got {timeout}"
        finally:
            os.environ.pop("SIFTA_BRAIN_NO_TOKEN_TIMEOUT_S", None)
            os.environ.pop("SIFTA_STATE_DIR", None)


def test_watchdog_mimo_alignment():
    from Applications import sifta_talk_to_alice_widget as widget
    import os
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SIFTA_STATE_DIR"] = tmpdir
        try:
            timeout = widget._brain_no_token_watchdog_s(model="mimo:")
            # Should align with cloud timeout, not use separate adaptive patience
            assert 30.0 <= timeout <= 600.0, f"MiMo should align within bounds, got {timeout}"
        finally:
            os.environ.pop("SIFTA_STATE_DIR", None)


def test_watchdog_comment_describes_problem():
    from Applications import sifta_talk_to_alice_widget as widget
    import inspect
    src = inspect.getsource(widget._brain_no_token_watchdog_s)
    assert "thinking" in src.lower(), "Should reference thinking state"
    assert "cortex" in src.lower() or "token" in src.lower(), "Should describe the problem"


if __name__ == "__main__":
    test_watchdog_function_exists()
    test_watchdog_returns_float()
    test_watchdog_respects_env()
    test_watchdog_mimo_alignment()
    test_watchdog_comment_describes_problem()
    print("W7 deadline-abort check: OK")
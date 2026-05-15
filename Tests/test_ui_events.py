import time
import sys
import pytest

try:
    from Quartz.CoreGraphics import CGEventCreateKeyboardEvent, CGEventPost, kCGHIDEventTap
    _HAS_QUARTZ = True
except ImportError:
    _HAS_QUARTZ = False

def _press_key(keycode, shift=False):
    # a basic keystroke poster
    if shift:
        # We would post shift down here, but let's just do base case
        pass
    down = CGEventCreateKeyboardEvent(None, keycode, True)
    up = CGEventCreateKeyboardEvent(None, keycode, False)
    CGEventPost(kCGHIDEventTap, down)
    time.sleep(0.01)
    CGEventPost(kCGHIDEventTap, up)

@pytest.mark.skipif(not _HAS_QUARTZ, reason="Quartz.CoreGraphics unavailable")
def test_press_key_smoke():
    """Smoke-test that CGEvent keystroke API is callable (no assertion on effect)."""
    _press_key(0)  # keycode 0 = 'a'

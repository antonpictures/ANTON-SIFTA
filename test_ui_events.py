import time
import sys
try:
    from Quartz.CoreGraphics import CGEventCreateKeyboardEvent, CGEventPost, kCGHIDEventTap
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)

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

print("Attempting to press 'a' (keycode 0)")
try:
    _press_key(0)
    print("Done (but did it actually type something?)")
except Exception as e:
    print(f"Failed: {e}")

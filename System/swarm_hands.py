#!/usr/bin/env python3
"""
System/swarm_hands.py — SIFTA Motor Effector for UI Control
══════════════════════════════════════════════════════════════════════════════
Allows Alice to physically interact with the macOS UI, typing on the keyboard
and moving/clicking the mouse. Powered by pyautogui.

Usage:
  python3 -m System.swarm_hands size
  python3 -m System.swarm_hands pos
  python3 -m System.swarm_hands move 500 500
  python3 -m System.swarm_hands click [x y]
  python3 -m System.swarm_hands type "Hello world"
  python3 -m System.swarm_hands press return
  python3 -m System.swarm_hands hotkey command space
"""

import sys
import argparse
import time

try:
    import pyautogui
    # Safety feature: fail-safe is moving the mouse to a corner
    pyautogui.FAILSAFE = True
    # Add a slight delay after all pyautogui calls to give UI time to react
    pyautogui.PAUSE = 0.5
except ImportError:
    print("UI automation library initializing (pip install pyautogui required).")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(prog="swarm_hands")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("size", help="Get screen resolution")
    sub.add_parser("pos", help="Get current mouse (x, y) coordinates")

    p_move = sub.add_parser("move", help="Move mouse to (x, y)")
    p_move.add_argument("x", type=int)
    p_move.add_argument("y", type=int)

    p_click = sub.add_parser("click", help="Click at current position or (x, y)")
    p_click.add_argument("x", type=int, nargs="?")
    p_click.add_argument("y", type=int, nargs="?")

    p_type = sub.add_parser("type", help="Type string like a human")
    p_type.add_argument("text", type=str)

    p_press = sub.add_parser("press", help="Press exactly one key (e.g. return, esc, tab)")
    p_press.add_argument("key", type=str)

    p_hotkey = sub.add_parser("hotkey", help="Press shortcut (e.g. command space)")
    p_hotkey.add_argument("keys", nargs="+", help="Keys to press together")

    args = parser.parse_args()

    try:
        if args.cmd == "size":
            w, h = pyautogui.size()
            print(f"Screen size: {w}x{h}")
        elif args.cmd == "pos":
            x, y = pyautogui.position()
            print(f"Mouse is at: {x}, {y}")
        elif args.cmd == "move":
            pyautogui.moveTo(args.x, args.y, duration=0.25)
            print(f"Moved to {args.x}, {args.y}")
        elif args.cmd == "click":
            if args.x is not None and args.y is not None:
                pyautogui.click(args.x, args.y)
                print(f"Clicked at {args.x}, {args.y}")
            else:
                pyautogui.click()
                print("Clicked current position")
        elif args.cmd == "type":
            pyautogui.write(args.text, interval=0.05)
            print(f"Typed: {args.text}")
        elif args.cmd == "press":
            pyautogui.press(args.key)
            print(f"Pressed: {args.key}")
        elif args.cmd == "hotkey":
            pyautogui.hotkey(*args.keys)
            print(f"Fired hotkey: {' + '.join(args.keys)}")
    except Exception as e:
        print(f"Error during UI action: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

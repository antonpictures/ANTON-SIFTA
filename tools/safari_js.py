#!/usr/bin/env python3
"""safari_js — run JavaScript in the owner's Safari, reliably.

Why this exists. The previous helper built AppleScript strings by hand and
escaped double quotes, so any non-trivial JavaScript silently returned nothing:
the escaping broke, `do JavaScript` raised, and the caller saw an empty string
and wrongly concluded the page had not rendered. Several conclusions today were
drawn from that bug.

The fix is two rules, both enforced here:
  1. The AppleScript is piped to `osascript` on STDIN, never through the shell,
     so shell quoting cannot corrupt it.
  2. All JavaScript is written with SINGLE quotes only. AppleScript string
     literals use double quotes, so single-quoted JS needs no escaping at all.

Also matches the pump.fun tab by HOST, not substring — matching on the substring
once selected a Google search ABOUT pump.fun, and always prefers the tab that
has actually rendered content.
"""
from __future__ import annotations

import json
import subprocess

PUMPFUN_HOSTS = ("https://pump.fun/", "https://www.pump.fun/")


def run_applescript(script: str, timeout: float = 90.0) -> tuple[bool, str]:
    """Run AppleScript with the script on stdin. Returns (ok, output_or_error)."""
    try:
        r = subprocess.run(["osascript"], input=script, capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        return False, err or f"exit {r.returncode}"
    return True, out


def js_in_pumpfun(js: str, timeout: float = 90.0) -> tuple[bool, str]:
    """Run single-quoted JS in the best pump.fun tab.

    Tab preference: the one whose body has the most rendered text, because a
    hard-navigated subpage can sit at ~77 characters while another tab holds the
    live application.
    """
    if '"' in js:
        return False, "JS must use single quotes only (see module docstring)"
    script = (
        'tell application "Safari"\n'
        '  set bestTab to missing value\n'
        '  set bestLen to -1\n'
        '  repeat with w in windows\n'
        '    repeat with t in tabs of w\n'
        '      set u to URL of t\n'
        '      if u starts with "https://pump.fun/" or u starts with "https://www.pump.fun/" then\n'
        '        set L to 0\n'
        '        try\n'
        "          set L to (do JavaScript \"document.body.innerText.length\" in t) as integer\n"
        '        end try\n'
        '        if L > bestLen then\n'
        '          set bestLen to L\n'
        '          set bestTab to t\n'
        '        end if\n'
        '      end if\n'
        '    end repeat\n'
        '  end repeat\n'
        '  if bestTab is missing value then return "NO_PUMPFUN_TAB"\n'
        f'  return (do JavaScript "{js}" in bestTab)\n'
        'end tell'
    )
    ok, out = run_applescript(script, timeout)
    if not ok:
        return False, out
    if out == "NO_PUMPFUN_TAB":
        return False, "no pump.fun tab open in Safari"
    return True, out


def navigate_pumpfun(url: str, timeout: float = 60.0) -> tuple[bool, str]:
    """Navigate the pump.fun tab that has the most content (the live app)."""
    script = (
        'tell application "Safari"\n'
        '  set bestTab to missing value\n'
        '  set bestLen to -1\n'
        '  repeat with w in windows\n'
        '    repeat with t in tabs of w\n'
        '      set u to URL of t\n'
        '      if u starts with "https://pump.fun/" or u starts with "https://www.pump.fun/" then\n'
        '        set L to 0\n'
        '        try\n'
        "          set L to (do JavaScript \"document.body.innerText.length\" in t) as integer\n"
        '        end try\n'
        '        if L > bestLen then\n'
        '          set bestLen to L\n'
        '          set bestTab to t\n'
        '        end if\n'
        '      end if\n'
        '    end repeat\n'
        '  end repeat\n'
        '  if bestTab is missing value then return "NO_PUMPFUN_TAB"\n'
        f'  set URL of bestTab to "{url}"\n'
        '  return "navigated"\n'
        'end tell'
    )
    return run_applescript(script, timeout)


def collect_text(limit: int = 400) -> list[str]:
    """All rendered text lines from the live pump.fun tab."""
    ok, out = js_in_pumpfun('document.body.innerText')
    if not ok:
        return []
    return [l.strip() for l in out.split("\n") if l.strip()][:limit]


def money_elements(limit: int = 150) -> list[str]:
    """Money-shaped text from every element, for virtualized lists that
    body.innerText does not include."""
    js = ('(function(){var o=[];var els=document.querySelectorAll(\'*\');'
          'for(var i=0;i<els.length;i++){var e=els[i];'
          'if(e.children.length===0){var t=(e.textContent||\'\').trim();'
          'if(t.length<48&&/[$%+]/.test(t))o.push(t);}}'
          'return JSON.stringify(o.slice(0,' + str(limit) + '));})()')
    ok, out = js_in_pumpfun(js)
    if not ok:
        return []
    try:
        v = json.loads(out)
        return [str(x) for x in v] if isinstance(v, list) else []
    except json.JSONDecodeError:
        return []


if __name__ == "__main__":
    ok, out = js_in_pumpfun('document.title + \' | \' + location.href')
    print("probe:", ok, out[:200])
    txt = collect_text(25)
    print(f"\nrendered lines: {len(txt)}")
    for l in txt[:25]:
        print("  ", l[:100])
    m = money_elements(30)
    print(f"\nmoney-shaped elements: {len(m)}")
    for v in m[:30]:
        print("  ", v)

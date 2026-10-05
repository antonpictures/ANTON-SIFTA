#!/usr/bin/env python3
"""External browser video pause/resume — browser-aware (computer-use awareness).

Truth label: EXTERNAL_BROWSER_PAUSE_V2

Knows WHICH browser is on and which one holds a playing video:
  - Safari            -> AppleScript `do JavaScript` (needs Develop > Allow JavaScript from Apple Events)
  - Chrome/Brave/Edge/Arc -> Chrome DevTools Protocol (needs --remote-debugging-port)
  - Firefox           -> reported as present but no effector (no JS bridge)

The owner may use any browser. Detection is not browser-specific: we enumerate every
running browser, read its tabs, find the one with a PLAYING <video>, and pause THAT one.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping, Optional

TRUTH_LABEL = "EXTERNAL_BROWSER_PAUSE_V2"

DEFAULT_CDP_PORT = 9222
LOCALHOST = "127.0.0.1"
FIELD_SEP = "|"

# Hard control kill switch. With SIFTA_BROWSER_CONTROL="0" NO effector may touch a real
# browser: unit tests, batch jobs and headless work must never be able to freeze or start
# the owner's video as a side effect. (Regression: a test dummy reached a real effector
# and froze George's live podcast mid-episode.) Reads stay live — awareness, picking and
# snapshot probing are unaffected, so tests can still assert against the real machine.
CONTROL_ENV = "SIFTA_BROWSER_CONTROL"


def browser_control_enabled() -> bool:
    """False when this process has disabled real browser control."""
    return os.environ.get(CONTROL_ENV, "1").strip() != "0"

# Browsers we can detect. effector: how we reach into it.
BROWSER_PROFILES: dict[str, dict[str, Any]] = {
    "Safari": {"effector": "applescript_js", "cdp_port": None},
    "Google Chrome": {"effector": "cdp", "cdp_port": DEFAULT_CDP_PORT},
    "Google Chrome Canary": {"effector": "cdp", "cdp_port": DEFAULT_CDP_PORT},
    "Brave Browser": {"effector": "cdp", "cdp_port": DEFAULT_CDP_PORT},
    "Microsoft Edge": {"effector": "cdp", "cdp_port": DEFAULT_CDP_PORT},
    "Arc": {"effector": "cdp", "cdp_port": DEFAULT_CDP_PORT},
    "Chromium": {"effector": "cdp", "cdp_port": DEFAULT_CDP_PORT},
    "Firefox": {"effector": "none", "cdp_port": None},
    "Firefox Developer Edition": {"effector": "none", "cdp_port": None},
}

# No site list, no video list, no URL hints live here any more. Detection is generic by
# construction (see _JS_WALK below): any <video>/<audio> that is playing gets paused. George
# plays what he plays; there is nothing to keep up to date.


# --------------------------------------------------------------------------------------
# process / OS level awareness
# --------------------------------------------------------------------------------------

def _osascript(script: str, timeout_s: float = 12.0) -> str:
    """Run AppleScript from stdin, return stdout (stripped) or ''."""
    try:
        proc = subprocess.run(
            ["osascript", "-"],
            input=script,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if proc.returncode != 0:
            return ""
        return (proc.stdout or "").strip()
    except Exception:
        return ""


def running_browsers() -> list[str]:
    """Names of known browsers currently running."""
    out = []
    for name in BROWSER_PROFILES:
        try:
            r = subprocess.run(["pgrep", "-x", name], capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                out.append(name)
        except Exception:
            continue
    return out


def frontmost_app() -> str:
    """Name of the frontmost (focused) application."""
    return _osascript(
        'tell application "System Events" to get name of first process whose frontmost is true'
    )


# --------------------------------------------------------------------------------------
# Safari effector (AppleScript + do JavaScript)
# --------------------------------------------------------------------------------------

# JS returns '|'-joined fields; single-quotes only so it embeds safely in AppleScript.
#
# GENERIC BY CONSTRUCTION. We never name a site, a video id or a URL anywhere in this file.
# Anything that is <video> or <audio> is media: YouTube, Vimeo, Twitch, a podcast player, a
# bare <audio> tag, an embedded player inside a same-origin frame. If it is playing, Alice
# pauses it. Detection cannot go stale when George plays something nobody anticipated --
# there is no list to update.
#
# The walk order (document order, then same-origin iframes depth-first) is IDENTICAL for
# pause and for resume, so an index names the same element in both calls. That is what lets
# resume re-start EXACTLY the elements we stopped, and never anything else.
#
# Cross-origin iframes cannot be reached from page JS at all -- a browser security boundary,
# not a limitation of this code. The Chrome family can reach them per-frame over CDP.
_MAX_FRAME_DEPTH = 3
_JS_WALK = (
    "function W(doc,dep,out){"
    "var l=null;try{l=doc.querySelectorAll('video,audio');}catch(e){}"
    "if(l){for(var i=0;i<l.length;i++)out.push(l[i]);}"
    f"if(dep>={_MAX_FRAME_DEPTH})return;"
    "var f=null;try{f=doc.querySelectorAll('iframe');}catch(e){}"
    "if(!f)return;"
    "for(var j=0;j<f.length;j++){try{var cd=f[j].contentDocument;if(cd)W(cd,dep+1,out);}catch(e){}}"
    "}"
)

_SAFARI_INFO_JS = (
    "(function(){"
    + _JS_WALK +
    "var ms=[];W(document,0,ms);"
    "if(ms.length===0)return '0|||';"
    "var v=null,play=false;"
    "for(var i=0;i<ms.length;i++){if(!ms[i].paused&&!ms[i].ended){v=ms[i];play=true;break;}}"
    "if(!v){for(var k=0;k<ms.length;k++){if(!ms[k].ended){v=ms[k];break;}}}"
    "if(!v)v=ms[0];"
    "var t=Math.round((v.currentTime||0)*10)/10;"
    "var d=isFinite(v.duration)?Math.round(v.duration*10)/10:'';"
    "return ms.length+'|'+(play?0:1)+'|'+t+'|'+d;"
    "})()"
)

# Same wire format as _SAFARI_INFO_JS; kept because callers/tests may reference the old name.
_SAFARI_PROBE_JS = _SAFARI_INFO_JS

# Returns '1' if the tab has ANY playing (unpaused, unended) media, else '0'.
_SAFARI_PLAYING_JS = (
    "(function(){"
    + _JS_WALK +
    "var ms=[];W(document,0,ms);"
    "for(var i=0;i<ms.length;i++){if(!ms[i].paused&&!ms[i].ended)return '1';}"
    "return '0';"
    "})()"
)

# Pause EVERYTHING that is playing, not the first element we happen to find. One tab can hold
# several media elements (a video plus an ad track plus a background <audio>), and pausing one
# while another keeps playing is precisely the defect: Alice still speaks over the audio.
# Wire: ok|<was_playing>|<is_paused_now>|<t>|<d>|<csv of the indices we paused>
_SAFARI_PAUSE_JS = (
    "(function(){"
    + _JS_WALK +
    "var ms=[];W(document,0,ms);"
    "if(ms.length===0)return 'no_video|||||';"
    "var idx=[],was=0;"
    "for(var i=0;i<ms.length;i++){"
    "if(!ms[i].paused&&!ms[i].ended){was=1;try{ms[i].pause();idx.push(i);}catch(e){}}"
    "}"
    "var v=null;"
    "if(idx.length)v=ms[idx[0]];"
    "if(!v){for(var k=0;k<ms.length;k++){if(!ms[k].ended){v=ms[k];break;}}}"
    "if(!v)v=ms[0];"
    "var t=Math.round((v.currentTime||0)*10)/10;"
    "var d=isFinite(v.duration)?Math.round(v.duration*10)/10:'';"
    "return 'ok|'+was+'|1|'+t+'|'+d+'|'+idx.join(',');"
    "})()"
)


def _safari_resume_js(csv_indices: str) -> str:
    """Play back EXACTLY the media indices we paused -- nothing else, ever.

    Three refusals make this safe to run in George's real room:
      * skip anything that has ended;
      * skip anything already playing (it is not ours to touch);
      * skip anything that never actually played (currentTime == 0 means George had it
        deliberately stopped, so starting it would be a NEW sound, which pause-only must
        never cause).
    """
    nums = ",".join(x for x in str(csv_indices or "").split(",") if x.strip().isdigit())
    if not nums:
        nums = "-1"
    return (
        "(function(){"
        + _JS_WALK +
        "var ms=[];W(document,0,ms);"
        "var want=[" + nums + "];var n=0,first=null,res=[];"
        "for(var x=0;x<want.length;x++){"
        "var m=ms[want[x]];"
        "if(!m||m.ended)continue;"
        "if(!m.paused)continue;"
        "if(!(m.currentTime>0))continue;"
        "try{var p=m.play();if(p&&p.catch)p.catch(function(){});n++;res.push(want[x]);if(!first)first=m;}catch(e){}"
        "}"
        "var t=first?Math.round((first.currentTime||0)*10)/10:'';"
        "var d=(first&&isFinite(first.duration))?Math.round(first.duration*10)/10:'';"
        "return 'ok|'+(n?1:0)+'|'+(n?1:0)+'|'+t+'|'+d+'|'+res.join(',');"
        "})()"
    )


def _safari_tab_scan() -> list[dict[str, Any]]:
    """Enumerate every Safari tab with its video state.

    Returns [{window_index, tab_index, url, video_count, paused, current_time, duration, playing}]
    One osascript call for the whole browser.
    """
    script = f'''
tell application "Safari"
  set report to ""
  set wi to 0
  repeat with w in windows
    set wi to wi + 1
    set ti to 0
    repeat with t in tabs of w
      set ti to ti + 1
      set u to ""
      try
        set u to URL of t
      end try
      set vs to ""
      try
        set vs to do JavaScript "{_SAFARI_INFO_JS}" in t
      end try
      set report to report & wi & "{FIELD_SEP}" & ti & "{FIELD_SEP}" & u & "{FIELD_SEP}" & vs & linefeed
    end repeat
  end repeat
  return report
end tell
'''
    raw = _osascript(script)
    tabs: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split(FIELD_SEP)
        if len(parts) < 4:
            continue
        try:
            wi = int(parts[0]); ti = int(parts[1])
        except ValueError:
            continue
        url = parts[2]
        vstate = parts[3].split(FIELD_SEP)
        # vs looks like "1|0|1263.0|3991.5"; but url may contain '|'? unlikely; re-join safely
        vs = parts[3:]
        vs = FIELD_SEP.join(vs).split(FIELD_SEP)
        video_count = 0; paused: Optional[bool] = None; ct: Optional[float] = None; dur: Optional[float] = None
        if len(vs) >= 4:
            try:
                video_count = int(float(vs[0] or 0))
            except ValueError:
                video_count = 0
            if vs[1] in ("0", "1"):
                paused = vs[1] == "1"
            try:
                ct = float(vs[2]) if vs[2] else None
            except ValueError:
                ct = None
            try:
                dur = float(vs[3]) if vs[3] else None
            except ValueError:
                dur = None
        tabs.append({
            "browser": "Safari",
            "window_index": wi,
            "tab_index": ti,
            "url": url,
            "video_count": video_count,
            "paused": paused,
            "playing": (paused is False) if paused is not None else False,
            "current_time": ct,
            "duration": dur,
        })
    return tabs


def _safari_act(action: str, url_substring: str = "", indices: str = "") -> dict[str, Any]:
    """Pause/play the best Safari tab matching url_substring (or any media tab).

    `indices` is the csv of media indices we paused, used only by action='play' so resume
    touches exactly those elements.
    """
    if action == "pause":
        js = _SAFARI_PAUSE_JS
    elif action == "play":
        js = _safari_resume_js(indices)
    else:
        return {"ok": False, "action": action, "browser": "Safari", "reason": "bad_action"}

    match = url_substring.replace('"', "").replace("\\", "")
    script = f'''
tell application "Safari"
  set needle to "{match}"
  set best to missing value
  set bestScore to -1
  repeat with w in windows
    repeat with t in tabs of w
      set u to ""
      try
        set u to URL of t
      end try
      set sc to 0
      if needle is not "" and u contains needle then
        -- explicit URL match always wins (caller asked for THIS tab)
        set sc to 100
      else if needle is "" then
        set sc to 1
      end if
      -- No site is named here: any tab with media is a candidate, and the one that is
      -- actually PLAYING outranks every idle tab.
      try
        set isPlaying to do JavaScript "{_SAFARI_PLAYING_JS}" in t
        if isPlaying is "1" then set sc to sc + 10
      end try
      if sc > bestScore then
        try
          set probe to do JavaScript "{_SAFARI_INFO_JS}" in t
          if probe is not "0|||" then
            set bestScore to sc
            set best to t
          end if
        end try
      end if
    end repeat
  end repeat
  if best is missing value then return "no_video_tab"
  set r to do JavaScript "{js}" in best
  set u2 to ""
  try
    set u2 to URL of best
  end try
  return r & "{FIELD_SEP}" & u2
end tell
'''
    raw = _osascript(script)
    if not raw or raw == "no_video_tab":
        return {"ok": False, "action": action, "browser": "Safari", "reason": raw or "no_result"}

    parts = raw.split(FIELD_SEP)
    status = parts[0] if parts else ""
    was_paused = parts[1] if len(parts) > 1 else ""
    now_paused = parts[2] if len(parts) > 2 else ""
    ct = parts[3] if len(parts) > 3 else ""
    dur = parts[4] if len(parts) > 4 else ""
    csv = parts[5] if len(parts) > 5 else ""
    url = FIELD_SEP.join(parts[6:]) if len(parts) > 6 else ""

    def _f(x: str) -> Optional[float]:
        try:
            return float(x)
        except Exception:
            return None

    paused_indices = [int(x) for x in csv.split(",") if x.strip().isdigit()]

    return {
        "ok": status == "ok",
        "action": action,
        "browser": "Safari",
        "effector": "applescript_js",
        "was_paused": (was_paused == "1") if was_paused in ("0", "1") else None,
        "paused": (now_paused == "1") if now_paused in ("0", "1") else None,
        "current_time": _f(ct),
        "duration": _f(dur),
        # Which media elements this call actually touched. Empty means "nothing was playing",
        # which the caller must treat as a no-op, never as a success.
        "paused_indices": paused_indices,
        "media_count": len(paused_indices),
        "indices_csv": csv,
        "url": url,
        "reason": "" if status == "ok" else status,
    }


# --------------------------------------------------------------------------------------
# Chrome-family effector (CDP)
# --------------------------------------------------------------------------------------

def _port_is_open(host: str, port: int, timeout_s: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _cdp_targets(port: int) -> list[dict[str, Any]]:
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://{LOCALHOST}:{port}/json", timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data if isinstance(data, list) else []
    except Exception:
        return []


_CDP_VIDEO_JS = (
    "(function(){"
    + _JS_WALK +
    "var ms=[];W(document,0,ms);"
    "if(ms.length===0)return '0|||';"
    "var v=null,play=false;"
    "for(var i=0;i<ms.length;i++){if(!ms[i].paused&&!ms[i].ended){v=ms[i];play=true;break;}}"
    "if(!v){for(var k=0;k<ms.length;k++){if(!ms[k].ended){v=ms[k];break;}}}"
    "if(!v)v=ms[0];"
    "var t=Math.round((v.currentTime||0)*10)/10;"
    "var d=isFinite(v.duration)?Math.round(v.duration*10)/10:'';"
    "return ms.length+'|'+(play?0:1)+'|'+t+'|'+d;"
    "})()"
)


def _cdp_act(action: str, url_substring: str, port: int, indices: str = "") -> dict[str, Any]:
    """Pause/play the best Chrome-family tab matching url_substring.

    Uses the same effector-agnostic page JS as Safari: the media walk and the index-precise
    resume live in exactly one place, so the two effectors cannot drift apart.
    """
    if not _port_is_open(LOCALHOST, port):
        return {"ok": False, "action": action, "browser": "chromium", "reason": "cdp_port_closed"}

    targets = [t for t in _cdp_targets(port) if t.get("type") == "page"]
    if not targets:
        return {"ok": False, "action": action, "browser": "chromium", "reason": "no_cdp_targets"}

    needle = (url_substring or "").lower()
    best = None
    best_score = -1
    for t in targets:
        u = (t.get("url") or "").lower()
        # No site is named here: an explicit URL wins, otherwise any page is a candidate.
        sc = 3 if (needle and needle in u) else (1 if not needle else 0)
        if sc > best_score:
            best_score = sc
            best = t

    if best is None or best_score <= 0:
        return {"ok": False, "action": action, "browser": "chromium", "reason": "no_video_tab"}

    if action == "pause":
        js = _SAFARI_PAUSE_JS
    elif action == "play":
        js = _safari_resume_js(indices)
    else:
        return {"ok": False, "action": action, "browser": "chromium", "reason": "bad_action"}

    ws_url = best.get("webSocketDebuggerUrl")
    if not ws_url:
        return {"ok": False, "action": action, "browser": "chromium", "reason": "no_ws_url"}

    # stdlib transport (2026-10-05): the third-party `websocket` client is absent on
    # python3.14, the interpreter the body actually calls, so every Chrome pause used
    # to end at `websocket_client_missing`. Same protocol, no dependency.
    val = _cdp_eval(ws_url, js, timeout_s=10.0)
    if val is None:
        return {"ok": False, "action": action, "browser": "chromium", "reason": "cdp_error"}
    parts = str(val).split(FIELD_SEP)

    def _f(x: str) -> Optional[float]:
        try:
            return float(x)
        except Exception:
            return None

    status = parts[0] if parts else ""
    csv = parts[5] if len(parts) > 5 else ""
    paused_indices = [int(x) for x in csv.split(",") if x.strip().isdigit()]
    return {
        "ok": status == "ok",
        "action": action,
        "browser": "chromium",
        "effector": "cdp",
        "was_paused": (parts[1] == "1") if len(parts) > 1 and parts[1] in ("0", "1") else None,
        "paused": (parts[2] == "1") if len(parts) > 2 and parts[2] in ("0", "1") else None,
        "current_time": _f(parts[3]) if len(parts) > 3 else None,
        "duration": _f(parts[4]) if len(parts) > 4 else None,
        "paused_indices": paused_indices,
        "media_count": len(paused_indices),
        "indices_csv": csv,
        "url": best.get("url", ""),
        "reason": "" if status == "ok" else status,
    }


# --------------------------------------------------------------------------------------
# public: awareness + dispatch
# --------------------------------------------------------------------------------------

# Remembers the URL of the video we most recently paused, so resume targets the SAME tab
# instead of re-picking (which would grab a different, still-paused tab).
_last_pause_url: Optional[str] = None

# The exact set of tabs/media this organism silenced for the current utterance:
# [{"browser", "url", "indices", "media_count", "effector"}, ...].
# Resume replays exactly this set -- never a re-picked tab, never a media element that was
# already paused by the owner before Alice spoke.
_paused_targets: list[dict[str, Any]] = []


# --------------------------------------------------------------------------------------
# Reading the Chrome family's tabs over CDP (no third-party websocket client)
# --------------------------------------------------------------------------------------
# Two measured faults, both invisible until the port was finally open (2026-10-05):
#   * the CDP effector died on `import websocket` — python3.14 (the interpreter the
#     body calls) has no websocket-client, so Chrome could never be paused;
#   * `browser_awareness_snapshot()` scanned Safari only, so even with the port open
#     no Chrome tab could ever appear in `playing_tabs`, and `pause_only_if_playing()`
#     answered "nothing_playing" while George's video kept playing.
# The frame layer below is stdlib only: the organ stays sovereign on any interpreter.

def _recv_exact(sock, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise OSError("socket closed during CDP frame")
        buf += chunk
    return buf


def _ws_connect(ws_url: str, timeout_s: float = 6.0):
    """Minimal RFC6455 handshake. Returns a socket or raises."""
    import base64
    import urllib.parse

    u = urllib.parse.urlparse(ws_url)
    host = u.hostname or LOCALHOST
    port = int(u.port or 80)
    path = u.path or "/"
    sock = socket.create_connection((host, port), timeout=timeout_s)
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall(
        (
            "GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\n"
            "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n" % (path, host, port, key)
        ).encode()
    )
    head = b""
    while b"\r\n\r\n" not in head:
        chunk = sock.recv(4096)
        if not chunk:
            raise OSError("CDP closed during handshake")
        head += chunk
        if len(head) > 65536:
            raise OSError("CDP handshake too large")
    if b"101" not in head.split(b"\r\n")[0]:
        raise OSError("CDP refused the websocket upgrade")
    return sock


def _ws_send_text(sock, text: str) -> None:
    import struct

    payload = text.encode("utf-8")
    header = bytearray([0x81])
    n = len(payload)
    if n < 126:
        header.append(0x80 | n)
    elif n < 65536:
        header.append(0x80 | 126)
        header += struct.pack(">H", n)
    else:
        header.append(0x80 | 127)
        header += struct.pack(">Q", n)
    mask = os.urandom(4)
    header += mask
    sock.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))


def _ws_read_text(sock) -> str:
    import struct

    while True:
        b1, b2 = _recv_exact(sock, 2)
        opcode = b1 & 0x0F
        n = b2 & 0x7F
        if n == 126:
            n = struct.unpack(">H", _recv_exact(sock, 2))[0]
        elif n == 127:
            n = struct.unpack(">Q", _recv_exact(sock, 8))[0]
        payload = _recv_exact(sock, n) if n else b""
        if opcode == 0x1:
            return payload.decode("utf-8", "replace")
        if opcode == 0x8:
            raise OSError("CDP closed the websocket")
        # ping / pong / continuation: keep reading until a text frame arrives


def _cdp_eval(ws_url: Optional[str], expression: str, timeout_s: float = 6.0) -> Any:
    """Runtime.evaluate on one CDP page. Returns the value, or None on any failure."""
    if not ws_url:
        return None
    try:
        sock = _ws_connect(ws_url, timeout_s)
    except Exception:
        return None
    try:
        _ws_send_text(
            sock,
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expression, "returnByValue": True},
                }
            ),
        )
        for _ in range(12):
            msg = json.loads(_ws_read_text(sock))
            if msg.get("id") == 1:
                return ((msg.get("result") or {}).get("result") or {}).get("value")
        return None
    except Exception:
        return None
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _cdp_family_name() -> str:
    """Which Chrome-family app is up right now (its name is the BROWSER_PROFILES key)."""
    running = running_browsers()
    for name, profile in BROWSER_PROFILES.items():
        if profile.get("effector") == "cdp" and name in running:
            return name
    return "Google Chrome"


def _cdp_tab_scan(port: int = DEFAULT_CDP_PORT) -> list[dict[str, Any]]:
    """The Chrome family's tabs over CDP, in the same shape as the Safari scan."""
    tabs: list[dict[str, Any]] = []
    if not _port_is_open(LOCALHOST, port):
        return tabs
    name = _cdp_family_name()
    idx = 0
    for target in _cdp_targets(port):
        if target.get("type") != "page":
            continue
        url = target.get("url") or ""
        if url.startswith("devtools://") or url.startswith("chrome-extension://"):
            continue
        raw = _cdp_eval(target.get("webSocketDebuggerUrl"), _CDP_VIDEO_JS)
        video_count, paused, ct, dur = 0, None, None, None
        if isinstance(raw, str):
            parts = raw.split("|")
            if len(parts) >= 4:
                try:
                    video_count = int(float(parts[0] or 0))
                except ValueError:
                    video_count = 0
                if parts[1] in ("0", "1"):
                    paused = parts[1] == "1"
                try:
                    ct = float(parts[2]) if parts[2] else None
                except ValueError:
                    ct = None
                try:
                    dur = float(parts[3]) if parts[3] else None
                except ValueError:
                    dur = None
        tabs.append(
            {
                "browser": name,
                "window_index": 0,
                "tab_index": idx,
                "url": url,
                "title": target.get("title") or "",
                "video_count": video_count,
                "paused": paused,
                "playing": (paused is False) and video_count > 0,
                "current_time": ct,
                "duration": dur,
                "effector": "cdp",
            }
        )
        idx += 1
    return tabs


def browser_awareness_snapshot() -> dict[str, Any]:
    """Full computer-use picture: which browsers are on, which holds a playing video."""
    running = running_browsers()
    front = frontmost_app()
    tabs: list[dict[str, Any]] = []

    if "Safari" in running:
        tabs.extend(_safari_tab_scan())
    # Chrome-family tabs, read over CDP. Without this the co-watch Chrome was
    # invisible to the organ and every pause attempt answered "nothing_playing".
    if any((BROWSER_PROFILES.get(b) or {}).get("effector") == "cdp" for b in running):
        tabs.extend(_cdp_tab_scan(DEFAULT_CDP_PORT))

    snapshot = {
        "truth_label": TRUTH_LABEL,
        "running_browsers": running,
        "frontmost_app": front,
        "frontmost_is_browser": front in BROWSER_PROFILES,
        "video_tabs": [t for t in tabs if (t.get("video_count") or 0) > 0],
        "all_tabs": tabs,
        "cdp_port_open": _port_is_open(LOCALHOST, DEFAULT_CDP_PORT),
    }

    playing = [t for t in snapshot["video_tabs"] if t.get("playing")]
    snapshot["playing_tabs"] = playing
    snapshot["target"] = (playing[0] if playing else (snapshot["video_tabs"][0] if snapshot["video_tabs"] else None))
    return snapshot


def pick_video_browser(url_substring: str = "") -> dict[str, Any]:
    """Decide which browser currently owns a video worth pausing.

    Preference: frontmost browser with a PLAYING video > any PLAYING video >
    frontmost browser with a video > any video.
    """
    snap = browser_awareness_snapshot()
    tabs = snap["video_tabs"]
    if not tabs:
        return {"found": False, "reason": "no_video_tabs", "snapshot": snap}

    needle = (url_substring or "").lower()

    def matches(t: Mapping[str, Any]) -> bool:
        return (not needle) or (needle in (t.get("url") or "").lower())

    candidates = [t for t in tabs if matches(t)] or tabs
    playing = [t for t in candidates if t.get("playing")]
    front = snap["frontmost_app"]

    front_playing = [t for t in playing if t.get("browser") == front]
    if front_playing:
        chosen, why = front_playing[0], "frontmost_playing"
    elif playing:
        chosen, why = playing[0], "playing_video"
        if front_playing:
            chosen, why = front_playing[0], "frontmost_playing"
        else:
            front_videos = [t for t in candidates if t.get("browser") == front]
            if front_videos:
                chosen, why = front_videos[0], "frontmost_with_video"
    else:
        front_videos = [t for t in candidates if t.get("browser") == front]
        chosen, why = (front_videos[0], "frontmost_with_video") if front_videos else (candidates[0], "only_video_tab")

    return {"found": True, "why": why, "target": chosen, "snapshot": snap}


def pause_all_playing_videos(url_substring: str = "") -> dict[str, Any]:
    """Pause EVERY playing video/audio, in EVERY tab of EVERY browser.

    George's rule: "any video playing must be paused while she speaks". Pausing a single
    chosen tab is not enough -- if a second tab is playing, Alice still talks over it.
    So we do not pick a winner; we sweep every tab that is playing right now.

    For each target we remember the browser, the exact URL, and the exact media indices we
    paused, so `resume_all_paused` can undo precisely this set and nothing else.
    """
    if not browser_control_enabled():
        return {"ok": False, "action": "pause", "reason": "control_disabled", "browser": None, "url": ""}
    try:
        snap = browser_awareness_snapshot()
    except Exception as e:
        return {"ok": False, "action": "pause", "reason": "error", "browser": None, "url": "", "details": str(e)}

    playing = snap.get("playing_tabs") or []
    needle = (url_substring or "").lower()

    def _matches(t: Mapping[str, Any]) -> bool:
        return (not needle) or (needle in (t.get("url") or "").lower())

    targets = [t for t in playing if t.get("playing") and _matches(t)] or ([] if needle else list(playing))
    # Belt and braces: the snapshot already filters by `playing`, but the rule "never touch a
    # tab that is not playing" is enforced here too, at the point of action, because pausing a
    # stopped tab is what makes the paired resume START a video George had deliberately stopped.
    targets = [t for t in targets if t.get("playing")]
    if not targets:
        return {
            "ok": False,
            "action": "pause",
            "reason": "nothing_playing",
            "browser": None,
            "url": "",
            "playing_before": len(playing),
            "paused_targets": [],
            "frontmost_app": snap.get("frontmost_app"),
            "running_browsers": snap.get("running_browsers"),
        }

    paused: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for t in targets:
        browser = t.get("browser", "")
        url = t.get("url", "")
        if browser == "Safari":
            r = _safari_act("pause", url)
        elif BROWSER_PROFILES.get(browser, {}).get("effector") == "cdp":
            r = _cdp_act("pause", url, DEFAULT_CDP_PORT)
        else:
            r = {"ok": False, "browser": browser, "reason": "no_effector"}
        if r.get("ok") and r.get("paused_indices"):
            paused.append({
                "browser": browser,
                "url": r.get("url") or url,
                "indices": r.get("indices_csv", ""),
                "media_count": int(r.get("media_count") or 0),
                "effector": r.get("effector", ""),
            })
        else:
            failures.append({"url": url, "reason": str(r.get("reason") or "no_media_paused")})

    global _paused_targets, _last_pause_url
    if paused:
        _paused_targets = list(paused)
        _last_pause_url = paused[0]["url"]

    first = paused[0] if paused else {}
    return {
        "ok": bool(paused),
        "action": "pause",
        "browser": first.get("browser") or None,
        "url": first.get("url", ""),
        "effector": first.get("effector", ""),
        "tabs_paused": len(paused),
        "media_paused": sum(p["media_count"] for p in paused),
        "paused_targets": paused,
        "failed_targets": failures,
        "playing_before": len(playing),
        "reason": "" if paused else "no_media_paused",
        "chosen_why": "all_playing_tabs" if not needle else "all_playing_tabs_matching_hint",
        "frontmost_app": snap.get("frontmost_app"),
        "running_browsers": snap.get("running_browsers"),
    }


def pause_video_anywhere(url_substring: str = "") -> dict[str, Any]:
    """Pause every playing video/audio, wherever it is. (V1 name, now a full sweep.)"""
    return pause_all_playing_videos(url_substring)


def pause_only_if_playing(url_substring: str = "") -> dict[str, Any]:
    """Pause ONLY when a video is genuinely playing right now.

    Speech-path guard (r-browser-aware-pause-v3). `pick_video_browser` deliberately
    falls back to `frontmost_with_video` / `only_video_tab` when nothing is playing,
    so a bare `pause_video_anywhere()` can "pause" a tab the owner had already
    stopped. That is harmless by itself — but the resume half would then PLAY that
    tab, starting a video George deliberately paused. So: no playing video, no pause,
    no resume, owner's hand stays untouched.
    """
    try:
        snap = browser_awareness_snapshot()
        playing = snap.get("playing_tabs") or []
    except Exception as e:
        return {"ok": False, "action": "pause", "reason": "error", "browser": None, "details": str(e)}
    if not playing:
        return {
            "ok": False,
            "action": "pause",
            "reason": "nothing_playing",
            "browser": None,
            "playing_tabs": [],
        }
    receipt = pause_video_anywhere(url_substring)
    receipt["playing_before"] = len(playing)
    receipt["playing_url_before"] = playing[0].get("url", "")
    receipt["playing_urls_before"] = [t.get("url", "") for t in playing]
    # Every playing tab must be silent before she speaks. If any target refused, say so
    # instead of returning a bland ok -- a half-pause is exactly the bug George heard.
    receipt["all_playing_paused"] = bool(receipt.get("ok")) and not receipt.get("failed_targets")
    return receipt


def resume_all_paused() -> dict[str, Any]:
    """Restore exactly the set that `pause_all_playing_videos` silenced, and nothing else.

    The pause remembers (browser, url, indices) per tab, and resume replays that record, so
    it cannot resume a different tab and cannot start a media element the owner had stopped
    themselves -- the JS refuses any element that is already playing or has never played.
    """
    if not browser_control_enabled():
        return {"ok": False, "action": "play", "reason": "control_disabled", "browser": None, "url": ""}
    global _paused_targets, _last_pause_url
    targets = list(_paused_targets)
    if not targets:
        return {"ok": False, "action": "play", "reason": "nothing_to_resume", "browser": None,
                "url": "", "resumed_targets": []}

    resumed: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for t in targets:
        browser = t.get("browser", "")
        url = t.get("url", "")
        idx = t.get("indices", "")
        if browser == "Safari":
            r = _safari_act("play", url, idx)
        elif BROWSER_PROFILES.get(browser, {}).get("effector") == "cdp":
            r = _cdp_act("play", url, DEFAULT_CDP_PORT, idx)
        else:
            r = {"ok": False, "browser": browser, "reason": "no_effector"}
        if r.get("ok"):
            resumed.append({"browser": browser, "url": r.get("url") or url,
                            "media_resumed": int(r.get("media_count") or 0)})
        else:
            failures.append({"url": url, "reason": str(r.get("reason") or "resume_failed")})

    _paused_targets = []
    _last_pause_url = None
    first = resumed[0] if resumed else {}
    return {
        "ok": bool(resumed),
        "action": "play",
        "browser": first.get("browser") or None,
        "url": first.get("url", ""),
        "tabs_resumed": len(resumed),
        "media_resumed": sum(r["media_resumed"] for r in resumed),
        "resumed_targets": resumed,
        "failed_targets": failures,
        "reason": "" if resumed else "resume_failed",
    }


def resume_video_anywhere(url_substring: str = "") -> dict[str, Any]:
    """Resume whatever this organism paused for the utterance that is now ending.

    Preferred path: replay the recorded target set (exact tabs, exact media indices).
    Fallback path: only when we have positive evidence of a URL we paused -- a caller hint or
    the remembered `_last_pause_url`. With no evidence at all we refuse rather than pick a
    tab, because picking is what once started a video the owner had deliberately stopped.
    """
    if not browser_control_enabled():
        return {"ok": False, "action": "play", "reason": "control_disabled", "browser": None}

    recorded = resume_all_paused()
    if recorded.get("ok"):
        return recorded
    if recorded.get("reason") != "nothing_to_resume":
        # We had targets and every one of them failed; do not also try a blind re-pick.
        return recorded

    global _last_pause_url
    needle = url_substring or _last_pause_url or ""
    if not needle:
        return {"ok": False, "action": "play", "reason": "nothing_to_resume", "browser": None}

    pick = pick_video_browser(needle)
    if not pick.get("found"):
        return {"ok": False, "action": "play", "reason": pick.get("reason", "no_target"), "browser": None}

    tgt = pick["target"]
    browser = tgt.get("browser", "")
    url = tgt.get("url", "")

    if browser == "Safari":
        receipt = _safari_act("play", needle or url)
    elif BROWSER_PROFILES.get(browser, {}).get("effector") == "cdp":
        receipt = _cdp_act("play", needle or url, DEFAULT_CDP_PORT)
    else:
        receipt = {"ok": False, "action": "play", "browser": browser, "reason": "no_effector"}

    if receipt.get("ok"):
        _last_pause_url = None
    receipt["chosen_why"] = pick.get("why")
    receipt["frontmost_app"] = pick["snapshot"].get("frontmost_app")
    return receipt


# ---- backward-compatible aliases (V1 names) ----

def pause_external_video(url: str, port: int = DEFAULT_CDP_PORT) -> dict[str, Any]:
    """Browser-aware pause (url is a substring hint)."""
    return pause_video_anywhere(url)


def resume_external_video(url: str, port: int = DEFAULT_CDP_PORT) -> dict[str, Any]:
    """Browser-aware resume (url is a substring hint)."""
    return resume_video_anywhere(url)


def detect_external_video_tab(url: str = "", port: int = DEFAULT_CDP_PORT) -> dict[str, Any]:
    """Detect video tabs across every running browser."""
    snap = browser_awareness_snapshot()
    tabs = snap["video_tabs"]
    needle = (url or "").lower()
    if needle:
        tabs = [t for t in tabs if needle in (t.get("url") or "").lower()] or tabs
    return {
        "detected": len(tabs) > 0,
        "count": len(tabs),
        "targets": tabs,
        "running_browsers": snap["running_browsers"],
        "frontmost_app": snap["frontmost_app"],
    }


# --------------------------------------------------------------------------------------
# Enabling the port (owner command, 2026-10-05)
# --------------------------------------------------------------------------------------
# George: "ENABLE THE PORT — Chrome must be started with --remote-debugging-port
# (the organ has ensure_cdp_port() for exactly this)." He was right that the organ
# had the *check* and not the *doing*. Two facts decide how the doing must work here:
#
#   1. Launching Chrome again while Chrome is already running does NOT open the port:
#      the new invocation is forwarded to the running process and the flag is dropped.
#      So the port cannot be added, after the fact, to the instance already up.
#   2. Chrome refuses remote debugging on the *default* profile directory. Relaunching
#      George's own Chrome with the flag would therefore neither open the port nor
#      keep his windows — the worst of both.
#
# So the port needs its own instance with its own profile: a co-watch Chrome that
# Alice can actually reach. This never touches, restarts or closes the running Chrome.

_REPO = Path(__file__).resolve().parent.parent
COWATCH_PROFILE_DIR = _REPO / ".sifta_state" / "chrome_cowatch_profile"
_PAUSE_LEDGER = _REPO / ".sifta_state" / "external_browser_pause.jsonl"

_CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)


def chrome_binary() -> Optional[str]:
    """The Chrome-family binary to launch for CDP, or None if this Mac has none."""
    for path in _CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def _launch_ledger(row: dict[str, Any]) -> None:
    try:
        _PAUSE_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _PAUSE_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def ensure_cdp_port(
    port: int = DEFAULT_CDP_PORT,
    *,
    launch: bool = True,
    wait_s: float = 15.0,
    open_url: str = "",
) -> dict[str, Any]:
    """Chrome-family only. Safari needs no port.

    When the port is closed and `launch` is true, start the co-watch Chrome with
    `--remote-debugging-port` and its own `--user-data-dir`, then wait for the socket.
    Returns a receipt; every launch attempt is written to
    `.sifta_state/external_browser_pause.jsonl`. Never raises, never touches the
    owner's running Chrome.
    """
    if _port_is_open(LOCALHOST, port):
        return {"ok": True, "port": port, "status": "listening", "action": "none"}
    if not launch:
        return {
            "ok": False,
            "port": port,
            "status": "closed",
            "action": "none",
            "note": "not needed for Safari",
        }

    binary = chrome_binary()
    if not binary:
        receipt = {
            "ok": False,
            "port": port,
            "status": "closed",
            "action": "launch",
            "reason": "no_chrome_family_binary",
        }
        _launch_ledger({"ts": time.time(), "truth_label": TRUTH_LABEL, "event": "ensure_cdp_port", **receipt})
        return receipt

    argv = [
        binary,
        "--remote-debugging-port=%d" % port,
        "--user-data-dir=%s" % COWATCH_PROFILE_DIR,
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if open_url:
        argv.append(open_url)
    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as exc:
        receipt = {
            "ok": False,
            "port": port,
            "status": "closed",
            "action": "launch",
            "reason": "spawn_failed",
            "details": str(exc),
        }
        _launch_ledger({"ts": time.time(), "truth_label": TRUTH_LABEL, "event": "ensure_cdp_port", **receipt})
        return receipt

    deadline = time.time() + max(1.0, wait_s)
    while time.time() < deadline:
        if _port_is_open(LOCALHOST, port):
            receipt = {
                "ok": True,
                "port": port,
                "status": "listening",
                "action": "launched",
                "pid": proc.pid,
                "binary": binary,
                "profile": str(COWATCH_PROFILE_DIR),
                "note": "co-watch Chrome; the owner's own Chrome is untouched",
            }
            _launch_ledger({"ts": time.time(), "truth_label": TRUTH_LABEL, "event": "ensure_cdp_port", **receipt})
            return receipt
        time.sleep(0.5)

    receipt = {
        "ok": False,
        "port": port,
        "status": "closed",
        "action": "launched",
        "reason": "port_never_opened",
        "pid": proc.pid,
        "binary": binary,
        "profile": str(COWATCH_PROFILE_DIR),
        "waited_s": wait_s,
    }
    _launch_ledger({"ts": time.time(), "truth_label": TRUTH_LABEL, "event": "ensure_cdp_port", **receipt})
    return receipt


__all__ = [
    "TRUTH_LABEL",
    "BROWSER_PROFILES",
    "running_browsers",
    "frontmost_app",
    "browser_awareness_snapshot",
    "pick_video_browser",
    "pause_video_anywhere",
    "pause_all_playing_videos",
    "pause_only_if_playing",
    "resume_video_anywhere",
    "resume_all_paused",
    "pause_external_video",
    "resume_external_video",
    "detect_external_video_tab",
    "ensure_cdp_port",
]

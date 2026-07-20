#!/usr/bin/env python3
"""Probe MiMo-V2.5-Pro-UltraSpeed API wiring for Alice (r1273).

Reads the same credential paths as System/swarm_gemini_brain.py, posts one
short chat/completions call, and prints latency + tokens/s for the first receipt.

Usage:
    # after placing key in Documents/mimo_ultraspeed_api.key or env:
    python3 tools/probe_mimo_ultraspeed.py
    SIFTA_MIMO_ULTRASPEED_API_KEY=us-... python3 tools/probe_mimo_ultraspeed.py
    SIFTA_MIMO_ULTRASPEED_BASE_URL=https://api.xiaomimimo.com/v1 python3 tools/probe_mimo_ultraspeed.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from System.swarm_gemini_brain import (  # noqa: E402
    _MIMO_ULTRASPEED_MODEL_ID,
    _mimo_ultraspeed_credentials,
    _mimo_ultraspeed_wiring_error,
)


def main() -> int:
    key, base = _mimo_ultraspeed_credentials()
    if not key:
        print(_mimo_ultraspeed_wiring_error())
        return 2

    payload = {
        "model": _MIMO_ULTRASPEED_MODEL_ID,
        "messages": [{"role": "user", "content": "Say hi in one short sentence."}],
        "max_tokens": 64,
        "stream": False,
    }
    url = f"{base.rstrip('/')}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    print(f"POST {url}")
    print(f"model={_MIMO_ULTRASPEED_MODEL_ID}")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:800]
        print(f"HTTP {exc.code}: {err_body}")
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    latency_s = time.time() - t0
    data = json.loads(body)
    text = data["choices"][0]["message"]["content"].strip()
    usage = data.get("usage") or {}
    completion_t = int(usage.get("completion_tokens") or 0)
    total_t = int(usage.get("total_tokens") or 0)
    tps = completion_t / max(latency_s, 0.001)
    print(f"latency_s={latency_s:.2f}")
    print(f"completion_tokens={completion_t} total_tokens={total_t}")
    print(f"observed_tps={tps:.1f}")
    print(f"reply={text[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
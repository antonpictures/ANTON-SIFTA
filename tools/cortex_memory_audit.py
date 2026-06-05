#!/usr/bin/env python3
"""cortex_memory_audit.py — what's actually resident in RAM, and is it optimized?

George worried scout/classifier eat memory ("no double-spending swimmers is law").
The old dedicated `sifta-classifier-c1-3.1b-6.2gb` and
`alice-Q-m1-scout-2.3b-2.7gb` Ollama tags are retired; corvid_scout remains a
virtual/internal arm backed by the shared Gemma path.
This asks Ollama what is *currently loaded* (/api/ps: size, VRAM, unload time) and
what is installed (/api/tags), then prints the memory picture + how to tune it.
Pure stdlib. Run on the Mac with ollama up:  python3 tools/cortex_memory_audit.py
"""
from __future__ import annotations

import json
import sys
import urllib.request

PS = "http://localhost:11434/api/ps"
TAGS = "http://localhost:11434/api/tags"


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def _gb(n) -> float:
    return round((n or 0) / 1e9, 2)


def main() -> int:
    try:
        loaded = _get(PS).get("models", [])
        installed = _get(TAGS).get("models", [])
    except Exception as exc:
        print(f"could not reach ollama ({exc}); is `ollama` running?", file=sys.stderr)
        return 1

    print("=== LOADED RIGHT NOW (resident in unified memory) ===")
    if not loaded:
        print("  nothing loaded — all models cold. That's the ideal idle state.")
    resident = 0.0
    for m in loaded:
        size = _gb(m.get("size"))
        resident += size
        print(
            f"  {str(m.get('name'))[:45]:45s} {size:6.2f} GB"
            f"  (vram {_gb(m.get('size_vram')):.2f})  unloads_at={m.get('expires_at')}"
        )
    print(f"  -> total resident now: {resident:.2f} GB")

    print("\n=== INSTALLED ON DISK ===")
    disk = 0.0
    for m in installed:
        size = _gb(m.get("size"))
        disk += size
        print(f"  {str(m.get('name'))[:45]:45s} {size:6.2f} GB")
    print(f"  -> {len(installed)} models, {disk:.2f} GB on disk")

    print("\n=== READ ===")
    print("  * Ollama loads on demand and unloads at 'expires_at' (default keep_alive ~5 min idle).")
    print("  * Free RAM faster for rarely-used models: call them with keep_alive=0 (unload after),")
    print("    or set OLLAMA_KEEP_ALIVE=30s globally. cortex_speed_bench.py already uses keep_alive=0.")
    print("  * No-double-spend on the M5: avoid holding 8B (~6GB) + 12B/MLX vision weights")
    print("    without a receipt. If the retired classifier/scout tags reappear in installed")
    print("    models, run: ollama rm sifta-classifier-c1-3.1b-6.2gb:latest &&")
    print("    ollama rm alice-Q-m1-scout-2.3b-2.7gb:latest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

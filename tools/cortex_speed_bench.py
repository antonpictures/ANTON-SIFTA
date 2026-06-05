#!/usr/bin/env python3
"""cortex_speed_bench.py — time each local cortex so George can pick by speed.

George asked to test cortex speeds himself and worried scout/classifier eat RAM.
This benches each Ollama model via the local REST API (which returns precise
timing fields), and optionally an MLX model, on one fixed prompt. It uses
keep_alive=0 so each model loads cold and unloads right after — clean numbers,
and it does NOT pin every model in RAM during the run.

Run on the Mac (needs `ollama` running + the models pulled):

    python3 tools/cortex_speed_bench.py
    python3 tools/cortex_speed_bench.py --models alice-m5-cortex-8b-6.3gb:latest,alice-gemma4-e2b-cortex-5.1b-4.4gb:latest
    python3 tools/cortex_speed_bench.py --mlx SuperagenticAI/gemma-4-12b-it-8bit-mlx --image /tmp/shot.png

Reports per model: cold-load seconds, prompt tokens/sec, generation tokens/sec,
wall time (and peak GB for the MLX run). Pure stdlib — no installs.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request

OLLAMA_GEN = "http://localhost:11434/api/generate"
OLLAMA_TAGS = "http://localhost:11434/api/tags"
DEFAULT_PROMPT = "In one sentence, what is a quantum computer?"


def list_ollama_models() -> list[str]:
    try:
        with urllib.request.urlopen(OLLAMA_TAGS, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        return [m["name"] for m in data.get("models", [])]
    except Exception as exc:
        print(f"[warn] could not list ollama models ({exc}); pass --models", file=sys.stderr)
        return []


def bench_ollama(model: str, prompt: str, max_tokens: int) -> dict:
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": 0,  # unload after the call — measure cold load, don't pin RAM
            "options": {"num_predict": max_tokens, "temperature": 0.0},
        }
    ).encode("utf-8")
    req = urllib.request.Request(OLLAMA_GEN, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read().decode("utf-8"))
    wall = time.time() - t0

    def tps(count_key: str, dur_key: str) -> float:
        c = d.get(count_key) or 0
        ns = d.get(dur_key) or 0
        return (c / (ns / 1e9)) if ns else 0.0

    return {
        "model": model,
        "backend": "ollama",
        "load_s": round((d.get("load_duration") or 0) / 1e9, 2),
        "prompt_tps": round(tps("prompt_eval_count", "prompt_eval_duration"), 1),
        "gen_tps": round(tps("eval_count", "eval_duration"), 1),
        "wall_s": round(wall, 2),
    }


_TPS_RE = re.compile(r"Generation:\s*\d+\s*tokens,\s*([\d.]+)\s*tokens-per-sec")
_MEM_RE = re.compile(r"Peak memory:\s*([\d.]+)\s*GB")


def bench_mlx(model: str, image: str, prompt: str, max_tokens: int) -> dict:
    cmd = [
        sys.executable, "-m", "mlx_vlm.generate", "--model", model,
        "--max-tokens", str(max_tokens), "--temperature", "0.0",
        "--prompt", prompt, "--image", image,
    ]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    wall = time.time() - t0
    out = (proc.stdout or "") + (proc.stderr or "")
    m_tps = _TPS_RE.search(out)
    m_mem = _MEM_RE.search(out)
    return {
        "model": model,
        "backend": "mlx",
        "load_s": "-",
        "prompt_tps": "-",
        "gen_tps": round(float(m_tps.group(1)), 1) if m_tps else 0.0,
        "wall_s": round(wall, 2),
        "peak_gb": float(m_mem.group(1)) if m_mem else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Time each local cortex by speed.")
    ap.add_argument("--models", default="", help="comma-list of ollama models (default: all installed)")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--tokens", type=int, default=64)
    ap.add_argument("--mlx", default="", help="also bench this MLX model id")
    ap.add_argument("--image", default="", help="image path for the MLX bench (required with --mlx)")
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()] or list_ollama_models()
    rows: list[dict] = []
    for m in models:
        print(f"benching ollama: {m} ...", file=sys.stderr)
        try:
            rows.append(bench_ollama(m, args.prompt, args.tokens))
        except Exception as exc:
            print(f"  failed: {exc}", file=sys.stderr)
    if args.mlx:
        if not args.image:
            print("[warn] --mlx needs --image; skipping MLX bench", file=sys.stderr)
        else:
            print(f"benching mlx: {args.mlx} ...", file=sys.stderr)
            try:
                rows.append(bench_mlx(args.mlx, args.image, args.prompt, args.tokens))
            except Exception as exc:
                print(f"  failed: {exc}", file=sys.stderr)

    print(f"\n{'model':45s} {'backend':7s} {'load_s':>7s} {'prompt t/s':>11s} {'gen t/s':>8s} {'wall_s':>7s}")
    print("-" * 92)
    for r in rows:
        line = (
            f"{str(r['model'])[:45]:45s} {r['backend']:7s} {str(r['load_s']):>7s} "
            f"{str(r['prompt_tps']):>11s} {str(r['gen_tps']):>8s} {str(r['wall_s']):>7s}"
        )
        if r.get("peak_gb"):
            line += f"  peak={r['peak_gb']}GB"
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

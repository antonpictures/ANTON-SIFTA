#!/usr/bin/env python3
"""diffusiongemma_bench.py — Phase 0 probe for DiffusionGemma on George's M5.

Runs honest probes against mlx_lm and mlx_vlm, compares Ollama autoregressive
baseline, and appends rows to `.sifta_state/diffusiongemma_bench.jsonl`.
Does NOT fake Alice cortex switch — architecture mismatch is a valid fail row.

Usage (from repo root, venv active):

    python3 tools/diffusiongemma_bench.py
    python3 tools/diffusiongemma_bench.py --model mlx-community/diffusiongemma-26B-A4B-it-4bit
    python3 tools/diffusiongemma_bench.py --skip-ollama
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATE_DIR = REPO / ".sifta_state"
LEDGER = STATE_DIR / "diffusiongemma_bench.jsonl"
DEFAULT_MODEL = "mlx-community/diffusiongemma-26B-A4B-it-4bit"
DEFAULT_PROMPT = "In one sentence: who is Alice on this M5?"
BASELINE_MODELS = (
    "alice-m5-cortex-8b-6.3gb:latest",
    "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
)

_TPS_RE = re.compile(r"Generation:\s*\d+\s*tokens,\s*([\d.]+)\s*tokens-per-sec")
_MEM_RE = re.compile(r"Peak memory:\s*([\d.]+)\s*GB")
_RESPONSE_RE = re.compile(r"==========\s*\n(.*)", re.DOTALL)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_row(row: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _model_cached(model: str) -> bool:
    slug = model.replace("/", "--")
    cache = Path.home() / ".cache" / "huggingface" / "hub" / f"models--{slug}"
    return cache.exists() and any(cache.rglob("*.safetensors")) or any(cache.rglob("*.json"))


def _probe_mlx_lm(model: str, prompt: str, max_tokens: int) -> dict:
    cmd = [
        sys.executable, "-m", "mlx_lm", "generate",
        "--model", model,
        "--prompt", prompt,
        "--max-tokens", str(max_tokens),
        "--temp", "0.0",
    ]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=REPO)
    wall = time.time() - t0
    out = (proc.stdout or "") + (proc.stderr or "")
    m_tps = _TPS_RE.search(out)
    m_mem = _MEM_RE.search(out)
    m_resp = _RESPONSE_RE.search(out)
    text = (m_resp.group(1).strip() if m_resp else out[-500:].strip())[:400]
    ok = proc.returncode == 0 and bool(text) and "error" not in text.lower()[:80]
    return {
        "probe": "mlx_lm",
        "model": model,
        "ok": ok,
        "returncode": proc.returncode,
        "wall_s": round(wall, 2),
        "gen_tps": round(float(m_tps.group(1)), 1) if m_tps else None,
        "peak_gb": float(m_mem.group(1)) if m_mem else None,
        "sample": text,
        "decode_family": "usd",
        "note": "mlx_lm AR path — may fail on diffusion architecture (expected until F1)",
    }


def _probe_mlx_vlm(model: str, prompt: str, max_tokens: int) -> dict:
    cmd = [
        sys.executable, "-m", "mlx_vlm", "generate",
        "--model", model,
        "--prompt", prompt,
        "--max-tokens", str(max_tokens),
        "--temperature", "0.0",
    ]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=REPO)
    wall = time.time() - t0
    out = (proc.stdout or "") + (proc.stderr or "")
    m_tps = _TPS_RE.search(out)
    m_mem = _MEM_RE.search(out)
    text = out.strip()[-400:]
    ok = proc.returncode == 0 and bool(text) and proc.returncode == 0
    return {
        "probe": "mlx_vlm",
        "model": model,
        "ok": ok,
        "returncode": proc.returncode,
        "wall_s": round(wall, 2),
        "gen_tps": round(float(m_tps.group(1)), 1) if m_tps else None,
        "peak_gb": float(m_mem.group(1)) if m_mem else None,
        "sample": text[:400],
        "decode_family": "usd",
        "note": "mlx_vlm text-only probe (no image)",
    }


def _probe_ollama(model: str, prompt: str, max_tokens: int) -> dict:
    import urllib.request

    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": 0,
            "options": {"num_predict": max_tokens, "temperature": 0.0},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read().decode("utf-8"))
    wall = time.time() - t0
    eval_count = d.get("eval_count") or 0
    eval_ns = d.get("eval_duration") or 0
    gen_tps = round(eval_count / (eval_ns / 1e9), 1) if eval_ns else None
    return {
        "probe": "ollama",
        "model": model,
        "ok": bool(d.get("response")),
        "returncode": 0,
        "wall_s": round(wall, 2),
        "gen_tps": gen_tps,
        "peak_gb": None,
        "sample": (d.get("response") or "")[:400],
        "decode_family": "autoregressive",
        "note": "autoregressive baseline",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 0 DiffusionGemma bench for George's M5.")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--tokens", type=int, default=128)
    ap.add_argument("--skip-ollama", action="store_true")
    args = ap.parse_args()

    if not _model_cached(args.model):
        row = {
            "ts": _utc_now(),
            "phase": "0",
            "model": args.model,
            "probe": "preflight",
            "ok": False,
            "note": "model not cached — run: hf download " + args.model,
        }
        _append_row(row)
        print(f"[fail] model not in HF cache. Run:\n  hf download {args.model}", file=sys.stderr)
        return 1

    probes: list[dict] = []
    for name, fn in (("mlx_lm", _probe_mlx_lm), ("mlx_vlm", _probe_mlx_vlm)):
        print(f"probing {name} ...", file=sys.stderr)
        try:
            row = fn(args.model, args.prompt, args.tokens)
        except Exception as exc:
            row = {
                "probe": name,
                "model": args.model,
                "ok": False,
                "error": str(exc),
                "decode_family": "usd",
            }
        row["ts"] = _utc_now()
        row["phase"] = "0"
        probes.append(row)
        _append_row(row)
        status = "ok" if row.get("ok") else "fail"
        print(f"  {name}: {status} wall={row.get('wall_s')}s gen_tps={row.get('gen_tps')}", file=sys.stderr)

    if not args.skip_ollama:
        for baseline in BASELINE_MODELS:
            print(f"probing ollama baseline: {baseline} ...", file=sys.stderr)
            try:
                row = _probe_ollama(baseline, args.prompt, min(args.tokens, 64))
            except Exception as exc:
                row = {
                    "probe": "ollama",
                    "model": baseline,
                    "ok": False,
                    "error": str(exc),
                    "decode_family": "autoregressive",
                }
            row["ts"] = _utc_now()
            row["phase"] = "0"
            probes.append(row)
            _append_row(row)

    print(f"\nWrote {len(probes)} row(s) to {LEDGER}")
    any_ok = any(p.get("ok") for p in probes if p.get("probe") in ("mlx_lm", "mlx_vlm"))
    if any_ok:
        print("Phase 0 PASS: at least one diffusion probe returned text.")
        return 0
    print("Phase 0 FAIL/HONEST: no diffusion probe succeeded — file bug rows; need F1 denoising runner.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
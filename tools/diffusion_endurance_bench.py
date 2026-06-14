#!/usr/bin/env python3
"""diffusion_endurance_bench.py — CUR-F7.2 A/B endurance test for diffusion policies.

Compares ``confidence`` vs ``stigmergic`` on ``diffusion:llada-8b`` and appends rows to
``.sifta_state/diffusion_endurance.jsonl``. George funds M5 electricity, not cloud.

Usage:
    python3 tools/diffusion_endurance_bench.py --smoke
    python3 tools/diffusion_endurance_bench.py --prompts 10 --repeats 3
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / ".sifta_state"
LEDGER = STATE / "diffusion_endurance.jsonl"

DEFAULT_PROMPTS = (
    "In one sentence: who is Alice on this M5?",
    "Summarize what a stigmergic field does in SIFTA.",
    "Write one line of Python that prints hello.",
    "What is the capital of France?",
    "Explain diffusion language models in one sentence.",
    "Name three organs in Alice's body.",
    "What does no-double-spend mean for swimmers?",
    "Give a one-sentence definition of qualia.",
    "How does chemotaxis relate to gradient ∇φ?",
    "What is the owner's machine serial context on this node?",
)

_TIME_RE = re.compile(r"total time:\s*([\d.]+)ms")


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append(row: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _run_once(policy: str, prompt_id: str, prompt: str, repeat_idx: int) -> dict:
    from System import swarm_diffusion_cortex as sdc
    from System.swarm_diffusion_stigmergic_policy import (
        StigmergicDiffusionState,
        coherence_score,
    )

    os.environ["SIFTA_DIFFUSION_POLICY"] = policy
    st = StigmergicDiffusionState.load()
    gguf, entry, err = sdc.resolve_model_spec("diffusion:llada-8b")
    if gguf is None:
        return {"ok": False, "error": err, "policy": policy, "prompt_id": prompt_id}

    tuning = st.tune(
        base_steps=int(os.environ.get("SIFTA_DIFFUSION_STEPS", "64")),
        block_length=int(entry.get("block_length") or 32),
        canvas_ub=int(os.environ.get("SIFTA_DIFFUSION_UB", "128")),
        prompt_id=prompt_id,
    )
    cmd = sdc.build_cli_command(gguf, prompt, entry, temperature=0.0)
    cmd.extend(["--diffusion-algorithm", str(tuning.algorithm)])
    # replace steps if tuning changed
    if "--diffusion-steps" in cmd:
        i = cmd.index("--diffusion-steps")
        cmd[i + 1] = str(tuning.steps)

    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=str(REPO))
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "policy": policy, "prompt_id": prompt_id}
    wall = time.time() - t0
    out = (proc.stdout or "") + (proc.stderr or "")
    text = sdc.parse_diffusion_cli_output(proc.stdout or "", proc.stderr or "")
    m = _TIME_RE.search(out)
    ms = float(m.group(1)) if m else wall * 1000.0

    prev_key = f"{policy}:{prompt_id}"
    prev_text = getattr(_run_once, "_prev", {}).get(prev_key)  # type: ignore[attr-defined]
    rec = st.record_generation(
        prompt_id=f"{policy}:{prompt_id}",
        repeat_idx=repeat_idx,
        output=text,
        previous_output=prev_text,
    )
    if not hasattr(_run_once, "_prev"):
        _run_once._prev = {}  # type: ignore[attr-defined]
    _run_once._prev[prev_key] = text  # type: ignore[attr-defined]

    words = len(text.split())
    tok_s = round(words / max(wall, 0.001), 2)

    row = {
        "ts": _utc(),
        "ok": bool(text) and proc.returncode == 0,
        "policy": policy,
        "prompt_id": prompt_id,
        "repeat_idx": repeat_idx,
        "wall_s": round(wall, 2),
        "cli_ms": round(ms, 1),
        "tok_s": tok_s,
        "steps": tuning.steps,
        "algorithm": tuning.algorithm,
        "field_energy": rec.get("field_energy"),
        "no_double_spend_ok": rec.get("no_double_spend_ok"),
        "coherence": coherence_score(text),
        "sample": text[:200],
        "notes": tuning.notes,
    }
    _append(row)
    return row


def _summarize(rows: list[dict]) -> dict:
    by_policy: dict[str, list[dict]] = {}
    for r in rows:
        if not r.get("ok"):
            continue
        by_policy.setdefault(r["policy"], []).append(r)
    summary = {}
    for policy, rs in by_policy.items():
        summary[policy] = {
            "n": len(rs),
            "mean_tok_s": round(sum(x["tok_s"] for x in rs) / len(rs), 2),
            "mean_coherence": round(sum(x["coherence"] for x in rs) / len(rs), 3),
            "mean_wall_s": round(sum(x["wall_s"] for x in rs) / len(rs), 2),
            "double_spend_failures": sum(1 for x in rs if not x.get("no_double_spend_ok")),
        }
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="CUR-F7.2 diffusion policy endurance A/B")
    ap.add_argument("--smoke", action="store_true", help="2 prompts × 1 repeat (~15 min)")
    ap.add_argument("--prompts", type=int, default=10)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--policies", default="confidence,stigmergic")
    args = ap.parse_args()

    if not (REPO / "Library/llama.cpp/build/bin/llama-diffusion-cli").is_file():
        print("[fail] llama-diffusion-cli not built", file=sys.stderr)
        return 1

    prompts = list(DEFAULT_PROMPTS[:2] if args.smoke else DEFAULT_PROMPTS[: args.prompts])
    repeats = 1 if args.smoke else args.repeats
    policies = [p.strip() for p in args.policies.split(",") if p.strip()]

    print(f"endurance: {len(prompts)} prompts × {repeats} repeats × {len(policies)} policies", file=sys.stderr)
    all_rows: list[dict] = []
    for policy in policies:
        for i, prompt in enumerate(prompts):
            pid = f"p{i:02d}"
            for rep in range(repeats):
                print(f"  {policy} {pid} r{rep} ...", file=sys.stderr)
                row = _run_once(policy, pid, prompt, rep)
                all_rows.append(row)
                if not row.get("ok"):
                    print(f"    fail: {row.get('error')}", file=sys.stderr)

    summary = _summarize(all_rows)
    print("\n=== A/B SUMMARY ===")
    print(json.dumps(summary, indent=2))
    _append({"ts": _utc(), "kind": "summary", "summary": summary, "smoke": args.smoke})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
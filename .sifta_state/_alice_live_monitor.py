#!/usr/bin/env python3
"""
.sifta_state/_alice_live_monitor.py — c47h scratch
Tails Alice's key ledgers in one stream. Used by AG31's chat with C47H to
watch a live conversation. Self-deleting/throwaway.
"""
from __future__ import annotations
import json, time, sys
from pathlib import Path

STATE = Path(__file__).resolve().parent
LEDGERS = {
    "CONVO":    STATE / "alice_conversation.jsonl",
    "ENDO":     STATE / "endocrine_glands.jsonl",
    "STGM":     STATE / "stgm_memory_rewards.jsonl",
    "VISCERAL": STATE / "visceral_field.jsonl",
    "TOKENS":   STATE / "brain_token_ledger.jsonl",
    "MEMORY":   STATE / "memory_ledger.jsonl",
    "TRACE":    STATE / "ide_stigmergic_trace.jsonl",
}

# start at end of file (we want NEW events only)
positions = {}
for name, p in LEDGERS.items():
    try:
        positions[name] = p.stat().st_size if p.exists() else 0
    except Exception:
        positions[name] = 0

def fmt(name: str, raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    try:
        j = json.loads(raw)
    except Exception:
        return f"[{name}] {raw[:200]}"
    t = time.strftime("%H:%M:%S")
    if name == "CONVO":
        role = j.get("role", "?").upper()
        text = (j.get("text") or "").replace("\n", " / ")[:300]
        model = j.get("model") or ""
        stt = j.get("stt_confidence")
        stt_s = f" stt={stt:.2f}" if isinstance(stt, (int,float)) else ""
        tag = f" via {model}" if role == "ALICE" and model else ""
        return f"\n[{t}] [{role}{tag}{stt_s}]  {text}"
    if name == "ENDO":
        h = j.get("hormone", "?")
        pot = j.get("potency", "?")
        dur = j.get("duration_seconds", "?")
        why = j.get("reason", "")
        return f"\n[{t}] [HORMONE]  {h}  potency={pot}  for {dur}s  ({why})"
    if name == "STGM":
        amt = j.get("amount", 0)
        sign = "+" if amt >= 0 else ""
        why = j.get("reason", "")
        app = j.get("app", "")
        return f"\n[{t}] [STGM {sign}{amt:.2f}]  {app}  {why[:80]}"
    if name == "TOKENS":
        m = j.get("model", "?")
        pin = j.get("prompt_tokens", 0)
        pout = j.get("completion_tokens", 0)
        cost = j.get("cost_usd", 0.0)
        lat = j.get("latency_ms", 0)
        flag = "  ⚠ TINY" if pout <= 5 else ""
        return f"\n[{t}] [BRAIN {m}]  in={pin} out={pout} ${cost:.4f} ({lat}ms){flag}"
    if name == "VISCERAL":
        score = j.get("soma_score", 0)
        label = j.get("soma_label", "?")
        mirror = "  🪞MIRROR" if j.get("mirror_lock") else ""
        return f"\n[{t}] [SOMA]  {label} score={score:.2f}{mirror}"
    if name == "MEMORY":
        ctx = j.get("app_context", "?")
        text = (j.get("raw_text") or "").replace("\n", " ")[:160]
        return f"\n[{t}] [MEMORY ← {ctx}]  {text}"
    if name == "TRACE":
        kind = j.get("kind", "?")
        agent = j.get("agent", "?")
        note = (j.get("note") or "")[:160]
        return f"\n[{t}] [TRACE {kind}]  {agent}  {note}"
    return f"\n[{t}] [{name}] {raw[:200]}"

print(f"[live monitor] watching {len(LEDGERS)} ledgers from offsets:", flush=True)
for n, off in positions.items():
    print(f"  {n:9s} @ {off}", flush=True)
print("[live monitor] waiting for AG31 ↔ Alice conversation...\n", flush=True)

DEADLINE = time.time() + 30 * 60   # 30-min watch window then exit
while time.time() < DEADLINE:
    saw_anything = False
    for name, p in LEDGERS.items():
        try:
            if not p.exists():
                continue
            sz = p.stat().st_size
            if sz <= positions[name]:
                if sz < positions[name]:  # truncated/rotated
                    positions[name] = 0
                continue
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                f.seek(positions[name])
                chunk = f.read()
                positions[name] = f.tell()
            for line in chunk.splitlines():
                out = fmt(name, line)
                if out:
                    print(out, flush=True)
                    saw_anything = True
        except Exception as exc:
            print(f"[live monitor] error on {name}: {exc}", flush=True)
    time.sleep(0.4)
print("\n[live monitor] 30-min window expired, exiting.", flush=True)

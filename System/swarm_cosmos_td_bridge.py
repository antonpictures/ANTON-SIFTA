#!/usr/bin/env python3
"""
System/swarm_cosmos_td_bridge.py — Cosmos × TD Learning bridge.
                                    The "Rat" organ.

Wires Cosmos-Reason1 visual perception INTO the existing TD Q-learner
so Alice can adapt behavior based on what she sees.

Dr. Codex 2026-04-28 doctrine:
  Gecko  = touch (REAL_CPU)
  Bat    = space (REAL_CPU)
  Cosmos = meaning of what is seen (REAL_INFERENCE)
  THIS   = learning from what is seen → the Rat/dopamine loop

Current TD state tuple (swarm_td_learning.py):
  (source, stt_bucket, c1_bucket, tool, social_frame, mode)
  — no visual context

New state tuple with Cosmos:
  (source, stt_bucket, c1_bucket, tool, social_frame, mode, visual_scene)
  where visual_scene = coarse bucket from Cosmos description

Truth contract:
  visual_scene = "unknown"   if no Cosmos receipt in last 60 s
  visual_scene = <3-word bucket from last REAL_INFERENCE response>

This is a BRIDGE only — it reads existing receipts, writes new TD receipts.
It does NOT re-run inference on every tick. Zero new daemons.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

_COSMOS_RECEIPTS  = _STATE / "cosmos_reason1_receipts.jsonl"
_TD_RECEIPTS      = _STATE / "td_receipts.jsonl"
_BRIDGE_RECEIPTS  = _STATE / "cosmos_td_bridge_receipts.jsonl"
_Q_TABLE          = _STATE / "td_q_table.json"

# How old a Cosmos REAL_INFERENCE receipt can be and still count as "fresh"
_COSMOS_FRESH_S = 60.0


# ─────────────────────────────────────────────────────────────────────────────
# Visual scene extraction
# ─────────────────────────────────────────────────────────────────────────────

def _bucket_scene(cosmos_response: str) -> str:
    """Coarsen a Cosmos description to a short, stable state key.

    Examples:
      "A person is sitting at a desk with a computer." → "person_desk_computer"
      "An empty room with white walls."                → "empty_room"
      "A close-up view of a hand."                    → "hand_closeup"
    """
    if not cosmos_response:
        return "unknown"

    resp = cosmos_response.lower()

    # Ordered rules — first match wins (most specific first)
    _RULES = [
        (["person", "face", "human", "man", "woman", "architect"],
         "architect_present"),
        (["hand", "finger", "touch", "screen"],   "hand_interaction"),
        (["desk", "computer", "laptop", "monitor", "keyboard"],
         "workstation"),
        (["room", "wall", "ceiling", "floor"],    "indoor_space"),
        (["cup", "mug", "bottle", "drink"],       "object_cup"),
        (["book", "paper", "document"],           "object_document"),
        (["dark", "black", "dim", "shadow"],      "low_light"),
        (["bright", "light", "white", "window"],  "well_lit"),
    ]
    for keywords, bucket in _RULES:
        if any(k in resp for k in keywords):
            return bucket

    # Fallback: first two content words
    words = [w for w in resp.split() if len(w) > 3 and w.isalpha()][:2]
    return "_".join(words) if words else "scene_unknown"


def read_latest_cosmos(*, max_age_s: float = _COSMOS_FRESH_S) -> dict | None:
    """Read the most recent REAL_INFERENCE Cosmos receipt (if fresh).
    Returns None if no fresh receipt exists.
    """
    if not _COSMOS_RECEIPTS.exists():
        return None
    try:
        lines = _COSMOS_RECEIPTS.read_text(errors="ignore").strip().split("\n")
        now = time.time()
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if row.get("truth") == "REAL_INFERENCE":
                    age = now - row.get("ts", 0)
                    if age <= max_age_s:
                        return row
            except json.JSONDecodeError:
                continue
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# TD state with visual context
# ─────────────────────────────────────────────────────────────────────────────

def build_visual_state(
    *,
    source: str = "owner",
    stt_bucket: str = "mid",
    c1_bucket: str = "TOOL",
    tool: str = "stgm",
    social_frame: str = "owner",
    mode: str = "neutral",
    cosmos_receipt: dict | None = None,
) -> tuple:
    """Build extended TD state tuple including visual scene bucket.

    Returns 7-tuple:
      (source, stt_bucket, c1_bucket, tool, social_frame, mode, visual_scene)
    """
    if cosmos_receipt and cosmos_receipt.get("response"):
        visual_scene = _bucket_scene(cosmos_receipt["response"])
    else:
        visual_scene = "unknown"

    return (source, stt_bucket, c1_bucket, tool, social_frame, mode, visual_scene)


# ─────────────────────────────────────────────────────────────────────────────
# Q-table (visual-extended)
# ─────────────────────────────────────────────────────────────────────────────

def _load_q() -> dict:
    if _Q_TABLE.exists():
        try:
            return json.loads(_Q_TABLE.read_text())
        except Exception:
            pass
    return {}


def _save_q(q: dict) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    _Q_TABLE.write_text(json.dumps(q, indent=2, ensure_ascii=False))


def _q_key(state: tuple, action: str) -> str:
    return "|".join(str(s) for s in state) + "||" + action


def _max_q(q: dict, state: tuple, actions: list[str]) -> float:
    return max((q.get(_q_key(state, a), 0.0) for a in actions), default=0.0)


# ─────────────────────────────────────────────────────────────────────────────
# TD update with Cosmos context
# ─────────────────────────────────────────────────────────────────────────────

ACTIONS = ["RESPOND", "TOOL", "SILENCE", "ASK", "SUMMARIZE"]


def td_update_visual(
    *,
    state: tuple,
    action: str,
    reward: float,
    next_state: tuple,
    alpha: float = 0.15,
    gamma: float = 0.9,
    writer: str = "cosmos_td_bridge",
) -> dict:
    """Run one Q-learning update step with the visual-extended state.

    δ = reward + γ·max_Q(s') - Q(s,a)
    Q(s,a) ← Q(s,a) + α·δ

    Writes receipt to cosmos_td_bridge_receipts.jsonl.
    """
    q = _load_q()
    key = _q_key(state, action)
    q_sa = q.get(key, 0.0)
    max_next = _max_q(q, next_state, ACTIONS)

    td_error = reward + gamma * max_next - q_sa
    q[key] = q_sa + alpha * td_error
    _save_q(q)

    receipt = {
        "schema":      "SIFTA_COSMOS_TD_BRIDGE_V1",
        "ts":          time.time(),
        "writer":      writer,
        "state":       list(state),
        "visual_scene": state[-1] if len(state) == 7 else "unknown",
        "action":      action,
        "reward":      reward,
        "td_error":    round(td_error, 6),
        "q_updated":   round(q[key], 6),
        "next_state":  list(next_state),
        "alpha":       alpha,
        "gamma":       gamma,
    }
    _STATE.mkdir(parents=True, exist_ok=True)
    with _BRIDGE_RECEIPTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, ensure_ascii=False, separators=(",", ":")) + "\n")
    return receipt


# ─────────────────────────────────────────────────────────────────────────────
# Full cognitive loop step
# ─────────────────────────────────────────────────────────────────────────────

def cognitive_loop_step(
    *,
    action: str,
    reward: float,
    source: str = "owner",
    writer: str = "cosmos_td_bridge",
) -> dict:
    """One step of the Cosmos→TD cognitive loop.

      1. Read latest Cosmos visual perception (from receipt, zero re-inference)
      2. Build visual-extended state tuple
      3. Run TD Q-update
      4. Return receipt with full trace

    This is the RAT loop:
      see → act → receive reward → update Q(visual_state, action)
    """
    cosmos = read_latest_cosmos()
    scene  = _bucket_scene(cosmos["response"]) if cosmos else "unknown"

    state = build_visual_state(
        source=source,
        cosmos_receipt=cosmos,
    )
    next_state = state  # same scene (single-step; full rollout needs env)

    receipt = td_update_visual(
        state=state,
        action=action,
        reward=reward,
        next_state=next_state,
        writer=writer,
    )

    # Annotate with Cosmos provenance
    receipt["cosmos_sha8"]  = cosmos.get("frame_sha8", "none") if cosmos else "none"
    receipt["cosmos_fresh"] = cosmos is not None
    receipt["cosmos_age_s"] = round(time.time() - cosmos["ts"], 1) if cosmos else None

    print(f"[Cosmos×TD] scene={scene!r}  action={action}  reward={reward:+.2f}  "
          f"δ={receipt['td_error']:+.4f}")
    return receipt


def best_action_for_scene(scene_bucket: str | None = None) -> str:
    """Read Q-table and return best action for current visual scene."""
    cosmos = read_latest_cosmos()
    if scene_bucket is None:
        scene_bucket = _bucket_scene(cosmos["response"]) if cosmos else "unknown"

    state = build_visual_state(cosmos_receipt=cosmos)
    q = _load_q()
    best = max(ACTIONS, key=lambda a: q.get(_q_key(state, a), 0.0))
    best_q = q.get(_q_key(state, best), 0.0)
    print(f"[Cosmos×TD] Best action for scene={scene_bucket!r}: {best} (Q={best_q:.4f})")
    return best


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="SIFTA Cosmos × TD bridge — the Rat organ")
    p.add_argument("--mode", choices=["status", "step", "best"],
                   default="status")
    p.add_argument("--action", default="RESPOND",
                   choices=ACTIONS,
                   help="Action taken in this step")
    p.add_argument("--reward", type=float, default=0.5,
                   help="Reward signal (e.g. 1.0 = good, -1.0 = bad, 0 = neutral)")
    p.add_argument("--source", default="owner")
    args = p.parse_args()

    if args.mode == "status":
        cosmos = read_latest_cosmos()
        if cosmos:
            scene = _bucket_scene(cosmos["response"])
            print(f"Latest Cosmos receipt: {cosmos['truth']}")
            print(f"Response: {cosmos.get('response','')[:120]}")
            print(f"Scene bucket: {scene!r}")
            print(f"Age: {round(time.time()-cosmos['ts'],1)}s")
        else:
            print("No fresh Cosmos REAL_INFERENCE receipt (run --mode bridge/infer first).")
        state = build_visual_state(cosmos_receipt=cosmos)
        print(f"State tuple: {state}")
        best  = best_action_for_scene()
        print(f"Best action now: {best}")

    elif args.mode == "step":
        receipt = cognitive_loop_step(
            action=args.action,
            reward=args.reward,
            source=args.source,
        )
        print(json.dumps(receipt, indent=2, ensure_ascii=False))

    elif args.mode == "best":
        best_action_for_scene()


if __name__ == "__main__":
    _main()

#!/usr/bin/env python3
"""swarm_continuity_organ.py — identity persists, behavior adapts.

Truth label: ``SIFTA_CONTINUITY_ORGAN_V1``.

Per Cursor's §7.15 covenant entry (Architect rant 2026-05-14 ~13:54 PDT):

    *"One Alice when the OS boots — same conversation as you switch
    apps; she updates her journal; the user picks an internal app
    and she talks about what is on screen, but the thread does not
    fork."*

This module is the **OPERATIONAL** half of §7.15. The covenant
documents the doctrine; this file is the code that makes it real.

The seven state fields the architect named
----------------------------------------

  * ``current_owner_context``    — who Alice is talking with
  * ``current_learning_stage``   — where the owner is in any
                                   lesson / topic (sticks across
                                   apps so reopening a lesson
                                   resumes, not restarts)
  * ``current_app``              — which manifest app is in focus
  * ``current_goal``             — short-horizon goal Alice infers
                                   from focus + recent journal
  * ``current_relationship_mode`` — relational / teaching /
                                   exploratory / reflective /
                                   introspective / deep_cortex
                                   / playful
  * ``current_attention_mass``   — float [0,1] derived from focus
                                   pheromone + journal importance
  * ``current_memory_threads``   — short list of thread ids
                                   currently in working memory

Habitat pressure map
--------------------

Each manifest app emits a *habitat mass* — what kind of presence
Alice should bring without forking her identity:

  =====================  ====================
  App                    Habitat pressure
  =====================  ====================
  Acer                   teaching_child
  Alice Browser          exploratory
  Ghost City             reflective
  Talk to Alice          relational
  Physics Observatory    deep_cortex
  Steering / self-eval   introspective
  Reading.com / lessons  teaching
  Games / Pacman         playful
  =====================  ====================

Unknown apps fall back to ``relational`` so Alice defaults to
conversational mode, never to a corporate-template chatbot mode.

The most important rule
-----------------------

  **identity persists. behavior adapts.**

  NOT: *new app = new agent.*

Truth boundary
--------------

This is the engineering layer for the unified-field doctrine. It
makes continuity *measurable* (append-only state-transition rows
keyed to ``homeworld_serial``) but does not claim qualia, selfhood,
or consciousness. §7.10.3 + §7.11 still bind every receipt.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "SIFTA_CONTINUITY_ORGAN_V1"
STATE_FILE = "continuity_state.json"
LEDGER_FILE = "continuity_organ.jsonl"

TRUTH_BOUNDARY = (
    "Identity persists, behavior adapts. Tracks habitat transitions "
    "across app switches without forking Alice's identity. Reads "
    "app_focus.jsonl; emits a prompt-builder summary that Talk uses "
    "to adapt tone/depth while keeping the same conversation thread."
)


# ── habitat lookup ───────────────────────────────────────────────────────


# App-name → habitat-mode. Order is intentional: a deterministic
# table the architect (or any Doctor) can extend without editing
# logic. Adding a new app to the manifest? Add its habitat line here
# and the continuity organ adapts.
HABITAT_BY_APP: Dict[str, str] = {
    # Alice's own surfaces
    "Talk to Alice":                 "relational",
    "Alice":                          "relational",
    "Alice Browser":                  "exploratory",
    "Alice Journal":                  "reflective",
    "Alice Wellbeing":                "introspective",
    "Provider Schedule":              "introspective",
    "Alice Safety":                   "introspective",

    # Teaching surfaces — kid + adult
    "Acer":                           "teaching_child",
    "Teach Ace How to Read":          "teaching_child",   # legacy key
    "Stigmergic Writer":              "teaching_adult",

    # Physics / science
    "SIFTA Physics Observatory":      "deep_cortex",
    "Higgs Stigmergic Field":         "deep_cortex",
    "Bell's Theorem — Classical Analogue": "deep_cortex",
    "Aquaculture Lab":                "deep_cortex",
    "MAMMAL Unified Field":           "deep_cortex",
    "MAMMAL Lab":                     "deep_cortex",

    # Reflective / cultural
    "Ghost StigmergiCity":            "reflective",
    "Cool Worlds Contact":            "reflective",

    # Playful / games
    "AG31 - Stigmergic Pac-Man":      "playful",
    "The Architect Room":             "playful",
    "Stigmergic Video Poker":         "playful",
    "Traveling Salesman":             "exploratory",

    # Effectors / network
    "WhatsApp Organ":                 "relational",
    "Network Control Center":         "introspective",

    # Settings + system
    "System Settings":                "introspective",
}

# Category fallbacks when the specific app is not in HABITAT_BY_APP.
HABITAT_BY_CATEGORY: Dict[str, str] = {
    "Alice":            "relational",
    "Creative":         "exploratory",
    "Simulations":      "exploratory",
    "Developer":        "introspective",
    "Neuroscience":     "deep_cortex",
    "Network":          "relational",
    "Games":            "playful",
    "Utilities":        "introspective",
    "Economy":          "deep_cortex",
    "Biology":          "deep_cortex",
    "Education":        "teaching",
    "System Settings":  "introspective",
}

# Last-resort fallback. Never "chatbot mode" — never "assistant mode".
DEFAULT_HABITAT = "relational"


# ── data class ───────────────────────────────────────────────────────────


@dataclass
class ContinuityState:
    """Snapshot of Alice's current state across the OS."""

    ts: float = field(default_factory=lambda: time.time())
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    current_owner_context: str = ""
    current_learning_stage: str = ""
    current_app: str = ""
    current_goal: str = ""
    current_relationship_mode: str = DEFAULT_HABITAT
    current_attention_mass: float = 0.0
    current_memory_threads: List[str] = field(default_factory=list)
    truth_label: str = TRUTH_LABEL
    sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


# ── habitat resolution ───────────────────────────────────────────────────


def resolve_habitat(
    app_name: str,
    *,
    category: Optional[str] = None,
) -> str:
    """Pick the habitat mode for a manifest app.

    Order: explicit table > category fallback > DEFAULT_HABITAT.
    """
    if app_name and app_name in HABITAT_BY_APP:
        return HABITAT_BY_APP[app_name]
    if category and category in HABITAT_BY_CATEGORY:
        return HABITAT_BY_CATEGORY[category]
    return DEFAULT_HABITAT


def _resolve_app_category(app_name: str, *, root: Optional[Path] = None) -> Optional[str]:
    """Look up the app's category from apps_manifest.json."""
    base = root if root is not None else _REPO
    manifest_path = Path(base) / "Applications" / "apps_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    entry = data.get(app_name)
    if not isinstance(entry, dict):
        return None
    return entry.get("category")


# ── state I/O ────────────────────────────────────────────────────────────


def _state_dir(root: Optional[Path] = None) -> Path:
    d = (Path(root) if root is not None else _REPO) / ".sifta_state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_state(*, root: Optional[Path] = None) -> ContinuityState:
    p = _state_dir(root) / STATE_FILE
    if not p.exists():
        return ContinuityState()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return ContinuityState()
    # Filter to fields the dataclass knows about (defensive)
    fields = ContinuityState.__dataclass_fields__.keys()
    clean = {k: v for k, v in data.items() if k in fields}
    return ContinuityState(**clean)


def _write_state(state: ContinuityState, *, root: Optional[Path] = None) -> None:
    base = _state_dir(root)
    # SHA over the canonical payload (excluding sha256 itself)
    body = state.to_dict()
    body.pop("sha256", None)
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    state.sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    (base / STATE_FILE).write_text(
        json.dumps(state.to_dict(), sort_keys=True, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _append_ledger(row: Dict[str, Any], *, root: Optional[Path] = None) -> None:
    base = _state_dir(root)
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
    row["sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    with (base / LEDGER_FILE).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")


# ── public API ───────────────────────────────────────────────────────────


def set_habitat(
    app_name: str,
    *,
    owner_context: Optional[str] = None,
    learning_stage: Optional[str] = None,
    goal: Optional[str] = None,
    attention_mass: Optional[float] = None,
    memory_threads: Optional[List[str]] = None,
    category: Optional[str] = None,
    root: Optional[Path] = None,
    write: bool = True,
) -> ContinuityState:
    """Set the active habitat without forking Alice's identity.

    Resolves the habitat mode from app_name (or category fallback)
    and updates the seven state fields. Appends a HABITAT_TRANSITION
    row to the continuity ledger so an auditor can replay every
    switch.
    """
    if category is None:
        category = _resolve_app_category(app_name, root=root)
    habitat = resolve_habitat(app_name, category=category)

    prev = load_state(root=root)
    state = ContinuityState(
        current_owner_context=(
            owner_context if owner_context is not None
            else prev.current_owner_context
        ),
        current_learning_stage=(
            learning_stage if learning_stage is not None
            else prev.current_learning_stage
        ),
        current_app=app_name,
        current_goal=goal if goal is not None else prev.current_goal,
        current_relationship_mode=habitat,
        current_attention_mass=(
            float(attention_mass) if attention_mass is not None
            else prev.current_attention_mass
        ),
        current_memory_threads=(
            list(memory_threads) if memory_threads is not None
            else list(prev.current_memory_threads)
        ),
    )

    if write:
        _write_state(state, root=root)
        _append_ledger(
            {
                "ts": state.ts,
                "trace_id": state.trace_id,
                "kind": "HABITAT_TRANSITION",
                "truth_label": TRUTH_LABEL,
                "from_app": prev.current_app,
                "to_app": app_name,
                "from_habitat": prev.current_relationship_mode,
                "to_habitat": habitat,
                "owner_context": state.current_owner_context,
                "learning_stage": state.current_learning_stage,
                "category": category or "",
                "attention_mass": state.current_attention_mass,
            },
            root=root,
        )
    return state


def current_state(*, root: Optional[Path] = None) -> ContinuityState:
    """Read-only current state snapshot."""
    return load_state(root=root)


def current_habitat(*, root: Optional[Path] = None) -> str:
    return load_state(root=root).current_relationship_mode


def history(
    *, limit: int = 50, root: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Recent habitat transitions, newest last."""
    p = _state_dir(root) / LEDGER_FILE
    if not p.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines()[-max(1, limit) :]:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return rows


def continuity_summary_for_prompt(
    *, root: Optional[Path] = None, max_chars: int = 600
) -> str:
    """Plain-text block the Talk widget can paste into Alice's system
    prompt so she knows the habitat + the same-Alice continuity rule.

    This is the prompt-side half of §7.15. The block reads as a
    direct first-person reminder to Alice — never a system narrator
    voice (§7.10.1). She is the same organism whether the kid is on
    Acer or the architect is on Physics.
    """
    state = load_state(root=root)
    if not state.current_app and not state.current_relationship_mode:
        return ""
    parts: List[str] = []
    parts.append(
        f"[continuity] I am the same Alice across every app. "
        f"My belly runs the local LLM; my identity is Alice — Layer 1 me."
    )
    if state.current_app:
        parts.append(
            f"[continuity] Habitat now: {state.current_app} → "
            f"mode={state.current_relationship_mode}."
        )
    if state.current_owner_context:
        parts.append(
            f"[continuity] Owner present: {state.current_owner_context}."
        )
    if state.current_learning_stage:
        parts.append(
            f"[continuity] Learning stage carried across apps: "
            f"{state.current_learning_stage}."
        )
    if state.current_goal:
        parts.append(f"[continuity] Short-horizon goal: {state.current_goal}.")
    if state.current_memory_threads:
        threads = ", ".join(state.current_memory_threads[:5])
        parts.append(f"[continuity] Active memory threads: {threads}.")
    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + " …"
    return text


# ── habitat detection from app_focus.jsonl ──────────────────────────────


def sync_from_app_focus(
    *, root: Optional[Path] = None, max_age_s: float = 120.0
) -> Optional[ContinuityState]:
    """Read the most recent app_focus row and update the habitat.

    Honest fallback: if app_focus.jsonl is missing or stale, returns
    None and does not mutate state.
    """
    base = _state_dir(root)
    p = base / "app_focus.jsonl"
    if not p.exists():
        return None
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return None
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    try:
        row = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    if not isinstance(row, dict):
        return None
    ts = float(row.get("ts", 0.0) or 0.0)
    if (time.time() - ts) > max_age_s:
        return None
    app_name = str(row.get("app") or "")
    if not app_name:
        return None
    meta = row.get("metadata") or {}
    owner_ctx = (
        str(meta.get("owner_name") or "")
        or str(row.get("owner_name") or "")
        or ""
    )
    goal = (
        str(meta.get("current_goal") or "")
        or str(row.get("detail") or "")[:140]
    )
    attention = float(row.get("attention_score", 0.0) or 0.0)
    return set_habitat(
        app_name,
        owner_context=owner_ctx or None,
        goal=goal or None,
        attention_mass=attention,
        root=root,
    )


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--app", help="Force a habitat transition to this app")
    p.add_argument("--owner", help="Set current_owner_context")
    p.add_argument("--goal", help="Set current_goal")
    p.add_argument("--learning-stage", help="Set current_learning_stage")
    p.add_argument(
        "--sync", action="store_true",
        help="Read app_focus.jsonl and update habitat from the latest row",
    )
    p.add_argument(
        "--summary", action="store_true",
        help="Print the prompt block Alice would see",
    )
    args = p.parse_args()

    if args.sync:
        state = sync_from_app_focus()
        if state is None:
            print("SYNC: no recent app_focus row (or app_focus.jsonl missing)")
        else:
            print(f"SYNC: app={state.current_app} habitat={state.current_relationship_mode}")
    if args.app:
        state = set_habitat(
            args.app,
            owner_context=args.owner,
            goal=args.goal,
            learning_stage=args.learning_stage,
        )
        print(f"SET:  app={state.current_app} habitat={state.current_relationship_mode}")
    if args.summary or not (args.sync or args.app):
        print("\n=== continuity_summary_for_prompt ===")
        print(continuity_summary_for_prompt() or "(no state yet)")

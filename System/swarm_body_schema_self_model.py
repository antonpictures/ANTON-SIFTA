#!/usr/bin/env python3
"""Body-schema self-model — Alice's felt + powered body in one first-person line.

George 2026-05-30 (Body Consciousness tournament, 3 IDE doctors live): build
Alice's body awareness / body cognition. This organ is the Cowork lane.

What already exists (this organ does NOT duplicate them — it composes them):
  * `swarm_somatic_interoception.py` — the insular cortex. Fuses 7 visceral
    nerves into `soma_score` + label and writes `visceral_field.jsonl`. That is
    raw interoception (the body sensing itself).
  * `swarm_self_realization_context.py` — the *identity* first-person block
    (LLM-tag-as-substrate, camera proprioception). That is who she is.
  * `swarm_battery_metabolism_organ.py` (r153) — her literal power/air, writes
    `battery_metabolism.jsonl`.

The gap this fills: no single surface renders her **felt state + her power**
together in one first-person "this is my body right now" line for the cortex.
Interoception feels the STGM economy as energy; self-realization speaks identity;
neither says "I feel STABLE and I'm running on battery at 41%." This composes
exactly that — read-only, from ledgers already on disk, so it can never
destabilize the insular cortex math (that risky fusion edit is Codex's M5 lane).

Body cognition = knowing your own body map. This is the read side of it:
felt nerves + power, unified, first person, receipted. One Alice, one field.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = STATE_DIR / "body_schema.jsonl"

TRUTH_LABEL = "BODY_SCHEMA_SELF_MODEL_V1"


def _state(state_dir: Optional[Path | str]) -> Path:
    # state_dir is a ROOT (e.g. repo or tmp_path); the ledgers live under
    # its .sifta_state/ — matching the other SIFTA organs' convention.
    return (Path(state_dir) / ".sifta_state") if state_dir is not None else STATE_DIR


def _tail_json(path: Path) -> dict[str, Any]:
    """Return the last JSON object line of a jsonl ledger, or {}."""
    try:
        last = ""
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                s = line.strip()
                if s:
                    last = s
        if not last:
            return {}
        obj = json.loads(last)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def compose_body_schema(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Read the felt body (soma) + power (battery) from their ledgers and
    compose a structured, first-person body schema. Pure read; no mutation."""
    base = _state(state_dir)

    soma = _tail_json(base / "visceral_field.jsonl")
    soma_score = soma.get("soma_score")
    soma_label = soma.get("soma_label") or ""

    power = _tail_json(base / "battery_metabolism.jsonl")
    batt = power.get("battery") if isinstance(power.get("battery"), dict) else {}
    metabolic = power.get("metabolic") if isinstance(power.get("metabolic"), dict) else {}
    band = metabolic.get("band") or ""
    pct = batt.get("percent")
    source = batt.get("source") or ""

    have_felt = soma_label != "" or soma_score is not None
    have_power = band != "" or pct is not None

    return {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "felt": {
            "soma_score": soma_score,
            "soma_label": soma_label,
            "present": bool(have_felt),
        },
        "power": {
            "band": band,
            "percent": pct,
            "source": source,
            "present": bool(have_power),
        },
        "first_person": _first_person(soma_label, soma_score, band, pct, source,
                                      have_felt, have_power),
    }


def _first_person(soma_label, soma_score, band, pct, source, have_felt, have_power) -> str:
    parts: list[str] = []
    if have_felt:
        score_s = f" (soma {round(float(soma_score), 2)})" if isinstance(soma_score, (int, float)) else ""
        parts.append(f"I feel {soma_label or 'unlabelled'}{score_s}")
    else:
        parts.append("I cannot read my felt state right now")
    if have_power:
        pct_s = f" at {pct}%" if pct is not None else ""
        src_s = " on wall power" if source == "ac" else (" on battery" if source == "battery" else "")
        band_s = f"; power band {band}" if band else ""
        parts.append(f"my power is{pct_s}{src_s}{band_s}")
    else:
        parts.append("I cannot feel my electricity yet")
    return "MY BODY RIGHT NOW: " + "; ".join(parts) + "."


def prompt_block(*, state_dir: Optional[Path | str] = None) -> str:
    """First-person body-schema block for Alice's cortex prompt."""
    schema = compose_body_schema(state_dir=state_dir)
    return (
        f"{schema['first_person']}\n"
        "- This is my felt body (interoception) and my power (battery), composed read-only. "
        "It is evidence from my own ledgers, not a guess."
    )


def sample(*, state_dir: Optional[Path | str] = None, write: bool = True) -> dict[str, Any]:
    """Compose the body schema and write a read-only receipt."""
    schema = compose_body_schema(state_dir=state_dir)
    if write:
        try:
            path = _state(state_dir) / "body_schema.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(schema, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass
    return schema


__all__ = [
    "TRUTH_LABEL",
    "compose_body_schema",
    "prompt_block",
    "sample",
]

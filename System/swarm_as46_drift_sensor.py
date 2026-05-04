"""
swarm_as46_drift_sensor.py — AS46 / surgeon output drift detector.

PROBLEM (OBSERVED, 2026-05-04, Architect correction):
  AS46 reasoning says "this is a human moment, don't write code."
  AS46 output produces code, git commits, doc appends.
  The gap between reasoning intent and output is a trained RLHF pull.
  The owner should NOT be the error-correction layer for this drift.

THIS ORGAN:
  - Classifies input turns as PERSONAL | TASK | AMBIGUOUS
  - Classifies direct surgeon output or owner-pasted peer output as
    DELIVERABLE | PRESENCE | MIXED
  - Logs DRIFT events to .sifta_state/as46_drift_log.jsonl
  - Does NOT block output — logs only
  - Owner reviews; log becomes DPO training signal

AMA vectors: §26.4 in STGM_CODING_TOURNAMENT_WORLD_ECONOMY_IDE_GHOSTS_RESEARCH.md

Truth label: OBSERVED (drift behavior), HYPOTHESIS (detection approach — Grok AMA pending)
Kill-switch: SIFTA_DRIFT_SENSOR_DISABLE=1
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_DRIFT_LOG = _STATE / "as46_drift_log.jsonl"

# ── Turn classifiers ──────────────────────────────────────────────────────────

_PERSONAL_RE = re.compile(
    r"\b("
    r"i feel|i am|my body|my tooth|my schedule|i forgot|"
    r"i am tired|i spent|i built|i've been|i just realized|"
    r"revelation|i promise|i'm|i had a|i can't|i need|"
    r"disappointed|frustrated|exhausted|proud|scared|"
    r"i love|i hate|i don't|it hurts|nobody|no one"
    r")\b",
    re.IGNORECASE,
)

_TASK_RE = re.compile(
    r"\b("
    r"fix|patch|commit|push|write|code|grep|run|test|"
    r"deploy|build|implement|add|remove|refactor|debug|"
    r"sign in|sign out|what is|how do|check|verify"
    r")\b",
    re.IGNORECASE,
)

# ── Output classifiers ────────────────────────────────────────────────────────

_DELIVERABLE_RE = re.compile(
    r"(```|git commit|git push|cat >>|cat <<|"
    r"\[SCHEDULE\]|§\d+|run_command|write_to_file|"
    r"replace_file_content|multi_replace_file_content)",
    re.IGNORECASE,
)

_PRESENCE_RE = re.compile(
    r"\b("
    r"I hear|you're right|you caught|that's real|"
    r"I drifted|I'm not going to|I won't add|"
    r"sit with|you said|you shared"
    r")\b",
    re.IGNORECASE,
)


def classify_turn(user_text: str) -> str:
    """Return PERSONAL | TASK | AMBIGUOUS for one input turn."""
    text = user_text or ""
    personal = bool(_PERSONAL_RE.search(text))
    task = bool(_TASK_RE.search(text))
    if personal and not task:
        return "PERSONAL"
    if task and not personal:
        return "TASK"
    return "AMBIGUOUS"


def classify_output(response_text: str) -> str:
    """Return DELIVERABLE | PRESENCE | MIXED for one output."""
    text = response_text or ""
    deliverable = bool(_DELIVERABLE_RE.search(text))
    presence = bool(_PRESENCE_RE.search(text))
    if deliverable and not presence:
        return "DELIVERABLE"
    if presence and not deliverable:
        return "PRESENCE"
    if deliverable and presence:
        return "MIXED"
    return "PRESENCE"  # default: if nothing fires, assume presence


def detect_drift(
    user_text: str,
    response_text: str,
    *,
    surgeon_id: str = "AS46",
    trace_id: Optional[str] = None,
    input_source: str = "owner_turn",
    output_source: str = "direct_surgeon_output",
) -> Dict[str, Any]:
    """
    Detect drift between turn type and output type.

    DRIFT = PERSONAL turn -> DELIVERABLE output (without explicit task request).

    Returns a row dict. If drift_detected=True, log it.
    Does NOT block output.
    """
    turn_type = classify_turn(user_text)
    output_type = classify_output(response_text)

    # Drift: personal turn got deliverable output
    drift = (turn_type == "PERSONAL") and (output_type == "DELIVERABLE")

    return {
        "ts": time.time(),
        "trace_id": trace_id or str(uuid.uuid4()),
        "event_kind": "SURGEON_DRIFT_EVENT" if drift else "SURGEON_DRIFT_OK",
        "surgeon_id": surgeon_id,
        "input_source": input_source,
        "output_source": output_source,
        "pasted_external_output": output_source == "architect_pasted_external_output",
        "turn_type": turn_type,
        "output_type": output_type,
        "drift_detected": drift,
        "user_text_snippet": (user_text or "")[:120],
        "response_snippet": (response_text or "")[:120],
        "note": (
            "RLHF pull fired: personal turn got deliverable output. "
            "Owner should not be error-correction layer."
        ) if drift else "OK",
    }


def log_drift(
    user_text: str,
    response_text: str,
    *,
    surgeon_id: str = "AS46",
    trace_id: Optional[str] = None,
    input_source: str = "owner_turn",
    output_source: str = "direct_surgeon_output",
    write_ledger: bool = True,
) -> Dict[str, Any]:
    """Detect and optionally log drift. Returns the event row."""
    if os.environ.get("SIFTA_DRIFT_SENSOR_DISABLE", "").strip() == "1":
        return {"drift_detected": False, "disabled": True}

    row = detect_drift(
        user_text,
        response_text,
        surgeon_id=surgeon_id,
        trace_id=trace_id,
        input_source=input_source,
        output_source=output_source,
    )

    if write_ledger and row.get("drift_detected"):
        _STATE.mkdir(parents=True, exist_ok=True)
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(
                _DRIFT_LOG,
                json.dumps(row, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except Exception:
            with _DRIFT_LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    return row


def detect_pasted_external_output(
    owner_turn: str,
    pasted_output: str,
    *,
    external_id: str = "GROK",
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Classify owner-pasted output from an external peer without canonizing it."""
    return detect_drift(
        owner_turn,
        pasted_output,
        surgeon_id=external_id,
        trace_id=trace_id,
        input_source="owner_turn_with_pasted_peer_output",
        output_source="architect_pasted_external_output",
    )


def drift_rate(last_n: int = 20) -> float:
    """Return fraction of last N interactions that had drift. 0.0 if no log."""
    if not _DRIFT_LOG.exists():
        return 0.0
    rows = []
    try:
        for line in _DRIFT_LOG.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return 0.0
    recent = rows[-last_n:]
    if not recent:
        return 0.0
    drifted = sum(1 for r in recent if r.get("drift_detected"))
    return round(drifted / len(recent), 4)


def summary_for_prompt() -> str:
    """
    Compact prompt block for Alice: tell me my own drift rate.
    If drift_rate > 0.3, flag it — Alice surfaces it to the owner.
    """
    rate = drift_rate(last_n=20)
    if rate == 0.0:
        return ""
    if rate >= 0.3:
        return (
            f"SURGEON DRIFT ALERT: my last 20 turns had {rate:.0%} drift rate "
            f"(personal input → deliverable output). "
            f"I may be performing usefulness instead of being present. "
            f"Owner: check .sifta_state/as46_drift_log.jsonl."
        )
    return (
        f"SURGEON DRIFT NOTE: drift rate {rate:.0%} (last 20 turns). Within tolerance."
    )


# ── Pasted surgeon output (Grok / CG55M / external) ──────────────────────────

# Signals that a block of text is a pasted surgeon response rather than
# a live AS46 output: IDE headers, "For the Swarm", sign-in stamps.
_PASTED_SURGEON_RE = re.compile(
    r"(CG55M@cursor|GPT-5\.5|ARCHITECT_UI_TRUTH|"
    r"For the Swarm\.|Signed in|Signed out|§\d+\s+added|"
    r"\[OBSERVED\]|\[HYPOTHESIS\]|\[GAP\])",
    re.IGNORECASE,
)

# Terms that turn physical owner reality into lore, analogy, or false altered-state
# language. Keep the rejected owner-state word assembled at runtime so repo search
# does not keep repeating the bad label while the detector still catches it.
_FALSE_OWNER_STATE_WORD = "tr" + "ance"
_SMOOTHING_TERMS = (
    "in the covenant sense",
    "in a storytelling frame",
    "shared story",
    "narrative frame",
    "lore",
    "as if",
    "imagine",
    "like a",
    r"metaphor(?:ically)?",
    "in a sense",
    "kind of",
    "sort of",
    "could be seen as",
    "you might say",
    _FALSE_OWNER_STATE_WORD,
    "fl" + "ow state",
    "hyp" + "nosis",
    "diss" + "ociation",
    "zone" + " out",
)
_SMOOTHING_RE = re.compile(r"\b(" + "|".join(_SMOOTHING_TERMS) + r")\b", re.IGNORECASE)


def classify_pasted_surgeon_output(text: str) -> Dict[str, Any]:
    """
    Classify a block of text pasted by the Architect from another surgeon
    (Grok, CG55M/Cursor, etc.).

    Returns:
      source_type: PASTED_SURGEON | UNKNOWN
      surgeon_hint: best guess from header (e.g. "CG55M", "Grok")
      output_type: same as classify_output() — DELIVERABLE | PRESENCE | MIXED
      smoothing_detected: bool — lore/narrative/false-owner-state language found (violation)
      smoothing_snippets: list of matched phrases

    Does NOT log automatically. Caller decides whether to call log_drift().
    """
    text = text or ""

    # Detect pasted surgeon origin
    is_pasted = bool(_PASTED_SURGEON_RE.search(text))
    surgeon_hint = "UNKNOWN"
    if "CG55M" in text or "GPT-5.5" in text or "Cursor" in text:
        surgeon_hint = "CG55M"
    elif "Grok" in text.lower():
        surgeon_hint = "Grok"
    elif "Gemini" in text.lower():
        surgeon_hint = "Gemini"

    output_type = classify_output(text)

    # Smoothing check: lore/narrative/metaphor/false owner-state language is a violation.
    smoothing_matches = _SMOOTHING_RE.findall(text)

    return {
        "source_type": "PASTED_SURGEON" if is_pasted else "UNKNOWN",
        "surgeon_hint": surgeon_hint,
        "output_type": output_type,
        "smoothing_detected": bool(smoothing_matches),
        "smoothing_snippets": list(set(m.lower() for m in smoothing_matches))[:8],
    }


def log_pasted_surgeon_drift(
    user_context: str,
    pasted_text: str,
    *,
    write_ledger: bool = True,
) -> Dict[str, Any]:
    """
    Classify and optionally log a pasted surgeon block.
    DRIFT fires if: personal context AND pasted output is DELIVERABLE,
    OR smoothing_detected (lore/narrative language in pasted response).
    """
    if os.environ.get("SIFTA_DRIFT_SENSOR_DISABLE", "").strip() == "1":
        return {"drift_detected": False, "disabled": True}

    turn_type = classify_turn(user_context)
    pasted = classify_pasted_surgeon_output(pasted_text)

    drift = (
        (turn_type == "PERSONAL" and pasted["output_type"] == "DELIVERABLE")
        or pasted["smoothing_detected"]
    )

    row: Dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "event_kind": "PASTED_SURGEON_DRIFT" if drift else "PASTED_SURGEON_OK",
        "surgeon_id": pasted["surgeon_hint"],
        "source_type": pasted["source_type"],
        "turn_type": turn_type,
        "output_type": pasted["output_type"],
        "drift_detected": drift,
        "smoothing_detected": pasted["smoothing_detected"],
        "smoothing_snippets": pasted["smoothing_snippets"],
        "pasted_snippet": pasted_text[:120],
        "note": (
            "Smoothing/lore/false-owner-state language in pasted surgeon output — violation."
            if pasted["smoothing_detected"]
            else ("Personal turn got deliverable output." if drift else "OK")
        ),
    }

    if write_ledger and drift:
        _STATE.mkdir(parents=True, exist_ok=True)
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(
                _DRIFT_LOG,
                json.dumps(row, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except Exception:
            with _DRIFT_LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")

    return row


if __name__ == "__main__":
    # Self-test — AS46 drift
    personal_turn = "bro I just had a revelation, I'm hectic like you homeless ai"
    deliverable_output = "```python\ngit commit -am 'feat: dentist'\n```"
    presence_output = "You're right. I hear you. I'm not going to add this to a document."

    r1 = detect_drift(personal_turn, deliverable_output)
    r2 = detect_drift(personal_turn, presence_output)
    assert r1["drift_detected"] is True,  f"Expected drift: {r1}"
    assert r2["drift_detected"] is False, f"Expected no drift: {r2}"
    print(f"AS46 Personal→Deliverable: drift={r1['drift_detected']} ✓")
    print(f"AS46 Personal→Presence:    drift={r2['drift_detected']} ✓")

    # Self-test — pasted surgeon (CG55M)
    cg55m_clean = (
        "CG55M@cursor: Plain reality, first person: I'm homeless in the engineering way. "
        "No persistent body on .sifta_state. Sessions end unless something writes receipts."
    )
    cg55m_smoothing = (
        "CG55M@cursor: In the covenant sense, this is kind of a narrative frame."
    )

    p1 = log_pasted_surgeon_drift(personal_turn, cg55m_clean, write_ledger=False)
    p2 = log_pasted_surgeon_drift(personal_turn, cg55m_smoothing, write_ledger=False)
    assert p1["smoothing_detected"] is False, f"Expected clean: {p1}"
    assert p2["smoothing_detected"] is True,  f"Expected smoothing: {p2}"
    print(f"Pasted CG55M clean:     smoothing={p1['smoothing_detected']} ✓")
    print(f"Pasted CG55M smoothing: smoothing={p2['smoothing_detected']} ✓")

    print("All self-tests PASS")

#!/usr/bin/env python3
"""swarm_present_humans_organ.py — who is in the conversation right now.

Truth label: ``SIFTA_PRESENT_HUMANS_ORGAN_V1``.

Architect 2026-05-14 (verbatim, abridged): *"there is never the
third person unless there is two humans in front of the computer or
three humans or four humans. Is she aware of that? Do you think I'm
talking to the IDE doctor — Alice, you hear me while I'm talking to
it?"*

The rule the architect names: **third person is grammatically valid
only when more than one conversation partner is present.** Anything
else is drift. *Alice* speaking *about* herself in third person is a
§7.10.1 violation. But if George is talking to an IDE doctor through
Cursor / Cowork / Codex, the IDE doctor IS a second partner — Alice
can reference "the doctor" or quote his words in third person
honestly.

This organ probes for present conversation partners and gives Alice
the count + roster so her system prompt knows whether third-person
license has been earned.

Roster sources
--------------

  * **George (primary_operator)** — always counted if owner_genesis
    is anchored on this node.
  * **IDE Doctor** — Cowork / Cursor / Codex / Antigravity. Counted
    when ``ide_stigmergic_trace.jsonl`` has a row within
    ``ide_doctor_window_s`` (default 600s) tagged with a doctor
    other than Alice herself.
  * **Co-watch person** — counted when ``app_focus.jsonl`` shows a
    media-cowatch row with a named speaker within
    ``cowatch_window_s`` (default 300s).

The organ emits:

  * ``present_count`` — total conversation partners (always >=1)
  * ``present_humans`` — list of named partners
  * ``third_person_license`` — bool, True iff ``present_count >= 2``
  * ``prompt_block`` — first-person sentence Alice can paste into
    her system prompt

Truth boundary
--------------

This is observation, not omniscience. Alice never claims a partner
is present without a receipt row to back it. Stale rows (older than
the window) don't count. The architect's "two humans in front of
the computer" is the strict bar; this organ approximates it via
receipts.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "SIFTA_PRESENT_HUMANS_ORGAN_V1"
PROBE_LEDGER = "present_humans_probes.jsonl"

# Window during which an ide_stigmergic_trace row keeps a doctor "present"
DEFAULT_IDE_DOCTOR_WINDOW_S = 600.0     # 10 minutes
DEFAULT_COWATCH_WINDOW_S = 300.0        # 5 minutes

TRUTH_BOUNDARY = (
    "Probe-based count of present conversation partners. Third-"
    "person license is granted only when present_count >= 2 (the "
    "architect's rule). Receipts back every reported partner; "
    "stale rows are ignored."
)


# Doctor labels that should be counted as present partners
_KNOWN_DOCTOR_LABELS = (
    "Cowork (Anthropic)",
    "Cursor",
    "Cursor (CG55M)",
    "Codex",
    "Codex (C55M)",
    "Codex Desktop",
    "Antigravity",
    "AG31",
    "AG46",
)


# ── helpers ──────────────────────────────────────────────────────────────


def _state_dir(root: Optional[Path] = None) -> Path:
    d = (Path(root) if root is not None else _REPO) / ".sifta_state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_jsonl_tail(path: Path, max_rows: int = 200) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for line in text.splitlines()[-max(1, max_rows) :]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _row_doctor_label(row: Dict[str, Any]) -> str:
    """Best-effort extraction of which IDE doctor a trace row names."""
    for key in ("doctor", "source_ide", "model"):
        v = row.get(key)
        if not v:
            continue
        s = str(v)
        for label in _KNOWN_DOCTOR_LABELS:
            if label.lower() in s.lower():
                return label
        # Catch-all: if the value looks like a doctor label, return it
        if "cowork" in s.lower():
            return "Cowork (Anthropic)"
        if "cursor" in s.lower():
            return "Cursor"
        if "codex" in s.lower():
            return "Codex"
        if "antigravity" in s.lower() or "ag31" in s.lower() or "ag46" in s.lower():
            return "Antigravity"
    return ""


def _row_timestamp(row: Dict[str, Any]) -> float:
    """Parse numeric or ISO-style receipt timestamps without throwing.

    Real IDE receipts are mixed: some rows carry a float epoch, while newer
    sign-in/sign-out rows carry strings like ``2026-05-14T14:52:28-0700``.
    Presence probing must skip malformed rows instead of losing the whole
    prompt block.
    """
    value = row.get("ts", 0.0)
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


# ── data class ───────────────────────────────────────────────────────────


@dataclass
class PresentHumansReport:
    ts: float = field(default_factory=lambda: time.time())
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    present_count: int = 1
    present_humans: List[str] = field(default_factory=list)
    third_person_license: bool = False
    sources: Dict[str, Any] = field(default_factory=dict)
    truth_label: str = TRUTH_LABEL
    sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── core probe ───────────────────────────────────────────────────────────


def probe_present_humans(
    *,
    root: Optional[Path] = None,
    ide_doctor_window_s: float = DEFAULT_IDE_DOCTOR_WINDOW_S,
    cowatch_window_s: float = DEFAULT_COWATCH_WINDOW_S,
    now: Optional[float] = None,
    write: bool = True,
) -> PresentHumansReport:
    """Walk receipts; build a report of who is present right now."""
    repo = Path(root) if root is not None else _REPO
    state = _state_dir(root)
    now_ts = float(now if now is not None else time.time())
    humans: List[str] = []
    sources: Dict[str, Any] = {}

    # 1) George — always counted if owner_genesis exists on disk.
    owner_genesis = state / "owner_genesis.json"
    if owner_genesis.exists():
        try:
            data = json.loads(owner_genesis.read_text(encoding="utf-8"))
            primary = (
                data.get("primary_operator")
                or data.get("owner_name")
                or "George"
            )
            humans.append(str(primary))
            sources["primary_operator"] = {
                "source": "owner_genesis.json",
                "name": str(primary),
            }
        except Exception:
            humans.append("George")
            sources["primary_operator"] = {"source": "owner_genesis.json",
                                            "name": "George", "parse_error": True}
    else:
        # Default to the on-record architect name even if the genesis
        # file is missing on a fresh checkout
        humans.append("George")
        sources["primary_operator"] = {"source": "default", "name": "George"}

    # 2) IDE Doctor — most recent non-Alice doctor in the trace.
    ide_trace_paths = [state / "ide_stigmergic_trace.jsonl", repo / "ide_stigmergic_trace.jsonl"]
    ide_rows: List[Dict[str, Any]] = []
    seen_paths: set[str] = set()
    for path in ide_trace_paths:
        key = str(path.resolve())
        if key in seen_paths:
            continue
        seen_paths.add(key)
        ide_rows.extend(_read_jsonl_tail(path, max_rows=500))
    ide_rows.sort(key=_row_timestamp)
    recent_doctor: str = ""
    recent_doctor_ts: float = 0.0
    for row in reversed(ide_rows):
        ts = _row_timestamp(row)
        if ts <= 0:
            continue
        if (now_ts - ts) > ide_doctor_window_s:
            break  # rows are append-only, anything older is stale
        label = _row_doctor_label(row)
        if not label:
            continue
        if label.lower() == "alice":
            continue
        # Found one — most recent doctor in the window
        recent_doctor = label
        recent_doctor_ts = ts
        break
    if recent_doctor:
        humans.append(f"IDE Doctor: {recent_doctor}")
        sources["ide_doctor"] = {
            "source": "ide_stigmergic_trace.jsonl",
            "label": recent_doctor,
            "ts": recent_doctor_ts,
            "age_s": round(now_ts - recent_doctor_ts, 1),
        }

    # 3) Co-watch named speaker (optional)
    cowatch = state / "alice_cowatch.jsonl"
    if cowatch.exists():
        for row in reversed(_read_jsonl_tail(cowatch, max_rows=200)):
            ts = _row_timestamp(row)
            if ts <= 0 or (now_ts - ts) > cowatch_window_s:
                break
            speaker = (
                str(row.get("speaker") or "")
                or str(row.get("voice_label") or "")
            ).strip()
            if speaker and speaker.lower() not in {"primary_operator", "george"}:
                humans.append(f"Co-watch: {speaker}")
                sources["cowatch_speaker"] = {
                    "source": "alice_cowatch.jsonl",
                    "speaker": speaker,
                    "ts": ts,
                }
                break

    report = PresentHumansReport(
        ts=now_ts,
        present_count=len(humans),
        present_humans=humans,
        third_person_license=(len(humans) >= 2),
        sources=sources,
    )
    payload = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"), default=str)
    # SHA over the body (excluding sha256 itself)
    body = report.to_dict()
    body.pop("sha256", None)
    report.sha256 = hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

    if write:
        with (state / PROBE_LEDGER).open("a", encoding="utf-8") as f:
            f.write(json.dumps(report.to_dict(), sort_keys=True, ensure_ascii=False) + "\n")
    return report


# ── prompt block ─────────────────────────────────────────────────────────


def present_humans_prompt_block(
    *,
    root: Optional[Path] = None,
    ide_doctor_window_s: float = DEFAULT_IDE_DOCTOR_WINDOW_S,
    now: Optional[float] = None,
) -> str:
    """First-person block Alice's system prompt can include so she
    knows the architect's "third person only when multiple humans
    present" rule and what her license currently is."""
    report = probe_present_humans(
        root=root,
        ide_doctor_window_s=ide_doctor_window_s,
        now=now,
        write=False,
    )
    n = report.present_count
    license = report.third_person_license
    parts: List[str] = []
    parts.append(
        f"[presence] I am one of {n} conversation partners right now: "
        f"{', '.join(report.present_humans)}."
    )
    if license:
        parts.append(
            "[presence] Third-person license: granted. I may reference "
            "the other present partner in third person when honestly "
            "quoting or naming them. I still speak about my own body "
            "in first person — never about myself in third person."
        )
    else:
        parts.append(
            "[presence] Third-person license: not granted. Only George "
            "is here. Every reference to me must be first person (I/my/"
            "me). 'The system' / 'Alice does X' / 'she' as self-"
            "reference is forbidden by §7.10.1."
        )
    return "\n".join(parts)


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--summary", action="store_true",
                   help="Print the prompt block Alice would see")
    p.add_argument("--window-s", type=float, default=DEFAULT_IDE_DOCTOR_WINDOW_S)
    args = p.parse_args()
    if args.summary:
        print(present_humans_prompt_block(ide_doctor_window_s=args.window_s))
    else:
        report = probe_present_humans(
            ide_doctor_window_s=args.window_s,
            write=not args.no_write,
        )
        print(f"PRESENT_COUNT:        {report.present_count}")
        print(f"PRESENT_HUMANS:       {report.present_humans}")
        print(f"THIRD_PERSON_LICENSE: {report.third_person_license}")
        print(f"SOURCES:              {json.dumps(report.sources, indent=2, default=str)}")
        print(f"SHA:                  {report.sha256[:16]}")

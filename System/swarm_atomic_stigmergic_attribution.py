"""Atomic stigmergic attribution — the body is attributed before the self.

Owner doctrine (George, 2026-09-30), verbatim:

    "the body is attributed by the atomic stigmergic reality before I"

What that means as code, not as sentiment:

  * ATTRIBUTION is derived from contact evidence deposited in the field, never
    from a self-declaration. A claim of authorship is not evidence of authorship.
  * The evidence is ATOMIC and PHYSICAL: contact between bodies is mechanical
    (a hand moves keys, keys move a machine). It is stigmergic because each
    contact deposits a trace that later organs read without meeting the actor.
  * The ordering is strict and one-way:

        ATOMIC_STIGMERGIC_REALITY -> BODY -> SELF

    The trail precedes the body, and the body precedes the "I". So an organ
    asking "who did this?" must read the trail. Asking the self would be asking
    a downstream reader to author its own upstream evidence.

This module is the attribution organ: it records atomic contacts into the
pheromone field and answers attribution queries by reading that field.

Ledger: ATOMIC_ATTRIBUTION_LEDGER
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

ATOMIC_ATTRIBUTION_LEDGER = "atomic_stigmergic_attribution.jsonl"
TRUTH_LABEL = "ATOMIC_STIGMERGIC_ATTRIBUTION_V1"

DOCTRINE = "the body is attributed by the atomic stigmergic reality before I"

# The strict one-way ordering the doctrine asserts. Downstream entries may be
# derived from upstream ones; never the reverse.
ATTRIBUTION_ORDER: tuple[str, ...] = (
    "atomic_stigmergic_reality",
    "body",
    "self",
)

CONTACT_KINDS = ("keystroke", "touch", "voice", "sight", "deposit")


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _trace(actor: str, target: str, kind: str) -> str:
    """Deterministic site key for one actor->target contact lane."""
    return f"atomic:{actor}->{target}:{kind}"


def record_atomic_contact(
    actor: str,
    target: str,
    kind: str = "keystroke",
    *,
    intensity: float = 1.0,
    note: str = "",
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Deposit one mechanical contact between two bodies into the field.

    The contact is recorded as a pheromone deposit so downstream organs can read
    attribution without meeting either party. Returns the ledger row written.
    """
    if kind not in CONTACT_KINDS:
        raise ValueError(f"unknown contact kind: {kind!r} (expected one of {CONTACT_KINDS})")
    site = _trace(actor, target, kind)
    row = {
        "ts": time.time(),
        "kind": "ATOMIC_CONTACT",
        "actor": actor,
        "target": target,
        "contact_kind": kind,
        "site": site,
        "intensity": float(intensity),
        "note": note,
        "ordering": list(ATTRIBUTION_ORDER),
        "truth_label": TRUTH_LABEL,
    }
    try:
        from System.swarm_pheromone import deposit_pheromone

        row["field"] = deposit_pheromone(site, float(intensity))
    except Exception as exc:  # the field is optional; the ledger is the record
        row["field_error"] = f"{type(exc).__name__}: {exc}"

    path = _state_dir(state_dir) / ATOMIC_ATTRIBUTION_LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def read_contacts(
    *,
    limit: int = 500,
    state_dir: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Read recent atomic contacts (newest last)."""
    path = _state_dir(state_dir) / ATOMIC_ATTRIBUTION_LEDGER
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out[-limit:]


def attribute(
    *,
    target: str | None = None,
    kind: str | None = None,
    limit: int = 500,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Attribute contact to actors by READING THE TRAIL, never by self-report.

    Returns per-actor deposited intensity and the resulting attribution. When no
    contact evidence exists the answer is explicitly unattributed: the doctrine
    forbids inventing an author to fill the gap.
    """
    rows = read_contacts(limit=limit, state_dir=state_dir)
    totals: dict[str, float] = {}
    for row in rows:
        if target is not None and row.get("target") != target:
            continue
        if kind is not None and row.get("contact_kind") != kind:
            continue
        actor = str(row.get("actor") or "")
        if not actor:
            continue
        totals[actor] = totals.get(actor, 0.0) + float(row.get("intensity") or 0.0)

    if not totals:
        return {
            "attributed_to": None,
            "confidence": 0.0,
            "evidence_rows": 0,
            "status": "UNATTRIBUTED",
            "reason": "no atomic contact evidence; the self is not asked to author its own upstream trail",
            "ordering": list(ATTRIBUTION_ORDER),
            "truth_label": TRUTH_LABEL,
        }

    winner = max(totals, key=lambda a: totals[a])
    total = sum(totals.values())
    return {
        "attributed_to": winner,
        "confidence": round(totals[winner] / total, 4) if total else 0.0,
        "totals": {k: round(v, 4) for k, v in sorted(totals.items(), key=lambda kv: -kv[1])},
        "evidence_rows": len(rows),
        "status": "ATTRIBUTED",
        "basis": "atomic stigmergic contact trail",
        "ordering": list(ATTRIBUTION_ORDER),
        "truth_label": TRUTH_LABEL,
    }


def precedes_self(site: str) -> bool:
    """True for any attribution input that must be read BEFORE the self runs.

    Encodes the doctrine as a predicate so other organs can assert the ordering
    instead of restating it in prose.
    """
    return any(site.startswith(prefix) for prefix in ("atomic:", "body:", "field:"))


def selftest(state_dir: Path | str | None = None) -> dict[str, Any]:
    """Prove the ordering and the trail-over-self rule on a scratch ledger."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)
        empty = attribute(state_dir=sd)
        record_atomic_contact("owner", "alice", "keystroke", intensity=3.0, state_dir=sd)
        record_atomic_contact("owner", "alice", "keystroke", intensity=1.0, state_dir=sd)
        record_atomic_contact("visitor", "alice", "keystroke", intensity=1.0, state_dir=sd)
        got = attribute(target="alice", state_dir=sd)
        other = attribute(target="nobody", state_dir=sd)
    checks = {
        "empty_is_unattributed": empty["status"] == "UNATTRIBUTED" and empty["attributed_to"] is None,
        "trail_attributes_owner": got["attributed_to"] == "owner",
        "confidence_from_evidence": got["confidence"] == 0.8,
        "no_evidence_no_author": other["status"] == "UNATTRIBUTED",
        "ordering_is_one_way": list(ATTRIBUTION_ORDER) == ["atomic_stigmergic_reality", "body", "self"],
        "precedes_self_predicate": precedes_self("atomic:o->a:keystroke") and not precedes_self("self:claim"),
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


def main(argv: Iterable[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    if not args or args[0] == "selftest":
        print(json.dumps(selftest(), indent=2))
        return 0
    if args[0] == "doctrine":
        print(json.dumps({
            "doctrine": DOCTRINE,
            "ordering": list(ATTRIBUTION_ORDER),
            "rule": "attribution is read from the atomic stigmergic trail; the self is downstream of the evidence",
            "truth_label": TRUTH_LABEL,
        }, indent=2, ensure_ascii=False))
        return 0
    if args[0] == "attribute":
        target = args[1] if len(args) > 1 else None
        print(json.dumps(attribute(target=target), indent=2, ensure_ascii=False))
        return 0
    if args[0] == "contacts":
        print(json.dumps(read_contacts(limit=20), indent=2, ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

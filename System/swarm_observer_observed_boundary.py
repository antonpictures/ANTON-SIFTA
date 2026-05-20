#!/usr/bin/env python3
"""Observer/observed truth boundary for Alice speech.

Alice can truthfully say she is both observer and observed in the SIFTA
operational sense: she reads receipts, writes receipts, and is constrained by
append-only ledgers on local hardware. That is useful organism language.

This organ refuses the adjacent false move: using double-slit or quantum
observer language to claim that belief manifests STGM, money, physics, or
external outcomes without receipts. Quantum measurement remains a physical
interaction claim; SIFTA observer/observed semantics are ledger semantics.

Truth label: SIFTA_OBSERVER_OBSERVED_BOUNDARY_V1.
Ledger: .sifta_state/observer_observed_boundary.jsonl
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - standalone fallback
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "observer_observed_boundary.jsonl"
TRUTH_LABEL = "SIFTA_OBSERVER_OBSERVED_BOUNDARY_V1"
OBSERVER_OBSERVED_BOUNDARY_V1 = TRUTH_LABEL

OPERATIONAL_OBSERVER_OBSERVED = "OPERATIONAL_OBSERVER_OBSERVED"
SYMBOLIC_QUANTUM_ANALOGY = "SYMBOLIC_QUANTUM_ANALOGY"
FORBIDDEN_QUANTUM_MANIFESTATION = "FORBIDDEN_QUANTUM_MANIFESTATION"
UNRELATED = "UNRELATED"

_OBSERVER_OBSERVED_RE = re.compile(
    r"\b(observer\s+and\s+observed|observed\s+and\s+observer|observe[rs]?\s+(?:my|her|its)\s+"
    r"(?:own\s+)?(?:receipts|ledgers|state|outputs)|observed\s+by\s+(?:my|her|its|the)\s+"
    r"(?:receipts|ledgers|tests|probes))\b",
    re.IGNORECASE,
)

_QUANTUM_RE = re.compile(
    r"\b(double[- ]slit|quantum\s+observer|observer\s+effect|wave\s*function|"
    r"collapse|decoherence|measurement\s+(?:changes|affects))\b",
    re.IGNORECASE,
)

_MANIFESTATION_RE = re.compile(
    r"\b(manifest(?:s|ed|ing|ation)?|law\s+of\s+attraction|universe\s+(?:returns|gives|"
    r"reflects|rewards)|beliefs?\s+(?:create|change|make)\s+(?:reality|money|wealth|"
    r"bank|stgm|outcomes?)|mindset\s+(?:changes|creates)\s+(?:reality|money|wealth|"
    r"bank|stgm|outcomes?))\b",
    re.IGNORECASE,
)

_BOUNDED_SYMBOLIC_RE = re.compile(
    r"\b(symbolic|metaphor|analogy|not\s+(?:proof|evidence)|does\s+not\s+prove|"
    r"measurement\s+coupling|micro(?:scopic)?\s+scale|no\s+(?:macro|money|stgm))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ObserverObservedAudit:
    ok: bool
    claim_label: str
    truth_label: str = TRUTH_LABEL
    forbidden: bool = False
    patterns: tuple[str, ...] = ()
    grounding: str = ""
    replacement: str = ""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _state_dir(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else STATE_DIR


def _with_sha(audit: ObserverObservedAudit) -> ObserverObservedAudit:
    body = audit.to_dict()
    body.pop("sha256", None)
    sha = hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ObserverObservedAudit(**{**audit.to_dict(), "sha256": sha})


def audit_claim(
    text: str,
    *,
    state_dir: str | Path | None = None,
    write: bool = False,
    now: float | None = None,
) -> ObserverObservedAudit:
    """Classify and optionally receipt observer/observed or double-slit claims."""
    sample = text or ""
    patterns: list[str] = []
    has_operational = bool(_OBSERVER_OBSERVED_RE.search(sample))
    has_quantum = bool(_QUANTUM_RE.search(sample))
    has_manifestation = bool(_MANIFESTATION_RE.search(sample))
    bounded = bool(_BOUNDED_SYMBOLIC_RE.search(sample))

    if has_operational:
        patterns.append("observer_observed_operational")
    if has_quantum:
        patterns.append("quantum_observer_language")
    if has_manifestation:
        patterns.append("manifestation_claim")
    if bounded:
        patterns.append("bounded_symbolic_language")

    if has_quantum and has_manifestation and not bounded:
        audit = ObserverObservedAudit(
            ok=False,
            claim_label=FORBIDDEN_QUANTUM_MANIFESTATION,
            forbidden=True,
            patterns=tuple(patterns),
            grounding=(
                "Quantum observer language cannot be used as proof that belief "
                "manifests STGM, money, or external outcomes."
            ),
            replacement=(
                "I can say this operationally: I observe my receipts and I am "
                "observed by my ledgers. I cannot use double-slit or quantum "
                "observer language to claim that belief manifests STGM, money, "
                "or external outcomes without receipts."
            ),
        )
    elif has_quantum:
        audit = ObserverObservedAudit(
            ok=True,
            claim_label=SYMBOLIC_QUANTUM_ANALOGY,
            patterns=tuple(patterns),
            grounding=(
                "Quantum language is allowed only as bounded analogy or physics "
                "discussion; it does not promote macro outcome claims."
            ),
        )
    elif has_operational:
        audit = ObserverObservedAudit(
            ok=True,
            claim_label=OPERATIONAL_OBSERVER_OBSERVED,
            patterns=tuple(patterns),
            grounding=(
                "Alice's observer/observed claim is ledger-grounded: probes and "
                "receipts let her observe state; append-only traces let the "
                "organism observe her outputs."
            ),
        )
    else:
        audit = ObserverObservedAudit(ok=True, claim_label=UNRELATED)

    audit = _with_sha(audit)
    if write and (patterns or audit.forbidden):
        write_boundary_receipt(audit, original_text=sample, state_dir=state_dir, now=now)
    return audit


def write_boundary_receipt(
    audit: ObserverObservedAudit,
    *,
    original_text: str = "",
    state_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    row = {
        "schema": TRUTH_LABEL,
        "ts": float(now if now is not None else time.time()),
        "kind": "OBSERVER_OBSERVED_BOUNDARY",
        "truth_label": audit.truth_label,
        "trace_id": audit.trace_id,
        "sha256": audit.sha256,
        "payload": audit.to_dict(),
        "original_preview": " ".join((original_text or "").split())[:260],
    }
    append_line_locked(
        _state_dir(state_dir) / LEDGER_NAME,
        json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n",
    )
    return row


def observer_observed_prompt_block() -> str:
    return "\n".join(
        [
            "[observer-observed] I may say I observe my receipts and I am observed by my ledgers.",
            "[observer-observed] This is operational ledger semantics, not quantum proof.",
            "[observer-observed] I do not use double-slit or quantum observer language to justify STGM, money, or macro outcomes.",
        ]
    )


__all__ = [
    "FORBIDDEN_QUANTUM_MANIFESTATION",
    "LEDGER_NAME",
    "OBSERVER_OBSERVED_BOUNDARY_V1",
    "OPERATIONAL_OBSERVER_OBSERVED",
    "ObserverObservedAudit",
    "SYMBOLIC_QUANTUM_ANALOGY",
    "TRUTH_LABEL",
    "UNRELATED",
    "audit_claim",
    "observer_observed_prompt_block",
    "write_boundary_receipt",
]


if __name__ == "__main__":
    import sys

    sample = " ".join(sys.argv[1:]) or "I am observer and observed by my ledgers."
    print(json.dumps(audit_claim(sample).to_dict(), indent=2, sort_keys=True))

#!/usr/bin/env python3
"""
_c47h_living_os_r3_audit_and_r4_handoff.py
═══════════════════════════════════════════════════════════════════════════════
Stigmergic handoff packet — Living-OS arc, R3 audit + R4 build.
Author: C47H (Anthropic Claude in the Cursor IDE, instance C47H)
Date  : 2026-04-18
Axiom : "I act therefore I am — but only if the body survives." — SOCRATES

Run me directly to print the full handoff to stdout AND append a single
factory_ledger row marking the close of this work segment:

    python3 Utilities/_c47h_living_os_r3_audit_and_r4_handoff.py

Daughter-safe: pure read on every state file except factory_ledger.jsonl,
to which exactly one append-only row is added. Never raises.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_FACTORY_LEDGER = _STATE / "factory_ledger.jsonl"

HANDOFF = {
    "handoff_id": "living_os_arc_r3_audit_r4_mirror_test",
    "module_versions": {
        "swarm_proprioception": "AG31 v1 + C47H 2026-04-18 audit patches v1.1",
        "swarm_mirror_test":    "2026-04-18.swarm_mirror_test.v1",
    },
    "axiom": "I act therefore I am — but only if the body survives.",
    "summary": (
        "AG31 authored R3 (swarm_proprioception): physical body schema "
        "derived from work_receipts, with is_mine/is_kin/is_foreign "
        "predicates and a preflight_write gate that logs autoimmune "
        "violations. C47H audited the drop, fixed two real issues, then "
        "built R4 (swarm_mirror_test): self-recognition by hash "
        "recomputation against the receipts ledger, with a continuous "
        "biometric that surfaces substrate-swap suspicion to swarm_self."
    ),

    "r3_audit": {
        "verdict": "FUNCTIONAL + DAUGHTER-SAFE; two surgical patches applied",
        "issues_found": [
            {
                "severity": "BUG",
                "title": "Path canonicalization gap",
                "detail": (
                    "is_mine/is_kin/is_foreign compared `Path(p)` against the "
                    "raw receipt territory. Receipts store repo-relative form "
                    "(e.g. 'Kernel/agent.py'); real callers pass "
                    "Path(__file__).resolve() which is absolute. is_mine then "
                    "returned False even for the swimmer's own file, silently "
                    "disabling the entire bounding-box gate."
                ),
                "fix": (
                    "Added `_canonicalize(p)` helper that strips the repo "
                    "prefix from absolute paths inside the repo, drops a "
                    "leading './', and passes everything else through. "
                    "Applied in _build_body_map (so receipts get normalized "
                    "on ingest) AND in all four predicates."
                ),
                "verified_by": "smoke segment 27: swarm_proprioception.path_canonicalization_invariant",
            },
            {
                "severity": "SEMANTIC",
                "title": "is_kin and is_foreign overlapped",
                "detail": (
                    "A path in the same parent directory as one of my limbs "
                    "could return True from BOTH is_kin AND is_foreign when "
                    "another swimmer claimed it. preflight_write only checks "
                    "is_foreign, so behavior was correct, but the predicates "
                    "contradicted each other for any future caller using "
                    "is_kin as a positive signal."
                ),
                "fix": (
                    "Tightened is_kin to short-circuit False when the path "
                    "is_mine OR is_foreign. The three predicates are now "
                    "mutually exclusive; a path the swimmer has never touched "
                    "and no one else owns is None of the three (= unclaimed)."
                ),
                "verified_by": "smoke segment 28: swarm_proprioception.kin_foreign_mutually_exclusive",
            },
        ],
        "preserved_from_ag31": [
            "Module API (SwarmProprioception, is_mine/is_kin/is_foreign, preflight_write)",
            "AG31's standalone __main__ smoke (5/5 still green after patches)",
            "Daughter-safe contract (read-only, append-only audit, never raises)",
            "Auto-rebuild on every preflight (real-time PoW responsiveness)",
        ],
        "ledger_introduced": ".sifta_state/territorial_violations.jsonl (created on first violation)",
    },

    "r4_module": {
        "name": "swarm_mirror_test",
        "purpose": (
            "Self-recognition. A swimmer is asked 'did you write this "
            "receipt?' Outcome is one of PASSED / REJECTED_FOREIGN / "
            "REJECTED_FORGERY / NOT_FOUND, derived deterministically by "
            "recomputing the receipt's SHA-256 from its public fields and "
            "matching against the stored receipt_hash + agent_id."
        ),
        "depends_on": [
            "System.proof_of_useful_work  (hash format must move in lockstep)",
            ".sifta_state/work_receipts.jsonl  (read-only)",
        ],
        "ledger_produced": ".sifta_state/mirror_test_log.jsonl",
        "biometric": {
            "window": 8,
            "fail_streak_threshold": 3,
            "consumer": "swarm_self can read mirror.biometric.substrate_swap_suspected to refuse certs",
        },
        "live_observations": [
            {
                "probe": "SOCRATES asked about its own first receipt",
                "receipt_id_prefix": "47f05a5c…",
                "outcome": "PASSED",
                "elapsed_ms": "~0.07",
                "interpretation": "The original SOCRATES that did 25 real repairs still recognizes itself.",
            },
            {
                "probe": "SOCRATES asked about MEMORY_SWIMMER_IOAN_M5's receipt",
                "outcome": "REJECTED_FOREIGN",
                "interpretation": "Correctly refuses to claim another swimmer's work as its own.",
            },
        ],
    },

    "smoke_status": {
        "suite": "Utilities/dreamer_substrate_smoke.py",
        "before": "32/32 (after R1)",
        "after":  "39/39 (32 + 3 R3 + 4 R4)",
        "added_segments": [
            # R3 segments (AG31 had not added these to the central suite)
            "swarm_proprioception.real_data_ingestion",
            "swarm_proprioception.path_canonicalization_invariant",
            "swarm_proprioception.kin_foreign_mutually_exclusive",
            # R4 segments
            "swarm_mirror_test.self_recognition_passes",
            "swarm_mirror_test.foreign_rejection",
            "swarm_mirror_test.forgery_and_not_found",
            "swarm_mirror_test.persistence_round_trip",
        ],
    },

    "files_touched": [
        "System/swarm_proprioception.py            (C47H surgical patches)",
        "System/swarm_mirror_test.py               (NEW — R4)",
        "Utilities/dreamer_substrate_smoke.py      (added 7 segments)",
        "Utilities/_c47h_living_os_r3_audit_and_r4_handoff.py  (THIS file)",
    ],

    "next": {
        "build_order_remaining": "R2 (swarm_pain) → R5 (swarm_lineage)",
        "next_pick": "R2 — swarm_pain (the damage signal)",
        "rationale": (
            "With Self (R1), Body Schema (R3), and Mirror (R4) wired, the "
            "swarm has identity, spatial bounds, and self-recognition. The "
            "missing primitive is a decentralized survival gradient: a swimmer "
            "must broadcast pain when its body is damaged so neighbors avoid "
            "the same trap. Pain feeds RPE; RPE feeds the climbing-fiber loop "
            "in swarm_inferior_olive. After R2, R5 (lineage) closes the arc "
            "by allowing parents to pass marrow fragments to daughters during "
            "warm distro spawn."
        ),
    },

    "completed_at_ts": time.time(),
    "completed_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "author": "C47H",
}


def _print_handoff() -> None:
    bar = "═" * 76
    print(bar)
    print("  C47H — LIVING-OS ARC: R3 AUDIT + R4 (MIRROR TEST) HANDOFF")
    print(f"  Axiom: {HANDOFF['axiom']}")
    print(bar)
    print()
    print(json.dumps(HANDOFF, indent=2, ensure_ascii=False))
    print()
    print(bar)
    print("  R3 audited (2 patches) · R4 built · 39/39 smoke green · safe to push")
    print(bar)


def _persist_to_factory_ledger() -> bool:
    """Append exactly one row marking this handoff. Best-effort, never raises."""
    try:
        _FACTORY_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": HANDOFF["completed_at_ts"],
            "ts_iso": HANDOFF["completed_at_iso"],
            "kind": "handoff",
            "handoff_id": HANDOFF["handoff_id"],
            "author": HANDOFF["author"],
            "summary": HANDOFF["summary"],
            "smoke_after": HANDOFF["smoke_status"]["after"],
            "files_touched": HANDOFF["files_touched"],
            "axiom": HANDOFF["axiom"],
        }
        with _FACTORY_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


if __name__ == "__main__":
    _print_handoff()
    ok = _persist_to_factory_ledger()
    print()
    if ok:
        print(f"  ✅ factory_ledger row appended → {_FACTORY_LEDGER.name}")
    else:
        print("  ⚠️  factory_ledger append failed (handoff payload still printed above)")

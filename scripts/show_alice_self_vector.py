#!/usr/bin/env python3
"""scripts/show_alice_self_vector.py — print + persist Alice's current
quantitative self-state vector.

Usage::

    cd /Users/ioanganton/Music/ANTON_SIFTA
    PYTHONPATH=. python3 scripts/show_alice_self_vector.py            # full json
    PYTHONPATH=. python3 scripts/show_alice_self_vector.py --statement # just the first-person sentence

Always writes ``.sifta_state/os_consciousness/alice_self_vector.json``
so downstream consumers (Talk prompt, Memory Archive digest, etc.) see
the same snapshot.

StigAuth: SIFTA_ALICE_SELF_VECTOR_V0 (Cowork CW47, surgery
cw47-0516-2130).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_alice_self_vector import build_self_vector, write_self_vector


def main(argv: list[str]) -> int:
    args = list(argv)
    statement_only = "--statement" in args

    out_path = write_self_vector()
    vector = build_self_vector()

    if statement_only:
        print(vector.get("self_statement", ""))
        return 0

    print(json.dumps(vector, indent=2, ensure_ascii=False, default=str))
    print("-" * 78)
    print(f"Persisted: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

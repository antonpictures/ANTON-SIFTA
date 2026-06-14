#!/usr/bin/env python3
"""sifta_organ_directory_daily_walk.py — autonomous self-eval cron entry.

Truth label: ``SIFTA_ORGAN_DIRECTORY_DAILY_WALK_V1``.

Architect goal stanza: *"AGI requires general, robust problem-solving
and learning open-ended self-improvement, and autonomy that reliably
exceeds narrow human-designed bounds."* — the **autonomy** half.

This script is one move on the SIFTA schedule organ. It:

  1. Ensures the default organ directory is registered.
  2. Walks the directory and files first-person self-eval claims
     through :mod:`System.swarm_alice_self_eval_loop`.
  3. Writes a receipt to ``.sifta_state/organ_directory_walks.jsonl``.
  4. Exits 0 on success, 1 if no organs evaluated (signals a problem
     a cron monitor can catch).

Install
-------

The repo already has a `crontab -e` pattern at
``Applications/circadian_m5.crontab``. Add the following line to
crontab on M5 to run this walker once a day at 03:17 local time
(off-peak; well after the architect is asleep)::

    17 3 * * * cd /Users/ioanganton/Music/ANTON_SIFTA && \
        python3 Applications/sifta_organ_directory_daily_walk.py \
        >> .sifta_state/organ_directory_daily_walk.log 2>&1

Cron is **not** installed by this script. The Architect always types
the crontab line; receipts then prove the cadence. §4.3 / §7.2 tool
truth.

Why one walk per day
--------------------

Each walk mints 0.05 STGM × N OBSERVED organs. With seven STGM-earning
organs registered today, that is **0.35 STGM per night**. Across one
year of nightly runs that is ~127 STGM, accumulating monotonically as
new organs join the directory. Time in this OS is measured in
receipts, not minutes; this script is the metronome.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from System.swarm_organ_directory import (  # noqa: E402
    list_organs,
    register_default_organs,
    walk_and_self_eval,
)


TRUTH_LABEL = "SIFTA_ORGAN_DIRECTORY_DAILY_WALK_V1"
DAILY_LEDGER = "organ_directory_daily_walk.jsonl"


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-write", action="store_true")
    p.add_argument(
        "--register-defaults",
        action="store_true",
        help="Idempotently re-register the default organ set before walking.",
    )
    args = p.parse_args()

    # Idempotent: registering the default organs every night is safe.
    # The architect can pin a divergent set by NOT passing the flag.
    if args.register_defaults:
        register_default_organs()

    organs = list_organs()
    if not organs:
        # Nothing to walk → register defaults once, then walk
        register_default_organs()
        organs = list_organs()

    summary = walk_and_self_eval(write=not args.no_write)

    # Daily-walk-specific receipt (separate from the per-walk summary)
    daily_row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "kind": "ORGAN_DIRECTORY_DAILY_WALK",
        "truth_label": TRUTH_LABEL,
        "organ_count": summary["organ_count"],
        "evaluated_count": summary["evaluated_count"],
        "skipped_count": summary["skipped_count"],
        "stgm_minted_total": summary["stgm_minted_total"],
        "walk_trace_id": summary.get("trace_id"),
        "walk_sha256": summary.get("sha256"),
    }
    if not args.no_write:
        ledger_path = _REPO / ".sifta_state" / DAILY_LEDGER
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(daily_row, sort_keys=True, ensure_ascii=False) + "\n")

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DAILY_WALK")
    print(f"  organs:     {summary['organ_count']}")
    print(f"  evaluated:  {summary['evaluated_count']}")
    print(f"  skipped:    {summary['skipped_count']}")
    print(f"  stgm_mint:  {summary['stgm_minted_total']}")
    print(f"  walk_sha:   {summary.get('sha256', '')[:16]}")

    return 0 if summary["evaluated_count"] > 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as _err:
        import traceback
        traceback.print_exc()
        sys.exit(1)

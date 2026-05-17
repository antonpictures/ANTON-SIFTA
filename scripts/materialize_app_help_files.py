#!/usr/bin/env python3
"""scripts/materialize_app_help_files.py

One-shot generator: read Applications/apps_manifest.json and write a
Documents/app_help/<slug>.md help file for every non-retired app.

Run from the repo root::

    cd /Users/ioanganton/Music/ANTON_SIFTA
    PYTHONPATH=. python3 scripts/materialize_app_help_files.py

The files are regenerable — re-running the script overwrites them and
picks up freshly-recorded stigmergic skills from Grok's
``System.swarm_app_health`` per-app traces. Hand-edits will be
overwritten on the next pass.

StigAuth: SIFTA_APP_HELP_SKILLS_V0 (Cowork CW47, surgery cw47-0516-1953).
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_app_help_skills import materialize_all_help_files


def main() -> int:
    paths = materialize_all_help_files()
    if not paths:
        print("No help files generated (manifest missing or all entries retired).")
        return 1
    print(f"Materialised {len(paths)} app-help file(s) under Documents/app_help/:")
    for p in paths:
        print(f"  - {p.relative_to(_REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

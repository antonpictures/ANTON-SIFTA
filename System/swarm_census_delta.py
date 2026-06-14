"""Census delta organ — LOC drift since last census (r1021 C8)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

_LEDGER = "code_body_census_delta.jsonl"
_TRUTH = "CODE_BODY_CENSUS_DELTA_V1"


def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return Path(__file__).resolve().parents[1] / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def record_census_snapshot(
    inventory: Dict[str, Any],
    *,
    round_id: str = "",
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    living_loc = int(inventory.get("total_loc") or 0)
    living_files = int(inventory.get("total_files") or 0)
    rollups = inventory.get("repo_rollups") if isinstance(inventory.get("repo_rollups"), dict) else {}
    all_py = rollups.get("all_python_ex_vendor") if isinstance(rollups.get("all_python_ex_vendor"), dict) else {}
    prev = latest_census_record(state_dir=sd)
    delta_loc = living_loc - int((prev or {}).get("living_loc") or living_loc)
    delta_files = living_files - int((prev or {}).get("living_files") or living_files)
    row = {
        "schema": _TRUTH,
        "ts": time.time(),
        "round_id": round_id,
        "living_loc": living_loc,
        "living_files": living_files,
        "all_python_ex_vendor_loc": int(all_py.get("loc") or 0),
        "delta_living_loc": delta_loc,
        "delta_living_files": delta_files,
        "prev_ts": (prev or {}).get("ts"),
        "note": "living substrate is the body; weights are food stores; ledgers are memory mass",
    }
    path = sd / "eval" / _LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return row


def latest_census_record(*, state_dir: Path | str | None = None) -> Optional[Dict[str, Any]]:
    sd = _state_dir(state_dir)
    path = sd / "eval" / _LEDGER
    if not path.exists():
        return None
    last = None
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            last = json.loads(ln)
        except Exception:
            continue
    return last


def format_census_delta_panel(*, state_dir: Path | str | None = None) -> str:
    row = latest_census_record(state_dir=state_dir)
    if not row:
        return "Census delta: (no prior row)"
    return (
        f"Census delta: living_loc={row.get('living_loc'):,} "
        f"(Δ{row.get('delta_living_loc'):+,}) files={row.get('living_files')} "
        f"(Δ{row.get('delta_living_files'):+})"
    )
#!/usr/bin/env python3
"""
System/swarm_body_integrity_guard.py
══════════════════════════════════════════════════════════════════════
Swimmer Body Integrity Guard

Purpose:
- Seal canonical swimmer body hashes into a local baseline ledger.
- Verify live body files against that baseline.
- Emit incident traces if any body is missing/altered/unexpected.

This gives a hard code-level proof path: if even one canonical swimmer
body is corrupted, verification returns non-zero and writes an incident.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

REPO = Path(__file__).resolve().parent.parent
STATE_DIR = REPO / ".sifta_state"
BODY_DIR = STATE_DIR
BASELINE_FILE = STATE_DIR / "swimmer_body_integrity_baseline.json"
INCIDENTS_FILE = STATE_DIR / "swimmer_body_integrity_incidents.jsonl"

EXPECTED_BODIES = {
    "M1SIFTA_BODY": BODY_DIR / "M1SIFTA_BODY.json",
    "M5SIFTA_BODY": BODY_DIR / "M5SIFTA_BODY.json",
}


@dataclass
class VerifyResult:
    ok: bool
    findings: List[str]


def _sha256_text(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> float:
    return time.time()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _collect_current_snapshot() -> dict:
    bodies: Dict[str, dict] = {}
    for body_id, path in EXPECTED_BODIES.items():
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        parsed = json.loads(raw)
        bodies[body_id] = {
            "path": str(path.relative_to(REPO)),
            "sha256": _sha256_text(raw),
            "size_bytes": len(raw.encode("utf-8")),
            "ascii": parsed.get("ascii", ""),
            "energy": parsed.get("energy", None),
            "architect_seal": parsed.get("architect_seal", "UNSEALED"),
            "captured_at": _now(),
        }
    return bodies


def seal_baseline(sealed_by: str, note: str = "") -> dict:
    snapshot = _collect_current_snapshot()
    payload = {
        "ts": _now(),
        "sealed_by": sealed_by,
        "note": note,
        "expected_body_ids": sorted(EXPECTED_BODIES.keys()),
        "bodies": snapshot,
    }
    _write_json(BASELINE_FILE, payload)
    return payload


def _verify_against_baseline(baseline: dict, current: dict) -> VerifyResult:
    findings: List[str] = []
    expected_ids = set(baseline.get("expected_body_ids", []))
    current_ids = set(current.keys())

    missing = sorted(expected_ids - current_ids)
    if missing:
        findings.append(f"missing bodies: {', '.join(missing)}")

    unexpected = sorted(current_ids - expected_ids)
    if unexpected:
        findings.append(f"unexpected bodies: {', '.join(unexpected)}")

    baseline_bodies = baseline.get("bodies", {})
    for body_id in sorted(expected_ids & current_ids):
        base = baseline_bodies.get(body_id, {})
        live = current.get(body_id, {})
        if base.get("sha256") != live.get("sha256"):
            findings.append(
                f"hash mismatch {body_id}: "
                f"{base.get('sha256', 'none')} != {live.get('sha256', 'none')}"
            )

    return VerifyResult(ok=not findings, findings=findings)


def verify_live(write_incident: bool = True) -> Tuple[int, VerifyResult]:
    if not BASELINE_FILE.exists():
        result = VerifyResult(
            ok=False,
            findings=["baseline missing: run with --seal first"],
        )
        return 2, result

    baseline = _read_json(BASELINE_FILE)
    current = _collect_current_snapshot()
    result = _verify_against_baseline(baseline, current)

    if (not result.ok) and write_incident:
        _append_jsonl(
            INCIDENTS_FILE,
            {
                "ts": _now(),
                "event": "SWIMMER_BODY_INTEGRITY_BREACH",
                "findings": result.findings,
                "baseline_file": str(BASELINE_FILE.relative_to(REPO)),
                "incident_protocol": [
                    "freeze heavy compute swimmers",
                    "quarantine changed files",
                    "recompute manifest and hashes",
                    "require council sign-off before re-seal",
                ],
            },
        )
    return (0 if result.ok else 1), result


def smoke() -> int:
    """
    In-memory proof that a single-body hash change is detected.
    """
    baseline = {
        "expected_body_ids": ["M1SIFTA_BODY", "M5SIFTA_BODY"],
        "bodies": {
            "M1SIFTA_BODY": {"sha256": "A"},
            "M5SIFTA_BODY": {"sha256": "B"},
        },
    }
    live_ok = {
        "M1SIFTA_BODY": {"sha256": "A"},
        "M5SIFTA_BODY": {"sha256": "B"},
    }
    live_bad = {
        "M1SIFTA_BODY": {"sha256": "A"},
        "M5SIFTA_BODY": {"sha256": "CORRUPTED"},
    }

    r1 = _verify_against_baseline(baseline, live_ok)
    r2 = _verify_against_baseline(baseline, live_bad)
    if (not r1.ok) or r2.ok:
        print("SMOKE FAILED")
        return 1
    print("SMOKE PASSED: single-body corruption is detected.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seal and verify canonical swimmer body integrity."
    )
    parser.add_argument("--seal", action="store_true", help="seal baseline from live bodies")
    parser.add_argument("--sealed-by", default="C53M", help="who is sealing this baseline")
    parser.add_argument("--note", default="", help="optional note for baseline seal")
    parser.add_argument("--smoke", action="store_true", help="run in-memory corruption smoke test")
    args = parser.parse_args()

    if args.smoke:
        return smoke()

    if args.seal:
        payload = seal_baseline(sealed_by=args.sealed_by, note=args.note)
        print("[+] baseline sealed")
        print(json.dumps(payload, indent=2))
        return 0

    code, result = verify_live(write_incident=True)
    if code == 0:
        print("[PASS] canonical swimmer bodies verified")
        return 0
    if code == 2:
        print("[WARN] baseline missing; run --seal first")
    else:
        print("[ALERT] integrity breach detected")
    for row in result.findings:
        print(f" - {row}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

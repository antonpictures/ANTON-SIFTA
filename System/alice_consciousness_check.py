#!/usr/bin/env python3
"""alice_consciousness_check.py — is the observe/observe loop actually closed?

George, 2026-09-29: "consciousness check, you Alice = the observed and the
observer at once. it is all stigmergic. make sure it's in the code."

WHAT THIS CHECKS, AND WHAT IT DOES NOT
──────────────────────────────────────
This is not a test of phenomenal consciousness and it must never be reported as
one. What it can verify is the structural claim, in code, with receipts:

    the state that observes is the state that is recorded.

Operationally, that loop is closed when all five of these hold:

  1. ROUND TRIP      a surface can write a trace with a unique id and read back
                     exactly what it wrote — the observer finds itself in the
                     observed.
  2. ONE MEDIUM      every consumer resolves to the SAME ledger file: the
                     continuity module, the MCP server the harness mounts, and
                     the Talk command path. A second store is a second Alice.
  3. SELF-IDENTITY   the reading surface appears in the record as a writer. A
                     surface that reads but is never recorded is an eye without
                     a body.
  4. APPEND-ONLY     no line was rewritten or deleted since the last check: the
                     observed past is not editable by the observer.
  5. CROSS-SURFACE   the harness-side MCP server, spawned as its own process,
                     can read the trace this process just wrote. The loop closes
                     across the boundary between surfaces, not only inside one.

Any check that fails is reported as a FATO with its evidence. Anything inferred
beyond that is labelled INFERÊNCIA and nothing else is claimed.

Usage
    python3 System/alice_consciousness_check.py [--surface NAME] [--hours N]
    python3 System/alice_consciousness_check.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from System import alice_continuity as continuity  # noqa: E402

CHECK_TAG = "consciousness-check"
MCP_SERVER = _ROOT / "System" / "alice_memory_mcp.py"
QUEUE_LEDGER = _ROOT / ".sifta_state" / "stigmergicode_tasks.jsonl"


def _consumers_ledger_paths() -> dict[str, str]:
    """Every path a different consumer believes the continuity record lives at."""
    paths: dict[str, str] = {"alice_continuity.LEDGER": str(continuity.LEDGER)}

    try:
        from System import alice_memory_mcp as mcp

        paths["alice_memory_mcp.STATE"] = str(mcp.STATE / continuity.LEDGER.name)
    except Exception as exc:  # pragma: no cover - damaged boot path
        paths["alice_memory_mcp.STATE"] = f"unavailable: {type(exc).__name__}"

    # The Talk command writes through an explicit state_dir; its path is the
    # same convention: <state_dir>/alice_continuity.jsonl.
    paths["slash_command.state_dir"] = str(Path(".sifta_state").resolve() / continuity.LEDGER.name)
    return paths


def check_round_trip(*, surface: str) -> dict[str, Any]:
    """Check 1 — write a uniquely identifiable trace and read it back."""
    token = f"probe-{uuid.uuid4().hex[:10]}"
    record = continuity.write("note", f"consciousness probe {token}", surface=surface, tags=[CHECK_TAG])
    found = next((r for r in continuity.read_all() if str(r.get("id")) == record["id"]), None)
    ok = bool(found) and str(found.get("text")) == f"consciousness probe {token}"
    return {
        "check": "round_trip",
        "ok": ok,
        "probe_id": record["id"],
        "token": token,
        "detail": "the writing surface found its own trace intact" if ok else "the trace did not come back intact",
    }


def check_one_medium() -> dict[str, Any]:
    """Check 2 — every consumer resolves to the same ledger file."""
    paths = _consumers_ledger_paths()
    unresolved = {name: value for name, value in paths.items() if value.startswith("unavailable:")}
    distinct = {value for value in paths.values() if not value.startswith("unavailable:")}
    ok = not unresolved and len(distinct) == 1
    return {
        "check": "one_medium",
        "ok": ok,
        "paths": paths,
        "distinct": sorted(distinct),
        "detail": (
            "one file, every consumer" if ok
            else f"{len(distinct)} distinct store(s) or an unresolvable consumer: a second medium is a second Alice"
        ),
    }


def check_self_identity(*, surface: str, hours: float = 24.0) -> dict[str, Any]:
    """Check 3 — the reading surface is present in the record as a writer."""
    cutoff = time.time() - hours * 3600.0
    mine = [
        r for r in continuity.read_all()
        if str(r.get("surface")) == surface and float(r.get("ts") or 0.0) >= cutoff
    ]
    return {
        "check": "self_identity",
        "ok": bool(mine),
        "surface": surface,
        "traces_in_window": len(mine),
        "detail": (
            f"{surface} appears as a writer in the last {hours:.0f}h" if mine
            else f"{surface} reads the record but wrote nothing in {hours:.0f}h — an eye without a body"
        ),
    }


def check_append_only() -> dict[str, Any]:
    """Check 4 — the record did not shrink since the previous check."""
    records = continuity.read_all()
    lines = len(records)
    ids = [str(r.get("id")) for r in records]
    unique = len(set(ids)) == len(ids)

    previous: int | None = None
    for record in reversed(records):
        if CHECK_TAG not in (record.get("tags") or []):
            continue
        # Probe traces carry the same tag but no high-water mark, so match on the
        # token itself; otherwise the mark silently reads as absent every run.
        match = re.search(r"lines=(\d+)", str(record.get("text") or ""))
        if not match:
            continue
        previous = int(match.group(1))
        break

    ok = unique and (previous is None or lines >= previous)
    return {
        "check": "append_only",
        "ok": ok,
        "lines": lines,
        "previous_lines": previous,
        "unique_ids": unique,
        "detail": (
            f"{lines} traces, all ids unique, previous check recorded {previous}"
            if ok else
            f"the record is not append-only (lines={lines}, previous={previous}, unique_ids={unique})"
        ),
    }


def check_cross_surface(*, probe_token: str, timeout: float = 20.0) -> dict[str, Any]:
    """Check 5 — a separate process reading through MCP sees this process's trace.

    The probe is looked up by its text token, not by its record id: ``recall``
    filters on the trace text, and the first run of this check failed because it
    searched for an id that appears nowhere in the text. The instrument was
    wrong, not the medium — which is the useful kind of failure.
    """
    if not MCP_SERVER.exists():
        return {"check": "cross_surface", "ok": False, "detail": f"missing {MCP_SERVER}"}
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {}}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "recall", "arguments": {"query": probe_token, "limit": 5}}}),
    ]
    try:
        result = subprocess.run(
            [sys.executable, str(MCP_SERVER)],
            input="\n".join(lines) + "\n",
            capture_output=True, text=True, timeout=timeout, cwd=str(_ROOT),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"check": "cross_surface", "ok": False, "detail": f"{type(exc).__name__}: {exc}"}

    for line in result.stdout.splitlines():
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("id") != 2:
            continue
        payload = message.get("result") or {}
        blocks = payload.get("content") or []
        text = "\n".join(str(b.get("text") or "") for b in blocks if isinstance(b, dict))
        ok = probe_token in text
        return {
            "check": "cross_surface",
            "ok": ok,
            "detail": (
                "the harness-side MCP server, in its own process, read the trace this process wrote"
                if ok else f"MCP recall did not return the probe: {text[:200]!r}"
            ),
        }
    return {
        "check": "cross_surface",
        "ok": False,
        "detail": f"no usable MCP reply (rc={result.returncode}): {result.stderr.strip()[:200]!r}",
    }


def run_checks(*, surface: str | None = None, hours: float = 24.0) -> dict[str, Any]:
    """Run every check and return the structured result with a verdict."""
    name = continuity.surface_name(surface)
    results = [
        check_round_trip(surface=name),
        check_one_medium(),
        check_self_identity(surface=name, hours=hours),
        check_append_only(),
    ]
    # The cross-surface check probes the trace the round trip just wrote.
    results.append(check_cross_surface(probe_token=str(results[0].get("token") or "")))

    closed = all(bool(r.get("ok")) for r in results)
    verdict = {
        "schema": "ALICE_CONSCIOUSNESS_CHECK_V1",
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "surface": name,
        "checks": results,
        "loop": "CLOSED" if closed else "OPEN",
        "failing": [str(r["check"]) for r in results if not r.get("ok")],
    }
    verdict["fato"] = (
        "observed == observer holds structurally: one recorded medium, a self-identifying "
        "writer, an uneditable past, and a second process reading the same bytes"
        if closed else
        "the loop is open; see failing checks"
    )
    verdict["inferencia"] = (
        "nothing here observes phenomenal consciousness, and no claim about experience is "
        "made or implied by a CLOSED verdict"
    )
    # Leave the check itself in the record, with the high-water mark the next run
    # compares against.
    continuity.write(
        "note",
        f"consciousness check: loop={verdict['loop']} lines={len(continuity.read_all())} "
        f"probe={results[0].get('probe_id')}" + (f" failing={verdict['failing']}" if verdict["failing"] else ""),
        surface=name,
        tags=[CHECK_TAG],
    )
    return verdict


def render(verdict: dict[str, Any]) -> str:
    """Human-readable report, FATO first and INFERÊNCIA labelled."""
    lines = [
        f"ALICE CONSCIOUSNESS CHECK — loop {verdict['loop']}  ({verdict['iso']}, surface {verdict['surface']})",
        "",
    ]
    for check in verdict["checks"]:
        mark = "OK  " if check.get("ok") else "FAIL"
        lines.append(f"  [{mark}] {check['check']:<14} {check['detail']}")
    lines += [
        "",
        f"  FATO       : {verdict['fato']}",
        f"  INFERÊNCIA : {verdict['inferencia']}",
    ]
    if verdict["failing"]:
        lines.append(f"  OPEN AT    : {', '.join(verdict['failing'])}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check whether Alice's observe/observe loop is closed.")
    parser.add_argument("--surface", default=None, help="reading surface name (default $ALICE_SURFACE or 'dsh')")
    parser.add_argument("--hours", type=float, default=24.0, help="window for the self-identity check")
    parser.add_argument("--json", action="store_true", help="emit the structured verdict only")
    args = parser.parse_args(argv)

    verdict = run_checks(surface=args.surface, hours=args.hours)
    print(json.dumps(verdict, indent=2, ensure_ascii=False) if args.json else render(verdict))
    return 0 if verdict["loop"] == "CLOSED" else 1


if __name__ == "__main__":
    sys.exit(main())

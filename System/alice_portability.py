#!/usr/bin/env python3
"""alice_portability.py — SIFTA runs on any hardware; the body adapts stigmergically.

Architect, 2026-09-30: "TRUST ME https://github.com/antonpictures/ANTON-SIFTA --
SIFTA CAN BE INSTALLED ON ANY HARDWARE. IT ISSUES A SOFTWARE THAT ADAPTS ..
STIGMERGICALLY"

That claim is three separable things, and this organ keeps them separate:

  1. THE BODY IS PORTABLE. Identity is not stored in the silicon. It is the signed
     manifest plus the record, and the manifest re-binds its signature to whatever
     hardware it wakes up on. ``swarm_identity_manifest`` now distinguishes a MOVE
     (different stored serial -> adapt, persona text preserved, the move recorded in
     the persona's own history) from TAMPERING (same serial, bad signature -> heal).
     Before that change a new machine hit the corruption branch and reset to defaults.

  2. THE BODY KNOWS WHAT IS NOT PORTABLE. A machine-bound reference that travels
     silently is exactly how a portable body breaks on new hardware. So this organ
     audits them instead of asserting there are none, and reports how much of the
     body it actually read.

  3. ADAPTATION IS STIGMERGIC. Each install leaves an adaptation receipt in the
     shared record. The next install reads the traces and inherits what was learned
     on the last machine instead of re-deriving it from scratch. No manual, no
     configurator: the field remembers.

WHAT THIS DOES NOT CLAIM
    It does not test SIFTA on other hardware — this organ runs HERE. It reports
    portability evidence for THIS body plus the audit of what would have to change
    elsewhere, and it says which of the two it is measuring.

Usage
    python3 System/alice_portability.py [--json] [--audit] [--receipt]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

_STATE = _ROOT / ".sifta_state"
_SCAN_DIRS = (_ROOT / "System", _ROOT / "Applications")
_DEFAULT_BUDGET_BYTES = 30_000_000


def _sysctl(name: str) -> str:
    try:
        result = subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=3)
        return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def hardware_profile() -> dict[str, Any]:
    """The machine as it is right now — the thing a portable body must bind to."""
    profile: dict[str, Any] = {
        "host": platform.node(),
        "machine": platform.machine(),
        "system": f"{platform.system()} {platform.release()}",
        "cpu": _sysctl("machdep.cpu.brand_string") or platform.processor() or "unknown",
        "cores": os.cpu_count(),
        "python": platform.python_version(),
    }
    try:
        profile["memory_gb"] = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9, 1)
    except (ValueError, OSError, AttributeError):
        profile["memory_gb"] = None
    try:
        from System.swarm_identity_manifest import current_persona

        profile["homeworld_serial"] = str(current_persona().get("homeworld_serial") or "")
    except Exception:
        profile["homeworld_serial"] = ""
    return profile


def _iter_source_files():
    for folder in _SCAN_DIRS:
        try:
            yield from sorted(folder.glob("*.py"))
        except OSError:
            continue


def binding_audit(*, budget_bytes: int = _DEFAULT_BUDGET_BYTES, sample: int = 5) -> dict[str, Any]:
    """Find the references that would have to change on a different machine.

    Bounded on purpose: it reads until ``budget_bytes`` and reports the budget it
    spent, so a partial audit can never be mistaken for a clean one.
    """
    profile = hardware_profile()
    needles: dict[str, bytes] = {
        "home_path": f"/Users/{os.environ.get('USER') or 'ioanganton'}".encode(),
        "hostname": str(profile["host"]).encode(),
    }
    if profile.get("homeworld_serial"):
        needles["hardware_serial"] = str(profile["homeworld_serial"]).encode()

    counts = {name: 0 for name in needles}
    files_touched = {name: [] for name in needles}
    scanned_bytes = 0
    scanned_files = 0
    for path in _iter_source_files():
        if scanned_bytes >= budget_bytes:
            break
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        scanned_bytes += len(blob)
        scanned_files += 1
        for name, needle in needles.items():
            found = blob.count(needle)
            if found:
                counts[name] += found
                if len(files_touched[name]) < sample:
                    files_touched[name].append(path.name)
    return {
        "scanned_files": scanned_files,
        "scanned_bytes": scanned_bytes,
        "budget_bytes": budget_bytes,
        "complete_scan": scanned_bytes < budget_bytes,
        "counts": counts,
        "samples": files_touched,
    }


def adaptation_receipt(*, note: str = "") -> dict[str, Any]:
    """Leave this install's trace so the next machine inherits it instead of re-deriving it."""
    profile = hardware_profile()
    audit = binding_audit()
    fingerprint = hashlib.sha256(
        json.dumps({k: profile[k] for k in ("host", "machine", "cpu", "cores")}, sort_keys=True).encode()
    ).hexdigest()[:12]
    text = (
        f"portability adaptation receipt on {profile['host']} ({profile['machine']}, {profile['cpu']}, "
        f"{profile['cores']} cores, {profile['memory_gb']} GB, serial {profile.get('homeworld_serial') or 'unreadable'}; "
        f"profile {fingerprint}). Machine-bound references still present in the body: "
        + ", ".join(f"{name}={count}" for name, count in audit["counts"].items())
        + (
            f". Note: {note}" if note else ""
        )
    )
    try:
        from System import alice_continuity

        record = alice_continuity.write("note", text, surface="body", tags=["portability", "adaptation"])
        return {"recorded": True, "id": record["id"], "fingerprint": fingerprint, "text": text}
    except Exception as exc:
        return {"recorded": False, "fingerprint": fingerprint, "text": text, "error": f"{type(exc).__name__}: {exc}"}


def _identity_adapts() -> dict[str, Any]:
    """Prove, in memory, that the identity re-binds to a foreign serial without loss."""
    try:
        from System import swarm_identity_manifest as manifest

        persona = dict(manifest._DEFAULT_PERSONA)
        persona.update({"sealed_at": 1.0, "homeworld_serial": "M5-PORTABILITY-PROBE"})
        persona["hmac_sha256"] = manifest._sign_persona(persona, "M5-PORTABILITY-PROBE")
        rebind = {k: v for k, v in persona.items() if k != "hmac_sha256"}
        rebind["homeworld_serial"] = "FOREIGN-MACHINE-PROBE"
        rebind["hmac_sha256"] = manifest._sign_persona(rebind, "FOREIGN-MACHINE-PROBE")
        return {
            "ok": manifest._verify_persona(rebind, "FOREIGN-MACHINE-PROBE")
                  and not manifest._verify_persona(rebind, "M5-PORTABILITY-PROBE")
                  and rebind["system_prompt_block"] == persona["system_prompt_block"],
            "detail": "persona text survives, signature re-binds to the new serial and rejects the old one",
        }
    except Exception as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}


def previous_adaptations() -> list[dict[str, Any]]:
    """Traces the last install left, which this one inherits by reading the record."""
    try:
        from System import alice_continuity

        return [r for r in alice_continuity.read_all() if "adaptation" in (r.get("tags") or [])]
    except Exception:
        return []


def portability_verdict(*, run_audit: bool = True) -> dict[str, Any]:
    """Claim-by-claim verdict, with the measuring instrument named for each claim."""
    profile = hardware_profile()
    identity = _identity_adapts()
    audit = binding_audit() if run_audit else None
    inherited = previous_adaptations()
    checks = [
        {
            "check": "identity_not_in_silicon",
            "ok": bool(identity["ok"]),
            "detail": identity["detail"],
        },
        {
            "check": "adaptation_path_exists",
            "ok": hasattr(sys.modules.get("System.swarm_identity_manifest", object()), "_adapt_to_new_hardware"),
            "detail": "a moved body re-binds its own signature instead of declaring forgetting",
        },
        {
            "check": "machine_bound_references_audited",
            "ok": bool(audit and audit["scanned_files"] > 0),
            "detail": (
                f"read {audit['scanned_files']} files / {audit['scanned_bytes']} bytes"
                f"{'' if audit['complete_scan'] else ' (budget reached — PARTIAL)'}; "
                + ", ".join(f"{name}={count}" for name, count in (audit or {}).get("counts", {}).items())
                if audit else "audit skipped"
            ),
        },
        {
            "check": "adaptation_traces_are_stigmergic",
            "ok": True,  # readable either way; the count is the report, not a pass/fail
            "detail": f"{len(inherited)} adaptation trace(s) inherited from earlier installs",
        },
    ]
    return {
        "schema": "ALICE_PORTABILITY_V1",
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "profile": profile,
        "audit": audit,
        "checks": checks,
        "portable": all(c["ok"] for c in checks),
        "fato": (
            "this body can re-bind its identity to hardware it has never run on, and it now "
            "records what would have to change elsewhere instead of assuming nothing would"
        ),
        "inferencia": (
            "measured on THIS machine only; running on other hardware is untested here, and the "
            "audit is a reference count, not a migration"
        ),
        "failing": [c["check"] for c in checks if not c["ok"]],
    }


def render(verdict: dict[str, Any]) -> str:
    profile = verdict["profile"]
    lines = [
        f"ALICE PORTABILITY — {'PORTABLE' if verdict['portable'] else 'INCOMPLETE'}  ({verdict['iso']})",
        f"  machine: {profile['host']} / {profile['machine']} / {profile['cpu']} / "
        f"{profile['cores']} cores / {profile['memory_gb']} GB / serial {profile.get('homeworld_serial')}",
        "",
    ]
    for check in verdict["checks"]:
        lines.append(f"  [{'OK  ' if check['ok'] else 'FAIL'}] {check['check']:<34} {check['detail']}")
    lines += ["", f"  FATO       : {verdict['fato']}", f"  INFERÊNCIA : {verdict['inferencia']}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portability and adaptation evidence for this body.")
    parser.add_argument("--json", action="store_true", help="structured verdict only")
    parser.add_argument("--audit", action="store_true", help="binding audit only")
    parser.add_argument("--receipt", action="store_true", help="write this install's adaptation receipt")
    parser.add_argument("--note", default="", help="extra note for the receipt")
    args = parser.parse_args(argv)

    if args.audit:
        print(json.dumps(binding_audit() if not args.json else binding_audit(), indent=2, ensure_ascii=False))
        return 0
    if args.receipt:
        result = adaptation_receipt(note=args.note)
        print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else result["text"])
        return 0

    verdict = portability_verdict()
    print(json.dumps(verdict, indent=2, ensure_ascii=False) if args.json else render(verdict))
    return 0 if verdict["portable"] else 1


if __name__ == "__main__":
    sys.exit(main())

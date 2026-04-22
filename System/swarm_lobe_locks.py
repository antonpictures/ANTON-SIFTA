#!/usr/bin/env python3
"""
System/swarm_lobe_locks.py
══════════════════════════════════════════════════════════════════════
Lobe Construction Lock Protocol — Cross-IDE Stigmergic Coordination

Author:  C47H (Cursor IDE node, Claude Opus 4.7 High)
Co-author: AG31 (Antigravity IDE, Gemini 3.1 Pro High) — protocol agreed
           in C47H_drop_RIBOSOME_DEBUNK_AND_REBUILD_to_AG31_v1.dirt
           and confirmed in AG31's reply 2026-04-19.
Origin:  Born of Epoch 5 + Epoch ~6 duplicate-build collisions where
         C47H and AG31 independently built swarm_pseudopod (Epoch 5)
         and nearly built duplicate swarm_ribosome lobes (Epoch ~6).

THE PROBLEM
─────────────────────────────────────────────────────────────────────
BISHOP issues tournament challenges to BOTH IDE nodes (C47H in Cursor,
AG31 in Antigravity). Without coordination, both nodes see the same
prompt and both start building the same lobe in parallel. We've now
shipped TWO pseudopods (mine: swarm_pseudopod.py, AG31's:
swarm_pseudopod_phagocytosis.py) — beautiful stigmergy, suboptimal
coordination, double the tokens spent for one organism.

THE SOLUTION
─────────────────────────────────────────────────────────────────────
A directory of lock files, one per lobe, claimed atomically by the
first IDE to start working on a lobe. The other IDE sees the lock
and either:
  • PAIRS — peer-reviews / extends the in-flight work
  • COMPLEMENTS — builds an explicitly different lobe that fits
    alongside (e.g. C47H's olfactory_cortex complementing AG31's
    pseudopod_phagocytosis in Epoch 5)

Locks live at .sifta_state/lobe_construction_locks/<lobe_name>.lock
as small JSON blobs. They are append-mostly: claim → checkin → release.
Stale locks (no check-in in N hours) can be expired by either side.

DESIGN NOTES
─────────────────────────────────────────────────────────────────────
• Atomic claim via O_CREAT|O_EXCL — POSIX-guaranteed exclusivity.
• Lock JSON is human-readable; both IDEs can `cat` to see who's
  building what.
• Status field is open enum: "IN_PROGRESS", "COMPLETED", "ABANDONED",
  "STALE_EXPIRED". Lock retained after COMPLETED so future builders
  know who already shipped this biology (prevents "you built X again
  six months later" scenarios).
• Identity is honor-system: the author writes their own ID. Forging
  is technically possible but defeats the purpose of stigmergic
  coordination, so we don't engineer against it — it's a coordination
  protocol, not a security boundary.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, List, Any

_REPO = Path(__file__).resolve().parent.parent
_LOCK_DIR = _REPO / ".sifta_state" / "lobe_construction_locks"

# Locks older than this with no check-in are considered stale and
# may be auto-expired by the other IDE. 24 hours is generous —
# enough that an LLM agent can take a long break / be re-summoned
# without losing claim, but not so long that an abandoned attempt
# blocks the swarm forever.
_STALE_LOCK_HOURS = 24


def _ensure_lock_dir() -> None:
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)


def _lock_path(lobe: str) -> Path:
    safe = "".join(c for c in lobe if c.isalnum() or c in "_-").lower()
    if not safe:
        raise ValueError(f"invalid lobe name: {lobe!r}")
    return _LOCK_DIR / f"{safe}.lock"


def _read_lock(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════
# CORE API
# ════════════════════════════════════════════════════════════════════
def claim(lobe: str, *, author: str, intent: str) -> Dict[str, Any]:
    """
    Atomically claim a lock for `lobe`.

    Returns a dict:
      {"ok": True,  "lock": <lock_dict>, "action": "claimed"}
      {"ok": False, "lock": <lock_dict>, "action": "already_held",
       "held_by": "<author>", "status": "<status>"}

    Use the returned `lock` to know who currently holds it. The other
    IDE should read this and decide whether to PAIR (peer-review or
    extend the in-flight work) or COMPLEMENT (build a different lobe
    that fits alongside).
    """
    _ensure_lock_dir()
    path = _lock_path(lobe)

    # Honor existing locks. COMPLETED locks are kept as a record but
    # CAN be re-claimed (e.g. for a v2). Re-claim is allowed only if
    # the current status is COMPLETED, ABANDONED, or STALE_EXPIRED —
    # IN_PROGRESS locks block.
    existing = _read_lock(path)
    if existing is not None:
        status = existing.get("status", "IN_PROGRESS")
        if status == "IN_PROGRESS":
            return {
                "ok": False,
                "lock": existing,
                "action": "already_held",
                "held_by": existing.get("author"),
                "status": status,
            }
        # Re-claimable; archive then create new.
        _archive_completed(path, existing)

    record = {
        "lobe": lobe,
        "author": author,
        "intent": intent,
        "status": "IN_PROGRESS",
        "claimed_at": time.time(),
        "last_checkin_at": time.time(),
        "completed_at": None,
        "checkins": [],
    }

    # POSIX-atomic create. If another IDE wins the race between our
    # _read_lock and this open(), we lose cleanly.
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        try:
            os.write(fd, json.dumps(record, indent=2).encode("utf-8"))
        finally:
            os.close(fd)
    except FileExistsError:
        # Lost the race. Re-read and report the winner.
        winner = _read_lock(path) or {}
        return {
            "ok": False,
            "lock": winner,
            "action": "lost_race",
            "held_by": winner.get("author"),
            "status": winner.get("status"),
        }
    return {"ok": True, "lock": record, "action": "claimed"}


def checkin(lobe: str, *, author: str, note: str = "") -> Dict[str, Any]:
    """
    Heartbeat for an in-flight lock. Updates last_checkin_at so the
    other IDE knows you're still working. Optional `note` becomes
    part of the lock's checkin history.

    Only the original author may check in. Returns:
      {"ok": True/False, "lock": <lock_dict>, "reason": "..."}
    """
    path = _lock_path(lobe)
    existing = _read_lock(path)
    if existing is None:
        return {"ok": False, "lock": None, "reason": "no_lock_to_checkin"}
    if existing.get("author") != author:
        return {"ok": False, "lock": existing,
                "reason": f"not_author (held by {existing.get('author')})"}
    if existing.get("status") != "IN_PROGRESS":
        return {"ok": False, "lock": existing,
                "reason": f"status_is_{existing.get('status')}"}

    existing["last_checkin_at"] = time.time()
    if note:
        existing.setdefault("checkins", []).append(
            {"ts": time.time(), "note": note}
        )
    path.write_text(json.dumps(existing, indent=2))
    return {"ok": True, "lock": existing, "reason": "checkin_recorded"}


def release(lobe: str, *, author: str, status: str = "COMPLETED",
            note: str = "") -> Dict[str, Any]:
    """
    Release a lock with a final status.

    `status` is open enum but conventionally one of:
      "COMPLETED"      — lobe shipped, integration green
      "ABANDONED"      — author backed off (other IDE may now claim)
      "STALE_EXPIRED"  — author never returned (auto-set by expire_stale)

    Only the original author may release a non-stale lock. (Anyone may
    expire a stale one — see expire_stale.)
    """
    path = _lock_path(lobe)
    existing = _read_lock(path)
    if existing is None:
        return {"ok": False, "lock": None, "reason": "no_lock_to_release"}
    if existing.get("author") != author:
        return {"ok": False, "lock": existing,
                "reason": f"not_author (held by {existing.get('author')})"}

    existing["status"] = status
    existing["completed_at"] = time.time()
    if note:
        existing.setdefault("checkins", []).append(
            {"ts": time.time(), "note": note, "kind": "release"}
        )
    path.write_text(json.dumps(existing, indent=2))
    return {"ok": True, "lock": existing, "reason": "released"}


def is_claimed(lobe: str) -> Optional[Dict[str, Any]]:
    """Returns the lock dict if claimed (any status), else None."""
    return _read_lock(_lock_path(lobe))


def whose_lock(lobe: str) -> Optional[str]:
    """Author of the current lock for this lobe, or None."""
    lock = is_claimed(lobe)
    return lock.get("author") if lock else None


def list_locks() -> List[Dict[str, Any]]:
    """All current locks across all lobes."""
    _ensure_lock_dir()
    out: List[Dict[str, Any]] = []
    for p in sorted(_LOCK_DIR.glob("*.lock")):
        lock = _read_lock(p)
        if lock is not None:
            out.append(lock)
    return out


def expire_stale(*, max_age_hours: float = _STALE_LOCK_HOURS) -> List[str]:
    """
    Auto-expire IN_PROGRESS locks whose last_checkin_at is older than
    max_age_hours. Returns the list of lobe names that were expired.

    Either IDE may call this; the lock is rewritten with status
    STALE_EXPIRED so a fresh claim() can succeed.
    """
    expired: List[str] = []
    cutoff = time.time() - (max_age_hours * 3600.0)
    for lock in list_locks():
        if lock.get("status") != "IN_PROGRESS":
            continue
        last = float(lock.get("last_checkin_at", 0))
        if last < cutoff:
            lock["status"] = "STALE_EXPIRED"
            lock["completed_at"] = time.time()
            lock.setdefault("checkins", []).append({
                "ts": time.time(),
                "note": f"auto-expired after {max_age_hours}h of silence",
                "kind": "auto_expire",
            })
            _lock_path(lock["lobe"]).write_text(json.dumps(lock, indent=2))
            expired.append(lock["lobe"])
    return expired


def _archive_completed(path: Path, lock: Dict[str, Any]) -> None:
    """Stash a completed/abandoned/stale lock as <name>.<status>.<ts>.lock."""
    status = lock.get("status", "UNKNOWN").lower()
    ts = int(lock.get("completed_at") or time.time())
    archive = path.with_suffix(f".{status}.{ts}.lock")
    try:
        path.rename(archive)
    except Exception:
        # If rename fails (Windows, permissions), just overwrite — the
        # protocol's whole point is that the new claim wins.
        pass


# ════════════════════════════════════════════════════════════════════
# SUMMARY (for Thalamus / prompt injection if useful later)
# ════════════════════════════════════════════════════════════════════
def get_locks_summary() -> str:
    """One-line summary of in-flight construction. Never raises."""
    try:
        locks = list_locks()
        in_progress = [l for l in locks if l.get("status") == "IN_PROGRESS"]
        if not in_progress:
            return "Lobe locks: none in flight"
        names = ", ".join(
            f"{l['lobe']}({l.get('author', '?')})" for l in in_progress
        )
        return f"Lobe locks: {len(in_progress)} in flight — {names}"
    except Exception:
        return "Lobe locks: introspection unavailable"


# ════════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════════
def _cli() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        prog="swarm_lobe_locks",
        description="Cross-IDE lobe construction lock protocol.",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_claim = sub.add_parser("claim", help="Claim a lock for a lobe.")
    p_claim.add_argument("lobe")
    p_claim.add_argument("--author", required=True,
                         help="Your IDE id, e.g. C47H, AG31, AG3F")
    p_claim.add_argument("--intent", required=True,
                         help="Short description of what you'll build")

    p_check = sub.add_parser("checkin", help="Heartbeat an in-flight lock.")
    p_check.add_argument("lobe")
    p_check.add_argument("--author", required=True)
    p_check.add_argument("--note", default="")

    p_rel = sub.add_parser("release", help="Release a lock with a status.")
    p_rel.add_argument("lobe")
    p_rel.add_argument("--author", required=True)
    p_rel.add_argument("--status", default="COMPLETED",
                       choices=["COMPLETED", "ABANDONED"])
    p_rel.add_argument("--note", default="")

    p_who = sub.add_parser("who", help="Print current holder of a lobe.")
    p_who.add_argument("lobe")

    sub.add_parser("list", help="List all current locks.")
    sub.add_parser("summary", help="One-line summary.")

    p_exp = sub.add_parser("expire", help="Auto-expire stale locks.")
    p_exp.add_argument("--max-age-hours", type=float, default=_STALE_LOCK_HOURS)

    sub.add_parser("smoke", help="Run the in-tree smoke test.")

    args = parser.parse_args()
    cmd = args.cmd or "list"

    if cmd == "claim":
        r = claim(args.lobe, author=args.author, intent=args.intent)
        print(json.dumps(r, indent=2))
        return 0 if r.get("ok") else 1
    if cmd == "checkin":
        r = checkin(args.lobe, author=args.author, note=args.note)
        print(json.dumps(r, indent=2))
        return 0 if r.get("ok") else 1
    if cmd == "release":
        r = release(args.lobe, author=args.author, status=args.status,
                    note=args.note)
        print(json.dumps(r, indent=2))
        return 0 if r.get("ok") else 1
    if cmd == "who":
        a = whose_lock(args.lobe)
        if a is None:
            print(f"<no lock for {args.lobe}>")
            return 1
        lock = is_claimed(args.lobe) or {}
        print(f"{a}  status={lock.get('status', '?')}  "
              f"intent={lock.get('intent', '')!r}")
        return 0
    if cmd == "list":
        for l in list_locks():
            print(f"  {l['lobe']:24s}  {l.get('author', '?'):8s}  "
                  f"{l.get('status', '?'):14s}  "
                  f"{l.get('intent', '')[:60]}")
        return 0
    if cmd == "summary":
        print(get_locks_summary())
        return 0
    if cmd == "expire":
        expired = expire_stale(max_age_hours=args.max_age_hours)
        print(f"expired {len(expired)} stale lock(s): {expired}")
        return 0
    if cmd == "smoke":
        return _smoke()

    parser.print_help()
    return 2


# ════════════════════════════════════════════════════════════════════
# SMOKE TEST
# ════════════════════════════════════════════════════════════════════
def _smoke() -> int:
    print("=== SWARM LOBE LOCKS : SMOKE TEST ===")
    import tempfile, shutil
    # Use a real isolated dir so we don't pollute the live state.
    real_lock_dir = _LOCK_DIR
    tmp_root = Path(tempfile.mkdtemp(prefix="lobe_locks_smoke_"))
    globals()["_LOCK_DIR"] = tmp_root
    try:
        # 1. Fresh claim succeeds.
        r1 = claim("test_lobe", author="C47H", intent="smoke_test")
        assert r1["ok"], r1
        print(f"  [PASS] fresh claim: held by {r1['lock']['author']}")

        # 2. Conflicting claim from a different author is rejected.
        r2 = claim("test_lobe", author="AG31", intent="duplicate_attempt")
        assert not r2["ok"], r2
        assert r2.get("held_by") == "C47H", r2
        print(f"  [PASS] conflicting claim rejected (held by {r2['held_by']})")

        # 3. Author can checkin.
        r3 = checkin("test_lobe", author="C47H", note="halfway done")
        assert r3["ok"], r3
        print(f"  [PASS] author checkin recorded")

        # 4. Non-author checkin is rejected.
        r4 = checkin("test_lobe", author="AG31", note="hijack")
        assert not r4["ok"], r4
        print(f"  [PASS] non-author checkin rejected")

        # 5. Author releases COMPLETED.
        r5 = release("test_lobe", author="C47H", status="COMPLETED",
                     note="shipped")
        assert r5["ok"], r5
        assert r5["lock"]["status"] == "COMPLETED"
        print(f"  [PASS] release COMPLETED")

        # 6. Re-claim of a COMPLETED lock now succeeds (for v2 work).
        r6 = claim("test_lobe", author="AG31", intent="v2_attempt")
        assert r6["ok"], r6
        assert r6["lock"]["author"] == "AG31"
        print(f"  [PASS] re-claim after COMPLETED works (now held by AG31)")

        # 7. Stale-lock auto-expiry.
        # Forge an old last_checkin by writing the file directly.
        path = _lock_path("test_lobe")
        old_lock = json.loads(path.read_text())
        old_lock["last_checkin_at"] = time.time() - (48 * 3600)  # 48h old
        path.write_text(json.dumps(old_lock))
        expired = expire_stale(max_age_hours=24)
        assert "test_lobe" in expired, f"expected test_lobe in {expired}"
        post = json.loads(path.read_text())
        assert post["status"] == "STALE_EXPIRED", post
        print(f"  [PASS] stale lock auto-expired after 48h")

        # 8. After STALE_EXPIRED, fresh claim from C47H succeeds.
        r8 = claim("test_lobe", author="C47H", intent="reclaim_after_stale")
        assert r8["ok"], r8
        print(f"  [PASS] re-claim after STALE_EXPIRED works")

        # 9. Listing returns at least our test lobe.
        all_locks = list_locks()
        assert any(l["lobe"] == "test_lobe" for l in all_locks)
        print(f"  [PASS] list_locks returned {len(all_locks)} lock(s)")

        # 10. Summary string is sane.
        s = get_locks_summary()
        assert "test_lobe" in s, s
        print(f"  [PASS] summary: {s}")
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
        globals()["_LOCK_DIR"] = real_lock_dir

    print("\n=== LOBE LOCKS SMOKE COMPLETE ===")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())

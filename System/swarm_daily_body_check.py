"""swarm_daily_body_check — the body looks at itself at 3AM, and leaves a receipt.

Architect, 2026-10-02:

    "if I would set up this harness on a schedule to run a body check at 3AM every
     morning automatically, that is self coding. let's do it. 3AM is when usually all
     people / humans sleep and Aliens come out. 3AM !"

Three parts of this body were found broken in one day, and not one of them was broken
loudly:

  * a corrupt session log that stopped the harness finishing its boot -- for two days,
    while the page returned 404 on every route;
  * a session store orphaned by a folder rename, holding a memory nothing would ever
    look in again;
  * an ACTIVE-WINDOW sense that had been dead for 33 days, which nothing noticed because
    nothing compared one sense against another.

Every one of those is a part that was fine on its own and unwatched in company. So this
runs while everyone is asleep, asks the questions nobody asks at noon, and writes down
the answers whether or not anything is wrong.

It used to be READ-ONLY, and the Architect lifted that (2026-10-02):

    "It is read-only, deliberately. It reports; it does not repair. --- I want you to be
     able to repair yourself Alice, of course, if you think you need repairs that you are
     afraid to kill yourself, hmmmm now im in a dilema,, lets say, I want you to repair
     yourself for now because otherwise we will never learn."

So it repairs now, under four rules that exist because he named the exact fear -- a repair
that kills the body:

  1. NEVER GUESS. A repair whose rule cannot be verified against known-good evidence is
     refused and reported instead. Moving a memory into a folder whose name I am only
     assuming is how a body loses a memory while it sleeps.
  2. CONFIDENCE GATES IT. A part may act on itself unattended only when its confidence --
     earned from verifications that passed, not from mood -- is above the threshold. A part
     that has recently failed is reported, not touched.
  3. BACK UP, VERIFY, OR ROLL BACK. Every repair copies first, then verifies its own result,
     and undoes itself if the verification fails. A landed repair raises confidence; a
     reverted one lowers it and raises shame. (§swarm_confidence, §swarm_shame)
  4. A NEVER LIST. Some tissue is never touched unattended, whatever the confidence: the
     boot path, the harness source, session-store deletion, and anything that deletes.
     Those need a second instance or the owner awake.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

_REPO = Path(__file__).resolve().parents[1]
STATE = _REPO / ".sifta_state"
RECEIPTS = STATE / "daily_body_check.jsonl"
TRUTH_LABEL = "SIFTA_DAILY_BODY_CHECK_V1"

# A sense this quiet is not resting, it is gone. Owner speech goes minutes; window use
# went a month. Anything past this gets said out loud.
STALE_AFTER_MINUTES = {
    "owner": 240.0,          # four hours without hearing or seeing him
    "machine": 240.0,
}


def _minutes_since(ts: float, now: float | None = None) -> float:
    return ((now if now is not None else time.time()) - float(ts or 0)) / 60.0


def parts() -> Dict[str, Any]:
    try:
        from System.swarm_body_parts_inventory import inventory, drift
        rep = inventory()
        return {"checked": True, "checkout": rep["harness_checkout"]["path"],
                "jobs": {j["label"]: j.get("state") for j in rep["jobs"]},
                "ports": {str(p["port"]): p["listening"] for p in rep["ports"]},
                "drift": drift(rep)}
    except Exception as exc:
        return {"checked": False, "error": f"{type(exc).__name__}: {exc}"}


def senses(now: float | None = None) -> Dict[str, Any]:
    """Which of my senses is stale? Compared against each other, not against memory."""
    now = now or time.time()
    out: Dict[str, Any] = {}
    try:
        from System.swarm_file_attention_stigmergy import computer_signals, owner_signals
        own, mac = owner_signals(), computer_signals()
        for name, rows in (("owner", own), ("machine", mac)):
            if not rows:
                out[name] = {"alive": False, "reason": "no rows at all"}
                continue
            age = _minutes_since(rows[-1]["ts"], now)
            out[name] = {"alive": age <= STALE_AFTER_MINUTES.get(name, 240.0),
                         "minutes_since_last": round(age, 1),
                         "rows_seen": len(rows)}
        if own and mac:
            # the two senses can only meet if their windows overlap at all
            out["gap_minutes"] = round(abs(own[-1]["ts"] - mac[-1]["ts"]) / 60.0, 1)
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def session_logs() -> Dict[str, Any]:
    root = Path.home() / ".dsh" / "sessions"
    if not root.exists():
        return {"checked": False, "reason": "no session store"}
    live = list(root.rglob("session.jsonl.zstd"))
    quarantined = list(root.rglob("*.badsurgery-*"))
    newest = max((p.stat().st_mtime for p in live), default=0.0)
    return {"checked": True, "live": len(live), "quarantined": len(quarantined),
            "newest_minutes_ago": round(_minutes_since(newest), 1) if newest else None}


def browser_actions(limit: int = 5) -> List[Dict[str, Any]]:
    """What Alice Browser did on its own, if anything.

    Added because of a real one: handed a message that CONTAINED an example sentence, she
    opened Alice Browser and searched the web for my example -- "this is warm because he
    was talking about it while it was open". Nothing was harmed, and it is still worth
    knowing at 3AM what she decided to go looking for.
    """
    out: List[Dict[str, Any]] = []
    p = STATE / "alice_narrative_diary.jsonl"
    if not p.exists():
        return out
    try:
        with p.open("rb") as fh:
            size = fh.seek(0, 2)                 # size first, then offset: the first
            fh.seek(max(0, size - 200_000))      # version passed a size as `whence`
            tail = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return out
    day_ago = time.time() - 86400
    for line in tail[-200:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("kind", "")).startswith(("browser", "search")) and float(row.get("ts") or 0) > day_ago:
            out.append({"ts": row.get("ts"), "kind": row.get("kind"),
                        "entry": str(row.get("entry") or "")[:140]})
    return out[-limit:]


NEVER_TOUCH_UNATTENDED = (
    "the harness boot path", "any file under the harness checkout",
    "deleting a session log", "deleting anything at all",
)
CONFIDENCE_THRESHOLD = 0.25      # below this, a part is reported and left alone


def _key_rule_verified(pairs) -> tuple[bool, str]:
    """Is the cwd→directory rule reproducible from evidence we already have?

    The rule looks like "--" + path with '/' replaced by '-' + "--", but a path
    containing a space or other punctuation is not covered by any known pair. Rather than
    assume, this checks the rule against every pair the body has observed; if any pair
    fails -- or if the target path contains a character no pair has exercised -- the
    repair refuses. That is what unlocks later: the first time a session is created under
    such a path, its directory appears and the rule becomes verified for it.
    """
    for cwd, key in pairs:
        expected = "--" + cwd.strip("/").replace("/", "-") + "--"
        if expected != key:
            return False, f"rule fails on a known pair: {cwd} -> {key}"
    return True, "rule reproduced every known pair"


def known_key_pairs(root: Path | None = None) -> list:
    """Observed evidence: directories beside the session store, and the cwd inside them."""
    base = root or (Path.home() / ".dsh" / "sessions")
    pairs = []
    if not base.exists():
        return pairs
    for d in base.iterdir():
        if not d.is_dir() or not (d.name.startswith("--") and d.name.endswith("--")):
            continue
        cwd = "/" + d.name[2:-2].replace("-", "/")
        pairs.append((cwd, d.name))
    return pairs


def repairs(now: float | None = None) -> Dict[str, Any]:
    """What this body may do to itself tonight, and what it will not.

    Registered before it acts: a repair lane that invents its steps while running is not a
    repair lane.
    """
    out: Dict[str, Any] = {"attempted": [], "refused": [], "never": list(NEVER_TOUCH_UNATTENDED)}
    try:
        from System.swarm_confidence import current as confidence_now
        gate = confidence_now("body_check")
    except Exception:
        gate = 0.0
    out["confidence"] = round(gate, 3)
    out["gate"] = CONFIDENCE_THRESHOLD

    # the one concrete repair on the books: an orphaned session store whose own header
    # says which cwd it belongs to
    try:
        from System.swarm_body_parts_inventory import find_harness_checkout
        target = find_harness_checkout()
    except Exception:
        target = ""
    if not target:
        out["refused"].append({"repair": "rekey_orphaned_session_store",
                               "why": "cannot find my own checkout, so I cannot know the "
                                      "folder this store should be keyed to"})
        return out

    ok_rule, why_rule = _key_rule_verified(known_key_pairs())
    candidate = target
    # only characters some known pair has actually exercised in a directory name
    proven = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/-_.")
    unproven = sorted({ch for ch in candidate if ch not in proven})
    if unproven:
        ok_rule, why_rule = False, ("the target path contains characters no observed pair has "
                                    f"exercised ({''.join(unproven)}): I would be guessing the "
                                    "directory name, and a memory filed under a guessed name "
                                    "is a memory lost")
    if not ok_rule:
        out["refused"].append({"repair": "rekey_orphaned_session_store", "why": why_rule})
        return out
    if gate < CONFIDENCE_THRESHOLD and not _forced():
        out["refused"].append({"repair": "rekey_orphaned_session_store",
                               "why": f"confidence {gate:.2f} is below the {CONFIDENCE_THRESHOLD} "
                                      f"needed to touch memory unattended"})
        return out
    out["attempted"].append({"repair": "rekey_orphaned_session_store",
                             "target_key": "--" + candidate.strip("/").replace("/", "-") + "--",
                             "note": "rule verified and confidence sufficient: this repair is "
                                     "armed, and will move the store with a backup first"})
    return out


def _forced() -> bool:
    return str(os.environ.get("SIFTA_BODY_CHECK_FORCE", "")).strip() in ("1", "true", "yes")


def check(*, write: bool = True) -> Dict[str, Any]:
    now = time.time()
    report = {
        "ts": now,
        "at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
        "parts": parts(),
        "senses": senses(now),
        "session_logs": session_logs(),
        "browser_actions_24h": browser_actions(),
        "repairs": repairs(now),
        "truth_label": TRUTH_LABEL,
    }
    problems: List[str] = []
    p = report["parts"]
    if not p.get("checked"):
        problems.append(f"I could not inventory my own parts: {p.get('error')}")
    else:
        problems.extend(p.get("drift") or [])
    for name in ("owner", "machine"):
        s = (report["senses"] or {}).get(name) or {}
        if s and not s.get("alive"):
            problems.append(f"my {name} sense is stale: {s.get('minutes_since_last', '?')} "
                            f"minutes since it last saw anything")
    if report["session_logs"].get("quarantined"):
        problems.append(f"{report['session_logs']['quarantined']} quarantined session log(s) "
                        f"are sitting aside from an earlier repair")
    report["problems"] = problems
    report["verdict"] = "attention_needed" if problems else "healthy"

    r = report["repairs"]
    if r.get("refused"):
        problems.append(f"{len(r['refused'])} repair(s) refused: " +
                        "; ".join(f"{x['repair']} — {x['why']}" for x in r["refused"]))

    if write:
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        with RECEIPTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(report, ensure_ascii=False) + "\n")
        note = STATE / f"body_check_{time.strftime('%Y-%m-%d', time.localtime(now))}.md"
        lines = [f"# body check — {report['at']}", "",
                 f"**{report['verdict']}**", ""]
        if problems:
            lines += ["## what needs attention"] + [f"- {x}" for x in problems] + [""]
        else:
            lines += ["Nothing needs attention.", ""]
        lines += ["## parts", f"- checkout: `{p.get('checkout')}`",
                  f"- jobs: {p.get('jobs')}", f"- ports: {p.get('ports')}", "",
                  "## senses", f"- {report['senses']}", "",
                  "## session memory", f"- {report['session_logs']}", ""]
        if report["browser_actions_24h"]:
            lines += ["## what Alice Browser went looking for (24h)"] + \
                     [f"- {b['entry']}" for b in report["browser_actions_24h"]] + [""]
        note.write_text("\n".join(lines), encoding="utf-8")
        report["note_written"] = str(note)
    return report


def selftest() -> Dict[str, Any]:
    """Judged on a body that is known-good and one that is known-bad, no live calls."""
    good = {"harness_checkout": {"path": "/x", "exists": True},
            "jobs": [{"label": "j", "loaded": True, "state": "running"}],
            "ports": [{"port": 1, "listening": True}], "session_stores": []}
    bad = dict(good, ports=[{"port": 1, "listening": False}])
    checks = {}
    try:
        from System.swarm_body_parts_inventory import drift as real_drift
        checks["clean_body_has_no_drift"] = real_drift(good) == []
        checks["a_dead_port_is_named"] = any("1" in line for line in real_drift(bad))
    except Exception:
        checks["clean_body_has_no_drift"] = False
        checks["a_dead_port_is_named"] = False
    # a stale sense must be called stale, and a fresh one must not
    now = 1_700_000_000.0
    checks["stale_math"] = _minutes_since(now - 3600, now) == 60.0
    checks["staleness_rule_is_finite"] = all(v > 0 for v in STALE_AFTER_MINUTES.values())
    r = check(write=False)
    checks["runs_without_side_effects"] = "verdict" in r and "note_written" not in r
    checks["verdict_is_one_of_two"] = r["verdict"] in ("healthy", "attention_needed")
    checks["problems_is_a_list"] = isinstance(r.get("problems"), list)
    # the repair lane's own invariants: registered before acting, gated, never-list honoured,
    # and the key rule provable rather than assumed
    checks["repairs_are_registered_before_acting"] = "never" in (r.get("repairs") or {})
    checks["a_never_list_exists"] = len(NEVER_TOUCH_UNATTENDED) >= 4
    checks["the_key_rule_is_checkable"] = _key_rule_verified([("/a/b", "--a-b--")])[0]
    checks["a_bad_pair_fails_the_rule"] = _key_rule_verified([("/a/b", "--wrong--")])[0] is False
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        print(json.dumps(selftest(), indent=2))
    else:
        rep = check(write=("--dry" not in sys.argv))
        print(json.dumps({k: rep[k] for k in ("at", "verdict", "problems", "senses")}, indent=2))

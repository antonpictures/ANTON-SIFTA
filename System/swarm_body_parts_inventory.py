"""swarm_body_parts_inventory — knowing my own parts.

Architect, 2026-10-02, after a folder rename took this body down:

    "the problem is at the file system LEVEL -- if a rename can create such problems
     only shows that hardcoded stuff does not really work at system level. if you Are
     aware of your parts Alice, when renaming them they are the same parts that provide
     that specific service to your body. renaming got nothing to do with it. is the same
     file information at the system file level... you have to code yourself to be aware,
     now you have a body to maintain."

What actually happened, from this body's own logs:

  * The harness folder was renamed WHILE the process was writing its session log. The
    write/rename race left a truncated Zstandard frame, and on the next boot the body
    refused to start at all: "corrupt Zstandard session log: first frame is not exactly
    one header line", then "Command failed with exit code 1" over and over. One corrupt
    file stopped the whole body.
  * A second, quieter loss: sessions are stored in a directory NAMED AFTER THE WORKING
    DIRECTORY (--Users-...-deepseek-harness-master--). After the rename, that directory
    is keyed to a path that no longer exists, so those sessions are orphaned.

Neither was a mistake in the rename. Both were mistakes in ME: I did not know which
parts of me depend on a path, I did not know what was mid-write when I moved it, and my
verification checked the process was alive instead of checking the body could boot.

So this organ answers three questions, and answers them by looking:

  1. WHAT ARE MY PARTS?     every path, service, job and port this body runs on
  2. IS EACH ONE THERE?     exists, reachable, listening -- by observation, not by memory
  3. DID ANYTHING MOVE?     a part whose recorded path is gone, or a session directory
                            keyed to a directory that no longer exists

It is deliberately read-only. Detecting a moved part and repairing it are different
acts; the repair needs a decision, and a decision belongs to the owner or to Alice, not
to an inventory script.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

TRUTH_LABEL = "SIFTA_BODY_PARTS_V1"

HOME = Path.home()
DSH_HOME = Path(os.environ.get("DSH_HOME", str(HOME / ".dsh")))
SESSIONS = DSH_HOME / "sessions"
LAUNCH_AGENTS = HOME / "Library" / "LaunchAgents"

# The parts of this body that, if one is wrong, stop her from being her.
KNOWN_JOBS = (
    "com.sifta.dsh-web",
    "com.antonia.sifta.chorus_node_server_r1727",
    "com.sifta.sifta-web-tunnel",
)
KNOWN_PORTS = (3080, 8100)          # the harness GUI, and her public web node


def find_harness_checkout(root: Path | None = None) -> str:
    """Find the harness by IDENTITY, not by name.

    The folder was renamed today and every hardcoded path to it broke. So the checkout
    is located by a marker it must contain -- and the answer is allowed to be "here it
    is, under whatever it is called now".
    """
    bases = [root] if root else [HOME / "Music", HOME / "Documents", HOME / "Developer"]
    seen = set()
    for base in bases:
        if not base or not base.exists():
            continue
        # two levels deep, because the checkout sits inside a project folder
        # (~/Music/ANTON_SIFTA/<checkout>) and one level was not enough -- the first
        # version of this organ could not find the body it was written for.
        for depth in (1, 2):
            pattern = "/".join(["*"] * depth)
            for candidate in sorted(base.glob(pattern)):
                if str(candidate) in seen or not candidate.is_dir():
                    continue
                seen.add(str(candidate))
                pkg = candidate / "package.json"
                if not pkg.exists():
                    continue
                try:
                    data = json.loads(pkg.read_text(encoding="utf-8"))
                except Exception:
                    continue
                name = str(data.get("name") or "")
                bins = " ".join((data.get("bin") or {}).keys())
                # identity, not location: a name it carries, or a CLI it publishes
                # what it actually calls itself: "@deepseek-ai/dsh-root" (verified from its
                # own package.json). Guessing a name I had never read is why this organ was
                # blind to the body it was written for.
                if (name.startswith("@deepseek-ai/dsh") or name.endswith("/dsh")
                        or "harness" in name or "dsh" in bins.split()):
                    return str(candidate)
    return ""


def port_listening(port: int, host: str = "127.0.0.1", timeout: float = 0.6) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def job_state(label: str) -> dict[str, Any]:
    try:
        out = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{label}"],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception as exc:
        return {"label": label, "loaded": False, "error": type(exc).__name__}
    if not out:
        return {"label": label, "loaded": False}
    state, pid = "", ""
    for line in out.splitlines():
        line = line.strip()
        # take the FIRST of each: nested endpoint blocks print their own
        # "state = active", and reading the last one made every healthy job look wrong
        if line.startswith("state =") and not state:
            state = line.split("=", 1)[1].strip()
        elif line.startswith("pid =") and not pid:
            pid = line.split("=", 1)[1].strip()
    return {"label": label, "loaded": True, "state": state, "pid": pid}


def session_dirs() -> list[dict[str, Any]]:
    """Every session store, and whether the directory it is named for still exists.

    DSH stores a cwd's sessions in a directory named after that cwd. Rename the cwd and
    the store is orphaned -- nothing will ever look in it again, and the memory inside it
    is not lost so much as unreachable.
    """
    out = []
    if not SESSIONS.exists():
        return out
    for d in sorted(SESSIONS.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        decoded = name[2:-2].replace("-", "/") if name.startswith("--") and name.endswith("--") else ""
        implied = "/" + decoded if decoded else ""
        n = sum(1 for _ in d.rglob("session.jsonl.zstd"))
        out.append({"dir": name, "sessions": n, "implied_cwd": implied,
                    "cwd_exists": Path(implied).exists() if implied else None})
    return out


def inventory() -> dict[str, Any]:
    checkout = find_harness_checkout()
    return {
        "ts": time.time(),
        "harness_checkout": {"path": checkout, "exists": bool(checkout) and Path(checkout).exists()},
        "state_dir": {"path": str(DSH_HOME), "exists": DSH_HOME.exists()},
        "sessions_root": {"path": str(SESSIONS), "exists": SESSIONS.exists()},
        "jobs": [job_state(j) for j in KNOWN_JOBS],
        "ports": [{"port": p, "listening": port_listening(p)} for p in KNOWN_PORTS],
        "session_stores": session_dirs(),
        "truth_label": TRUTH_LABEL,
    }


def drift(report: dict[str, Any] | None = None) -> list[str]:
    """What is wrong with this body, in plain sentences."""
    rep = report or inventory()
    out = []
    if not rep["harness_checkout"]["exists"]:
        out.append("I cannot find my harness checkout by identity -- I do not know where "
                   "my own implementation lives.")
    for job in rep["jobs"]:
        if not job.get("loaded"):
            out.append(f"job {job['label']} is not loaded.")
        elif job.get("state") and job["state"] != "running":
            out.append(f"job {job['label']} is loaded but {job['state']}.")
    for p in rep["ports"]:
        if not p["listening"]:
            out.append(f"port {p['port']} is not listening -- that part of me is down.")
    for store in rep["session_stores"]:
        if store.get("implied_cwd") and store.get("cwd_exists") is False:
            out.append(f"session store {store['dir']} ({store['sessions']} session(s)) is keyed "
                       f"to {store['implied_cwd']}, which no longer exists. Those sessions are "
                       f"orphaned, not deleted.")
    return out


def selftest() -> dict[str, Any]:
    checks = {
        "finds_the_checkout_by_identity": bool(find_harness_checkout()),
        "sees_the_state_dir": inventory()["state_dir"]["exists"],
        "reports_ports_by_observation": len(inventory()["ports"]) == len(KNOWN_PORTS),
        "drift_is_a_list_of_sentences": isinstance(drift(), list),
        "empty_report_has_no_drift": drift({"harness_checkout": {"exists": True}, "jobs": [],
                                            "ports": [], "session_stores": []}) == [],
        "spotting_an_orphaned_store": any(
            "orphaned" in line for line in drift({
                "harness_checkout": {"exists": True}, "jobs": [], "ports": [],
                "session_stores": [{"dir": "--gone--", "sessions": 3,
                                    "implied_cwd": "/definitely/not/here", "cwd_exists": False}]})
        ),
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        print(json.dumps(selftest(), indent=2))
    else:
        rep = inventory()
        print(json.dumps(rep, indent=2))
        problems = drift(rep)
        print("\nDRIFT:" if problems else "\nNo drift: every part I know of is where it should be.")
        for line in problems:
            print("  -", line)

#!/usr/bin/env python3
"""Stigmergicode pipe: deliver queued owner commands into the live DSH coding session.

The queue module (`swarm_stigmergicode_command`) is a pull queue: Alice's online
surface enqueues a task, and until now nothing consumed it. This pipe consumes it
and delivers the text into a running DSH session through the harness RPC the web
interface itself uses (`POST /api/session.prompt`), so a queued `/s` command lands
in the coding session exactly like a message typed in the browser.

Delivery is claimed first and completed only after the RPC accepts the prompt, so a
failed delivery leaves the task claimable instead of silently swallowed.

Delivery mode defaults to `auto`: when the target session is running a turn the
command is steered into that running turn (the same channel the browser's steering
box uses), and when the session is idle it is queued for the next turn. A steered
command is therefore acted on mid-turn instead of waiting for the turn boundary.

Usage:
  python3 System/swarm_stigmergicode_pipe.py --once
  python3 System/swarm_stigmergicode_pipe.py --interval 2
  python3 System/swarm_stigmergicode_pipe.py --once --mode queue
  python3 System/swarm_stigmergicode_pipe.py --once --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import swarm_stigmergicode_command as queue  # noqa: E402

DEFAULT_BASE_URL = os.environ.get("DSH_WEB_URL", "http://127.0.0.1:3080")
LOG_PATH = Path(queue.DEFAULT_STATE_DIR) / "stigmergicode_pipe.log"


def _rpc(base_url: str, method: str, payload: dict, *, timeout: float = 20.0) -> dict:
    """POST one client request to the harness RPC carrier and return its value.

    The carrier answers 200 with a ServerResponse for business results and reserves
    HTTP status for transport faults, so a non-200 is always a transport failure.
    """
    body = json.dumps({
        "type": "client-request",
        "rpcId": f"stigmergicode-pipe-{int(time.time() * 1000)}",
        "method": method,
        "payload": payload,
    }).encode()
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/{method}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        frame = json.load(response)
    result = frame.get("result") or {}
    if not result.get("ok"):
        error = result.get("error") or {}
        raise RuntimeError(f"{method} refused: {error.get('code', 'unknown')} {error.get('message', '')}".strip())
    return result.get("value")


def target_session(base_url: str, explicit: str | None = None) -> tuple[str, bool]:
    """Return the session to prompt and whether it is running a turn right now.

    The running flag is what selects steering over queuing, so it is read from the
    same `session.list` snapshot the browser uses to render its live state.
    @param base_url - harness web origin serving the RPC carrier.
    @param explicit - session id to use instead of the most recently updated one.
    @returns the session id and its running state.
    """
    sessions = _rpc(base_url, "session.list", {})
    if isinstance(sessions, list):
        rows = sessions
    else:
        rows = sessions.get("items") or sessions.get("sessions") or []
    if not rows:
        raise RuntimeError("no DSH session is available to receive the command")
    ordered = sorted(rows, key=lambda row: row.get("updatedAt") or row.get("createdAt") or 0, reverse=True)
    chosen = None
    if explicit is not None:
        for row in ordered:
            if str(row.get("id") or row.get("sessionId")) == str(explicit):
                chosen = row
                break
    else:
        chosen = ordered[0]
    if chosen is None:
        return str(explicit), False
    target = chosen.get("id") or chosen.get("sessionId")
    if not target:
        raise RuntimeError("session.list returned a row without an id")
    return str(target), bool(chosen.get("running"))


def deliver(base_url: str, session_id: str, task: dict, *, mode: str = "queue") -> dict:
    """Deliver one claimed task into the session and return the RPC value."""
    text = str(task.get("task") or "").strip()
    if not text:
        raise RuntimeError("claimed task carries no text")
    header = f"[stigmergicode {task.get('task_id', 'unknown')}]"
    return _rpc(base_url, "session.prompt", {
        "sessionId": session_id,
        "mode": mode,
        "content": [{"type": "text", "text": f"{header}\n{text}"}],
    })


def _log(row: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _orphaned_opened(state_dir: Path | str = queue.DEFAULT_STATE_DIR) -> dict | None:
    """Claim the oldest command a previous claim left OPENED without delivery.

    `claim_next_task` only picks PENDING rows, so a command claimed by an arm that
    then died stays OPENED forever: the owner sees a receipt and nothing is ever
    delivered. Re-claiming it here is what makes the queue a pipe instead of a
    place tickets go to die.
    """
    _, tasks_path, lock_path = queue._paths(state_dir)
    with queue._locked(lock_path):
        states = queue._task_states(tasks_path)
        orphans = [row for row in states.values() if str(row.get("status") or "") == "OPENED"]
        if not orphans:
            return None
        row = dict(sorted(orphans, key=lambda item: float(item.get("created_at") or 0.0))[0])
        stamp = time.time()
        row.update({"status": "CLAIMED", "updated_at": stamp, "claimed_at": stamp, "claimed_by": "stigmergicode_pipe"})
        queue._append(tasks_path, row)
    queue._append_receipt(row, state_dir=Path(state_dir))
    return row


def pump_once(base_url: str, *, session_id: str | None, mode: str, max_age: float | None = 900.0) -> int:
    """Claim at most one task and deliver it; return a process exit status.

    A command queued long ago must not hijack a live session hours later, so a
    claimed task older than `max_age` seconds is canceled with its age recorded
    instead of delivered. `max_age=None` drains the whole backlog.
    """
    task = queue.claim_next_task() or _orphaned_opened()
    if task is None:
        return 0
    task_id = str(task.get("task_id") or "unknown")
    age = time.time() - float(task.get("created_at") or 0.0)
    if max_age is not None and age > max_age:
        queue.complete_task(task_id, status="CANCELED", reason=f"stale: queued {age:.0f}s ago, exceeds {max_age:.0f}s window")
        _log({"task_id": task_id, "status": "STALE", "ageSeconds": round(age), "at": time.time()})
        print(f"stigmergicode: canceled stale task {task_id} (queued {age:.0f}s ago)")
        return 0
    try:
        target, running = target_session(base_url, session_id)
        effective = ("steer" if running else "queue") if mode == "auto" else mode
        value = deliver(base_url, target, task, mode=effective)
    except (RuntimeError, urllib.error.URLError, OSError) as error:
        queue.release_task(task_id, reason=f"pipe delivery failed: {error}")
        _log({"task_id": task_id, "status": "RELEASED", "error": str(error), "at": time.time()})
        print(f"stigmergicode: delivery failed for {task_id}: {error}", file=sys.stderr)
        return 1
    queue.complete_task(task_id, status="DELIVERED", reason=f"{effective} to session {target}")
    _log({"task_id": task_id, "status": "DELIVERED", "session": target, "mode": effective,
          "value": value, "at": time.time()})
    print(f"stigmergicode: delivered {task_id} to session {target} ({effective})")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the pipe once, or continuously, against the live harness RPC."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--session", default=os.environ.get("SIFTA_PIPE_SESSION") or None)
    parser.add_argument("--mode", choices=("auto", "queue", "steer"), default="auto",
                        help="auto steers a running session and queues an idle one")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--max-age", type=float, default=900.0,
                        help="cancel claimed commands older than this many seconds (0 drains the backlog)")
    parser.add_argument("--self-test", action="store_true", help="enqueue a harmless marker task first")
    args = parser.parse_args(argv)

    if args.self_test:
        queued = queue.enqueue_task(
            "stigmergicode pipe self-test — acknowledge with one line and do no filesystem work.",
            source="pipe-self-test",
        )
        print(f"stigmergicode: self-test task enqueued ({queued.get('task_id')})")

    window = None if args.max_age <= 0 else args.max_age
    if args.once:
        return pump_once(args.base_url, session_id=args.session, mode=args.mode, max_age=window)
    while True:
        pump_once(args.base_url, session_id=args.session, mode=args.mode, max_age=window)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

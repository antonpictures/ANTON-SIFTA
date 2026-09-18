"""Owner-triggered WCT dispatch through the existing local Harness Host API.

No new agent loop, permission override, cloud fallback, or background scheduler.
An admitted prompt is not evidence of completed code. Ambiguous sends are never
automatically retried; reconcile against the durable Harness session first.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener, HTTPRedirectHandler


ORNITH = "codecraftersllc/ornith-1.5-35b-a3b-abliterated:latest"
HANDOFF = "Documents/WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md"


class BridgeError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BridgeError("Harness redirects are not allowed")


class HarnessClient:
    def __init__(self, url="http://127.0.0.1:3080", timeout=15.0, max_bytes=8_000_000):
        parsed = urlsplit(url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}
                or parsed.username or parsed.password or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment):
            raise BridgeError("Use a literal loopback HTTP Harness origin")
        if not math.isfinite(timeout) or timeout <= 0 or max_bytes <= 0:
            raise BridgeError("Timeout and response limit must be positive")
        self.url, self.timeout, self.max_bytes = url.rstrip("/"), timeout, max_bytes
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def call(self, method, payload, rpc_id=None):
        if method not in {"session.list", "session.models", "session.history", "session.prompt"}:
            raise BridgeError("Unsupported bridge method")
        rpc_id = rpc_id or str(uuid.uuid4())
        body = {"type": "client-request", "rpcId": rpc_id, "method": method, "payload": payload}
        request = Request(self.url + "/api/" + method, data=json.dumps(body).encode(),
                          headers={"Content-Type": "application/json"})
        with self.opener.open(request, timeout=self.timeout) as response:
            raw = response.read(self.max_bytes + 1)
        if len(raw) > self.max_bytes:
            raise BridgeError("Harness response exceeded the byte limit")
        reply = json.loads(raw)
        if not isinstance(reply, dict) or reply.get("type") != "server-response" or reply.get("rpcId") != rpc_id:
            raise BridgeError("Harness response correlation mismatch")
        result = reply.get("result", {})
        if result.get("ok") is not True:
            raise BridgeError("Harness rejected request: " + str(result.get("error", {}).get("code", "unknown")))
        return result["value"]


def job_prompt(root, jobs):
    """Read only the current named jobs, not the entire historical handoff."""
    path = root / HANDOFF
    with path.open("rb") as stream:
        raw = stream.read(1_000_001)
    if len(raw) > 1_000_000:
        raise BridgeError("WCT handoff too large")
    source = raw.decode("utf-8")
    sections = re.split(r"(?m)(?=^#{2,3} )", source)
    selected = []
    for job in jobs:
        if not re.fullmatch(r"ORNITH-0[1-5]", job):
            raise BridgeError("Unknown job: " + job)
        matches = [section for section in sections
                   if re.match(r"^### (?:Start here: )?" + re.escape(job) + r"\b", section)]
        if len(matches) != 1:
            raise BridgeError("Expected one canonical section for " + job)
        selected.append(matches[0].strip())
    if not jobs or len(set(jobs)) != len(jobs):
        raise BridgeError("Select distinct WCT jobs")
    prompt = (
        "Alice's owner-authorized WCT coding assignment. Execute, do not only plan.\n"
        f"Workspace: {root}\nCanonical handoff: {HANDOFF}\n"
        "Read the handoff's top status update first: another arm may have already fixed part of a job. "
        "Inspect current diffs; preserve other work. Use bounded reads (under 150 lines) and "
        "small tool calls. Reproduce -> patch -> run tests -> record actual results. "
        "Continue the selected jobs in order without asking for the next task. "
        "After two identical tool failures, record the blocker and try independent work. "
        "A notes-only answer, a green AST shape test, or a claimed receipt is not proof of execution. "
        "Keep approval/mutation gates. Do not change DNS, stigmergicode.com deployment, "
        "permissions, model/provider, credentials, ledgers' validation rules, or robot motors. "
        "No git commit/push or private sensor data in fixtures. No cloud fallback. "
        "Report changed files, commands, real outcomes and pending hardware tests in WCT.\n\n"
        + "\n\n".join(selected)
    )
    if len(prompt) > 24_000:
        raise BridgeError("Selected jobs exceed the prompt limit; dispatch fewer jobs")
    return prompt


def session_summary(client, root, session_id):
    rows = client.call("session.list", {}).get("items", [])
    session = next((row for row in rows if row.get("sessionId") == session_id), None)
    if not session or not session.get("cwd") or Path(session["cwd"]).resolve() != root.resolve():
        raise BridgeError("Session not found in the selected SIFTA workspace")
    if session.get("origin") == "subagent":
        raise BridgeError("Select the existing root Ornith session")
    return session


def dispatch(client, root, session_id, jobs, state_dir=None):
    prompt = job_prompt(root, jobs)
    dispatch_id = hashlib.sha256((session_id + "\n" + prompt).encode()).hexdigest()
    state_dir = state_dir or root / ".sifta_state" / "dsh_wct"
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Separate file per request bounds reads. flock prevents competing callers;
    # the prepared receipt precedes the network side effect, surviving a crash.
    flags = os.O_CREAT | os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW
    fd = os.open(state_dir / (dispatch_id + ".jsonl"), flags, 0o600)
    with os.fdopen(fd, "a+", encoding="utf-8") as journal:
        fcntl.flock(journal, fcntl.LOCK_EX | fcntl.LOCK_NB)
        journal.seek(0)
        previous = journal.read(64_001)
        if len(previous) > 64_000:
            raise BridgeError("Dispatch receipt exceeds limit")
        if previous.strip():
            return {"status": "not_resent", "dispatch_id": dispatch_id,
                    "session_id": session_id, "reason": "Existing attempt; reconcile session history"}
        session = session_summary(client, root, session_id)
        if session.get("running"):
            raise BridgeError("Ornith is busy; do not overlap writers")
        model = client.call("session.models", {"sessionId": session_id})
        current = model.get("current", {})
        if not model.get("routable") or current.get("provider") != "local-ollama" or current.get("model") != ORNITH:
            raise BridgeError("Session must already select the local Ornith model; no automatic switch")
        baseline = session.get("projections", {}).get("asOfSeq", 0)
        def record(status, **extra):
            row = {"status": status, "dispatch_id": dispatch_id, "session_id": session_id,
                   "jobs": jobs, "time": time.time(), "baseline_seq": baseline, **extra}
            journal.write(json.dumps(row, sort_keys=True) + "\n")
            journal.flush()
            os.fsync(journal.fileno())
            return row
        record("prepared")
        try:
            answer = client.call("session.prompt", {"sessionId": session_id, "mode": "queue",
                "content": [{"type": "text", "text": f"WCT dispatch {dispatch_id}\n{prompt}"}]},
                rpc_id=dispatch_id)
            if answer.get("accepted") is not True:
                raise BridgeError("No durable admission acknowledgement")
        except (BridgeError, OSError, ValueError) as exc:
            record("delivery_uncertain", error_type=type(exc).__name__)
            raise BridgeError("Delivery uncertain; inspect session history before any new assignment") from exc
        return record("accepted_not_completed")


def status(client, root, session_id):
    session = session_summary(client, root, session_id)
    history = client.call("session.history", {"sessionId": session_id, "maxMessages": 1})
    events = [row.get("event", {}) for row in history.get("events", [])]
    ends = [event for event in events if event.get("type") == "turn/end"]
    values = session.get("projections", {}).get("values", {})
    return {"session_id": session_id, "running": session.get("running", False),
            "title": values.get("title"), "stats": values.get("sessionStats", {}),
            "last_turn_reason": ends[-1].get("data", {}).get("reason", {}).get("kind") if ends else None,
            "history_is_partial": history.get("hasMore", False),
            "verification": "Session activity only; code and tests require separate verification"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preview", "dispatch", "status"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--session", required=True)
    parser.add_argument("--jobs", nargs="+", default=["ORNITH-01"])
    parser.add_argument("--url", default="http://127.0.0.1:3080")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)
    try:
        if args.action == "preview":
            print(job_prompt(args.root.resolve(), args.jobs))
            return 0
        client = HarnessClient(args.url, args.timeout)
        result = (dispatch(client, args.root.resolve(), args.session, args.jobs)
                  if args.action == "dispatch" else status(client, args.root.resolve(), args.session))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (BridgeError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

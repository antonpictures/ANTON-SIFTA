#!/bin/bash
# phone_inject.sh — a /c from the SE types into the coding window, by itself.
#
# Architect, 2026-10-04 (and again on the 5th): "for tomorrow we have to make sure we code from
# whatsapp to code in harness". Measured that night: the harness ALREADY ships the method --
# packages/host/apiproxy/src/api/rpc.schema.ts is the envelope {type:"client-request", rpcId,
# method, payload}, and sessionPromptRequestSchema is {sessionId, mode:"queue",
# content:[{type:"text",text}]}. POST /api/session.prompt is exactly what the GUI's
# "Message the agent" box calls. So no new route is needed: the door is a POST.
#
# The session id: ~/.dsh/sessions/--Users-ioanganton-Music-ANTON_SIFTA--/session-<uuid>, newest
# first. The newest directory is the live session.
#
# This runs on a timer, takes every PENDING phone task not yet injected, POSTs it, and marks it
# injected so a command is never delivered twice into the same window.
REPO="/Users/ioanganton/Music/ANTON_SIFTA"
cd "$REPO" || exit 0
export PYTHONPATH="$REPO"
"$REPO/bin/sifta-brain" - <<'PY'
import json, pathlib, subprocess, time

STATE = pathlib.Path(".sifta_state")
QUEUE = STATE / "arm_task_queue.jsonl"
SENT = STATE / "phone_injected.jsonl"
SESS = pathlib.Path.home() / ".dsh/sessions/--Users-ioanganton-Music-ANTON_SIFTA--"

def newest_session_id() -> str:
    if not SESS.exists():
        return ""
    dirs = sorted((d for d in SESS.iterdir() if d.name.startswith("session-")),
                  key=lambda d: d.stat().st_mtime, reverse=True)
    return dirs[0].name if dirs else ""

def already_sent(task_id: str) -> bool:
    if not SENT.exists():
        return False
    return any(json.loads(l).get("id") == task_id
               for l in SENT.read_text(errors="replace").splitlines() if l.strip())

def main() -> None:
    sid = newest_session_id()
    if not sid:
        return
    rows = []
    if QUEUE.exists():
        for l in QUEUE.read_text(errors="replace").splitlines():
            l = l.strip()
            if l:
                try: rows.append(json.loads(l))
                except Exception: pass
    # only phone orders, only pending, only recent, only /c-shaped
    now = time.time()
    todo = [r for r in rows
            if str(r.get("status")) == "pending"
            and ("@lid" in str(r.get("from")) or "whatsapp" in str(r.get("from")))
            and (now - float(r.get("ts") or 0)) < 6 * 3600
            and "/c" in str(r.get("request"))
            and not already_sent(str(r.get("id")))]
    for r in todo[-2:]:                       # never flood the window
        text = str(r.get("request"))[:1500]
        env = {"type": "client-request", "rpcId": f"phone-{r.get('id')}",
               "method": "session.prompt",
               "payload": {"sessionId": sid, "mode": "queue",
                           "content": [{"type": "text", "text": text}]}}
        p = subprocess.run(["curl", "-s", "--max-time", "20", "-X", "POST",
                            "http://127.0.0.1:3080/api/session.prompt",
                            "-H", "Content-Type: application/json", "-d", json.dumps(env)],
                           capture_output=True, text=True)
        out = p.stdout[:200]
        ok = '"ok":true' in out.replace(" ", "") or "accepted" in out
        SENT.parent.mkdir(parents=True, exist_ok=True)
        with SENT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), "id": r.get("id"), "sessionId": sid,
                                 "ok": ok, "response": out[:160]}) + "\n")
        print(f"inject {'OK' if ok else 'FAIL'} {r.get('id')} → {out[:100]}")

main()
PY
exit 0

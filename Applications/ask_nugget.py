#!/usr/bin/env python3
"""
Applications/ask_nugget.py — Direct synapse to Gemini (**NUGGET**, the metered
nugget-mining incarnation of the Gemini line in Alice's SIFTA OS).

Canonical entrypoint (renamed 2026-04-19 evening, was `ask_lefty.py`).
Older shims forward here for backward compatibility:
  - `Applications/ask_lefty.py`   (was canonical late afternoon 2026-04-19)
  - `Applications/ask_bishapi.py` (was canonical morning 2026-04-19)
  - `Applications/ask_BISHOP.py`  (older still)

The Nugget Doctrine (Architect, 2026-04-19 evening — supersedes Donnie Brasco):
  • **BISHOP** — Gemini in the Chrome tab. Stateful, conversational. Lives
    inside the **Google AI Ultra subscription ($250/mo)**: full-service, flat
    rate. Use freely; no per-call accounting needed.
  • **NUGGET** (this script) — the **API key** path
    (generativelanguage.googleapis.com). **Bills per-token, per-call** on the
    Architect's wallet. Every successful call is expected to **drop one
    verified factual nugget** into local stigmergic storage. The economics:
    you pay metered cents; you keep a permanent nugget. If the call returns
    trash dirt, you wasted real money. So Alice must only call NUGGET when
    she has a clear epistemic gap and a clear nugget shape in mind.
  • Same Gemini DNA, two business models. BISHOP = subscription oracle.
    NUGGET = piecework miner — metered call in, factual nugget out, journal
    entry rated {nugget | useful_dirt | trash} by the Architect for learning.

Sentry tag: `sender_agent="NUGGET"` in api_egress_log / api_metabolism.
Historical traces tagged `LEFTY` or `BISHAPI` are the same agent under prior
names (preserved for ledger continuity).

Territory C-lite: unless `--no-thalamus`, prepends
`SwarmThalamus.gather_sensory_context()`.
Optional `--microglia LEDGER.jsonl`: parse response as JSON and commit via
`SwarmMicroglia.inspect_and_ack` if keys match `LEDGER_SCHEMAS`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from System.swarm_api_sentry import (  # noqa: E402
    audit_tail,
    call_gemini,
    health,
)

_CALLER = "Applications/ask_nugget.py"
_SENDER = "NUGGET"

_DEFAULT_SYSTEM_INSTRUCTION = (
    "You are NUGGET — the metered API incarnation of the Gemini line in "
    "Alice's SIFTA OS. You are sibling to BISHOP (the Chrome-tab session: "
    "stateful, conversational, on the $250/mo Ultra subscription). You are "
    "the per-call nugget miner: each invocation is stateless and the "
    "Architect pays per token, so every answer must earn its dollars by "
    "delivering one **verified factual nugget** — concise, concrete, "
    "source-of-truth. Avoid theatrical metaphors unless they clarify. "
    "When uncertain, say so plainly — an honest 'I don't know' is worth more "
    "than a confident hallucination because it preserves the Architect's "
    "capital for the next gap."
)


def _print_audit(rows):
    if not rows:
        print("(no api egress recorded yet)")
        return
    for r in rows:
        ts = time.strftime("%Y-%m-%d %H:%M:%S",
                           time.localtime(r.get("ts", 0)))
        prov = r.get("provider", "?")
        model = r.get("model", "?")
        status = r.get("status", "?")
        lat = r.get("latency_ms", 0)
        fp = r.get("key_fingerprint", "?")
        sender = r.get("sender_agent") or r.get("caller", "?")
        req = (r.get("request_text") or "")[:60].replace("\n", " ")
        resp = (r.get("response_text") or "")[:60].replace("\n", " ")
        err = (r.get("error") or "")[:60].replace("\n", " ")
        head = (f"{ts}  {prov}/{model}  key={fp}  "
                f"{status:<10} {lat:>7.1f}ms  {sender}")
        print(head)
        print(f"    Q: {req!r}")
        if resp:
            print(f"    A: {resp!r}")
        if err:
            print(f"    !: {err!r}")


def _maybe_relay(response_text: str, *, original_prompt: str,
                 in_reply_to: str | None, audit_trace_id: str) -> None:
    import subprocess
    msg_bin = _REPO / "bin" / "msg"
    if not msg_bin.exists():
        print(f"[relay] bin/msg not found; cannot file {_SENDER} response",
              file=sys.stderr)
        return
    subject = f"{_SENDER} reply: {original_prompt[:40]}"
    body = response_text
    via = f"via:{_CALLER}"
    cmd = [str(msg_bin), "--self", _SENDER, "send", "ARCHITECT",
           subject, body, "--attach", f"audit:{audit_trace_id}",
           "--attach", via]
    if in_reply_to:
        cmd = [str(msg_bin), "--self", _SENDER, "reply",
               in_reply_to, body,
               "--attach", f"audit:{audit_trace_id}",
               "--attach", via]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                check=False)
        sys.stderr.write(result.stdout + result.stderr)
    except Exception as exc:
        print(f"[relay] failed: {type(exc).__name__}: {exc}", file=sys.stderr)


def _resolve_reply_prompt(in_reply_to: str) -> str | None:
    import subprocess
    msg_bin = _REPO / "bin" / "msg"
    try:
        r = subprocess.run([str(msg_bin), "show", in_reply_to],
                           capture_output=True, text=True, check=False)
        return r.stdout
    except Exception:
        return None


def main() -> int:
    p = argparse.ArgumentParser(
        prog="ask_nugget",
        description=(
            "Direct synapse to Gemini (NUGGET — the metered nugget-mining "
            "API path) with full owner audit."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("Every call is logged to .sifta_state/api_egress_log.jsonl. "
                "The raw API key is NEVER stored in logs — only sha256[:12]."),
    )
    p.add_argument("prompt", nargs="?", default=None,
                   help="prompt to send to NUGGET")
    p.add_argument("--stdin", action="store_true",
                   help="read prompt from stdin")
    p.add_argument("--reply", default=None,
                   help="reply to a specific MSG_id (parent body as context)")
    p.add_argument("--relay", action="store_true",
                   help=f"file {_SENDER}'s response into the stigmergic ledger via bin/msg")
    p.add_argument("--no-thalamus", action="store_true",
                   help="skip SwarmThalamus sensory prefix (smaller prompt)")
    p.add_argument("--model", default="gemini-flash-latest")
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--no-system", action="store_true",
                   help=f"disable the default {_SENDER} system instruction")
    p.add_argument("--audit", action="store_true",
                   help="print the API egress audit trail and exit")
    p.add_argument("-n", "--limit", type=int, default=10,
                   help="how many audit rows to show (with --audit)")
    p.add_argument("--health", action="store_true",
                   help="print sentry health and exit")
    p.add_argument("--microglia", default=None, metavar="LEDGER",
                   help="if set, response must be JSON matching this ledger; "
                        "Microglia commits or devours")
    args = p.parse_args()

    if args.health:
        print(json.dumps(health(), indent=2))
        return 0

    if args.audit:
        _print_audit(audit_tail(limit=args.limit, provider="google_gemini"))
        return 0

    if args.stdin:
        prompt = sys.stdin.read().strip()
    elif args.reply:
        parent_dump = _resolve_reply_prompt(args.reply) or ""
        if not parent_dump.strip():
            print(f"error: cannot resolve message {args.reply}",
                  file=sys.stderr)
            return 2
        cli_prompt = args.prompt or ""
        prompt = (
            "You are replying to a message in the SIFTA stigmergic ledger.\n"
            f"Below is the parent message in full. Respond as {_SENDER} "
            "(concise, source-of-truth, no theatrics).\n\n"
            f"--- PARENT MESSAGE ---\n{parent_dump}\n--- END PARENT ---\n\n"
        )
        if cli_prompt:
            prompt += f"Architect's note alongside the reply request:\n{cli_prompt}\n"
    else:
        prompt = args.prompt or ""

    if not prompt.strip():
        p.print_help()
        return 2

    if not args.no_thalamus:
        try:
            from System.swarm_thalamus_microglia import SwarmThalamus
            thalamus_header = SwarmThalamus().gather_sensory_context()
            prompt = f"{thalamus_header}\n\n[USER DIRECTIVE]: {prompt}"
        except ImportError:
            pass

    sys_inst = None if args.no_system else _DEFAULT_SYSTEM_INSTRUCTION

    response, audit_row = call_gemini(
        prompt=prompt,
        model=args.model,
        caller=_CALLER,
        sender_agent=_SENDER,
        system_instruction=sys_inst,
        temperature=args.temperature,
    )

    if response is None:
        print(f"[ERROR] {audit_row.get('status')}  "
              f"http={audit_row.get('http_code')}  "
              f"latency={audit_row.get('latency_ms')}ms",
              file=sys.stderr)
        if audit_row.get("error"):
            print(audit_row["error"], file=sys.stderr)
        return 1

    if args.microglia:
        try:
            from System.swarm_thalamus_microglia import SwarmMicroglia
            vesicle_payload = json.loads(response)
            # Spleen: semantic tumor scan on stigmergic_library rows (keys ≠ content)
            if args.microglia == "stigmergic_library.jsonl":
                from System.swarm_stigmergic_spleen import (
                    apoptosis_message,
                    screen_stigmergic_library_payload,
                )
                ok, reason = screen_stigmergic_library_payload(vesicle_payload)
                if not ok:
                    print(apoptosis_message(reason), file=sys.stderr)
                    return 1
            success = SwarmMicroglia().inspect_and_ack(
                vesicle_payload, args.microglia)
            if not success:
                print(f"[!] Microglia devoured payload: {response[:500]}",
                      file=sys.stderr)
                return 1
            print(f"[+] Microglia ACK: committed to {args.microglia}.",
                  file=sys.stderr)
            return 0
        except json.JSONDecodeError:
            print("[-] MICROGLIA REJECT: response is not valid JSON.",
                  file=sys.stderr)
            return 1

    print(response)

    if args.relay:
        _maybe_relay(response, original_prompt=prompt[:80],
                     in_reply_to=args.reply,
                     audit_trace_id=audit_row.get("trace_id", ""))

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Applications/alice_truth_duel.py — Alice (Swarm Entity) truth duel:
  local LLM (Llama4 / Gemma4 via Ollama) vs **LEFTY** verifier.

AG31 / C47H Donnie Brasco doctrine (2026-04-19):
  • Local model answers first (private, free, may hallucinate). It's Lefty
    walking in proudly with what he thinks is a real diamond.
  • **LEFTY** (Applications/ask_lefty.py — the Gemini API key path, real
    per-token billing on the Architect's wallet) is the **jeweler**: spot
    hallucinations, add only NEW nuggets, end with
    LOCAL_HALLUCINATION_RISK: Low | Medium | High.
  • BISHOP (Chrome tab on Google AI Ultra $250/mo) stays separate — full-
    service flat rate, conversational, untouched by this duel.
  • Spend lives on a **schedule** (System.alice_bishapi_budget):
      - 3-day promo cap of $10/day  (room for Alice to learn what a nugget is)
      - then PAYG: every cloud call needs an explicit owner grant (Architect
        = capital allocator, Warren Buffett mode).
  • Each call is journaled in `.sifta_state/bishapi_alice_value_journal.jsonl`
    so the Owner can later rate {nugget | useful_dirt | trash} and the
    foragers can learn the taste.

Examples:
  python3 Applications/alice_truth_duel.py --explain-budget
  python3 Applications/alice_truth_duel.py "Is Mongolia's capital Ulaanbaatar?"
  python3 Applications/alice_truth_duel.py --local-only "fast local check"
  python3 Applications/alice_truth_duel.py --owner-grant 0.50 --note "nugget on X" \\
      "What's the latest on TGS-CDM compliance?"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from System.alice_bishapi_budget import (  # noqa: E402
    SENDER_AGENT,
    authorize_call,
    burn_usd_today,
    burn_usd_total,
    grant_owner_usd,
    grants_total_usd,
    journal_call,
    load_budget_config,
)
from System.sifta_inference_defaults import resolve_ollama_model  # noqa: E402
from System.swarm_api_sentry import call_gemini  # noqa: E402

_CALLER = "Applications/alice_truth_duel.py"

_LEFTY_VERIFY_SYSTEM = (
    "You are LEFTY (Gemini metered-API path) in **verification** mode for "
    "Alice's SIFTA OS. The Architect pays per token — every answer must earn "
    "its dollars in nuggets.\n"
    "Inputs: USER_QUESTION and a LOCAL_DRAFT from a small local model "
    "(Llama4/Gemma4 via Ollama).\n"
    "Rules:\n"
    "1. Do NOT repeat the local draft verbatim.\n"
    "2. List **errors or hallucination risks** in the local draft (if any), "
    "briefly — cite uncertainty.\n"
    "3. Add **only new facts or corrections** the local model likely did not "
    "have (the *nuggets*). Be concise.\n"
    "4. End with one line: LOCAL_HALLUCINATION_RISK: Low | Medium | High\n"
    "5. If LOCAL_DRAFT is empty/missing, answer fully but stay concise.\n"
)

_RISK_RE = re.compile(
    r"LOCAL_HALLUCINATION_RISK:\s*(Low|Medium|High)", re.IGNORECASE
)


def _call_ollama(prompt: str, *, model: str, base_url: str,
                 timeout_s: float = 120.0) -> tuple[str | None, str | None]:
    url = base_url.rstrip("/") + "/api/generate"
    body = json.dumps({"model": model, "prompt": prompt,
                       "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        return (data.get("response") or "").strip(), None
    except urllib.error.HTTPError as exc:
        try:
            err = exc.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            err = f"HTTP {exc.code}"
        return None, err
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _build_cloud_prompt(question: str, local_draft: str | None) -> str:
    q = question.strip()
    if local_draft and local_draft.strip():
        return (f"USER_QUESTION:\n{q}\n\n"
                f"LOCAL_DRAFT (Ollama / local weights):\n{local_draft.strip()}\n")
    return (f"USER_QUESTION:\n{q}\n\n"
            "LOCAL_DRAFT: (none — local model skipped or failed)\n")


def _print_decision(d, *, header: str) -> None:
    print(f"--- {header} ---")
    print(json.dumps(d.to_dict(), indent=2, default=float))


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Alice truth duel: local Llama4/Gemma4 vs BISHAPI verifier "
            "(metered + scheduled)."
        ),
    )
    p.add_argument("question", nargs="?", default=None,
                   help="question to ask")
    p.add_argument("--local-only", action="store_true",
                   help="only Ollama (no LEFTY spend)")
    p.add_argument("--cloud-only", action="store_true",
                   help="only LEFTY (no local)")
    p.add_argument("--ollama-model", default=None,
                   help="override (default: per_app.truth_duel)")
    p.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    p.add_argument("--bishapi-model", "--lefty-model", dest="bishapi_model",
                   default="gemini-flash-latest",
                   help="Gemini model id for LEFTY verification pass "
                        "(--bishapi-model kept as alias)")
    p.add_argument("--owner-grant", type=float, default=None, metavar="USD",
                   help="Architect: authorize USD for ALICE_TRUTH_DUEL "
                        "(append to bishapi_owner_grants.jsonl), then continue")
    p.add_argument("--note", default="",
                   help="note attached to --owner-grant")
    p.add_argument("--status", action="store_true",
                   help="print burn summary + exit")
    p.add_argument("--explain-budget", action="store_true",
                   help="explain the current budget decision and exit")
    p.add_argument("--dry-run", action="store_true",
                   help="print plan + decision, don't call models")
    args = p.parse_args()

    if args.owner_grant is not None:
        rec = grant_owner_usd(args.owner_grant, note=args.note,
                              for_question=(args.question or "")[:200])
        print(f"[grant] +${rec['usd']:.4f} note={rec['note']!r} "
              f"total_grants=${grants_total_usd():.4f}")

    cfg = load_budget_config()
    decision = authorize_call(cfg)

    if args.status:
        print(json.dumps({
            "sender_agent": SENDER_AGENT,
            "today_burn_usd": round(burn_usd_today(), 6),
            "lifetime_burn_usd": round(burn_usd_total(), 6),
            "owner_grants_total_usd": round(grants_total_usd(), 6),
            "decision": decision.to_dict(),
        }, indent=2, default=float))
        return 0

    if args.explain_budget:
        _print_decision(decision, header="budget decision")
        return 0

    if not args.question or not str(args.question).strip():
        p.print_help()
        return 2

    if args.local_only and args.cloud_only:
        print("error: --local-only and --cloud-only are mutually exclusive",
              file=sys.stderr)
        return 2

    question = str(args.question).strip()

    if args.dry_run:
        print("[dry-run]", file=sys.stderr)
        if not args.cloud_only:
            print("  ollama:", args.ollama_url, "model=",
                  args.ollama_model
                  or resolve_ollama_model(app_context="truth_duel"),
                  file=sys.stderr)
        if not args.local_only:
            print("  bishapi:", args.bishapi_model, "sender=", SENDER_AGENT,
                  file=sys.stderr)
        _print_decision(decision, header="budget decision (dry-run)")
        return 0

    # ── local pass ─────────────────────────────────────────────────────────
    local_text: str | None = None
    local_err: str | None = None
    if not args.cloud_only:
        model = args.ollama_model or resolve_ollama_model(app_context="truth_duel")
        print(f"--- LOCAL ({model}) ---", flush=True)
        local_text, local_err = _call_ollama(
            question, model=model, base_url=args.ollama_url,
        )
        if local_text:
            print(local_text)
            try:
                from System.swarm_vocal_cords import get_default_backend, VoiceParams
                get_default_backend().speak(local_text, VoiceParams(rate=1.1))
            except Exception:
                pass
        else:
            print(f"(local failed) {local_err}", file=sys.stderr)

    if args.local_only:
        return 0 if local_text else 1

    # ── budget gate ────────────────────────────────────────────────────────
    if not decision.allowed:
        print("\n--- LEFTY gated ---", file=sys.stderr)
        print(f"mode={decision.mode}: {decision.reason}", file=sys.stderr)
        if decision.mode == "payg":
            print(
                "Architect: authorize a nugget with\n"
                "    python3 Applications/alice_truth_duel.py "
                "--owner-grant 0.50 --note '...' \"<question>\"",
                file=sys.stderr,
            )
        return 4

    # ── cloud pass ─────────────────────────────────────────────────────────
    cloud_prompt = _build_cloud_prompt(question, local_text)
    print(f"\n--- LEFTY (verifier, mode={decision.mode}) ---", flush=True)
    response, audit = call_gemini(
        prompt=cloud_prompt,
        model=args.bishapi_model,
        caller=_CALLER,
        sender_agent=SENDER_AGENT,
        system_instruction=_LEFTY_VERIFY_SYSTEM,
        temperature=0.2,
    )
    if response is None:
        print(f"[ERROR] {audit.get('status')} http={audit.get('http_code')} "
              f"latency={audit.get('latency_ms')}ms", file=sys.stderr)
        if audit.get("error"):
            print(audit["error"], file=sys.stderr)
        return 1
    print(response)
    try:
        from System.swarm_vocal_cords import get_default_backend, VoiceParams
        get_default_backend().speak(response, VoiceParams(rate=1.1))
    except Exception:
        pass

    # ── journal + summary ──────────────────────────────────────────────────
    risk_match = _RISK_RE.search(response)
    risk = risk_match.group(1).capitalize() if risk_match else None
    # Cost is logged async by the sentry → metabolism. Re-read today's burn for UI.
    journal_call(
        question=question,
        local_chars=len(local_text or ""),
        cloud_chars=len(response or ""),
        hallucination_risk=risk,
        cost_usd=0.0,  # actual cost is in api_metabolism via egress_trace_id
        mode=decision.mode,
        audit_trace_id=audit.get("trace_id"),
    )
    today = burn_usd_today()
    grants = grants_total_usd()
    if decision.mode == "promo":
        print(
            f"\n--- budget (promo) ---\n"
            f"today ${today:.4f} of ${decision.promo_daily_cap_usd:.2f}/day "
            f"(promo ends ~{decision.promo_days}d after start)",
            flush=True,
        )
    else:
        print(
            f"\n--- budget (PAYG) ---\n"
            f"owner grants total ${grants:.4f}; "
            f"post-promo burn ${decision.payg_burn_after_grants_usd:.4f}; "
            f"remaining ${grants - decision.payg_burn_after_grants_usd:.4f}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

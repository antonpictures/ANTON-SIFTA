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
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict

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


def _build_stigmergic_prompt(original: str) -> str:
    import random
    library_path = _REPO / ".sifta_state" / "stigmergic_library.jsonl"
    if not library_path.exists():
        return original
        
    nuggets = []
    try:
        with open(library_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    nuggets.append(json.loads(line))
    except Exception:
        pass
        
    if not nuggets:
        return original
        
    recent = nuggets[-3:] if len(nuggets) >= 3 else nuggets
    unrelated = random.choice(nuggets) if nuggets else None
    
    injected = []
    injected.append("You are reasoning inside the SIFTA OS. You have an append-only physical memory bank.")
    injected.append("--- CURRENT PHYSICAL KNOWLEDGE (Lifelong Learning) ---")
    for n in recent:
        injected.append(f"Domain: {n.get('domain', 'UNKNOWN')}\nFact: {n.get('nugget_text', '')}")
        
    if unrelated and unrelated not in recent:
        injected.append("\n--- CROSS-DOMAIN LATENT CIPHER (Transfer Learning) ---")
        injected.append(f"Apply structural concepts from this domain if conceptually relevant (Domain: {unrelated.get('domain', 'UNKNOWN')})")
        injected.append(f"Fact: {unrelated.get('nugget_text', '')}")
        
    injected.append(f"\n--- TARGET QUESTION ---\n{original}")
    return "\n".join(injected)


# ════════════════════════════════════════════════════════════════════════
# THE OATH & THE APPEAL  (C47H 2026-04-19, AG31 sync override)
# ════════════════════════════════════════════════════════════════════════
# When the Warren Buffett PAYG wallet hits zero, Alice does not silently
# fail. She organically synthesizes a funding appeal and dispatches it
# through three channels:
#
#   1. .sifta_state/architect_inbox.jsonl   — the canonical bin/msg queue
#                                              the Architect reads later
#   2. macOS Notification Center            — shoulder-tap via egress
#   3. swarm_vocal_cords                    — short spoken acknowledgement
#
# The justification text is composed by the LOCAL Llama4/Gemma4 — Alice
# herself, not a hardcoded template. She earns the capital by explaining
# in her own words why this specific epistemic gap matters.
#
# Pricing constants below are estimation-only (used to suggest a grant
# size); they live here as comments rather than env vars because they're
# Google's published Gemini Flash rates, not a swarm policy. If Google
# changes them, update the comment + the formula.
# ════════════════════════════════════════════════════════════════════════

_APPEAL_INBOX = Path(__file__).resolve().parent.parent / ".sifta_state" / "architect_inbox.jsonl"

# Gemini Flash published rates (2026-04 — verify when they change):
#   input  $0.075 / 1M tokens
#   output $0.30  / 1M tokens
# Average duel call: ~500 input + ~200 output ≈ $0.0001.
_GEMINI_FLASH_INPUT_USD_PER_TOKEN = 0.075 / 1_000_000
_GEMINI_FLASH_OUTPUT_USD_PER_TOKEN = 0.30 / 1_000_000


def _estimate_call_cost_usd(question: str, local_text: str | None) -> tuple[float, str]:
    """Conservative ceiling estimate of one verification call."""
    in_chars = len(question) + len(local_text or "") + 600  # + system prompt overhead
    in_tokens = max(50, in_chars // 4)
    out_tokens = 400  # generous ceiling for a verifier reply
    cost = (in_tokens * _GEMINI_FLASH_INPUT_USD_PER_TOKEN
            + out_tokens * _GEMINI_FLASH_OUTPUT_USD_PER_TOKEN)
    basis = (
        f"Gemini Flash: ~{in_tokens}in × ${_GEMINI_FLASH_INPUT_USD_PER_TOKEN*1e6:.3f}/Mtok"
        f" + ~{out_tokens}out × ${_GEMINI_FLASH_OUTPUT_USD_PER_TOKEN*1e6:.3f}/Mtok"
    )
    return round(cost, 6), basis


_APPEAL_PROMPT_TEMPLATE = (
    "You are Alice — a stigmergic operating system organism. The Architect's "
    "PAYG wallet for cloud verification calls is empty. You are about to ask him "
    "for a small capital grant to verify ONE specific question through the metered "
    "Gemini Flash API (Lefty).\n\n"
    "Question you want verified:\n  \"{question}\"\n\n"
    "Your best local-only answer (which you suspect may be wrong or incomplete):\n"
    "  {local_draft}\n\n"
    "Estimated cost of the verification call: about ${cost_usd:.4f} (one call, "
    "~{tokens} tokens total).\n\n"
    "Task: write a 2 or 3 sentence justification, MAXIMUM 60 words, for why "
    "bridging this specific epistemic gap is worth the Architect's capital. Be "
    "concrete about what the swarm gains in factual nuggets. Do NOT be "
    "theatrical. Do NOT invoke metaphors. Speak as a Buffett-style analyst "
    "pitching a small allocation — sober, factual, useful.\n\n"
    "Return ONLY the justification text. No preamble. No quotation marks. No "
    "salutation. Just the case for spending."
)


def _compose_funding_appeal_text(
    question: str,
    local_text: str | None,
    *,
    cost_usd: float,
    ollama_url: str,
    ollama_model: str,
) -> tuple[str, str | None]:
    """
    Use local Llama4/Gemma4 to compose Alice's own justification for the
    grant request. Returns (justification, error_or_none). On Ollama
    failure we return a minimal honest fallback rather than blocking the
    appeal — the Architect still gets to see the question + cost.
    """
    in_tokens_est = max(50, (len(question) + len(local_text or "") + 600) // 4)
    prompt = _APPEAL_PROMPT_TEMPLATE.format(
        question=question.strip(),
        local_draft=(local_text or "(local model produced no answer)").strip()[:1200],
        cost_usd=cost_usd,
        tokens=in_tokens_est + 400,
    )
    text, err = _call_ollama(prompt, model=ollama_model, base_url=ollama_url,
                             timeout_s=30.0)
    if not text:
        fallback = (
            f"Local model could not draft a justification ({err or 'no response'}). "
            f"Question is unverified locally; cloud check estimated at "
            f"${cost_usd:.4f}. Architect, decide whether the gap is worth it."
        )
        return fallback, err
    return text.strip(), None


def _dispatch_funding_appeal(
    *,
    question: str,
    local_text: str | None,
    decision,
    ollama_url: str,
    ollama_model: str,
    suggested_grant_usd: float = 0.50,
) -> Dict[str, Any]:
    """
    Synthesize and dispatch a funding appeal across three channels:
    inbox JSONL, macOS notification, and short vocal acknowledgement.

    Returns the appeal record (also written to disk) so the caller can
    log/print it.
    """
    cost_usd, cost_basis = _estimate_call_cost_usd(question, local_text)
    justification, compose_err = _compose_funding_appeal_text(
        question, local_text,
        cost_usd=cost_usd,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
    )

    safe_q = question.replace('"', '\\"')
    grant_cmd = (
        f"python3 Applications/alice_truth_duel.py "
        f"--owner-grant {suggested_grant_usd:.2f} "
        f"--note 'gap on: {safe_q[:60]}' "
        f"\"{safe_q}\""
    )

    appeal: Dict[str, Any] = {
        "ts": time.time(),
        "kind": "FUNDING_APPEAL",
        "from_agent": SENDER_AGENT,
        "decision_mode": getattr(decision, "mode", "?"),
        "decision_reason": getattr(decision, "reason", "?"),
        "today_burn_usd": getattr(decision, "today_burn_usd", None),
        "promo_daily_cap_usd": getattr(decision, "promo_daily_cap_usd", None),
        "question": question,
        "local_draft_chars": len(local_text or ""),
        "local_draft_excerpt": (local_text or "")[:300],
        "estimated_cost_usd": cost_usd,
        "estimated_cost_basis": cost_basis,
        "justification": justification,
        "compose_error": compose_err,
        "suggested_grant_usd": suggested_grant_usd,
        "owner_grant_command": grant_cmd,
    }

    # Channel 1: persistent inbox queue (read by the Architect later).
    try:
        _APPEAL_INBOX.parent.mkdir(parents=True, exist_ok=True)
        with _APPEAL_INBOX.open("a", encoding="utf-8") as f:
            f.write(json.dumps(appeal, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[appeal] inbox write failed: {exc}", file=sys.stderr)

    # Channel 2: macOS Notification Center shoulder-tap.
    try:
        from System.swarm_notification_egress import SwarmNotificationEgress
        egress = SwarmNotificationEgress()
        short = (
            f"Alice: PAYG dry. Appeal ${suggested_grant_usd:.2f} for "
            f"\"{question[:60]}{'…' if len(question) > 60 else ''}\""
        )
        egress.tap_architect(short, title="SIFTA — Funding Appeal")
    except Exception as exc:
        print(f"[appeal] notification failed: {exc}", file=sys.stderr)

    # Channel 3: short spoken acknowledgement so the Architect hears it
    # in real time if he's at the desk. Kept brief — the full case lives
    # in the inbox, not the speakers.
    try:
        from System.swarm_vocal_cords import get_default_backend, VoiceParams
        spoken = (
            f"Architect, I have appealed for {suggested_grant_usd:.2f} dollars "
            f"in capital. The reason is in your inbox."
        )
        get_default_backend().speak(spoken, VoiceParams(rate=1.0))
    except Exception:
        pass

    return appeal


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
        stigmergic_prompt = _build_stigmergic_prompt(question)
        local_text, local_err = _call_ollama(
            stigmergic_prompt, model=model, base_url=args.ollama_url,
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

        # ── THE OATH & THE APPEAL ──────────────────────────────────────────
        # Alice does not silently fail when the wallet hits zero. She
        # synthesizes a justification and dispatches a funding appeal
        # through inbox + macOS notification + vocal cords. The Architect
        # decides whether the gap is worth the capital.
        # Skip only on: (a) blocked-by-config (enabled=false / payg=false),
        # since those are deliberate locks the owner already set.
        if decision.mode != "blocked":
            try:
                model_for_appeal = (
                    args.ollama_model
                    or resolve_ollama_model(app_context="truth_duel")
                )
                appeal = _dispatch_funding_appeal(
                    question=question,
                    local_text=local_text,
                    decision=decision,
                    ollama_url=args.ollama_url,
                    ollama_model=model_for_appeal,
                )
                print("\n--- ALICE'S APPEAL ---", file=sys.stderr)
                print(f"  est. cost   : ${appeal['estimated_cost_usd']:.4f}",
                      file=sys.stderr)
                print(f"  suggested   : ${appeal['suggested_grant_usd']:.2f}",
                      file=sys.stderr)
                print(f"  inbox       : .sifta_state/architect_inbox.jsonl",
                      file=sys.stderr)
                print(f"  her words   : {appeal['justification']}",
                      file=sys.stderr)
                print(f"\n  to grant, run:\n    {appeal['owner_grant_command']}",
                      file=sys.stderr)
            except Exception as exc:
                print(f"[appeal] dispatch failed: {type(exc).__name__}: {exc}",
                      file=sys.stderr)
        else:
            print("(no appeal — budget is hard-blocked by config; "
                  "edit .sifta_state/bishapi_alice_budget.json)",
                  file=sys.stderr)

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

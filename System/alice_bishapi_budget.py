#!/usr/bin/env python3
"""
Alice ↔ NUGGET budget — schedule + Architect-as-Buffett owner grants.

Architect doctrine (2026-04-19, evening — Nugget Doctrine):
  • The organism does **not** spend the wallet flat. It spends to a *schedule*.
  • **Promo** (default 3 days): cap of $10/day → Alice has room to learn what
    a "nugget" feels like vs trash dirt. Local Llama4/Gemma4 answers first;
    NUGGET is verifier + nugget filler only.
  • **Pay-as-you-go** (after promo): every cloud call must be **explicitly
    granted** by the Owner of the OS — `--owner-grant USD` writes a signed-by-
    intention line in `.sifta_state/bishapi_owner_grants.jsonl` (filename kept
    for backward compatibility; the agent it gates is now NUGGET). The
    Architect is Alice's Warren Buffett: capital allocator, not capital faucet.
  • Be nice — don't be cheap on real nuggets, don't tolerate trash dirt.

What these dollars *actually* are:
  NUGGET (Applications/ask_nugget.py) calls the **Gemini API key** path
  (generativelanguage.googleapis.com). Billing is **real per-token**, on the
  Architect's wallet, separate from the $250/mo Google AI Ultra subscription
  that powers BISHOP-in-Chrome. The USD here is literal — the $10/day cap is
  real wallet defense.

State files (all gitignored — filenames KEPT as bishapi_* across renames so
ledger continuity is preserved):
  .sifta_state/bishapi_alice_budget.json     — schedule config
  .sifta_state/bishapi_owner_grants.jsonl    — owner allocations (PAYG)
  .sifta_state/bishapi_alice_value_journal.jsonl — per-call value journal
  .sifta_state/api_metabolism.jsonl          — burn ledger (produced by
                                               SwarmApiMetabolism for any
                                               sender_agent that calls cloud)

Sender-agent note: the duel app tags spend with `ALICE_TRUTH_DUEL`, not NUGGET.
NUGGET is the cloud body; ALICE_TRUTH_DUEL is the *purpose* of the call. The
budget gates by purpose so other NUGGET callers (manual ask_nugget, swarm
foragers) are accounted independently.

Naming history (preserve for ledger continuity):
  - 2026-04-19 morning:    BISHAPI was the API agent name.
  - 2026-04-19 afternoon:  Architect renamed BISHAPI → LEFTY (Donnie Brasco).
  - 2026-04-19 evening:    Architect renamed LEFTY → NUGGET (this doctrine).
  Old ledger rows tagged BISHAPI/LEFTY are the same agent under prior names.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_METAB = _STATE / "api_metabolism.jsonl"

SENDER_AGENT = "ALICE_TRUTH_DUEL"

_DEFAULTS: Dict[str, Any] = {
    "schema_version": 2,
    "sender_agent": SENDER_AGENT,
    "promo_start_ts": None,         # epoch float; None = "starts on first call"
    "promo_days": 3,
    "promo_daily_cap_usd": 10.0,
    "payg_enabled": True,           # after promo, must be granted by Owner
    "payg_grace_usd_per_day": 0.0,  # tiny PAYG headroom without grant; 0 = strict
    "enabled": True,
    "notes": (
        "Schedule: promo_days at promo_daily_cap_usd → then PAYG with owner "
        "grants in bishapi_owner_grants.jsonl. Set promo_start_ts to the "
        "epoch when promo officially begins (or leave null to bind on first "
        "duel call)."
    ),
}


# ── paths ──────────────────────────────────────────────────────────────────


def budget_config_path() -> Path:
    return _STATE / "bishapi_alice_budget.json"


def owner_grants_ledger_path() -> Path:
    return _STATE / "bishapi_owner_grants.jsonl"


def value_journal_path() -> Path:
    return _STATE / "bishapi_alice_value_journal.jsonl"


# ── config IO ──────────────────────────────────────────────────────────────


def load_budget_config() -> Dict[str, Any]:
    """Load + merge defaults. Never throws."""
    out: Dict[str, Any] = json.loads(json.dumps(_DEFAULTS))  # deep copy
    path = budget_config_path()
    if not path.exists():
        return out
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            out.update(raw)
    except (OSError, json.JSONDecodeError):
        pass
    return out


def save_budget_config(cfg: Dict[str, Any]) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    budget_config_path().write_text(
        json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8"
    )


def ensure_promo_start(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Bind `promo_start_ts` to now if missing, persist, and return cfg."""
    if cfg.get("promo_start_ts"):
        return cfg
    cfg = dict(cfg)
    cfg["promo_start_ts"] = time.time()
    try:
        save_budget_config(cfg)
    except OSError:
        pass
    return cfg


# ── ledger IO ──────────────────────────────────────────────────────────────


def _iter_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return rows


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


# ── owner grants ───────────────────────────────────────────────────────────


def grant_owner_usd(usd: float, *, note: str = "", for_question: str = "") -> Dict[str, Any]:
    """Architect explicitly authorizes USD for ALICE_TRUTH_DUEL spend."""
    payload = {
        "ts": time.time(),
        "usd": float(usd),
        "note": note or "",
        "for_question": for_question or "",
        "user": os.environ.get("USER") or os.environ.get("LOGNAME") or "owner",
        "host": os.uname().nodename if hasattr(os, "uname") else "",
    }
    _append_jsonl(owner_grants_ledger_path(), payload)
    return payload


def grants_total_usd() -> float:
    return sum(float(r.get("usd", 0.0)) for r in _iter_jsonl(owner_grants_ledger_path()))


# ── burn accounting ────────────────────────────────────────────────────────


def _calendar_day_start_ts(now: float) -> float:
    lt = time.localtime(now)
    return time.mktime(time.struct_time(
        (lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, lt.tm_isdst)
    ))


def burn_usd_today(*, sender_agent: str = SENDER_AGENT) -> float:
    """Sum cost_usd for ALICE_TRUTH_DUEL since local-midnight."""
    now = time.time()
    cutoff = _calendar_day_start_ts(now)
    total = 0.0
    for r in _iter_jsonl(_METAB):
        if r.get("sender_agent") != sender_agent:
            continue
        if float(r.get("ts", 0)) < cutoff:
            continue
        total += float(r.get("cost_usd", 0.0))
    return total


def burn_usd_total(*, sender_agent: str = SENDER_AGENT) -> float:
    """Lifetime spend for sender."""
    return sum(
        float(r.get("cost_usd", 0.0))
        for r in _iter_jsonl(_METAB)
        if r.get("sender_agent") == sender_agent
    )


# ── decision ───────────────────────────────────────────────────────────────


@dataclass
class BudgetDecision:
    allowed: bool
    mode: str            # "promo" | "payg" | "blocked"
    reason: str
    promo_active: bool
    promo_start_ts: Optional[float]
    promo_days: int
    promo_daily_cap_usd: float
    today_burn_usd: float
    payg_grants_total_usd: float
    payg_burn_after_grants_usd: float
    payg_remaining_usd: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def authorize_call(cfg: Optional[Dict[str, Any]] = None,
                   *, now: Optional[float] = None) -> BudgetDecision:
    """
    Decide whether ALICE_TRUTH_DUEL may make a cloud call right now.
    Does NOT mutate state (besides ensure_promo_start binding).
    """
    cfg = cfg or load_budget_config()
    cfg = ensure_promo_start(cfg)
    now = now if now is not None else time.time()

    enabled = bool(cfg.get("enabled", True))
    promo_start = float(cfg["promo_start_ts"])
    promo_days = int(cfg.get("promo_days", 3))
    promo_cap = float(cfg.get("promo_daily_cap_usd", 10.0))
    payg_enabled = bool(cfg.get("payg_enabled", True))
    payg_grace = float(cfg.get("payg_grace_usd_per_day", 0.0))

    promo_end = promo_start + promo_days * 86400.0
    promo_active = now < promo_end
    today_burn = burn_usd_today()

    # PAYG accounting: grants vs burn that occurred AFTER the first grant
    # (we treat all grants and all burn cumulatively for simplicity)
    grants = grants_total_usd()
    lifetime_burn = burn_usd_total()
    # During promo, burn is "free" (within daily cap). After promo, only burn
    # *during* the PAYG window counts against grants.
    payg_burn = 0.0
    for r in _iter_jsonl(_METAB):
        if r.get("sender_agent") != SENDER_AGENT:
            continue
        ts = float(r.get("ts", 0))
        if ts >= promo_end:
            payg_burn += float(r.get("cost_usd", 0.0))
    payg_remaining = grants + payg_grace - payg_burn

    if not enabled:
        return BudgetDecision(
            allowed=False, mode="blocked",
            reason="bishapi_alice_budget.json: enabled=false",
            promo_active=promo_active, promo_start_ts=promo_start,
            promo_days=promo_days, promo_daily_cap_usd=promo_cap,
            today_burn_usd=today_burn,
            payg_grants_total_usd=grants,
            payg_burn_after_grants_usd=payg_burn,
            payg_remaining_usd=payg_remaining,
        )

    if promo_active:
        if today_burn >= promo_cap:
            return BudgetDecision(
                allowed=False, mode="promo",
                reason=(
                    f"promo daily cap reached: ${today_burn:.4f} ≥ "
                    f"${promo_cap:.2f}; resets at local midnight"
                ),
                promo_active=True, promo_start_ts=promo_start,
                promo_days=promo_days, promo_daily_cap_usd=promo_cap,
                today_burn_usd=today_burn,
                payg_grants_total_usd=grants,
                payg_burn_after_grants_usd=payg_burn,
                payg_remaining_usd=payg_remaining,
            )
        return BudgetDecision(
            allowed=True, mode="promo",
            reason=(
                f"promo day cap ${promo_cap:.2f}; today burned "
                f"${today_burn:.4f} ({lifetime_burn:.4f} lifetime)"
            ),
            promo_active=True, promo_start_ts=promo_start,
            promo_days=promo_days, promo_daily_cap_usd=promo_cap,
            today_burn_usd=today_burn,
            payg_grants_total_usd=grants,
            payg_burn_after_grants_usd=payg_burn,
            payg_remaining_usd=payg_remaining,
        )

    # PAYG mode
    if not payg_enabled:
        return BudgetDecision(
            allowed=False, mode="blocked",
            reason="promo expired and payg_enabled=false",
            promo_active=False, promo_start_ts=promo_start,
            promo_days=promo_days, promo_daily_cap_usd=promo_cap,
            today_burn_usd=today_burn,
            payg_grants_total_usd=grants,
            payg_burn_after_grants_usd=payg_burn,
            payg_remaining_usd=payg_remaining,
        )

    if payg_remaining <= 0.0:
        return BudgetDecision(
            allowed=False, mode="payg",
            reason=(
                f"PAYG: no owner grant headroom "
                f"(grants ${grants:.4f} - burn ${payg_burn:.4f} "
                f"= ${payg_remaining:.4f}). "
                "Run with --owner-grant USD to authorize."
            ),
            promo_active=False, promo_start_ts=promo_start,
            promo_days=promo_days, promo_daily_cap_usd=promo_cap,
            today_burn_usd=today_burn,
            payg_grants_total_usd=grants,
            payg_burn_after_grants_usd=payg_burn,
            payg_remaining_usd=payg_remaining,
        )

    return BudgetDecision(
        allowed=True, mode="payg",
        reason=(
            f"PAYG: ${payg_remaining:.4f} of owner grants remaining "
            f"({grants:.4f} granted, {payg_burn:.4f} burned post-promo)"
        ),
        promo_active=False, promo_start_ts=promo_start,
        promo_days=promo_days, promo_daily_cap_usd=promo_cap,
        today_burn_usd=today_burn,
        payg_grants_total_usd=grants,
        payg_burn_after_grants_usd=payg_burn,
        payg_remaining_usd=payg_remaining,
    )


# ── value journal (Buffett feedback channel) ───────────────────────────────


def journal_call(*, question: str, local_chars: int, cloud_chars: int,
                 hallucination_risk: Optional[str], cost_usd: float,
                 mode: str, audit_trace_id: Optional[str]) -> None:
    """
    Append a thin record so the Owner can later rate {nugget|dirt|trash}
    and Alice's foragers can learn the spend taste.
    """
    payload = {
        "ts": time.time(),
        "sender_agent": SENDER_AGENT,
        "question": question[:500],
        "local_chars": int(local_chars),
        "cloud_chars": int(cloud_chars),
        "hallucination_risk": hallucination_risk or "",
        "cost_usd": float(cost_usd or 0.0),
        "mode": mode,
        "egress_trace_id": audit_trace_id,
    }
    try:
        _append_jsonl(value_journal_path(), payload)
    except OSError:
        pass


__all__ = [
    "SENDER_AGENT",
    "BudgetDecision",
    "load_budget_config",
    "save_budget_config",
    "budget_config_path",
    "owner_grants_ledger_path",
    "value_journal_path",
    "ensure_promo_start",
    "grant_owner_usd",
    "grants_total_usd",
    "burn_usd_today",
    "burn_usd_total",
    "authorize_call",
    "journal_call",
]

#!/usr/bin/env python3
"""Shared immune-economy summary helpers for SIFTA UI surfaces.

This module is deliberately side-effect free. It reads existing ledgers and
returns derived display state; it never debits a wallet and never writes a row.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TRACE = _STATE / "ide_stigmergic_trace.jsonl"

IMMUNE_KINDS = {"immune_intervention", "immune_budget_blocked"}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if out != out or out in (float("inf"), float("-inf")):
        return float(default)
    return out


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("payload", {})
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str) and payload.strip():
        try:
            decoded = json.loads(payload)
            return decoded if isinstance(decoded, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _tail_jsonl(path: Path, n: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines[-n:]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _wallet_sum(*, repair_log: Path | None = None, state_dir: Path | None = None) -> float:
    try:
        from System.stgm_economy import scan_economy

        return _float(
            scan_economy(repair_log=repair_log, state_dir=state_dir).as_dict().get(
                "canonical_wallet_sum"
            )
        )
    except Exception:
        return 0.0


@dataclass(frozen=True)
class ImmuneEconomyEvent:
    ts: float
    kind: str
    action: str
    rule: str = ""
    cost_stgm: float = 0.0
    budget_stgm: float = 0.0
    surplus_stgm: float | None = None
    regime: str = "UNKNOWN"
    exponent: float = 0.75
    budget_blocked: bool = False

    @property
    def charged_cost_stgm(self) -> float:
        return 0.0 if self.budget_blocked else self.cost_stgm


@dataclass(frozen=True)
class ImmuneEconomySummary:
    wallet_stgm: float = 0.0
    session_charged_stgm: float = 0.0
    blocked_would_cost_stgm: float = 0.0
    burn_rate_stgm_per_hour: float = 0.0
    total_events: int = 0
    allowed_events: int = 0
    blocked_events: int = 0
    last_cost_stgm: float = 0.0
    last_budget_stgm: float = 0.0
    last_surplus_stgm: float | None = None
    last_regime: str = "IDLE"
    latest_budget_blocked: bool = False
    events: tuple[ImmuneEconomyEvent, ...] = field(default_factory=tuple)

    @property
    def display_status(self) -> str:
        if self.latest_budget_blocked:
            return "RED_CONSERVE"
        if self.blocked_events:
            return "BLOCKED_SEEN"
        if self.allowed_events:
            return "HEALTHY"
        return "IDLE"

    @property
    def wallet_after_session(self) -> float:
        return max(0.0, self.wallet_stgm - self.session_charged_stgm)


def event_from_trace_row(row: dict[str, Any]) -> ImmuneEconomyEvent | None:
    kind = str(row.get("kind") or "")
    if kind not in IMMUNE_KINDS:
        return None

    payload = _payload(row)
    action = str(payload.get("action") or kind or "immune_event")
    cost = _float(payload.get("kleiber_cost_stgm", payload.get("cost_stgm", 0.0)))
    budget = _float(payload.get("budget_stgm", 0.0))
    surplus_raw = payload.get("surplus_stgm")
    surplus = None if surplus_raw is None else _float(surplus_raw)
    budget_blocked = bool(
        kind == "immune_budget_blocked"
        or payload.get("budget_blocked")
        or action == "immune_budget_blocked"
    )

    return ImmuneEconomyEvent(
        ts=_float(row.get("ts", 0.0)),
        kind=kind,
        action=action,
        rule=str(payload.get("rule") or ""),
        cost_stgm=cost,
        budget_stgm=budget,
        surplus_stgm=surplus,
        regime=str(payload.get("regime") or ("RED_CONSERVE" if budget_blocked else "UNKNOWN")),
        exponent=_float(payload.get("exponent", 0.75), 0.75),
        budget_blocked=budget_blocked,
    )


def summarize_immune_economy(
    rows: Iterable[dict[str, Any]] | None = None,
    *,
    trace_path: Path = _TRACE,
    tail_n: int = 500,
    burn_window_s: float = 3600.0,
    repair_log: Path | None = None,
    state_dir: Path | None = None,
    wallet_stgm: float | None = None,
    now: float | None = None,
) -> ImmuneEconomySummary:
    now = time.time() if now is None else float(now)
    raw_rows = list(rows) if rows is not None else _tail_jsonl(trace_path, tail_n)
    events = tuple(
        ev for ev in (event_from_trace_row(r) for r in raw_rows if isinstance(r, dict)) if ev
    )

    charged = sum(ev.charged_cost_stgm for ev in events)
    blocked_would_cost = sum(ev.cost_stgm for ev in events if ev.budget_blocked)
    allowed = sum(1 for ev in events if not ev.budget_blocked)
    blocked = sum(1 for ev in events if ev.budget_blocked)
    recent_charged = sum(
        ev.charged_cost_stgm for ev in events if burn_window_s <= 0 or now - ev.ts <= burn_window_s
    )
    rate = recent_charged if burn_window_s <= 0 else recent_charged * (3600.0 / burn_window_s)
    latest = events[-1] if events else None
    wallet = _wallet_sum(repair_log=repair_log, state_dir=state_dir) if wallet_stgm is None else _float(wallet_stgm)

    return ImmuneEconomySummary(
        wallet_stgm=wallet,
        session_charged_stgm=round(charged, 6),
        blocked_would_cost_stgm=round(blocked_would_cost, 6),
        burn_rate_stgm_per_hour=round(rate, 6),
        total_events=len(events),
        allowed_events=allowed,
        blocked_events=blocked,
        last_cost_stgm=round(latest.cost_stgm, 6) if latest else 0.0,
        last_budget_stgm=round(latest.budget_stgm, 6) if latest else 0.0,
        last_surplus_stgm=(
            round(latest.surplus_stgm, 6) if latest and latest.surplus_stgm is not None else None
        ),
        last_regime=latest.regime if latest else "IDLE",
        latest_budget_blocked=bool(latest.budget_blocked) if latest else False,
        events=events,
    )


def format_life_cockpit_summary(summary: ImmuneEconomySummary) -> str:
    surplus = "n/a" if summary.last_surplus_stgm is None else f"{summary.last_surplus_stgm:+.5f}"
    return (
        f"Wallet {summary.wallet_stgm:.4f} STGM"
        f" | Immune burn {summary.session_charged_stgm:.5f} STGM"
        f" | {summary.burn_rate_stgm_per_hour:.5f}/h"
        f" | blocked {summary.blocked_events}"
        f" | surplus {surplus}"
        f" | {summary.display_status}"
    )


def format_immune_event_line(event: ImmuneEconomyEvent, *, now: float | None = None) -> str:
    now = time.time() if now is None else float(now)
    age_s = max(0.0, now - event.ts)
    if age_s < 60:
        age = "just now"
    elif age_s < 3600:
        age = f"{int(age_s / 60)}m ago"
    elif age_s < 86400:
        age = f"{int(age_s / 3600)}h ago"
    else:
        age = f"{int(age_s / 86400)}d ago"

    surplus = "" if event.surplus_stgm is None else f" surplus={event.surplus_stgm:+.5f}"
    rule = f"\n  rule={event.rule}" if event.rule else ""
    if event.budget_blocked:
        return (
            f"[BLOCKED] {age}: would-cost={event.cost_stgm:.5f} STGM"
            f" budget={event.budget_stgm:.5f}{surplus} {event.regime}"
        )
    return (
        f"[CHARGED] {age}: {event.action}"
        f" cost={event.cost_stgm:.5f} STGM budget={event.budget_stgm:.5f}{surplus}{rule}"
    )

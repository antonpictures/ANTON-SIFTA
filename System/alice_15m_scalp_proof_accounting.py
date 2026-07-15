#!/usr/bin/env python3
"""r1684-a — Honest scalp proof accounting (STGM laboratory).

Fixes selection bias: green-only shadow exits are NOT an unbiased win rate.
Recomputes proof from unique lifecycle events in alice_15m_scalp.jsonl.

Truth: ALICE_15M_SCALP_PROOF_ACCOUNTING_V1
Receipt: r1684-a-scalp-proof-accounting
"""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
TRUTH = "ALICE_15M_SCALP_PROOF_ACCOUNTING_V1"
RECEIPT = "r1684-a-scalp-proof-accounting"
LOG_NAME = "alice_15m_scalp.jsonl"
LEGACY_PROOF = "alice_15m_scalp_proof.json"
HONEST_PROOF = "alice_15m_scalp_proof_honest.json"
HONEST_MD = "alice_15m_scalp_proof_honest.md"
REPORT_JSON = "alice_15m_scalp_accounting_report.json"


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(o, dict):
                    rows.append(o)
    except OSError:
        return []
    return rows


def _uid(row: dict[str, Any], *, keys: tuple[str, ...]) -> str:
    parts = [str(row.get(k) or "") for k in keys]
    if not any(parts):
        return f"ts:{row.get('ts')}:{row.get('event')}"
    return "|".join(parts)


def recompute_honest_proof(
    *,
    state_dir: Optional[Path | str] = None,
    preserve_legacy: bool = True,
) -> dict[str, Any]:
    """Rebuild unbiased accounting from scalp log.

    Cohorts:
      - selected_green_exit: shadow paper ticket exit after fee-true green quote
        (selection-biased; do NOT report as strategy WR)
      - training_round_trip: independent multi-ticket training open→exit
      - scalp_vs_hold: counterfactual grades
    """
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    rows = _read_jsonl(root / LOG_NAME)

    by_event = Counter(str(r.get("event") or "unknown") for r in rows)

    # Selected green exits (shadow/execute paper) — selection-biased cohort
    selected: list[dict[str, Any]] = []
    seen_sel: set[str] = set()
    for r in rows:
        ev = str(r.get("event") or "")
        if ev not in ("scalp_exit", "scalp_cashout", "virtual_scalp_exit"):
            continue
        uid = _uid(r, keys=("ticker", "ts", "exit_price", "pnl_usd", "pnl_usd_fee_true"))
        if uid in seen_sel:
            continue
        seen_sel.add(uid)
        selected.append(r)

    training_opens: list[dict[str, Any]] = []
    training_exits: list[dict[str, Any]] = []
    seen_open: set[str] = set()
    seen_exit: set[str] = set()
    for r in rows:
        ev = str(r.get("event") or "")
        if ev == "training_scalp_open":
            uid = _uid(r, keys=("id", "ticker", "window_id", "ts"))
            if uid in seen_open:
                continue
            seen_open.add(uid)
            training_opens.append(r)
        elif ev == "training_scalp_exit":
            uid = _uid(r, keys=("id", "ticker", "window_id", "ts"))
            if uid in seen_exit:
                continue
            seen_exit.add(uid)
            training_exits.append(r)

    hold_cf = [r for r in rows if str(r.get("event") or "") == "scalp_vs_hold"]
    # dedup hold_cf by ticker+result ts
    seen_cf: set[str] = set()
    hold_unique: list[dict[str, Any]] = []
    for r in hold_cf:
        uid = _uid(r, keys=("ticker", "result", "scalp_net_usd", "hold_net_usd"))
        if uid in seen_cf:
            continue
        seen_cf.add(uid)
        hold_unique.append(r)

    def _pnl(r: dict[str, Any]) -> float:
        for k in ("pnl_usd_fee_true", "pnl_usd", "net_usd", "scalp_net_usd"):
            if r.get(k) is not None:
                try:
                    return float(r[k])
                except (TypeError, ValueError):
                    pass
        return 0.0

    def _fees(r: dict[str, Any]) -> float:
        if r.get("fees_total") is not None:
            try:
                return float(r["fees_total"])
            except (TypeError, ValueError):
                pass
        fi = float(r.get("fee_in") or 0)
        fo = float(r.get("fee_out") or 0)
        return round(fi + fo, 4)

    sel_pnls = [_pnl(r) for r in selected]
    tr_pnls = [_pnl(r) for r in training_exits]
    n_sel = len(selected)
    n_tr = len(training_exits)
    n_sel_win = sum(1 for p in sel_pnls if p >= 0)
    n_tr_win = sum(1 for p in tr_pnls if p >= 0)
    n_tr_loss = n_tr - n_tr_win

    beat = sum(1 for r in hold_unique if float(r.get("delta_scalp_minus_hold") or 0) > 0)
    lost = sum(1 for r in hold_unique if float(r.get("delta_scalp_minus_hold") or 0) < 0)

    # opportunity / zero-trade windows from training book open attempts
    zero_trade_reasons: Counter[str] = Counter()
    n_zero = 0
    for r in rows:
        if str(r.get("event") or "") in (
            "training_scalp_open_skip",
            "training_window_no_eligible",
            "training_scalp_armed",
        ):
            reason = str(r.get("reason") or r.get("note") or "unspecified")
            if int(r.get("opened") or r.get("n_opened") or 0) == 0:
                n_zero += 1
                zero_trade_reasons[reason] += 1

    windows_open = {str(r.get("window_id") or "") for r in training_opens if r.get("window_id")}
    windows_exit = {str(r.get("window_id") or "") for r in training_exits if r.get("window_id")}

    legacy: dict[str, Any] = {}
    legacy_path = root / LEGACY_PROOF
    if legacy_path.exists():
        try:
            legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
        except Exception:
            legacy = {}

    honest = {
        "truth_label": TRUTH,
        "receipt_id": RECEIPT,
        "ts": time.time(),
        "disclaimer": (
            "selected_green_exit cohort exits only after a fee-true green quote is observed. "
            "That is selection-biased and MUST NOT be read as an unbiased strategy win rate. "
            "Use training_round_trip + full opportunity counts for scientific claims."
        ),
        "legacy_preserved": bool(preserve_legacy and legacy),
        "legacy_headline": {
            "n_scalps": legacy.get("n_scalps"),
            "n_wins": legacy.get("n_wins"),
            "n_losses": legacy.get("n_losses"),
            "pnl_usd": legacy.get("pnl_usd"),
            "win_rate": legacy.get("win_rate"),
            "note": "legacy proof may mix selected greens with training; do not promote on WR",
        },
        "n_log_rows": len(rows),
        "event_counts": dict(by_event),
        # opportunity universe
        "n_opportunities": n_sel + n_tr,  # observed exit opportunities recorded
        "n_entries": len(training_opens) + n_sel,  # opens we know about
        "n_fills": n_tr + n_sel,  # recorded exits ≈ filled round trips in log
        "n_no_fills": 0,  # not yet instrumented pre-r1684 sim
        "n_round_trips": n_tr + n_sel,
        "n_forced_closes": sum(
            1 for r in training_exits if str(r.get("reason") or "") == "window_expired_mark"
        ),
        "n_zero_trade_windows": n_zero,
        "zero_trade_reason_dist": dict(zero_trade_reasons.most_common(20)),
        # selected green (biased)
        "selected_green_exit": {
            "n": n_sel,
            "n_wins": n_sel_win,
            "n_losses": n_sel - n_sel_win,
            "pnl_usd": round(sum(sel_pnls), 4),
            "fees_usd": round(sum(_fees(r) for r in selected), 4),
            "win_rate_biased": round(n_sel_win / n_sel, 4) if n_sel else None,
            "biased": True,
            "do_not_promote_on_this": True,
        },
        # independent training
        "training_round_trip": {
            "n_opens": len(training_opens),
            "n_exits": n_tr,
            "n_wins": n_tr_win,
            "n_losses": n_tr_loss,
            "pnl_usd": round(sum(tr_pnls), 4),
            "fees_usd": round(sum(_fees(r) for r in training_exits), 4),
            "win_rate": round(n_tr_win / n_tr, 4) if n_tr else None,
            "ev_per_rt": round(sum(tr_pnls) / n_tr, 4) if n_tr else None,
            "windows_with_open": len(windows_open),
            "windows_with_exit": len(windows_exit),
            "biased": False,
        },
        "hold_counterfactual": {
            "n": len(hold_unique),
            "scalp_beat_hold": beat,
            "scalp_lost_to_hold": lost,
            "hold_cf_pnl_usd": round(
                sum(float(r.get("hold_net_usd") or 0) for r in hold_unique), 4
            ),
            "scalp_cf_pnl_usd": round(
                sum(float(r.get("scalp_net_usd") or 0) for r in hold_unique), 4
            ),
        },
        "scientific_primary": "training_round_trip",
        "usd_orders": "NEVER_FROM_THIS_MODULE",
    }

    (root / HONEST_PROOF).write_text(
        json.dumps(honest, indent=2, sort_keys=True), encoding="utf-8"
    )
    (root / REPORT_JSON).write_text(
        json.dumps(honest, indent=2, sort_keys=True), encoding="utf-8"
    )
    _write_md(honest, state_dir=root)

    # annotate legacy proof without rewriting history numbers
    if preserve_legacy and legacy_path.exists() and isinstance(legacy, dict):
        try:
            annotated = dict(legacy)
            annotated["honest_accounting_path"] = HONEST_PROOF
            annotated["selection_bias_warning"] = honest["disclaimer"]
            annotated["receipt_id_accounting"] = RECEIPT
            annotated["accounting_ts"] = time.time()
            # do not change n_wins / win_rate — preserve as legacy evidence
            legacy_path.write_text(
                json.dumps(annotated, indent=2, sort_keys=True), encoding="utf-8"
            )
        except OSError:
            pass

    return honest


def _write_md(honest: dict[str, Any], *, state_dir: Path) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sel = honest.get("selected_green_exit") or {}
    tr = honest.get("training_round_trip") or {}
    hold = honest.get("hold_counterfactual") or {}
    lines = [
        f"# Alice SCALP honest accounting · {stamp}",
        "",
        f"**Receipt:** `{RECEIPT}`",
        "",
        "> ⚠️ Selected green exits are **selection-biased**. "
        "They are not an unbiased win rate.",
        "",
        "## Opportunity universe",
        f"- n_entries **{honest.get('n_entries')}** · n_fills **{honest.get('n_fills')}**",
        f"- n_round_trips **{honest.get('n_round_trips')}** · "
        f"n_forced_closes **{honest.get('n_forced_closes')}**",
        f"- n_zero_trade_windows **{honest.get('n_zero_trade_windows')}**",
        f"- n_no_fills **{honest.get('n_no_fills')}** (pre-sim default 0)",
        "",
        "## Selected green exits (BIASED)",
        f"- n **{sel.get('n')}** · WR (biased) **{sel.get('win_rate_biased')}**",
        f"- pnl **${float(sel.get('pnl_usd') or 0):+.4f}**",
        f"- **do_not_promote_on_this = true**",
        "",
        "## Training round trips (primary scientific cohort)",
        f"- opens **{tr.get('n_opens')}** · exits **{tr.get('n_exits')}** · "
        f"{tr.get('n_wins')}W/{tr.get('n_losses')}L",
        f"- WR **{tr.get('win_rate')}** · EV/rt **{tr.get('ev_per_rt')}**",
        f"- pnl **${float(tr.get('pnl_usd') or 0):+.4f}** · fees ${float(tr.get('fees_usd') or 0):.4f}",
        "",
        "## Scalp vs hold",
        f"- n **{hold.get('n')}** · beat hold **{hold.get('scalp_beat_hold')}** · "
        f"lost to hold **{hold.get('scalp_lost_to_hold')}**",
        "",
        "USD orders: NEVER from this module.",
        "",
    ]
    (state_dir / HONEST_MD).write_text("\n".join(lines), encoding="utf-8")


def annotate_legacy_proof_md(*, state_dir: Optional[Path | str] = None) -> None:
    """Ensure glass MD cannot be read as unbiased 99/99."""
    root = _state(state_dir)
    md = root / "alice_15m_scalp.md"
    if not md.exists():
        return
    try:
        text = md.read_text(encoding="utf-8")
    except OSError:
        return
    banner = (
        "\n> ⚠️ r1684: headline WR from green-only exits is **selection-biased**. "
        f"See `{HONEST_PROOF}` / `{HONEST_MD}`.\n"
    )
    if "selection-biased" in text:
        return
    try:
        md.write_text(text.rstrip() + "\n" + banner, encoding="utf-8")
    except OSError:
        pass


if __name__ == "__main__":
    out = recompute_honest_proof()
    print(json.dumps(out, indent=2, default=str)[:3000])

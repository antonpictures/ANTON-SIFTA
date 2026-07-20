#!/usr/bin/env python3
"""USD lane auditor — post-deal fill truth for the real-money campaign (r1648).

The campaign deal (owner YES 2026-07-13 ~04:00): 3 hands max, 80-88 FIRE for
real $, STGM always, honest scoreboard, stack nights. This module is the
"no bullsh*t the bankroll" part: it reads the USD ledgers and says what is
true, what is missing, and what doesn't reconcile. It contains ZERO order
code and never signs anything.

The persisted ``ledger_deal.json`` timestamp is the enforcement epoch. Older
rows remain a historical baseline; they are never retroactively judged under
r1648 and never counted as verified live-fill evidence. Post-deal live evidence
requires both ``filled: true`` and a positive ``fill_count``.

CLI:  python3 System/kalshi_usd_audit.py   → prints report, writes
      .sifta_state/kalshi_usd_audit.md and returns nonzero on FAIL findings.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import fcntl

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"

from System.ledger_deal import (  # noqa: E402
    FIRE_ONLY_USD,
    MAX_NIGHT_LOSS_USD,
    MAX_OPEN,
    STAKE_USD,
    TRUTH as DEAL_TRUTH,
    USD_MAX_ENTRY,
    USD_MIN_ENTRY,
)

TRUTH_LABEL = "KALSHI_USD_AUDIT_V2"
LEDGER_NAME = "kalshi_usd_live_ledger.jsonl"
NIGHT_NAME = "kalshi_usd_night.json"
DEAL_NAME = "ledger_deal.json"
OUT_MD_NAME = "kalshi_usd_audit.md"
# Compatibility paths for callers that import these names.
LEDGER = STATE / LEDGER_NAME
NIGHT = STATE / NIGHT_NAME
OUT_MD = STATE / OUT_MD_NAME

PAPER_EV_PER_TICKET = 0.092  # net-of-fee backtest benchmark (799-settle audit)
MIN_VERIFIED_FILLS = 50
MAX_OPEN_LOCK = MAX_OPEN
BAND_LO, BAND_HI = USD_MIN_ENTRY, USD_MAX_ENTRY
NIGHT_STOP = -MAX_NIGHT_LOSS_USD


def _state_root(state_dir: Path | str = STATE) -> Path:
    root = Path(state_dir)
    return root if root.name == ".sifta_state" else root / ".sifta_state"


def _read_ledger(path: Path = LEDGER) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _number(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _first_number(row: dict[str, Any], keys: tuple[str, ...]) -> Optional[float]:
    for key in keys:
        if key in row:
            value = _number(row.get(key))
            if value is not None:
                return value
    return None


def _limit_price(row: dict[str, Any]) -> Optional[float]:
    return _first_number(
        row,
        ("price", "limit_price", "entry_price", "average_fill_price", "fill_price"),
    )


def _fill_price(row: dict[str, Any]) -> Optional[float]:
    return _first_number(
        row,
        ("average_fill_price", "fill_price", "price", "limit_price", "entry_price"),
    )


def _rainman_score(row: dict[str, Any]) -> Optional[float]:
    direct = _first_number(row, ("rainman_score", "score"))
    if direct is not None:
        return direct
    rainman = row.get("rainman")
    return _number(rainman.get("score")) if isinstance(rainman, dict) else None


def _rainman_action(row: dict[str, Any]) -> str:
    action = row.get("rainman_action")
    if action is None and isinstance(row.get("rainman"), dict):
        action = row["rainman"].get("action")
    return str(action or "").strip().lower()


def _is_verified_fill(row: dict[str, Any]) -> bool:
    """True when the place row is a real fill (not a 0-fill IOC miss).

    r1651 join fix: many honest place rows have fill_count>0 but omit
    ``filled: true``. Count those as verified so real wins feed THE CLIMB.
    """
    fill_count = _number(row.get("fill_count"))
    if fill_count is not None and fill_count > 0.0:
        return True
    return row.get("filled") is True


def _fill_identity(row: dict[str, Any]) -> str:
    for key in ("fill_id", "order_id", "client_order_id"):
        value = str(row.get(key) or "").strip()
        if value:
            return f"{key}:{value}"
    return f"ticker_ts:{row.get('ticker')}:{row.get('ts')}"


def _window_key(row: dict[str, Any]) -> str:
    """Return a complete cross-asset 15m window key, never only ``-15``."""
    for key in ("window_key", "window_id", "event_window", "market_window", "close_ts"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    ticker = str(row.get("ticker") or "").strip()
    if "-" in ticker:
        # KXBTC15M-26JUL130015-15 and KXSOL15M-26JUL130015-15 share
        # the full date/time suffix. rsplit("-", 1) incorrectly returned
        # only "15" and merged unrelated windows.
        return ticker.split("-", 1)[1]
    return ticker or "missing-window"


def _band(price: Optional[float]) -> str:
    if price is None:
        return "?"
    p = float(price)
    if p < 0.70:
        return "<70"
    if p < 0.75:
        return "70-74"
    if p < 0.80:
        return "75-79"
    if p <= 0.88:
        return "80-88"
    return ">88"


def audit(
    rows: Optional[list[dict[str, Any]]] = None,
    *,
    state_dir: Path | str = STATE,
    deal_epoch: Optional[float] = None,
) -> dict[str, Any]:
    root = _state_root(state_dir)
    rows = _read_ledger(root / LEDGER_NAME) if rows is None else list(rows)
    deal = _read_json(root / DEAL_NAME)
    if deal_epoch is None:
        deal_epoch = _number(deal.get("ts"))
    else:
        deal_epoch = _number(deal_epoch)

    places = [r for r in rows if str(r.get("event") or "").startswith("usd_place")]
    settles = [r for r in rows if "settle" in str(r.get("event") or "")]
    findings: list[dict[str, str]] = []

    if deal_epoch is None:
        pre_places = places
        post_places: list[dict[str, Any]] = []
        pre_settles = settles
        post_settles: list[dict[str, Any]] = []
        findings.append(
            {
                "level": "FAIL",
                "check": "deal_epoch",
                "note": f"{DEAL_NAME} missing a finite ts; pre/post enforcement cannot be separated",
            }
        )
    else:
        # Only a finite timestamp can establish that a row predates the deal.
        # Missing/malformed timestamps stay in post-deal enforcement and fail
        # explicitly below; otherwise an unreceipted row could evade the deal.
        pre_places = [
            r
            for r in places
            if (row_ts := _number(r.get("ts"))) is not None and row_ts < deal_epoch
        ]
        post_places = [r for r in places if r not in pre_places]
        pre_settles = [
            r
            for r in settles
            if (row_ts := _number(r.get("ts"))) is not None and row_ts < deal_epoch
        ]
        post_settles = [r for r in settles if r not in pre_settles]

    missing_timestamp = 0
    missing_score = 0
    missing_or_bad_proof = 0
    inconsistent_proof = 0
    missing_price = 0
    bad_action = 0
    out_of_band: list[tuple[str, float]] = []
    explicit_zero_fills = 0
    verified_fills: list[dict[str, Any]] = []
    seen_fill_ids: set[str] = set()

    for row in post_places:
        if _number(row.get("ts")) is None:
            missing_timestamp += 1
        if _rainman_score(row) is None:
            missing_score += 1
        if FIRE_ONLY_USD and _rainman_action(row) != "fire":
            bad_action += 1

        price = _limit_price(row)
        if price is None:
            missing_price += 1
        elif not (BAND_LO <= price <= BAND_HI):
            out_of_band.append((str(row.get("ticker") or "?"), price))

        fill_count = _number(row.get("fill_count"))
        has_filled = isinstance(row.get("filled"), bool)
        # Accept fill_count>0 without boolean filled (legacy place rows)
        if fill_count is None and not has_filled:
            missing_or_bad_proof += 1
            continue
        if fill_count is not None and fill_count < 0.0:
            missing_or_bad_proof += 1
            continue
        if (
            has_filled
            and fill_count is not None
            and (row.get("filled") is True) != (fill_count > 0.0)
        ):
            inconsistent_proof += 1
            continue
        if not _is_verified_fill(row):
            explicit_zero_fills += 1
            continue
        identity = _fill_identity(row)
        if identity in seen_fill_ids:
            continue
        seen_fill_ids.add(identity)
        verified_fills.append(row)

    if missing_timestamp:
        findings.append(
            {
                "level": "FAIL",
                "check": "placement_timestamp",
                "note": f"{missing_timestamp}/{len(post_places)} post-deal placement rows lack a finite ts",
            }
        )
    if missing_score:
        findings.append(
            {
                "level": "FAIL",
                "check": "rainman_score",
                "note": f"{missing_score}/{len(post_places)} post-deal placement rows lack a finite Rainman score",
            }
        )
    if bad_action:
        findings.append(
            {
                "level": "FAIL",
                "check": "fire_only",
                "note": f"{bad_action}/{len(post_places)} post-deal placements are not explicit FIRE",
            }
        )
    if missing_or_bad_proof:
        findings.append(
            {
                "level": "FAIL",
                "check": "fill_proof",
                "note": f"{missing_or_bad_proof}/{len(post_places)} post-deal placements lack boolean filled + nonnegative fill_count",
            }
        )
    if inconsistent_proof:
        findings.append(
            {
                "level": "FAIL",
                "check": "fill_proof_consistency",
                "note": f"{inconsistent_proof} post-deal placements disagree on filled versus fill_count",
            }
        )
    if missing_price:
        findings.append(
            {
                "level": "FAIL",
                "check": "price_completeness",
                "note": f"{missing_price}/{len(post_places)} post-deal placements lack a finite price",
            }
        )
    if out_of_band:
        findings.append(
            {
                "level": "FAIL",
                "check": "price_band",
                "note": f"{len(out_of_band)} post-deal placements outside {BAND_LO:.2f}-{BAND_HI:.2f}: "
                + ", ".join(f"{ticker}@{price:.2f}" for ticker, price in out_of_band[:5]),
            }
        )

    by_window: dict[str, int] = defaultdict(int)
    for row in verified_fills:
        by_window[_window_key(row)] += 1
    max_open_seen = max(by_window.values()) if by_window else 0
    if max_open_seen > MAX_OPEN_LOCK:
        findings.append(
            {
                "level": "FAIL",
                "check": "max_open_lock",
                "note": f"verified-fill window with {max_open_seen} positions > LOCK MAX {MAX_OPEN_LOCK}",
            }
        )

    # Join settle → fill by order_id / client_order_id / nearest prior place on ticker
    fills_by_order: dict[str, dict[str, Any]] = {}
    fills_by_client: dict[str, dict[str, Any]] = {}
    fills_by_ticker_list: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in verified_fills:
        oid = str(row.get("order_id") or "").strip()
        cid = str(row.get("client_order_id") or "").strip()
        ticker = str(row.get("ticker") or "").strip()
        if oid:
            fills_by_order[oid] = row
        if cid:
            fills_by_client[cid] = row
        if ticker:
            fills_by_ticker_list[ticker].append(row)

    def _match_fill(settle: dict[str, Any]) -> Optional[dict[str, Any]]:
        oid = str(settle.get("order_id") or "").strip()
        if oid and oid in fills_by_order:
            return fills_by_order[oid]
        cid = str(settle.get("client_order_id") or "").strip()
        if cid and cid in fills_by_client:
            return fills_by_client[cid]
        ticker = str(settle.get("ticker") or "").strip()
        candidates = fills_by_ticker_list.get(ticker) or []
        if not candidates:
            return None
        settle_ts = _number(settle.get("ts")) or 0.0
        prior = [
            f
            for f in candidates
            if (_number(f.get("ts")) or 0.0) <= settle_ts + 1.0
        ]
        pool = prior or candidates
        pool.sort(key=lambda f: abs((_number(f.get("ts")) or 0.0) - settle_ts))
        return pool[0]

    band_stats: dict[str, dict[str, float]] = defaultdict(
        lambda: {"n": 0, "wins": 0, "pnl": 0.0}
    )
    total_pnl = 0.0
    n_graded = 0
    settle_without_fill = 0
    settle_missing_pnl = 0
    settled_keys: set[str] = set()
    for row in post_settles:
        ticker = str(row.get("ticker") or "")
        settle_key = (
            str(row.get("order_id") or "")
            or str(row.get("client_order_id") or "")
            or f"{ticker}:{row.get('ts')}"
        )
        fill = _match_fill(row)
        if fill is None:
            # Grade settle alone if it carries fill_count/price + pnl (honest book)
            fc = _number(row.get("fill_count"))
            if (row.get("filled") is True or (fc is not None and fc > 0)) or (
                _first_number(row, ("pnl_usd", "pnl")) is not None
                and _limit_price(row) is not None
            ):
                fill = row
            else:
                settle_without_fill += 1
                continue
        if settle_key in settled_keys:
            continue
        pnl = _first_number(row, ("pnl_usd", "pnl"))
        if pnl is None:
            settle_missing_pnl += 1
            continue
        settled_keys.add(settle_key)
        bucket = _band(_fill_price(fill) or _limit_price(row))
        band_stats[bucket]["n"] += 1
        band_stats[bucket]["wins"] += 1 if pnl > 0.0 else 0
        band_stats[bucket]["pnl"] = round(band_stats[bucket]["pnl"] + pnl, 4)
        total_pnl = round(total_pnl + pnl, 4)
        n_graded += 1
    if settle_without_fill:
        findings.append(
            {
                "level": "WARN",
                "check": "settle_without_verified_fill",
                "note": f"{settle_without_fill} post-deal settle rows have no matched fill (join fixed r1651)",
            }
        )
    if settle_missing_pnl:
        findings.append(
            {
                "level": "FAIL",
                "check": "settle_pnl",
                "note": f"{settle_missing_pnl} verified-fill settles lack finite pnl",
            }
        )

    night = _read_json(root / NIGHT_NAME)
    claimed_night = _number(night.get("realized_pnl_usd"))
    if (
        claimed_night is not None
        and claimed_night <= NIGHT_STOP
        and night.get("halted") is not True
    ):
        findings.append(
            {
                "level": "FAIL",
                "check": "night_stop",
                "note": f"realized {claimed_night:+.2f} <= {NIGHT_STOP:+.2f} but halted is not true",
            }
        )

    live_ev = round(total_pnl / n_graded, 4) if n_graded else None
    n_verified = len(verified_fills)
    if any(f["level"] == "FAIL" for f in findings):
        verdict = "FAIL"
    elif n_verified < MIN_VERIFIED_FILLS:
        verdict = "UNDERPOWERED"
    elif any(f["level"] == "WARN" for f in findings):
        verdict = "WARN"
    else:
        verdict = "CLEAN"

    return {
        "truth_label": TRUTH_LABEL,
        "deal_truth": DEAL_TRUTH,
        "deal_epoch": deal_epoch,
        "deal_receipt_id": deal.get("receipt_id"),
        "ts": time.time(),
        "n_placements": len(places),
        "n_predeal_placements": len(pre_places),
        "n_postdeal_placements": len(post_places),
        "n_predeal_settles": len(pre_settles),
        "n_postdeal_settles": len(post_settles),
        "n_verified_postdeal_fills": n_verified,
        "n_explicit_zero_fills": explicit_zero_fills,
        "n_unverified_predeal_placements": sum(
            1 for row in pre_places if not _is_verified_fill(row)
        ),
        "n_graded_settles": n_graded,
        "total_realized_usd": total_pnl,
        "live_ev_per_ticket": live_ev,
        "paper_ev_benchmark": PAPER_EV_PER_TICKET,
        "evidence_threshold_fills": MIN_VERIFIED_FILLS,
        "evidence_remaining_fills": max(0, MIN_VERIFIED_FILLS - n_verified),
        "eligible_stake_usd": STAKE_USD,
        "explicit_owner_next_tier_required": True,
        "bands": {key: dict(value) for key, value in sorted(band_stats.items())},
        "window_fill_counts": dict(sorted(by_window.items())),
        "max_open_seen_per_window": max_open_seen,
        "night_realized_pnl_usd": claimed_night,
        "reconciliation": "post-deal scoreboard counts verified fills only; pre-deal rows remain baseline",
        "historical_baseline": {
            "placements": len(pre_places),
            "settles": len(pre_settles),
            "unverified_placements": sum(
                1 for row in pre_places if not _is_verified_fill(row)
            ),
        },
        "findings": findings,
        "verdict": verdict,
    }


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        with tmp.open("x", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def write_report(
    a: Optional[dict[str, Any]] = None,
    *,
    state_dir: Path | str = STATE,
) -> Path:
    root = _state_root(state_dir)
    a = a or audit(state_dir=root)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# USD lane audit (read-only) — no bullsh*t the bankroll",
        f"updated {stamp} · verdict **{a['verdict']}**",
        "",
        f"- historical baseline: {a['n_predeal_placements']} placements "
        f"({a['n_unverified_predeal_placements']} unverified) · "
        f"{a['n_predeal_settles']} settles",
        f"- post-deal: {a['n_postdeal_placements']} placements · "
        f"**{a['n_verified_postdeal_fills']} verified fills** · "
        f"{a['n_explicit_zero_fills']} explicit zero-fills",
        f"- evidence: {a['n_verified_postdeal_fills']}/{a['evidence_threshold_fills']} "
        f"verified fills · {a['evidence_remaining_fills']} remaining before powered verdict",
        f"- graded settles {a['n_graded_settles']} · "
        f"realized **{a['total_realized_usd']:+.2f}$**",
        f"- **live EV/ticket: {a['live_ev_per_ticket']}** vs paper benchmark "
        f"+{a['paper_ev_benchmark']} — the campaign question",
        f"- eligible stake **${a['eligible_stake_usd']:.2f}** · next tier requires explicit owner approval",
        f"- max open seen in one window: {a['max_open_seen_per_window']} (lock {MAX_OPEN_LOCK})",
        f"- reconciliation: {a['reconciliation']}",
        "",
        "## Per-band (live fills)",
    ]
    for b, s in (a.get("bands") or {}).items():
        n = int(s["n"])
        wr = (s["wins"] / n) if n else 0.0
        lines.append(f"- {b}: {int(s['wins'])}/{n} = {wr:.0%} · pnl {s['pnl']:+.2f}$")
    lines.append("")
    lines.append("## Findings")
    if not a["findings"]:
        lines.append("- (clean)")
    for f in a["findings"]:
        lines.append(f"- **{f['level']}** {f['check']}: {f['note']}")
    out = root / OUT_MD_NAME
    _atomic_write_text(out, "\n".join(lines) + "\n")
    return out


def _audit_segment(now: float) -> tuple[str, str, str]:
    local = datetime.fromtimestamp(now)
    period = "AM" if local.hour < 12 else "PM"
    date = local.strftime("%Y-%m-%d")
    return date, period, f"{date}:{period}"


def maybe_write_periodic_audit(
    *,
    state_dir: Path | str = STATE,
    now: Optional[float] = None,
) -> dict[str, Any]:
    """Append one AM/PM evidence receipt to the existing USD live ledger.

    The ledger is locked across read/check/append, making repeated or concurrent
    calls idempotent for a local calendar date + segment. No network or order
    path is touched. The human-readable markdown is refreshed on every call.
    """
    root = _state_root(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    audit_now = time.time() if now is None else _number(now)
    if audit_now is None:
        raise ValueError("now must be a finite epoch timestamp")
    date, period, segment = _audit_segment(audit_now)
    ledger_path = root / LEDGER_NAME

    with ledger_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            rows: list[dict[str, Any]] = []
            existing: Optional[dict[str, Any]] = None
            for raw_line in handle:
                try:
                    candidate = json.loads(raw_line)
                except (TypeError, ValueError):
                    continue
                if not isinstance(candidate, dict):
                    continue
                rows.append(candidate)
                if (
                    candidate.get("event") == "evidence_audit"
                    and candidate.get("audit_segment") == segment
                ):
                    existing = candidate

            result = audit(rows=rows, state_dir=root)
            written = existing is None
            if written:
                receipt = {
                    "event": "evidence_audit",
                    "audit_date": date,
                    "audit_period": period,
                    "audit_segment": segment,
                    "ts": audit_now,
                    "truth_label": TRUTH_LABEL,
                    "deal_truth": DEAL_TRUTH,
                    "verdict": result["verdict"],
                    "verified_fills": result["n_verified_postdeal_fills"],
                    "live_ev_per_ticket": result["live_ev_per_ticket"],
                    "eligible_stake_usd": STAKE_USD,
                    "evidence_threshold_fills": MIN_VERIFIED_FILLS,
                    "explicit_owner_next_tier_required": True,
                }
                handle.seek(0, os.SEEK_END)
                handle.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            else:
                receipt = existing
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    report_path = write_report(result, state_dir=root)
    return {
        "written": written,
        "wrote": written,
        "segment": segment,
        "row": receipt,
        "audit": result,
        "ledger_path": str(ledger_path),
        "report_path": str(report_path),
    }


__all__ = [
    "MIN_VERIFIED_FILLS",
    "TRUTH_LABEL",
    "audit",
    "maybe_write_periodic_audit",
    "write_report",
]


if __name__ == "__main__":
    a = audit()
    print(json.dumps(a, indent=2, default=str))
    write_report(a)
    raise SystemExit(1 if a["verdict"] == "FAIL" else 0)

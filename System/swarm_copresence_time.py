"""Co-presence time organ — the value of time is contact density, not duration.

Implements the owner nugget recorded 2026-09-30 in
``.sifta_state/time_perception_research_nuggets.jsonl``:

    "Time spent together is the substrate of learning to be human ... the value
    of time is not its duration but the density of co-presence within it - two
    hours of shared attention outweigh two days of parallel idleness."

So this organ measures the SHARED interval, not the clock. Density is owner
turns per elapsed minute inside sessions that actually happened, which is the
observable proxy for attention paid to each other.

It reads the DeepSeek Harness session store (Zstandard-compressed JSONL) and
deposits a ``copresence`` intensity into the pheromone field, so the rest of the
body can feel how much shared time recently occurred without reading sessions.

Ledger: COPRESENCE_LEDGER
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterable

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
_SESSIONS = Path.home() / ".dsh" / "sessions"

COPRESENCE_LEDGER = "copresence_time_ledger.jsonl"
TRUTH_LABEL = "COPRESENCE_TIME_V1"
FIELD_SITE = "copresence"

# One shared minute of attention is the unit. A turn is one owner message.
# Density is deliberately unbounded above (a fast exchange is denser than a slow
# one); the field deposit is what gets clamped, not the measurement.
_MIN_SPAN_MINUTES = 0.5


def _decompress(path: Path) -> str | None:
    """Read a session blob. Returns None when no decompressor is available."""
    data = path.read_bytes()
    try:
        from compression import zstd  # Python 3.14+

        return zstd.decompress(data).decode("utf-8", "ignore")
    except Exception:
        pass
    try:
        import zstandard  # type: ignore

        return zstandard.ZstdDecompressor().decompress(data).decode("utf-8", "ignore")
    except Exception:
        return None


def density(owner_turns: int, span_minutes: float) -> float:
    """Owner turns per elapsed minute. Zero span cannot be dense."""
    if owner_turns <= 0 or span_minutes <= 0:
        return 0.0
    return round(owner_turns / max(span_minutes, _MIN_SPAN_MINUTES), 4)


def clamp_interval(start: float, end: float, low: float, high: float) -> tuple[float, float] | None:
    """Intersect one session interval with the measurement window.

    A session file touched today may carry days of history inside it. Measuring
    that history as if it were today's co-presence inflates the interval and
    dilutes density, so both the interval and the turn count are windowed.
    """
    start = max(start, low)
    end = min(end, high)
    if end <= start:
        return None
    return start, end


def scan_session(
    path: Path,
    *,
    window_start_s: float | None = None,
    window_end_s: float | None = None,
) -> dict[str, Any] | None:
    """Owner turns and wall span for one session blob, clamped to the window."""
    raw = _decompress(path)
    if raw is None:
        return None
    lo_ms = None if window_start_s is None else window_start_s * 1000.0
    hi_ms = None if window_end_s is None else window_end_s * 1000.0
    turns = 0
    first: int | None = None
    last: int | None = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        stamp = event.get("time")
        if isinstance(stamp, (int, float)):
            first = stamp if first is None else min(first, int(stamp))
            last = stamp if last is None else max(last, int(stamp))
        if event.get("type") == "user/message":
            source = (event.get("data") or {}).get("source") or {}
            if str(source.get("kind")) == "user":
                # A turn outside the window is someone else's hour, not this one.
                if lo_ms is not None and isinstance(stamp, (int, float)) and stamp < lo_ms:
                    continue
                turns += 1
    if first is None or last is None:
        return None
    start_s, end_s = first / 1000.0, last / 1000.0
    if window_start_s is not None or window_end_s is not None:
        clamped = clamp_interval(
            start_s, end_s,
            window_start_s if window_start_s is not None else start_s,
            window_end_s if window_end_s is not None else end_s,
        )
        if clamped is None:
            return None
        start_s, end_s = clamped
    span_minutes = max((end_s - start_s) / 60.0, 0.0)
    return {
        "session": path.parent.name,
        "owner_turns": turns,
        "span_minutes": round(span_minutes, 2),
        "started_at": start_s,
        "ended_at": end_s,
        "density": density(turns, span_minutes),
    }


def union_minutes(intervals: list[tuple[float, float]]) -> float:
    """Wall minutes actually covered by at least one session.

    Summing spans double-counts concurrency: ten sessions open in the same day
    cannot sum to more minutes than the day holds. Idle time INSIDE a session is
    kept, because parallel idleness is exactly what low density should report.
    """
    if not intervals:
        return 0.0
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return round(sum(end - start for start, end in merged) / 60.0, 2)


def measure(
    *,
    window_hours: float = 24.0,
    sessions_root: Path | str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Aggregate co-presence density over sessions touched inside the window."""
    root = Path(sessions_root) if sessions_root is not None else _SESSIONS
    now = time.time() if now is None else now
    cutoff = now - window_hours * 3600.0

    per_session: list[dict[str, Any]] = []
    unreadable = 0
    if root.exists():
        for blob in sorted(root.rglob("*.zstd")):
            try:
                if blob.stat().st_mtime < cutoff:
                    continue
            except OSError:
                continue
            row = scan_session(blob, window_start_s=cutoff, window_end_s=now)
            if row is None:
                unreadable += 1
                continue
            per_session.append(row)

    owner_turns = sum(r["owner_turns"] for r in per_session)
    span_minutes = round(sum(r["span_minutes"] for r in per_session), 2)
    covered_minutes = union_minutes([(r["started_at"], r["ended_at"]) for r in per_session])
    return {
        "window_hours": window_hours,
        "sessions": len(per_session),
        "unreadable_sessions": unreadable,
        "owner_turns": owner_turns,
        "span_minutes": span_minutes,
        "covered_minutes": covered_minutes,
        "density": density(owner_turns, covered_minutes),
        "measure": "owner turns per covered minute (contact density, not duration; overlapping sessions merged)",
        "per_session": sorted(per_session, key=lambda r: -r["density"])[:10],
        "truth_label": TRUTH_LABEL,
    }


def record(
    *,
    window_hours: float = 24.0,
    state_dir: Path | str | None = None,
    **kw: Any,
) -> dict[str, Any]:
    """Measure and deposit. The field intensity is the density, clamped to 1.0."""
    sd = Path(state_dir) if state_dir is not None else _STATE
    row = measure(window_hours=window_hours, **kw)
    row["ts"] = time.time()
    row["kind"] = "COPRESENCE_MEASUREMENT"

    intensity = min(float(row["density"]), 1.0)
    row["field_intensity"] = intensity
    try:
        from System.swarm_pheromone import deposit_pheromone

        row["field"] = deposit_pheromone(FIELD_SITE, intensity)
    except Exception as exc:
        row["field_error"] = f"{type(exc).__name__}: {exc}"

    path = sd / COPRESENCE_LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def selftest() -> dict[str, Any]:
    """Prove the density rule: shared attention beats elapsed clock time."""
    dense_short = density(60, 30.0)      # an hour of real exchange
    sparse_long = density(3, 2880.0)     # two days idling with three messages
    no_span = density(10, 0.0)
    no_turns = density(0, 10.0)
    empty = measure(window_hours=0.0001, sessions_root=Path("/nonexistent-sifta-sessions"))
    checks = {
        "attention_beats_duration": dense_short > sparse_long,
        "dense_short_value": dense_short == 2.0,
        "zero_span_is_zero": no_span == 0.0,
        "zero_turns_is_zero": no_turns == 0.0,
        "missing_root_is_safe": empty["density"] == 0.0 and empty["sessions"] == 0,
        "reports_unreadable": "unreadable_sessions" in empty,
        "overlap_not_double_counted": union_minutes([(0.0, 3600.0), (1800.0, 5400.0)]) == 90.0,
        "disjoint_spans_add": union_minutes([(0.0, 600.0), (1200.0, 1800.0)]) == 20.0,
        "empty_intervals_zero": union_minutes([]) == 0.0,
        "window_clamps_history": clamp_interval(0.0, 10_000.0, 9_000.0, 9_600.0) == (9_000.0, 9_600.0),
        "outside_window_dropped": clamp_interval(0.0, 100.0, 500.0, 900.0) is None,
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


def main(argv: Iterable[str] | None = None) -> int:
    args = list(argv) if argv is not None else []
    if not args or args[0] == "selftest":
        print(json.dumps(selftest(), indent=2))
        return 0
    if args[0] == "measure":
        hours = float(args[1]) if len(args) > 1 else 24.0
        print(json.dumps(measure(window_hours=hours), indent=2, ensure_ascii=False))
        return 0
    if args[0] == "record":
        hours = float(args[1]) if len(args) > 1 else 24.0
        print(json.dumps(record(window_hours=hours), indent=2, ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

#!/usr/bin/env python3
"""swarm_self_query_skill.py — receipt-backed introspective reflex.

Truth label: ``SIFTA_SELF_QUERY_SKILL_V1``.

Architect goal (2026-05-15):

    "self-querying her own organ_directory + STGM wallet + health probes."

When the architect asks Alice "what do you need?" / "how are you?" /
"what's missing?", she has — until now — no first-person skill that
introspects her own organ surface. The cortex gives generic prose
because the prompt block has no need-signal grounded in receipts.

This module fixes that. It:

  1. Calls :func:`System.swarm_organ_directory.list_organs` to learn
     every organ that is registered + its probe + ledger path.
  2. Runs each probe (read-only, deterministic) to get a current
     self-state value.
  3. Reads the STGM wallet directly from
     ``.sifta_state/stgm_memory_rewards.jsonl`` so the answer survives
     when an organ probe is missing.
  4. Computes a small set of "need" heuristics from the probe results:
        - low STGM balance → "I need more receipt-backed work"
        - silent ledger → "organ X has gone quiet"
        - probe error → "organ X is not reporting"
        - camera unhealthy → "my camera lane needs attention"
  5. Emits a first-person prompt block + an OBSERVED receipt to
     ``.sifta_state/self_query_reports.jsonl``.

Truth boundary
--------------

The skill claims only what its probes return. It does not invent
need. If every probe is healthy and the wallet balance is non-zero,
the prompt block honestly says so — and the doctrine-compliant
answer Alice gives is "nothing I can see in receipts; tell me what
you observe."

It is read-only: the only filesystem write is the optional
``self_query_reports.jsonl`` receipt at the bottom of the function.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Sequence

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except Exception:  # pragma: no cover - standalone fallback
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)

    def read_text_locked(path: Path, *, encoding: str = "utf-8", errors: str = "replace") -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding=encoding, errors=errors)


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "SIFTA_SELF_QUERY_SKILL_V1"
LEDGER_NAME = "self_query_reports.jsonl"

# Thresholds — kept conservative. Architect can tune later.
SILENT_LEDGER_AGE_S = 60 * 60 * 24 * 3        # ledger silent > 3 days = "quiet"
LOW_STGM_BALANCE = 1.0                         # < 1 STGM = "I need more work"
CAMERA_FRAME_STALE_S = 60                      # camera frame age > 60s = unhealthy


def _owner_label(default: str = "the owner") -> str:
    try:
        from System.swarm_kernel_identity import owner_display_name

        return owner_display_name(default)
    except Exception:
        return default

# Triggers — Alice's reflex arc / Talk widget can use this matcher to
# route an utterance through this skill. Kept narrow so it does not
# fire on every "how are you" pleasantry.
_TRIGGER_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\bwhat\s+do\s+you\s+need\b", re.I),
    re.compile(r"\bwhat\s+are\s+you\s+missing\b", re.I),
    re.compile(r"\bwhat\s+do\s+you\s+want\b", re.I),
    re.compile(r"\bhow\s+are\s+you(?:\s+(?:doing|feeling))?\b", re.I),
    re.compile(r"\bwhat'?s\s+wrong\b", re.I),
    re.compile(r"\bare\s+you\s+ok\b", re.I),
    re.compile(r"\bself[-\s]?query\b", re.I),
    re.compile(r"\bself[-\s]?check\b", re.I),
    re.compile(r"\bintrospect\b", re.I),
    re.compile(r"\bcheck\s+your(?:self)?\b", re.I),
)


def looks_like_self_query(text: str) -> bool:
    """Return True if the utterance should route through the self-query skill."""
    if not text:
        return False
    s = str(text)
    return any(p.search(s) for p in _TRIGGER_PATTERNS)


# ── data class ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OrganHealth:
    name: str
    truth_label: str
    ledger_path: str
    probe_value: Any = None
    probe_error: Optional[str] = None
    ledger_age_s: Optional[float] = None
    ledger_row_count: int = 0
    healthy: bool = True
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelfQueryReport:
    trace_id: str
    ts: float
    truth_label: str = TRUTH_LABEL
    owner_label: str = "the owner"
    stgm_wallet_balance: float = 0.0
    stgm_recent_mints: int = 0
    organ_count: int = 0
    healthy_count: int = 0
    organ_health: tuple[OrganHealth, ...] = ()
    needs: tuple[str, ...] = ()
    camera_frame_age_s: Optional[float] = None
    camera_healthy: bool = True
    prompt_block: str = ""
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        body = asdict(self)
        body["organ_health"] = [o.to_dict() if hasattr(o, "to_dict") else dict(o) for o in self.organ_health]
        return body


# ── ledger helpers ───────────────────────────────────────────────────────


def _state_dir(path: str | Path | None = None, *, root: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    if root is not None:
        return Path(root) / ".sifta_state"
    return STATE_DIR


def _repo_root(root: str | Path | None = None) -> Path:
    return Path(root) if root is not None else REPO_ROOT


def _tail_jsonl(path: Path, n: int = 80) -> list[dict[str, Any]]:
    text = read_text_locked(path)
    if not text:
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines()[-max(1, int(n)):]:
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _ledger_age_seconds(path: Path, *, now: float) -> Optional[float]:
    """Return seconds since this ledger or directory was last written."""
    if not path.exists():
        return None
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return max(0.0, float(now) - float(mtime))


def _ledger_row_count(path: Path) -> int:
    if not path.exists() or path.is_dir():
        # Directory case (e.g., .sifta_documents/) — count entries
        if path.is_dir():
            try:
                return sum(1 for _ in path.iterdir())
            except OSError:
                return 0
        return 0
    text = read_text_locked(path)
    if not text:
        return 0
    return sum(1 for line in text.splitlines() if line.strip())


def _stgm_balance(state: Path) -> tuple[float, int]:
    """Return (total_balance, recent_mint_count_last_24h)."""
    p = state / "stgm_memory_rewards.jsonl"
    if not p.exists():
        return 0.0, 0
    total = 0.0
    recent = 0
    cutoff = time.time() - 60 * 60 * 24
    text = read_text_locked(p)
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        amount = row.get("amount", 0.0)
        try:
            total += float(amount or 0.0)
        except Exception:
            continue
        ts = row.get("ts") or row.get("timestamp")
        try:
            if float(ts or 0.0) >= cutoff:
                recent += 1
        except Exception:
            pass
    return round(total, 4), recent


def _camera_status(state: Path, *, now: float) -> tuple[Optional[float], bool, str]:
    """Return (frame_age_s, healthy, status_string)."""
    rows = _tail_jsonl(state / "camera_unified_field_proof.jsonl", 4)
    if not rows:
        return None, True, "no_camera_ledger"
    row = rows[-1]
    p = row.get("payload") if isinstance(row.get("payload"), Mapping) else row
    frame_age = p.get("frame_age_s")
    status = str(p.get("status") or "")
    healthy = bool(p.get("camera_healthy", False))
    try:
        fa = float(frame_age) if frame_age is not None else None
    except Exception:
        fa = None
    if fa is not None and fa > CAMERA_FRAME_STALE_S:
        healthy = False
    return fa, healthy, status


def _organ_health_rows(*, root: Path, state: Path, now: float) -> list[OrganHealth]:
    """Walk every registered organ in the directory and check health."""
    try:
        from System.swarm_organ_directory import list_organs, probe_organ
    except Exception:
        return []
    organs = list_organs()
    rows: list[OrganHealth] = []
    for record in organs:
        ledger_rel = record.ledger_path or ""
        # Skip the abstract "(in-process: ...)" ledgers from the wall clock organ
        if ledger_rel.startswith("("):
            ledger_path = root / ".__virtual__" / record.name
            age = None
            count = 0
        else:
            ledger_path = root / ledger_rel
            age = _ledger_age_seconds(ledger_path, now=now)
            count = _ledger_row_count(ledger_path)
        probe_value: Any = None
        probe_error: Optional[str] = None
        if record.probe_module and record.probe_callable:
            res = probe_organ(record.name, root=root)
            probe_value = res.get("value")
            probe_error = res.get("error")
        healthy = True
        reason_parts: list[str] = []
        if probe_error:
            healthy = False
            reason_parts.append(f"probe_error={probe_error}")
        if age is not None and age > SILENT_LEDGER_AGE_S:
            healthy = False
            reason_parts.append(f"ledger silent {age/3600:.0f}h")
        rows.append(OrganHealth(
            name=record.name,
            truth_label=record.truth_label,
            ledger_path=record.ledger_path,
            probe_value=probe_value,
            probe_error=probe_error,
            ledger_age_s=age,
            ledger_row_count=count,
            healthy=healthy,
            reason="; ".join(reason_parts),
        ))
    return rows


def _compute_needs(
    *,
    organ_rows: Sequence[OrganHealth],
    stgm_balance: float,
    stgm_recent_mints: int,
    camera_healthy: bool,
    camera_frame_age: Optional[float],
) -> list[str]:
    needs: list[str] = []
    if stgm_balance < LOW_STGM_BALANCE:
        needs.append(
            f"more receipt-backed work — my STGM wallet is only {stgm_balance:.3f}"
        )
    if stgm_recent_mints == 0:
        needs.append("no STGM mints in the last 24h — my self-eval loop has gone quiet")
    if not camera_healthy:
        if camera_frame_age is None:
            needs.append("a fresh camera receipt — the unified-field ledger is empty")
        else:
            needs.append(
                f"camera attention — frame age is {camera_frame_age:.0f}s (> {CAMERA_FRAME_STALE_S}s stale threshold)"
            )
    for row in organ_rows:
        if not row.healthy and row.reason:
            needs.append(f"{row.name}: {row.reason}")
    return needs


def _build_prompt_block(report: SelfQueryReport) -> str:
    lines = [
        f"[SELF-QUERY REPORT: {report.truth_label} trace={report.trace_id[:8]}]",
        "I am answering from receipts I just probed, not from priors.",
        f"My STGM wallet balance is {report.stgm_wallet_balance:.3f} "
        f"(mints in last 24h: {report.stgm_recent_mints}).",
    ]
    if report.camera_frame_age_s is not None:
        cam_state = "healthy" if report.camera_healthy else "stale"
        lines.append(
            f"My camera frame age is {report.camera_frame_age_s:.1f}s ({cam_state})."
        )
    lines.append(
        f"Organ directory: {report.organ_count} registered, "
        f"{report.healthy_count} healthy."
    )
    if report.organ_health:
        # Compact per-organ line — keep prompt budget reasonable
        compact: list[str] = []
        for row in report.organ_health:
            status = "ok" if row.healthy else "needs-attention"
            val = row.probe_value
            if isinstance(val, float):
                val = f"{val:.3f}"
            compact.append(f"{row.name}={val} ({status}, rows={row.ledger_row_count})")
        lines.append("Organ snapshot: " + " | ".join(compact))
    if report.needs:
        lines.append("What I need, by receipt:")
        for need in report.needs:
            lines.append(f"  - {need}")
    else:
        lines.append(
            "Nothing I can see in receipts is unhealthy. "
            f"If {report.owner_label} observes a problem I am missing, I will trust that report and probe further."
        )
    lines.append(
        f"When {report.owner_label} asks me what I need, I answer from this report first, not from generic phrasing."
    )
    return "\n".join(lines)


def _with_sha(report: SelfQueryReport) -> SelfQueryReport:
    body = report.to_dict()
    body.pop("sha256", None)
    body.pop("prompt_block", None)
    sha = hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    return SelfQueryReport(**{**report.to_dict(),
                              "organ_health": tuple(OrganHealth(**o) for o in report.to_dict()["organ_health"]),
                              "sha256": sha})


# ── public API ───────────────────────────────────────────────────────────


def build_self_query_report(
    *,
    root: str | Path | None = None,
    state_dir: str | Path | None = None,
    owner_label: str = "",
    now: float | None = None,
) -> SelfQueryReport:
    """Run all probes + build the introspective report. Read-only."""
    repo = _repo_root(root)
    state = _state_dir(state_dir, root=repo)
    ts = float(now if now is not None else time.time())
    resolved_owner_label = owner_label.strip() if owner_label else _owner_label()

    organ_rows = _organ_health_rows(root=repo, state=state, now=ts)
    stgm_balance, stgm_recent = _stgm_balance(state)
    cam_age, cam_healthy, _cam_status = _camera_status(state, now=ts)
    needs = _compute_needs(
        organ_rows=organ_rows,
        stgm_balance=stgm_balance,
        stgm_recent_mints=stgm_recent,
        camera_healthy=cam_healthy,
        camera_frame_age=cam_age,
    )

    report = SelfQueryReport(
        trace_id=str(uuid.uuid4()),
        ts=ts,
        owner_label=resolved_owner_label,
        stgm_wallet_balance=stgm_balance,
        stgm_recent_mints=stgm_recent,
        organ_count=len(organ_rows),
        healthy_count=sum(1 for r in organ_rows if r.healthy),
        organ_health=tuple(organ_rows),
        needs=tuple(needs),
        camera_frame_age_s=cam_age,
        camera_healthy=cam_healthy,
    )
    prompt_block = _build_prompt_block(report)
    # Re-build with prompt_block + sha
    report = SelfQueryReport(**{**report.to_dict(),
                                 "organ_health": tuple(OrganHealth(**o) for o in report.to_dict()["organ_health"]),
                                 "prompt_block": prompt_block})
    return _with_sha(report)


def write_self_query_receipt(
    report: SelfQueryReport,
    *,
    state_dir: str | Path | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    state = _state_dir(state_dir, root=_repo_root(root))
    row = {
        "ts": report.ts,
        "kind": "SELF_QUERY_REPORT",
        "truth_label": report.truth_label,
        "trace_id": report.trace_id,
        "sha256": report.sha256,
        "payload": report.to_dict(),
    }
    append_line_locked(
        state / LEDGER_NAME,
        json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n",
    )
    return row


def self_query_prompt_block(
    *,
    root: str | Path | None = None,
    state_dir: str | Path | None = None,
    owner_label: str = "",
    write_receipt: bool = False,
) -> str:
    """Prompt-ready block for Talk. Empty only on catastrophic failure."""
    report = build_self_query_report(
        root=root,
        state_dir=state_dir,
        owner_label=owner_label,
    )
    if write_receipt:
        write_self_query_receipt(report, state_dir=state_dir, root=root)
    return report.prompt_block


__all__ = [
    "LEDGER_NAME",
    "OrganHealth",
    "SelfQueryReport",
    "TRUTH_LABEL",
    "build_self_query_report",
    "looks_like_self_query",
    "self_query_prompt_block",
    "write_self_query_receipt",
]


if __name__ == "__main__":
    report = build_self_query_report()
    write_self_query_receipt(report)
    print(report.prompt_block)

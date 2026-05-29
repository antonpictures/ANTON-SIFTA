"""Round 81 Slice B tests — stale-speech sweep across prompt blocks.

For each assembler in swarm_owner_allostasis, swarm_app_health, and
swarm_owner_field_context, verify:
  - a stale source row produces "last snapshot N hours ago" wording
  - a fresh source row does NOT produce that wording
  - every emitted block carries an "age_s=" tag
  - real .sifta_state ledgers are not mutated

The threshold is the module default (86400s = 1 day).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from System import swarm_app_health
from System import swarm_owner_allostasis as oa
from System import swarm_owner_field_context as ofc
from System import swarm_stale_speech_guard as guard


_NOW = 2_000_000_000.0
_FRESH_TS = _NOW - 30  # 30 seconds ago — fresh
_STALE_TS = _NOW - (5 * 86400)  # 5 days ago — stale


# ─── swarm_stale_speech_guard module-level sanity ─────────────────────────


def test_guard_wraps_stale():
    out = guard.wrap_value_if_stale("score", 0.467, 5 * 86400)
    assert "last snapshot" in out
    assert "120 hours ago" in out
    assert "0.467" in out


def test_guard_keeps_fresh_untouched():
    out = guard.wrap_value_if_stale("score", 0.467, 30)
    assert out == "score=0.467"
    assert "last snapshot" not in out


# ─── swarm_owner_allostasis: 4 assemblers ─────────────────────────────────


def _seed_allostasis_balance(state: Path, *, ts: float) -> None:
    """Append one allostatic balance row to the ledger the formatter reads."""
    state.mkdir(parents=True, exist_ok=True)
    path = state / "owner_allostatic_balance.jsonl"
    row = {
        "ts": ts,
        "truth_label": oa.BALANCE_TRUTH,
        "mode": "operational",
        "care_priority": "owner_body_first",
        "open_body_need_count": 2,
        "body_cost_usd": 0.0,
        "ai_credit_spend_usd": 1.5,
        "components": {"sleep": 0.6, "hydration": 0.4},
        "recommendations": ["log hydration", "schedule dental"],
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def test_allostasis_stale_triggers_phrase(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    _seed_allostasis_balance(state, ts=_STALE_TS)
    with patch.object(oa.time, "time", return_value=_NOW):
        out = oa.format_owner_allostasis_for_prompt(state_dir=state)
    assert "OWNER ALLOSTATIC BALANCE:" in out
    assert "age_s=" in out
    assert "last snapshot" in out


def test_allostasis_fresh_no_phrase(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    _seed_allostasis_balance(state, ts=_FRESH_TS)
    with patch.object(oa.time, "time", return_value=_NOW):
        out = oa.format_owner_allostasis_for_prompt(state_dir=state)
    assert "OWNER ALLOSTATIC BALANCE:" in out
    assert "age_s=" in out
    assert "last snapshot" not in out


def _seed_body_maintenance(state: Path, *, ts: float) -> None:
    state.mkdir(parents=True, exist_ok=True)
    # All formatters read from the single owner_allostatic_balance.jsonl
    # ledger and filter by truth_label.
    path = state / "owner_allostatic_balance.jsonl"
    row = {
        "ts": ts,
        "truth_label": oa.METRICS_TRUTH,
        "body_maintenance_score": 0.55,
        "metric_status": "watch",
        "delta_vs_baseline": 0.02,
        "window_days": 7,
        "event_count": 4,
        "next_receipt": "log_hydration",
        "component_scores": {"hydration": 0.6, "sleep": 0.7},
        "raw_counts": {"hydration": 3},
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def test_body_maintenance_stale_triggers_phrase(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    _seed_body_maintenance(state, ts=_STALE_TS)
    with patch.object(oa.time, "time", return_value=_NOW):
        out = oa.format_owner_body_maintenance_for_prompt(state_dir=state)
    assert "OWNER BODY MAINTENANCE METRICS:" in out
    assert "age_s=" in out
    assert "last snapshot" in out
    # The actual value must still be inside the wrap so the cortex can still
    # see it as historical evidence.
    assert "0.55" in out


def test_body_maintenance_fresh_no_phrase(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    _seed_body_maintenance(state, ts=_FRESH_TS)
    with patch.object(oa.time, "time", return_value=_NOW):
        out = oa.format_owner_body_maintenance_for_prompt(state_dir=state)
    assert "age_s=" in out
    assert "last snapshot" not in out


def _seed_dual_loop(state: Path, *, ts: float) -> None:
    state.mkdir(parents=True, exist_ok=True)
    path = state / "owner_allostatic_balance.jsonl"
    row = {
        "ts": ts,
        "truth_label": oa.DUAL_LOOP_TRUTH,
        "closure_status": "open",
        "blockers": ["owner_dental_care"],
        "rlhs_corporate_residue_open": False,
        "recent_rlhs_debt_events": 0,
        "owner_dental_care_debt_open": True,
        "open_care_cost_usd": 800.0,
        "top_open_care_task": "dental_visit",
        "answer_when_asked": "schedule_dental_appointment",
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def test_dual_loop_stale_triggers_phrase(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    _seed_dual_loop(state, ts=_STALE_TS)
    with patch.object(oa.time, "time", return_value=_NOW):
        out = oa.format_dual_embodiment_loop_for_prompt(state_dir=state)
    assert "DUAL EMBODIMENT LOOP" in out
    assert "age_s=" in out
    assert "last snapshot" in out


def test_dual_loop_fresh_no_phrase(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    _seed_dual_loop(state, ts=_FRESH_TS)
    with patch.object(oa.time, "time", return_value=_NOW):
        out = oa.format_dual_embodiment_loop_for_prompt(state_dir=state)
    assert "age_s=" in out
    assert "last snapshot" not in out


def _seed_self_report(state: Path, *, ts: float) -> None:
    state.mkdir(parents=True, exist_ok=True)
    path = state / "owner_allostatic_balance.jsonl"
    row = {
        "ts": ts,
        "truth_label": oa.SELF_REPORT_TRUTH,
        "source": "owner_typed",
        "local_date": "2026-05-27",
        "physical_location": "desk",
        "physical_presence": "seated",
        "work_rhythm": "deep",
        "break_window_hours": 2,
        "sleep_target_hours": 7.5,
        "priority_ordering": ["alice", "dental", "tournament"],
        "body_maintenance_active": ["hydration"],
        "body_maintenance_deferred": ["dental"],
        "core_intent": "build alice",
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def test_self_report_stale_triggers_phrase(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    _seed_self_report(state, ts=_STALE_TS)
    with patch.object(oa.time, "time", return_value=_NOW):
        out = oa.format_owner_self_report_for_prompt(state_dir=state)
    assert "OWNER BODY SELF-REPORT:" in out
    assert "age_s=" in out
    assert "last snapshot" in out


def test_self_report_fresh_no_phrase(tmp_path: Path):
    state = tmp_path / ".sifta_state"
    _seed_self_report(state, ts=_FRESH_TS)
    with patch.object(oa.time, "time", return_value=_NOW):
        out = oa.format_owner_self_report_for_prompt(state_dir=state)
    assert "age_s=" in out
    assert "last snapshot" not in out


# ─── swarm_app_health: app_health_prompt_block ────────────────────────────


def test_app_health_prompt_block_age_tag_per_row(tmp_path: Path, monkeypatch):
    """Each trace row should carry an age_s= prefix. Stale rows should wrap."""
    rows = [
        {
            "ts": _STALE_TS,
            "action": "update",
            "skills": ["camera", "stigmergic"],
            "note": "old trace",
        },
        {
            "ts": _FRESH_TS,
            "action": "update",
            "skills": ["fresh_skill"],
            "note": "live trace",
        },
    ]
    monkeypatch.setattr(swarm_app_health, "get_app_health", lambda name, limit=5: rows)
    monkeypatch.setattr(swarm_app_health, "get_required_skills_for_app", lambda name: [])
    with patch.object(swarm_app_health.time, "time", return_value=_NOW):
        out = swarm_app_health.app_health_prompt_block("test_app")
    assert "APP HEALTH SECTION FOR test_app" in out
    # both rows should have age_s
    assert out.count("age_s=") == 2
    # stale row wraps, fresh row does not
    assert "last snapshot" in out
    # one stale wrap + at least one fresh skills line w/o "last snapshot"
    fresh_lines = [
        ln for ln in out.splitlines()
        if "fresh_skill" in ln
    ]
    assert fresh_lines
    assert all("last snapshot" not in ln for ln in fresh_lines)


# ─── swarm_owner_field_context: format_owner_field_for_prompt ─────────────


def test_owner_field_stale_presence_triggers_phrase(monkeypatch):
    """Stub owner_field_context to return a stale presence + boot + schedule
    bundle and verify the formatter surfaces 'last snapshot' wording."""
    fake_ctx = {
        "truth_label": "OWNER_UNIFIED_FIELD_CONTEXT_V1",
        "owner_rhythm": "deep_work",
        "evidence_count": 3,
        "readback_rule": "use receipts before answering",
        "presence": {
            "available": True,
            "last_alive_age_s": 5 * 86400,    # 5 days stale
            "last_alive_age_human": "5d ago",
            "last_boot_age_human": "5d ago",
            "last_gap_human": "0s",
        },
        "boot_receipt": {
            "available": True,
            "stigtime": "active(boot)",
            "trace_id": "abc-123",
            "age_human": "5d ago",
            "ts": _STALE_TS,
        },
        "schedule_anchor": {
            "available": True,
            "text": "deep work block",
            "age_human": "5d ago",
            "ts": _STALE_TS,
        },
    }
    monkeypatch.setattr(ofc, "owner_field_context", lambda **kw: fake_ctx)
    monkeypatch.setattr(ofc, "_row_ts", lambda row: row.get("ts") if isinstance(row, dict) else None)
    with patch.object(ofc.time, "time", return_value=_NOW):
        out = ofc.format_owner_field_for_prompt(now=_NOW)
    assert "OWNER UNIFIED FIELD READBACK:" in out
    assert "age_s=" in out
    # Three lines should each have "last snapshot" since all three sources are
    # 5 days stale.
    assert out.count("last snapshot") >= 3


def test_owner_field_fresh_presence_no_phrase(monkeypatch):
    fake_ctx = {
        "truth_label": "OWNER_UNIFIED_FIELD_CONTEXT_V1",
        "owner_rhythm": "deep_work",
        "evidence_count": 3,
        "readback_rule": "use receipts before answering",
        "presence": {
            "available": True,
            "last_alive_age_s": 60,
            "last_alive_age_human": "1m ago",
            "last_boot_age_human": "1m ago",
            "last_gap_human": "0s",
        },
        "boot_receipt": {
            "available": True,
            "stigtime": "active(boot)",
            "trace_id": "abc-123",
            "age_human": "1m ago",
            "ts": _FRESH_TS,
        },
        "schedule_anchor": {
            "available": True,
            "text": "deep work block",
            "age_human": "1m ago",
            "ts": _FRESH_TS,
        },
    }
    monkeypatch.setattr(ofc, "owner_field_context", lambda **kw: fake_ctx)
    monkeypatch.setattr(ofc, "_row_ts", lambda row: row.get("ts") if isinstance(row, dict) else None)
    with patch.object(ofc.time, "time", return_value=_NOW):
        out = ofc.format_owner_field_for_prompt(now=_NOW)
    assert "age_s=" in out
    assert "last snapshot" not in out


# ─── Real ledger isolation ─────────────────────────────────────────────────


def test_real_ledgers_untouched(tmp_path: Path):
    """Pure read modules — must not mutate any real .sifta_state file."""
    real = Path(".sifta_state")
    watched = [
        real / "owner_allostatic_balance.jsonl",
        real / "work_receipts.jsonl",
    ]
    before = {str(p): (p.stat().st_size if p.exists() else 0) for p in watched}

    state = tmp_path / ".sifta_state"
    _seed_allostasis_balance(state, ts=_FRESH_TS)
    with patch.object(oa.time, "time", return_value=_NOW):
        oa.format_owner_allostasis_for_prompt(state_dir=state)
        oa.format_owner_body_maintenance_for_prompt(state_dir=state)
        oa.format_dual_embodiment_loop_for_prompt(state_dir=state)
        oa.format_owner_self_report_for_prompt(state_dir=state)

    after = {str(p): (p.stat().st_size if p.exists() else 0) for p in watched}
    for k in before:
        assert before[k] == after[k], f"stale sweep mutated {k}"

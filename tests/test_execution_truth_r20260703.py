"""r-execution-truth-20260703 — execution truth over narrated success.

OBSERVED incident 2026-07-03 05:46: George typed 'search maisie williams photos,
the actress'; the body-stabilization replay stomped his fresh owner slot with a
recovery context, the effector gate refused the navigate
(recovery_context_no_effector, gate receipt d979d638), and the chat still said
"I searched the web using DuckDuckGo" because the observe leg rebuilt its
observation from the predicted URL instead of the field.

Two invariants under test:
1. bind_recovery_context must NOT stomp a fresh spendable owner slot (§0.0 —
   no blind gate on a direct Architect command).
2. run_explicit_search_body_loop must read the gate refusal from the field and
   reply with the refusal truth, never the claim (§6 — prove X or rewrite
   honestly).
"""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_effector_gate as gate
from System import swarm_search_provider_reality as spr


def _state(tmp_path: Path) -> Path:
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    return sd


# ── invariant 1: fresh owner slot survives recovery replay ──────────────────


def test_recovery_bind_does_not_stomp_fresh_owner_slot(tmp_path: Path):
    sd = _state(tmp_path)
    owner = gate.bind_owner_ingress(
        owner_text="search maisie williams photos, the actress",
        ingress_kind="typed",
        state_dir=sd,
    )
    assert owner["effector_spend_allowed"] is True

    rec = gate.bind_recovery_context(source="cortex_timeout_recovery", state_dir=sd)
    assert rec.get("deferred") is True
    assert rec.get("kept_active") == "owner_ingress"

    active = gate.read_active_context(state_dir=sd)
    assert active.get("effector_spend_allowed") is True
    assert not active.get("recovery_only")
    assert active.get("nonce") == owner["nonce"]

    rows = [
        json.loads(l)
        for l in (sd / gate.LEDGER_NAME).read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    assert any(r.get("action") == "recovery_bind_deferred_owner_slot_fresh" for r in rows)


def test_recovery_bind_takes_slot_when_no_fresh_owner_context(tmp_path: Path):
    sd = _state(tmp_path)
    rec = gate.bind_recovery_context(source="cortex_timeout_recovery", state_dir=sd)
    assert not rec.get("deferred")
    active = gate.read_active_context(state_dir=sd)
    assert active.get("recovery_only") is True
    assert active.get("effector_spend_allowed") is False


def test_recovery_bind_takes_slot_when_owner_context_is_stale(tmp_path: Path, monkeypatch):
    sd = _state(tmp_path)
    owner = gate.bind_owner_ingress(owner_text="old turn", ingress_kind="typed", state_dir=sd)
    # Age the active slot past the protection window.
    active = gate.read_active_context(state_dir=sd)
    active["bound_ts"] = active["bound_ts"] - (gate.FRESH_OWNER_SLOT_PROTECT_S + 60.0)
    (sd / gate.ACTIVE_NAME).write_text(json.dumps(active), encoding="utf-8")

    rec = gate.bind_recovery_context(state_dir=sd)
    assert not rec.get("deferred")
    assert gate.read_active_context(state_dir=sd).get("recovery_only") is True
    assert owner["nonce"]  # the old nonce existed but its slot aged out honestly


# ── invariant 2: the body loop reads the field refusal, never claims ────────


def test_read_recent_refusal_finds_browser_refusal(tmp_path: Path):
    sd = _state(tmp_path)
    gate.bind_recovery_context(state_dir=sd)
    refusal = gate.require_browser_effector("browser_navigate", state_dir=sd)
    assert refusal.get("ok") is False

    found = gate.read_recent_refusal(effector="browser", state_dir=sd)
    assert found.get("reason") == refusal.get("reason")
    assert found.get("receipt_id") == refusal.get("gate_receipt_id")


def test_search_body_loop_reports_refusal_instead_of_claiming(tmp_path: Path):
    sd = _state(tmp_path)
    gate.bind_recovery_context(state_dir=sd)

    def _blocked_execute() -> None:
        # Widget path: the navigate hits the gate and is refused; the loop must
        # see that refusal on the field, not swallow it.
        gate.require_browser_effector("browser_navigate", state_dir=sd)

    loop = spr.run_explicit_search_body_loop(
        owner_text="search maisie williams photos, the actress",
        query="maisie williams photos, the actress",
        execution_url="https://duckduckgo.com/?q=maisie+williams+photos",
        state_dir=sd,
        execute=_blocked_execute,
    )
    assert loop.get("execution_refused") is True
    reply = str(loop.get("reply") or "")
    assert "did NOT search" in reply
    assert "refused" in reply
    assert "I searched the web" not in reply
    assert loop.get("gate_receipt_id")

    ledger = sd / "search_provider_reality.jsonl"
    if ledger.exists():
        rows = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
        refused_rows = [r for r in rows if r.get("execution_refused")]
        assert refused_rows and refused_rows[-1].get("claim_suppressed") is True


def test_search_body_loop_still_claims_honestly_when_not_refused(tmp_path: Path):
    sd = _state(tmp_path)
    gate.bind_owner_ingress(owner_text="search cats", ingress_kind="typed", state_dir=sd)

    loop = spr.run_explicit_search_body_loop(
        owner_text="search cats",
        query="cats",
        execution_url="https://duckduckgo.com/?q=cats",
        state_dir=sd,
        execute=lambda: None,
    )
    assert loop.get("execution_refused") is False
    assert "I searched the web using" in str(loop.get("reply") or "")

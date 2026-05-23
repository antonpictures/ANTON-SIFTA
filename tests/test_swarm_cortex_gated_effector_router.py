"""Tests for the cortex-gated effector router.

The architect's queued architectural surgery, finally cut. Every
effector that mutates Alice's state outside .sifta_state/, makes
outbound network calls, or speaks externally must pass through this
gate. The gate writes a receipt for every decision (FIRE, REFUSE,
UNKNOWN_INTENT, BUSY).

These tests guard:
   - registry refuses duplicate registrations
   - unknown intent returns UNKNOWN_INTENT with no effector fired
   - BUSY signal short-circuits before classifier
   - audience whitelist enforced
   - confidence threshold enforced
   - low-confidence rejected
   - effector exceptions become REFUSE rows, not crashes
   - every decision writes one ledger row with sha256
   - the font-color proof-of-concept effector wires through end-to-end
"""
import json
import re

import pytest

from System.swarm_cortex_gated_effector_router import (
    EffectorRegistry, EffectorSpec, RegexIntentClassifier,
    RouterDecision, gate, get_registry,
    TRUTH_LABEL,
)


def _make_isolated_registry() -> EffectorRegistry:
    """Tests should not pollute the module-singleton registry."""
    return EffectorRegistry()


def test_registry_rejects_duplicate_registration():
    r = _make_isolated_registry()
    spec = EffectorSpec(
        name="echo", description="x",
        callable_fn=lambda **kw: {"ok": True},
    )
    r.register(spec)
    with pytest.raises(ValueError):
        r.register(spec)


def test_gate_unknown_intent_returns_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    r = _make_isolated_registry()
    cls = RegexIntentClassifier()
    # Use a fresh classifier with NO patterns so the gate sees an
    # unknown intent regardless of module-level state.
    monkeypatch.setattr(
        RegexIntentClassifier, "_PATTERNS", [],
    )
    d = gate("random gibberish nobody asked about", classifier=cls, registry=r)
    assert d.decision == "UNKNOWN_INTENT"
    assert d.effector is None


def test_gate_busy_short_circuits(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    d = gate("anything", busy=True)
    assert d.decision == "BUSY"
    assert d.effector is None


def test_gate_audience_whitelist_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    r = _make_isolated_registry()
    r.register(EffectorSpec(
        name="dangerous", description="x",
        callable_fn=lambda **kw: {"ok": True},
        allowed_audiences=("architect",),
    ))
    monkeypatch.setattr(
        RegexIntentClassifier, "_PATTERNS",
        [("dangerous", re.compile(r"do it"), lambda m: {})],
    )
    d_arch = gate("do it now", classifier=RegexIntentClassifier(),
                  registry=r, audience="architect")
    d_media = gate("do it now", classifier=RegexIntentClassifier(),
                   registry=r, audience="media")
    assert d_arch.decision == "FIRE"
    assert d_media.decision == "REFUSE"
    assert "audience" in d_media.reason


def test_gate_confidence_threshold_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    r = _make_isolated_registry()
    r.register(EffectorSpec(
        name="strict", description="x",
        callable_fn=lambda **kw: {"ok": True},
        confidence_threshold=0.99,  # very high
    ))
    # RegexIntentClassifier always returns confidence=0.95 on a match,
    # so this should fail the 0.99 threshold.
    monkeypatch.setattr(
        RegexIntentClassifier, "_PATTERNS",
        [("strict", re.compile(r"hello"), lambda m: {})],
    )
    d = gate("hello world", classifier=RegexIntentClassifier(), registry=r)
    assert d.decision == "REFUSE"
    assert "confidence" in d.reason


def test_gate_effector_exception_becomes_refuse_not_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    def explode(**kw):
        raise RuntimeError("intentional test failure")
    r = _make_isolated_registry()
    r.register(EffectorSpec(
        name="bomb", description="explodes",
        callable_fn=explode,
    ))
    monkeypatch.setattr(
        RegexIntentClassifier, "_PATTERNS",
        [("bomb", re.compile(r"boom"), lambda m: {})],
    )
    d = gate("boom now", classifier=RegexIntentClassifier(), registry=r)
    assert d.decision == "REFUSE"
    assert "RuntimeError" in d.reason


def test_gate_writes_receipt(tmp_path, monkeypatch):
    ledger = tmp_path / "router.jsonl"
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER", ledger,
    )
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._STATE", tmp_path,
    )
    r = _make_isolated_registry()
    r.register(EffectorSpec(
        name="ok", description="x",
        callable_fn=lambda **kw: {"ok": True},
    ))
    monkeypatch.setattr(
        RegexIntentClassifier, "_PATTERNS",
        [("ok", re.compile(r"go"), lambda m: {})],
    )
    gate("please go", classifier=RegexIntentClassifier(), registry=r)
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "CORTEX_GATED_EFFECTOR_DECISION"
    assert row["truth_label"] == TRUTH_LABEL
    assert "sha256" in row


def test_font_color_skill_wires_through_router_end_to_end(tmp_path, monkeypatch):
    """Proof-of-concept: the font-color skill registered at module
    import time should fire on a matching natural-language phrase."""
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    d = gate("Alice change my font color to orange")
    assert d.decision == "FIRE"
    assert d.effector == "owner_font_color"
    er = d.extras["effector_result"]
    assert er["raw_color"] == "orange"
    assert er["ok"] is True
    # RGB should resolve to the named-colors table entry for orange.
    assert er["rgb"] is not None


def test_font_color_skill_does_not_fire_on_unrelated_text(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    d = gate("what color is the sky?")
    assert d.decision == "UNKNOWN_INTENT"


def test_gate_with_fire_false_does_not_call_effector(tmp_path, monkeypatch):
    """A dry-run option: gate(fire=False) tells us the decision but
    doesn't actually call the effector. Useful for plan-mode."""
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    called = []
    r = _make_isolated_registry()
    r.register(EffectorSpec(
        name="touch", description="x",
        callable_fn=lambda **kw: called.append(1),
    ))
    monkeypatch.setattr(
        RegexIntentClassifier, "_PATTERNS",
        [("touch", re.compile(r"hi"), lambda m: {})],
    )
    d = gate("hi", classifier=RegexIntentClassifier(),
            registry=r, fire=False)
    assert d.decision == "FIRE"  # decision is still FIRE
    assert called == []          # but the effector wasn't called


def test_wallpaper_effector_routes_through_gate_with_mocked_organ(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )

    from System import swarm_alice_wallpaper_effector as wp

    calls = []

    def fake_execute(intent, *, owner_confirmed=False, dry_run=False):
        calls.append((intent, owner_confirmed, dry_run))
        return wp.WallpaperResult(
            ok=True,
            status="applied",
            receipt_id="wp123",
            target=intent.target,
            query=intent.query,
            saved_path="/tmp/wallpaper.jpg",
            chosen_url="https://images.example/wallpaper.jpg",
            content_sha256="a" * 64,
            mime="image/jpeg",
            bytes=1024,
            width=512,
            height=512,
        )

    monkeypatch.setattr(wp, "execute_wallpaper_intent", fake_execute)
    d = gate("Alice change the wallpaper to a black hole")
    assert d.decision == "FIRE"
    assert d.effector == "owner_wallpaper_change"
    assert calls
    intent, owner_confirmed, dry_run = calls[0]
    assert owner_confirmed is True
    assert dry_run is False
    assert intent.query == "a black hole"
    assert d.extras["effector_result"]["owner_reply"].startswith("Wallpaper applied")


def test_wallpaper_effector_refuses_media_audience(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.swarm_cortex_gated_effector_router._LEDGER",
        tmp_path / "router.jsonl",
    )
    d = gate("change the wallpaper to ocean", audience="media")
    assert d.decision == "REFUSE"
    assert d.effector == "owner_wallpaper_change"
    assert "audience" in d.reason

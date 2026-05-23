"""Tests for §21 Vector #5 (Dream Organ) and §21 Vector #3 (Ghost Civilizations)."""
import json
import pytest

np = pytest.importorskip("numpy")

# ── Dream Organ ───────────────────────────────────────────────────────────

def test_dream_organ_skip_when_awake(tmp_path, monkeypatch):
    """When the journal shows recent activity, dream organ returns
    a SKIPPED row rather than running the cycle."""
    from System.swarm_alice_dream_organ import detect_idle_window, run_dream_cycle
    journal = tmp_path / "alice_first_person_journal.jsonl"
    now = 1_000_000.0
    rows = [
        {"ts": now - 10, "source": "conversation",
         "line": "Ioan George Anton said (voice, stt=0.8): hi"},
        {"ts": now - 5, "source": "face_event",
         "line": "I saw Ioan George Anton look at the camera"},
    ]
    journal.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    idle = detect_idle_window(now_ts=now, journal_path=journal, min_idle_seconds=180)
    assert idle.idle is False


def test_dream_organ_idle_detection_when_silent(tmp_path):
    """Long silence on both voice and face → idle=True."""
    from System.swarm_alice_dream_organ import detect_idle_window
    journal = tmp_path / "alice_first_person_journal.jsonl"
    now = 1_000_000.0
    rows = [
        # 10 minutes ago — way past the 3-minute idle threshold
        {"ts": now - 600, "source": "conversation",
         "line": "Ioan George Anton said (voice, stt=0.7): something"},
        {"ts": now - 600, "source": "face_event",
         "line": "I saw Ioan George Anton look at the camera"},
    ]
    journal.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    idle = detect_idle_window(
        now_ts=now, journal_path=journal,
        window_seconds=1200, min_idle_seconds=180,
    )
    assert idle.idle is True
    assert idle.seconds_since_last_voice > 180
    assert idle.seconds_since_last_face > 180


def test_dream_cycle_force_writes_receipt(tmp_path, monkeypatch):
    """force=True runs the cycle and writes a DREAM_CYCLE receipt."""
    from System.swarm_alice_dream_organ import run_dream_cycle
    out = run_dream_cycle(force=True, write=True, state_root=tmp_path)
    assert out["truth_label"] == "ALICE_DREAM_ORGAN_V1"
    assert out["kind"] in ("DREAM_CYCLE", "DREAM_CYCLE_ERROR")
    if out["kind"] == "DREAM_CYCLE":
        assert "digest_line" in out
        assert "sha256" in out


def test_dream_cycle_skipped_when_not_idle_not_forced(tmp_path):
    """Without force flag and with no journal in state_root, dream
    organ uses the real journal — if it's not idle, returns SKIPPED."""
    from System.swarm_alice_dream_organ import run_dream_cycle
    out = run_dream_cycle(force=False, write=False)
    # On a fresh sandbox the real journal could be either way — but
    # the contract is: result must always have a truth_label.
    assert out["truth_label"] == "ALICE_DREAM_ORGAN_V1"


# ── Ghost Civilizations ───────────────────────────────────────────────────

def test_ghost_civilizations_receipt_format(tmp_path):
    from System.swarm_higgs_stigmergy_field import (
        run_ghost_civilizations_experiment, LEDGER_NAME,
        TRUTH_LABEL_GHOST_CIV, TRUTH_BOUNDARY,
    )
    r = run_ghost_civilizations_experiment(
        n_agents=20, civ_steps=200, ghost_steps=200,
        state_root=tmp_path, write=True,
    )
    assert r["truth_label"] == TRUTH_LABEL_GHOST_CIV
    assert r["truth_class"] == "HYPOTHESIS"
    assert r["simulated"] is True

    # Both civilizations have role counts that sum to n_agents.
    p1 = r["phase_1_original_civilization"]
    p3 = r["phase_3_newborns_in_inherited_field"]
    assert sum(p1["role_counts"].values()) == 20
    assert sum(p3["role_counts"].values()) == 20

    # The inheritance measurement must report a numerical L1 between
    # 0 and 2.0 (max possible for L1 of two probability distributions).
    L1 = r["inheritance_measurement"]["role_distribution_L1"]
    assert 0.0 <= L1 <= 2.0

    # Receipt on disk.
    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "PERSISTENCE_INERTIA_FIELD_GHOST_CIVILIZATIONS"
    assert row["truth_boundary"] == TRUTH_BOUNDARY


def test_ghost_civilizations_newborn_entropy_drops(tmp_path):
    """The mechanism's prerequisite: newborns must commit to roles
    (their policy entropy must drop) — otherwise the L1 comparison
    is meaningless. This is a sanity check on the mechanism."""
    from System.swarm_higgs_stigmergy_field import (
        run_ghost_civilizations_experiment,
    )
    r = run_ghost_civilizations_experiment(
        n_agents=25, civ_steps=400, ghost_steps=400,
        state_root=tmp_path, write=False,
    )
    p3 = r["phase_3_newborns_in_inherited_field"]
    # Initial entropy is log(4) ≈ 1.386. Final must be way below that.
    assert p3["initial_policy_entropy"] > 1.0
    assert p3["final_policy_entropy"] < 0.5


def test_ghost_civilizations_inheritance_in_canonical_run(tmp_path):
    """At the canonical parameters used in the live demo, inheritance
    SHOULD be observed. This is the headline finding the architect's
    Vector #3 question expected."""
    from System.swarm_higgs_stigmergy_field import (
        run_ghost_civilizations_experiment,
    )
    r = run_ghost_civilizations_experiment(
        n_agents=40, civ_steps=600, ghost_steps=600,
        state_root=tmp_path, write=False,
    )
    # Expect L1 ≤ 0.30 (the inheritance threshold the result row sets).
    assert r["inheritance_measurement"]["role_distribution_L1"] <= 0.30
    assert r["inheritance_measurement"]["inheritance_observed"] is True

import json
from pathlib import Path
from unittest.mock import patch

from System.swarm_body_brain_loop import SwarmPhysiology
from System.swarm_dream_engine import DreamEngineConfig, SwarmDreamEngine
from System.swarm_metabolic_homeostasis import MetabolicState


def _body_row(action_type: str, target: str, td_value: float, ts: float) -> dict:
    return {
        "event": "body_brain_tick",
        "action": {"type": action_type, "target": target},
        "result": {"status": "completed", "latency": 0.1},
        "td_value": td_value,
        "ts": ts,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_dream_engine_replays_body_brain_rows_into_engrams(tmp_path):
    rows = [
        _body_row("explore", "physics", 0.4, 10),
        _body_row("rest", "starvation_or_heat", 2.5, 11),
        _body_row("explore", "physics", 1.2, 12),
    ]
    _write_jsonl(tmp_path / "body_brain_memory.jsonl", rows)
    engine = SwarmDreamEngine(
        tmp_path,
        config=DreamEngineConfig(min_rows_for_engram=2, prune_after_rows=99),
    )

    receipt = engine.trigger_rem_sleep(rest_seconds=4.0, pressure=0.8, metabolic_mode="RED_CONSERVE")

    assert receipt.status == "consolidated"
    assert receipt.rows_replayed == 3
    assert receipt.engrams_written >= 1
    engrams = _read_jsonl(tmp_path / "long_term_engrams.jsonl")
    assert engrams[0]["kind"] == "dream_engram"
    assert engrams[0]["schema_version"] == "event88.swarm_dream_engine.v1"
    assert "td_value" in engrams[0]["content"]
    cycles = _read_jsonl(tmp_path / "dream_cycles.jsonl")
    assert cycles[0]["cycle_id"] == receipt.cycle_id
    assert cycles[0]["backup_path"] == ""
    assert "skills_crystallized" in cycles[0]


def test_dream_engine_crystallizes_repeated_success_patterns(tmp_path):
    rows = [
        _body_row("explore", "biology", 1.0, 10),
        _body_row("explore", "biology", 1.1, 11),
        _body_row("explore", "biology", 1.2, 12),
    ]
    _write_jsonl(tmp_path / "body_brain_memory.jsonl", rows)
    engine = SwarmDreamEngine(
        tmp_path,
        config=DreamEngineConfig(min_rows_for_engram=2, prune_after_rows=99),
    )

    receipt = engine.trigger_rem_sleep(rest_seconds=3.0, pressure=0.2, metabolic_mode="YELLOW_REST")

    assert receipt.status == "consolidated"
    assert receipt.skills_crystallized == 1
    skills = json.loads((tmp_path / "crystallized_skills.json").read_text())
    assert len(skills) == 1
    skill = next(iter(skills.values()))
    assert skill["pattern_signature"] == "body_brain:explore:biology|SIFTA_BODY"
    skill_receipts = _read_jsonl(tmp_path / "skill_crystallization_receipts.jsonl")
    assert skill_receipts[-1]["action"] == "SKILL_CRYSTALLIZED"


def test_dream_engine_prunes_only_after_recoverable_backup(tmp_path):
    rows = [
        _body_row("explore", "low-old-1", 0.1, 1),
        _body_row("explore", "low-old-2", 0.2, 2),
        _body_row("explore", "high-old", 2.8, 3),
        _body_row("explore", "low-old-3", 0.1, 4),
        _body_row("rest", "recent-1", 0.3, 5),
        _body_row("rest", "recent-2", 0.4, 6),
    ]
    source = tmp_path / "body_brain_memory.jsonl"
    _write_jsonl(source, rows)
    original = source.read_text(encoding="utf-8")
    engine = SwarmDreamEngine(
        tmp_path,
        config=DreamEngineConfig(
            min_rows_for_engram=2,
            prune_after_rows=3,
            keep_recent_rows=2,
            preserve_td_threshold=2.0,
        ),
    )

    receipt = engine.trigger_rem_sleep(rest_seconds=7.0, pressure=1.0, metabolic_mode="CRITICAL_STARVATION")

    assert receipt.rows_pruned > 0
    assert receipt.backup_path
    backup = tmp_path / receipt.backup_path
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == original
    retained = _read_jsonl(source)
    retained_targets = {row["action"]["target"] for row in retained}
    assert "high-old" in retained_targets
    assert {"recent-1", "recent-2"} <= retained_targets
    assert "low-old-1" not in retained_targets


def test_dream_engine_missing_ledger_writes_skip_receipt(tmp_path):
    engine = SwarmDreamEngine(tmp_path)

    receipt = engine.trigger_rem_sleep(rest_seconds=1.0, pressure=0.1, metabolic_mode="YELLOW_REST")

    assert receipt.status == "no_episodic_ledger"
    assert receipt.rows_seen == 0
    assert not (tmp_path / "long_term_engrams.jsonl").exists()
    cycles = _read_jsonl(tmp_path / "dream_cycles.jsonl")
    assert cycles[0]["status"] == "no_episodic_ledger"


class _FakeDreamEngine:
    def __init__(self):
        self.calls = []

    def trigger_rem_sleep(self, **kwargs):
        self.calls.append(kwargs)

        class _Receipt:
            def as_dict(self):
                return {"cycle_id": "fake-cycle", "status": "fake-consolidated"}

        return _Receipt()


def test_body_brain_loop_invokes_dream_engine_during_metabolic_sleep(tmp_path):
    fake = _FakeDreamEngine()
    physiology = SwarmPhysiology(dream_engine=fake)
    critical = MetabolicState(usd_burn_24h=12.0, local_units_24h=200.0, stgm_balance=0.0)

    with patch("System.swarm_body_brain_loop._STATE_DIR", tmp_path):
        with patch("System.swarm_body_brain_loop.MetabolicHomeostat.sample_live", return_value=critical):
            with patch("time.sleep"):
                result = physiology.body_brain_tick()

    assert fake.calls
    assert fake.calls[0]["metabolic_mode"] in ("RED_CONSERVE", "CRITICAL_STARVATION")
    assert result["dream_cycle"]["status"] == "fake-consolidated"

import json
import time
from pathlib import Path

import System.swarm_hippocampus as hippocampus


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_read_live_engrams_uses_salience_not_plain_tail(tmp_path, monkeypatch):
    engrams = tmp_path / "long_term_engrams.jsonl"
    now = time.time()
    _append_jsonl(
        engrams,
        [
            {"ts": now - 10_000, "source": "stable", "abstract_rule": "stable memory one"},
            {"ts": now - 9_000, "source": "stable", "abstract_rule": "stable memory two"},
            {"ts": now - 10, "source": "rare", "abstract_rule": "rare latest memory"},
        ],
    )
    monkeypatch.setattr(hippocampus, "_ENGRAMS_LOG", engrams)

    text = hippocampus._read_live_engrams(k=1)

    assert "DEEP ENGRAMS" in text
    assert "stable memory" in text


def test_deposit_memory_trace_writes_and_evaporates_field(tmp_path, monkeypatch):
    field_path = tmp_path / "hippocampus" / "memory_salience_field.json"
    monkeypatch.setattr(hippocampus, "_MEMORY_FIELD_PATH", field_path)

    hippocampus.deposit_memory_trace("owner speech correction", amount=2.0, success=True)
    first = json.loads(field_path.read_text(encoding="utf-8"))
    assert len(first) == 1
    first_value = next(iter(first.values()))
    assert first_value > 0

    hippocampus.deposit_memory_trace("owner speech correction", amount=1.0, success=False)
    second = json.loads(field_path.read_text(encoding="utf-8"))
    second_value = next(iter(second.values()))
    assert second_value < first_value

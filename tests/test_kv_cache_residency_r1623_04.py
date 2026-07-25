"""r1623-04 phase 2 — KV-cache residency + lag stamps (George 2026-07-20).

The main Talk cortex must not evaporate 15 seconds after every reply, and
every turn must stamp what it cost (reload, re-ingest, prefix stability)
to .sifta_state/kv_cache_continuity.jsonl.
"""

import importlib.util
import inspect
import json
from pathlib import Path


def _load_widget_module():
    here = Path(__file__).resolve().parent.parent
    path = here / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _organ():
    from System import swarm_kv_cache_continuity as kv
    return kv


def test_keep_alive_bands_are_governed(tmp_path):
    kv = _organ()
    state = tmp_path / ".sifta_state"
    state.mkdir()
    homeo = state / "metabolic_homeostasis.jsonl"
    homeo.write_text(json.dumps({"mode": "GREEN_GROW", "pressure": 0.0}) + "\n")
    assert kv.keep_alive_for_talk(state_dir=tmp_path) == kv.KEEP_ALIVE_GREEN
    homeo.write_text(json.dumps({"mode": "RED_CONSERVE", "pressure": 0.9, "must_rest": True}) + "\n")
    assert kv.keep_alive_for_talk(state_dir=tmp_path) == kv.KEEP_ALIVE_DISTRESS
    homeo.write_text(json.dumps({"mode": "YELLOW_HOLD", "pressure": 0.4}) + "\n")
    assert kv.keep_alive_for_talk(state_dir=tmp_path) == kv.KEEP_ALIVE_NEUTRAL
    # No homeostasis ledger at all → neutral, never a crash.
    empty = tmp_path / "empty_node"
    empty.mkdir()
    assert kv.keep_alive_for_talk(state_dir=empty) == kv.KEEP_ALIVE_NEUTRAL


def test_turn_stamp_measures_reload_and_prefix_stability(tmp_path):
    kv = _organ()
    messages = [
        {"role": "system", "content": "STABLE SPINE. " * 100 + "volatile tail A"},
        {"role": "user", "content": "hello"},
    ]
    done = {
        "done": True,
        "load_duration": int(4.2e9),          # 4.2 s — a real cold reload
        "prompt_eval_count": 9000,
        "prompt_eval_duration": int(6.0e9),
        "eval_count": 120,
        "eval_duration": int(3.0e9),
    }
    row1 = kv.record_turn_stamp(
        model="alice-test", messages=messages, done_chunk=done, state_dir=tmp_path,
    )
    assert row1["cold_load"] is True
    assert row1["load_ms"] == 4200.0
    assert row1["prompt_eval_count"] == 9000
    assert row1["gen_tps"] == 40.0
    assert row1["system_prefix_stability"] == 0.0  # first turn, no previous

    # Second turn: same stable spine, different volatile tail → high stability.
    messages2 = [
        {"role": "system", "content": "STABLE SPINE. " * 100 + "volatile tail B"},
        {"role": "user", "content": "again"},
    ]
    warm = dict(done, load_duration=int(0.02e9))
    row2 = kv.record_turn_stamp(
        model="alice-test", messages=messages2, done_chunk=warm, state_dir=tmp_path,
    )
    assert row2["cold_load"] is False
    assert row2["system_prefix_common_chars"] >= len("STABLE SPINE. ") * 100
    assert row2["system_prefix_stability"] > 0.9

    ledger = tmp_path / ".sifta_state" / "kv_cache_continuity.jsonl"
    rows = [json.loads(l) for l in ledger.read_text().splitlines()]
    assert len(rows) == 2
    assert all(r["truth_label"] == kv.RESIDENCY_TRUTH_LABEL for r in rows)

    report = kv.continuity_report(state_dir=tmp_path)
    assert report["rows"] == 2
    assert report["cold_load_rate"] == 0.5


def test_widget_keep_alive_env_wins_and_lanes_keep_explicit_defaults(monkeypatch):
    mod = _load_widget_module()
    monkeypatch.setenv("SIFTA_OLLAMA_KEEP_ALIVE", "45s")
    assert mod._ollama_keep_alive() == "45s"
    assert mod._ollama_keep_alive("15s") == "45s"  # env outranks lanes too
    monkeypatch.delenv("SIFTA_OLLAMA_KEEP_ALIVE")
    # Explicit reflex/vision lanes keep their tuned 15s.
    assert mod._ollama_keep_alive("15s") == "15s"
    # Main cortex lane (no-arg) is metabolism-governed — one of the organ bands.
    from System import swarm_kv_cache_continuity as kv
    governed = mod._ollama_keep_alive()
    assert governed in {kv.KEEP_ALIVE_GREEN, kv.KEEP_ALIVE_NEUTRAL, kv.KEEP_ALIVE_DISTRESS, "10m"}
    assert governed != "15s"


def test_done_chunk_hook_is_wired_in_stream_loop():
    here = Path(__file__).resolve().parent.parent
    src = (here / "Applications" / "sifta_talk_to_alice_widget.py").read_text()
    hook = src.index("record_turn_stamp")
    done = src.index('if chunk.get("done"):')
    assert abs(hook - done) < 2000  # the stamp lives inside the done branch


def test_rehydrate_half_of_organ_still_intact():
    kv = _organ()
    snap = kv.rehydrate_mind_snapshot()
    assert snap["truth_label"] == kv.TRUTH_LABEL
    assert snap["mode"] == "ledger_rehydrate_not_gpu_kv"
    block = kv.continuity_prompt_block()
    assert "MIND CONTINUITY" in block

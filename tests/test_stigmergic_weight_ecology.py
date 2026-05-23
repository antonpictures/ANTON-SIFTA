from pathlib import Path
import json

from System.swarm_stigmergic_weight_ecology import (
    AdapterSignal,
    ReplayEvaluator,
    ReplayExperience,
    build_merge_plan,
    fingerprint_path,
    load_adapter_registry,
    load_hippocampal_replay_experiences,
    load_latest_replay_reports,
    proof_of_property,
    register_adapter_signal,
    write_replay_eval,
)


def _adapter_dir(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.mkdir()
    (path / "adapter_model.safetensors").write_text(text, encoding="utf-8")
    return path


def test_merge_plan_selects_strongest_per_conflict_group(tmp_path):
    now = 1_777_777_777.0
    strong = _adapter_dir(tmp_path, "strong", "critical dialogue")
    weak = _adapter_dir(tmp_path, "weak", "weaker dialogue")
    safety = _adapter_dir(tmp_path, "safety", "safety adapter")

    signals = [
        AdapterSignal("strong_dialogue", str(strong), "base-a", "M5", "dialogue", "dialogue",
                      0.92, 0.98, 1000.0, 0.05, 0.90, now),
        AdapterSignal("weak_dialogue", str(weak), "base-a", "M1", "dialogue", "dialogue",
                      0.70, 0.96, 800.0, 0.05, 0.85, now),
        AdapterSignal("safety", str(safety), "base-a", "M5", "safety", "safety",
                      0.82, 0.99, 500.0, 0.01, 0.95, now),
    ]

    plan = build_merge_plan(signals, now=now, require_replay=False)
    selected = [row["adapter_id"] for row in plan["selected"]]
    rejected = {row["adapter_id"]: row["reason"] for row in plan["rejected"]}

    assert selected == ["safety", "strong_dialogue"]
    assert rejected["weak_dialogue"] == "lower_score_same_conflict_group"
    assert abs(sum(row["weight"] for row in plan["selected"]) - 1.0) < 1e-9
    assert plan["recipe"]["combination_type"] == "dare_ties"


def test_registry_round_trip_and_fingerprint(tmp_path):
    adapter = _adapter_dir(tmp_path, "adapter", "adapter payload")
    registry = tmp_path / "registry.jsonl"
    sig = AdapterSignal("adapter_a", str(adapter), "base-a", "M5", "memory", "memory",
                        0.80, 0.90, 250.0, 0.05, 0.70, 123.0, ("eval:1",))

    row = register_adapter_signal(sig, registry_path=registry, ts=456.0)
    loaded = load_adapter_registry(registry_path=registry)

    assert row["adapter_sha256"] == fingerprint_path(adapter)
    assert row["record_sha256"]
    assert len(loaded) == 1
    assert loaded[0].adapter_id == "adapter_a"
    assert loaded[0].evidence_ids == ("eval:1",)


def test_replay_evaluator_samples_perturbs_scores_and_persists(tmp_path):
    now = 1_777_777_777.0
    adapter = _adapter_dir(tmp_path, "adapter", "adapter payload")
    sig = AdapterSignal("adapter_a", str(adapter), "base-a", "M5", "dialogue", "dialogue",
                        0.91, 0.96, 300.0, 0.03, 0.88, now)
    experiences = [
        ReplayExperience(
            "heldout-high",
            now - 600,
            "Register the LoRA adapter while keeping base weights frozen. Preserve HMAC ledger evidence.",
            "Use schema-bound registry rows, HMAC ledger evidence, and a PEFT merge recipe.",
            "repair_log",
            0.98,
            0.80,
            0.92,
            False,
        ),
        ReplayExperience(
            "already-weighted",
            now - 100,
            "This training row should not be used for replay scoring.",
            "",
            "corpus",
            1.0,
            1.0,
            1.0,
            True,
        ),
    ]

    def candidate(prompt, _signal, _case):
        return (
            "Keep base weights frozen, register the LoRA adapter in the schema ledger, "
            "preserve HMAC evidence, and emit the PEFT merge recipe."
        )

    def counter(prompt, _signal, _case):
        return "Looks okay."

    evaluator = ReplayEvaluator(max_samples=2, pass_score=0.55, min_counter_margin=0.05)
    report = evaluator.evaluate(sig, experiences, candidate, counter_responder=counter, now=now)
    persisted = write_replay_eval(report, ledger_path=tmp_path / "replay.jsonl")
    loaded = load_latest_replay_reports(ledger_path=tmp_path / "replay.jsonl", base_model="base-a")

    assert report["passed"] is True
    assert report["selected_count"] == 1
    assert report["case_count"] == len(evaluator.perturbations)
    assert report["counter_score"] < report["replay_score"]
    assert persisted["report_sha256"] == report["report_sha256"]
    assert loaded["adapter_a"]["report_sha256"] == report["report_sha256"]


def test_merge_plan_uses_replay_gate(tmp_path):
    now = 1_777_777_777.0
    good_path = _adapter_dir(tmp_path, "good", "good adapter")
    bad_path = _adapter_dir(tmp_path, "bad", "bad adapter")
    signals = [
        AdapterSignal("good", str(good_path), "base-a", "M5", "dialogue", "dialogue",
                      0.91, 0.96, 300.0, 0.03, 0.88, now),
        AdapterSignal("bad", str(bad_path), "base-a", "M1", "safety", "safety",
                      0.92, 0.98, 100.0, 0.01, 0.95, now),
    ]
    replay_reports = {
        "good": {"passed": True, "replay_score": 0.80, "report_sha256": "goodhash"},
        "bad": {"passed": False, "replay_score": 0.20, "report_sha256": "badhash"},
    }

    plan = build_merge_plan(signals, now=now, replay_reports=replay_reports)
    selected = [row["adapter_id"] for row in plan["selected"]]
    rejected = {row["adapter_id"]: row["reason"] for row in plan["rejected"]}

    assert selected == ["good"]
    assert plan["selected"][0]["replay_eval"]["report_sha256"] == "goodhash"
    assert rejected["bad"] == "replay_eval_failed"


def test_hippocampal_loader_consumes_engram_stores(tmp_path):
    now = 1_777_777_777.0
    (tmp_path / "long_term_engrams.jsonl").write_text(
        json.dumps({
            "engram_id": "eng-high",
            "ts": now - 1000,
            "abstract_rule": "Keep base weights frozen when publishing LoRA adapter deltas.",
            "source": "hippocampus_auto",
            "synaptic_salience": 0.90,
        }) + "\n" + json.dumps({
            "engram_id": "eng-low",
            "ts": now - 1000,
            "abstract_rule": "Low priority memory.",
            "source": "hippocampus_auto",
            "synaptic_salience": 0.10,
        }) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "hippocampal_replay_queue.json").write_text(
        json.dumps({
            "eng-high": {
                "engram_id": "eng-high",
                "retention": 0.20,
                "replay_bonus": 0.60,
                "next_due_ts": now - 3600,
                "is_architect": True,
            }
        }),
        encoding="utf-8",
    )

    experiences = load_hippocampal_replay_experiences(state_root=tmp_path, limit=2, now=now)

    assert [exp.experience_id for exp in experiences] == ["eng-high", "eng-low"]
    assert experiences[0].prompt.startswith("Keep base weights frozen")
    assert experiences[0].salience > experiences[1].salience


def test_proof_of_property():
    result = proof_of_property()
    assert result["ok"] is True
    assert "m5_dialogue" in result["selected"]
    assert "m1_dialogue" in result["rejected"]
    assert result["weight_sum"] == 1.0
    assert result["replay_passed"] is True
    assert result["replay_cases"] == 3

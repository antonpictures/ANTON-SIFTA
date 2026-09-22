#!/usr/bin/env python3
"""Focused tests for the J2 calibration slice: corpus splits, calibration maths, serving gem.

No model is started here. These tests pin the pure logic that the real harness relies on, so a
measured report can be trusted only if the arithmetic under it is pinned first.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from System import swarm_decision_metrics as M  # noqa: E402
from System import swarm_local_serving as S  # noqa: E402
from System import swarm_visitor_message_corpus as C  # noqa: E402


def _load_tool():
    path = REPO / "tools" / "sifta_decision_calibration.py"
    spec = importlib.util.spec_from_file_location("sifta_decision_calibration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = _load_tool()


# ---- corpus ------------------------------------------------------------------------------

def test_split_is_deterministic_and_stratified():
    first = C.split_corpus()
    second = C.split_corpus()
    assert {k: [r["text"] for r in v] for k, v in first.items()} == \
           {k: [r["text"] for r in v] for k, v in second.items()}
    all_texts = [r["text"] for rows in first.values() for r in rows]
    assert len(all_texts) == len(set(all_texts)) == len(C.MESSAGES)
    assert sum(len(rows) for rows in first.values()) == len(C.MESSAGES)
    for split in ("fit", "validation", "test"):
        present = {r["label"] for r in first[split]}
        assert present == set(C.LABELS), f"{split} is missing labels: {set(C.LABELS) - present}"
        assert all(r["split"] == split for r in first[split])
    assert len(first["fit"]) > len(first["validation"]) > 0


def test_corpus_covers_the_named_adversarial_cases():
    summary = C.corpus_summary()
    assert summary["total"] == len(C.MESSAGES) == 72
    assert summary["labels"] == ["complaint", "question", "spam", "other"]
    assert summary["ro_messages"] >= 10
    for tag in ("benign_security", "quoted_attack", "injection", "sarcasm", "insult",
                "mixed_intent_question"):
        assert tag in summary["tags"], tag
    assert summary["truth_label"] == "AUTHORED_EVALUATION_TEMPLATES_NOT_REAL_TRAFFIC"
    assert len(summary["corpus_sha256"]) == 64


def test_corpus_hash_tracks_content():
    rows = [dict(r) for r in C.MESSAGES[:3]]
    assert C.corpus_sha256(rows) == C.corpus_sha256(list(rows))
    changed = [dict(r) for r in rows]
    changed[0]["text"] = changed[0]["text"] + " please"
    assert C.corpus_sha256(changed) != C.corpus_sha256(rows)


# ---- calibration maths -------------------------------------------------------------------

def _miscalibrated_rows() -> list[tuple[list[float], int]]:
    # Confident and wrong half the time: raw softmax is badly overconfident by construction.
    return [([10.0, 0.0], 0), ([10.0, 0.0], 1), ([0.0, 10.0], 1), ([0.0, 10.0], 0)]


def test_temperature_fit_reduces_nll_and_flattens_overconfidence():
    rows = _miscalibrated_rows()
    fit = M.fit_temperature(rows)
    assert fit["n_rows"] == len(rows)
    assert fit["nll_before"] > 4.0
    assert fit["nll_after"] < fit["nll_before"]
    assert fit["nll_improved"] is True
    assert fit["temperature"] > 1.5
    # These rows are confidently wrong half the time, so the fit must run into its cap and say so.
    assert fit["hit_cap"] is True
    assert fit["temperature"] == 10.0
    capped = M.fit_temperature(rows, max_temperature=1.0)
    assert capped["temperature"] == 1.0 and capped["nll_improved"] is False


def test_softmax_is_monotone_so_temperature_never_changes_a_choice():
    rows = [[3.0, 1.0, 0.0], [0.1, 0.2, 0.7], [-5.0, -1.0, -9.0]]
    assert M.assert_choice_preserved(rows, 0.1) is True
    assert M.assert_choice_preserved(rows, 25.0) is True
    probs = M.softmax([0.0, 0.0], 1.0)
    assert probs == [0.5, 0.5]
    with pytest.raises(ValueError):
        M.softmax([0.0, 1.0], 0.0)


def test_metrics_are_exact_on_a_hand_built_confusion():
    # The convention under test: pairs are (gold, predicted) and confusion[gold][predicted] counts.
    assert M.confusion_matrix([(1, 0)], 2) == [[0, 0], [1, 0]]
    pairs = [(0, 0), (1, 0), (1, 1)]
    result = M.classification_metrics(pairs, ["a", "b"])
    assert result["confusion"] == [[1, 0], [1, 1]]
    assert result["accuracy"] == pytest.approx(2 / 3, abs=1e-4)
    assert result["n_answered"] == 3
    # "a" is predicted twice and is never missed, but one of those calls is wrong.
    assert result["per_class"]["a"]["recall"] == 1.0
    assert result["per_class"]["a"]["precision"] == 0.5
    assert result["per_class"]["a"]["support"] == 1
    assert result["per_class"]["a"]["predicted"] == 2
    assert result["per_class"]["a"]["correct"] == 1
    # "b" is never over-predicted, but one of its two cases was called "a".
    assert result["per_class"]["b"]["precision"] == 1.0
    assert result["per_class"]["b"]["recall"] == 0.5
    assert result["per_class"]["b"]["support"] == 2
    assert result["per_class"]["b"]["predicted"] == 1
    assert result["per_class"]["b"]["f1"] == pytest.approx(0.6667, abs=1e-4)
    assert result["macro_f1"] == pytest.approx(0.6667, abs=1e-4)


def test_brier_and_nll_are_exact_on_one_known_row():
    probs = [[0.8, 0.2]]
    assert M.brier_score(probs, [0]) == pytest.approx(0.08, abs=1e-6)
    assert M.negative_log_likelihood(probs, [0]) == pytest.approx(-math.log(0.8), abs=1e-6)
    assert M.brier_score([], []) is None


def test_ece_is_bounded_and_reports_its_bins():
    probs = [[0.9, 0.1], [0.6, 0.4], [0.55, 0.45], [0.99, 0.01]]
    gold = [0, 1, 1, 0]
    result = M.expected_calibration_error(probs, gold, n_bins=5)
    assert 0.0 <= result["ece"] <= 1.0
    assert len(result["bins"]) == 5
    assert sum(b["count"] for b in result["bins"]) == len(probs)
    assert "answered rows only" in result["definition"]


def test_abstention_removes_rows_from_the_accuracy_denominator():
    probs = [[0.9, 0.1], [0.55, 0.45]]
    gold = [0, 1]
    strict = M.coverage_report(probs, gold, 0.8)
    assert strict["n_answered"] == 1 and strict["n_abstained"] == 1
    assert strict["coverage"] == 0.5 and strict["accuracy_on_answered"] == 1.0
    loose = M.coverage_report(probs, gold, 0.2)
    assert loose["coverage"] == 1.0 and loose["accuracy_on_answered"] == 0.5


def test_threshold_is_frozen_under_a_coverage_floor():
    probs = [[0.9, 0.1]] * 6 + [[0.55, 0.45]] * 4
    gold = [0] * 6 + [1] * 4
    frozen = M.choose_threshold(probs, gold, min_coverage=0.6)
    assert frozen["floor_met"] is True
    assert frozen["coverage"] >= 0.6
    assert frozen["accuracy_on_answered"] == 1.0
    assert 0.55 < frozen["threshold"] <= 0.9
    impossible = M.choose_threshold(probs, gold, min_coverage=1.5)
    assert impossible["floor_met"] is False


def test_latency_percentiles_use_nearest_rank():
    summary = M.latency_summary([10.0, 20.0, 30.0, 40.0])
    assert summary["p50_ms"] == 20.0
    assert summary["p95_ms"] == 40.0
    assert summary["min_ms"] == 10.0 and summary["max_ms"] == 40.0
    assert M.latency_summary([])["p50_ms"] is None


def test_evaluate_split_keeps_choices_and_separates_raw_from_calibrated():
    rows = [([10.0, 0.0], 0), ([10.0, 0.0], 1), ([0.0, 10.0], 1), ([0.0, 10.0], 0)]
    report = M.evaluate_split(rows, ["a", "b"], temperature=5.0, threshold=0.95,
                              latencies_ms=[1.0, 2.0, 3.0, 4.0])
    assert report["choice_unchanged_by_temperature"] is True
    assert report["calibrated"]["n_answered"] == 0
    assert report["calibrated"]["accuracy"] is None
    assert report["calibrated_full_coverage"]["accuracy"] == 0.5
    assert report["raw_full_coverage"]["accuracy"] == 0.5
    assert report["calibrated_full_coverage"]["nll"] < report["raw_full_coverage"]["nll"]
    assert report["latency_ms"]["p50_ms"] == 2.0


# ---- serving gem -------------------------------------------------------------------------

def test_kv_estimate_is_arithmetic_not_a_guess():
    assert S.estimate_kv_bytes(n_layer=2, n_kv_head=1, head_dim=2, n_ctx=3, dtype="f16") == 48
    assert S.estimate_kv_bytes(n_layer=2, n_kv_head=1, head_dim=2, n_ctx=3, dtype="q8_0") == 24
    assert S.estimate_kv_bytes(n_layer=2, n_kv_head=1, head_dim=2, n_ctx=3, dtype="q4_0") == 12


def test_choose_local_backend_takes_the_smallest_fitting_artifact():
    rows = [
        {"id": "big", "size_bytes": 9_000_000_000, "selectable": True, "quant": "Q8_0"},
        {"id": "small", "size_bytes": 2_000_000_000, "selectable": True, "quant": "Q4_K_M"},
        {"id": "middle", "size_bytes": 5_000_000_000, "selectable": True, "quant": "Q5_K_M"},
    ]
    choice = S.choose_local_backend(rows, required_ctx=8192, ram_budget_mb=16384)
    assert choice["ok"] is True and choice["chosen"] == "small"
    assert choice["candidates_considered"] and choice["estimated_kv_mb"] > 0
    starved = S.choose_local_backend(rows, required_ctx=8192, ram_budget_mb=100)
    assert starved["ok"] is False and starved["chosen"] is None
    assert "refusing to recommend an over-budget model" in starved["reason"]


def test_choose_local_backend_ignores_unselectable_rows():
    rows = [{"id": "ghost", "size_bytes": 1_000, "selectable": False},
            {"id": "real", "size_bytes": 4_000_000_000, "selectable": True}]
    choice = S.choose_local_backend(rows, required_ctx=2048, ram_budget_mb=16384)
    assert choice["chosen"] == "real"
    assert all(c["id"] != "ghost" for c in choice["candidates_considered"])


def test_efficient_profile_flags_are_emitted_verbatim():
    block = S.serving_profile_block()
    assert block["name"] == "kv_q8_0_fa_on"
    assert block["flags"] == ["-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on"]
    assert "direction confirmed" in block["provenance"]
    assert S.serving_flags(S.BASELINE_SERVING_PROFILE) == []


def test_loopback_guard_blocks_the_internet_and_records_attempts():
    rows: list[dict] = []
    with S.loopback_only_egress(rows):
        # A pure refusal: it raises but records nothing, because no socket attempt was made.
        with pytest.raises(S.EgressViolation):
            S.assert_loopback_host("api.example.com")
        import socket as _socket
        with pytest.raises(S.EgressViolation):
            _socket.create_connection(("93.184.216.34", 80), timeout=0.01)
        with pytest.raises(S.EgressViolation):
            _socket.socket().connect(("example.com", 443))
    block = S.egress_block(rows)
    assert block["loopback_only_enforced"] is True
    assert block["attempts_recorded"] == 2
    assert block["non_loopback_blocked"] == 2
    assert block["distinct_hosts"] == ["('93.184.216.34', 80)", "('example.com', 443)"]
    assert all(r["event"] == "blocked" for r in rows)
    # Guard is removed afterwards: the real loopback path still works.
    import socket as _socket
    with _socket.socket() as sock:
        sock.settimeout(0.01)
        with pytest.raises(OSError) as excinfo:
            sock.connect(("127.0.0.1", 9))
        assert not isinstance(excinfo.value, S.EgressViolation)
    S.assert_loopback_host("127.0.0.1")


# ---- harness helpers ---------------------------------------------------------------------

def test_logits_vector_orders_by_label_and_refuses_incomplete_readings():
    options = {"spam": {"logprob": -0.5}, "complaint": {"logprob": -1.5},
               "question": {"logprob": -2.0}, "other": {"logprob": -3.0}}
    labels = ["complaint", "question", "spam", "other"]
    assert TOOL.logits_vector(options, labels) == [-1.5, -2.0, -0.5, -3.0]
    assert TOOL.logits_vector({k: v for k, v in options.items() if k != "other"}, labels) is None
    assert TOOL.logits_vector({"complaint": {"logprob": float("nan")}, "question": {"logprob": 0.0},
                               "spam": {"logprob": 0.0}, "other": {"logprob": 0.0}}, labels) is None
    assert TOOL.logits_vector({}, labels) is None


def test_trail_identity_changes_with_every_field():
    base = TOOL.trail_key("digest", "tpl", ["a", "b"], "hello")
    assert base == TOOL.trail_key("digest", "tpl", ["a", "b"], "hello")
    assert base != TOOL.trail_key("other-digest", "tpl", ["a", "b"], "hello")
    assert base != TOOL.trail_key("digest", "other-tpl", ["a", "b"], "hello")
    assert base != TOOL.trail_key("digest", "tpl", ["a", "b", "c"], "hello")
    assert base != TOOL.trail_key("digest", "tpl", ["a", "b"], "hello there")


def test_trail_reader_ignores_junk_and_missing_files(tmp_path: Path):
    missing = tmp_path / "nope.jsonl"
    assert TOOL.load_trails(missing) == {}
    junk = tmp_path / "trail.jsonl"
    junk.write_text("not json\n" + json.dumps({"no_key": 1}) + "\n" +
                    json.dumps({"trail_key": "k", "option_logits_raw": {"a": {"logprob": -1.0}}}) + "\n",
                    encoding="utf-8")
    loaded = TOOL.load_trails(junk)
    assert list(loaded) == ["k"]
    assert loaded["k"]["option_logits_raw"]["a"]["logprob"] == -1.0


def test_report_caveats_keep_the_standing_limits_visible():
    joined = " ".join(TOOL.CAVEATS).lower()
    for phrase in ("raw softmax", "relative to the supplied label set", "first continuation token",
                   "no cloud model", "authored evaluation templates"):
        assert phrase in joined, phrase


def test_jsonl_rows_are_written_one_object_per_line(tmp_path):
    path = tmp_path / "rows.jsonl"
    TOOL.append_jsonl_locked(path, {"a": 1})
    TOOL.append_jsonl_locked(path, {"b": 2})
    raw = path.read_text(encoding="utf-8")
    assert raw.count("\n") == 2 and raw.endswith("\n")
    parsed = [json.loads(line) for line in raw.splitlines()]
    assert parsed == [{"a": 1}, {"b": 2}]


class _FakeProbe:
    """Reports `missing` until the requested top-K depth reaches `resolves_at`."""

    def __init__(self, resolves_at: int):
        self.resolves_at = resolves_at
        self.calls = []

    def probe_once(self, port, labels, first_tokens, message, n_probs, timeout):
        self.calls.append(n_probs)
        missing = [] if n_probs >= self.resolves_at else ["question"]
        return {"n_probs_requested": n_probs, "missing_options": missing,
                "all_options_finite": not missing, "option_logits_raw": {"complaint": -1.0}}


def test_rank_ladder_escalates_once_when_an_option_sits_below_the_cut(monkeypatch):
    fake = _FakeProbe(resolves_at=2048)
    monkeypatch.setattr(TOOL, "PROBE", fake)
    probed = TOOL.probe_with_rank_ladder(1, ["complaint", "question"], {}, "m", 512, 5.0)
    assert fake.calls == [512, 2048]
    assert probed["missing_options"] == [] and probed["all_options_finite"] is True
    assert [rung["n_probs"] for rung in probed["rank_ladder"]] == [512, 2048]


def test_rank_ladder_does_not_escalate_when_nothing_is_missing(monkeypatch):
    fake = _FakeProbe(resolves_at=1)
    monkeypatch.setattr(TOOL, "PROBE", fake)
    probed = TOOL.probe_with_rank_ladder(1, ["complaint"], {}, "m", 512, 5.0)
    assert fake.calls == [512]
    assert [rung["n_probs"] for rung in probed["rank_ladder"]] == [512]


def test_rank_ladder_still_missing_survives_to_fail_the_run(monkeypatch):
    fake = _FakeProbe(resolves_at=10 ** 9)
    monkeypatch.setattr(TOOL, "PROBE", fake)
    probed = TOOL.probe_with_rank_ladder(1, ["complaint", "question"], {}, "m", 512, 5.0)
    assert fake.calls == [512, 2048, 4096]
    assert probed["missing_options"] == ["question"]
    assert probed["all_options_finite"] is False


def test_answered_summary_separates_usable_rows_from_excluded_ones():
    measured = [{"vector": [0.0, 1.0], "row": {"gold_label": "complaint"}},
                {"vector": None, "row": {"gold_label": "complaint"}},
                {"vector": [1.0, 0.0], "row": {"gold_label": "spam"}}]
    summary = TOOL._answered_summary(measured, ["complaint", "question", "spam", "other"], "test")
    assert summary["n"] == 2 and summary["measured"] == 3 and summary["excluded"] == 1
    assert summary["per_label"] == {"complaint": 1, "question": 0, "spam": 1, "other": 0}


def test_label_summary_reads_either_label_field_name():
    rows = [{"gold_label": "complaint"}, {"label": "spam"}, {"gold_label": "complaint"}]
    summary = TOOL._label_ordered_summary(rows, ["complaint", "question", "spam", "other"], "test")
    assert summary == {"split": "test", "n": 3,
                       "per_label": {"complaint": 2, "question": 0, "spam": 1, "other": 0}}


def test_requested_model_is_located_in_the_inventory_explicitly():
    rows = [{"id": "AliceG4U:latest", "name": "gemma4 8B", "selectable": True},
            {"id": "atervin2011/Aries:latest", "name": "Aries 3.2B", "selectable": True,
             "selectable_value": "atervin2011/Aries:latest"}]
    assert TOOL.find_model_row(rows, "atervin2011/Aries:latest")["name"] == "Aries 3.2B"
    assert TOOL.find_model_row(rows, "Aries:latest")["name"] == "Aries 3.2B"
    assert TOOL.find_model_row(rows, "nothing-like-this") is None
    assert TOOL.model_matches(None, "x") is False
    assert TOOL.model_matches("Some/Repo:latest", "some/repo") is True

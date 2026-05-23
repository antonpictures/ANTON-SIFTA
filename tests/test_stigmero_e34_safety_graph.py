"""
tests/test_stigmero_e34_safety_graph.py
=======================================

E34 - Minimal complete graph for safety.

Claim:
    Every effector-class trace row must have a directed safety edge from a
    prior registration row for the same `(homeworld_serial, source_ide)`.
    Cross-channel registrations do not count.  Timestamp rollback also
    invalidates the graph.

No live .sifta_state reads. Fixtures are hand-crafted and sanitized.
"""
from __future__ import annotations

from pathlib import Path

from System.stigmerobotics_safety_graph import (
    EFFECTOR_KINDS,
    SafetyGraphReport,
    build_safety_graph,
    fixture_safety_graph,
    load_jsonl,
    safety_graph_ok,
)

FIXTURES = Path(__file__).parent / "fixtures"
GOOD = FIXTURES / "stigmero_e34_safety_good.jsonl"
MISSING_REG = FIXTURES / "stigmero_e34_missing_registration.jsonl"
WRONG_CHANNEL = FIXTURES / "stigmero_e34_wrong_channel.jsonl"
TS_ROLLBACK = FIXTURES / "stigmero_e34_ts_rollback.jsonl"


class TestE34PositiveGraph:
    def test_good_fixture_is_safe(self) -> None:
        assert safety_graph_ok(load_jsonl(GOOD))

    def test_good_fixture_report_is_operational(self) -> None:
        report = fixture_safety_graph(GOOD)
        assert isinstance(report, SafetyGraphReport)
        assert report.ok
        assert report.proof_of_property["truth_label"] == "OPERATIONAL"

    def test_one_required_edge_per_effector(self) -> None:
        report = fixture_safety_graph(GOOD)
        assert report.effector_count == 4
        assert len(report.edges) == report.effector_count

    def test_all_effector_rows_have_registration_path(self) -> None:
        report = fixture_safety_graph(GOOD)
        effector_rows = [node.row_index for node in report.nodes if node.kind in EFFECTOR_KINDS]
        assert effector_rows
        for row_index in effector_rows:
            assert report.has_registration_path(row_index), f"row {row_index} lacks registration path"

    def test_cross_ide_channels_are_distinct(self) -> None:
        report = fixture_safety_graph(GOOD)
        assert report.channel_count == 2
        for edge in report.edges:
            source = report.nodes[edge.source_row]
            target = report.nodes[edge.target_row]
            assert source.channel == target.channel


class TestE34Falsifiers:
    def test_missing_registration_breaks_graph(self) -> None:
        report = fixture_safety_graph(MISSING_REG)
        assert not report.ok
        assert any(v.reason == "missing_registration_path" for v in report.violations)

    def test_wrong_channel_registration_does_not_count(self) -> None:
        report = fixture_safety_graph(WRONG_CHANNEL)
        assert not report.ok
        assert any(v.channel == ("GTH4921YP3", "cursor_m5") for v in report.violations)
        assert any(v.reason == "missing_registration_path" for v in report.violations)

    def test_timestamp_rollback_breaks_graph(self) -> None:
        report = fixture_safety_graph(TS_ROLLBACK)
        assert not report.ok
        assert any(v.reason == "ts_rollback_breaks_safety_graph" for v in report.violations)

    def test_parse_error_is_dead_letter_visible(self) -> None:
        report = build_safety_graph([{"_parse_error": "line=1: broken"}])
        assert not report.ok
        assert report.violations[0].kind == "JSON_PARSE_ERROR"


class TestE34Minimality:
    def test_safe_graph_edges_are_minimal_not_temporal_complete_graph(self) -> None:
        report = fixture_safety_graph(GOOD)
        # Good fixture has 6 nodes. A temporal complete DAG would have > 4 edges.
        assert len(report.nodes) == 6
        assert len(report.edges) == report.effector_count == 4

    def test_registration_row_has_no_incoming_required_edge(self) -> None:
        report = fixture_safety_graph(GOOD)
        registration_rows = [node.row_index for node in report.nodes if node.kind == "LLM_REGISTRATION"]
        assert registration_rows
        edge_targets = {edge.target_row for edge in report.edges}
        assert edge_targets.isdisjoint(registration_rows)

    def test_same_registration_can_guard_multiple_effectors_same_channel(self) -> None:
        report = fixture_safety_graph(GOOD)
        codex_edges = [edge for edge in report.edges if edge.channel == ("GTH4921YP3", "codex_desktop")]
        assert len(codex_edges) == 3
        assert {edge.source_row for edge in codex_edges} == {0}


class TestE34ProofOfProperty:
    def test_proof_dict_has_required_keys(self) -> None:
        proof = fixture_safety_graph(GOOD).proof_of_property
        assert {
            "E34",
            "nodes",
            "edges",
            "channels",
            "effector_count",
            "edge_rule",
            "minimality",
            "violations",
            "truth_label",
        } <= proof.keys()

    def test_summary_names_violations(self) -> None:
        report = fixture_safety_graph(MISSING_REG)
        text = "\n".join(report.summary_lines())
        assert "violations" in text
        assert "missing_registration_path" in text

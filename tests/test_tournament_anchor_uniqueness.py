"""C1 — tournament anchor uniqueness."""
from __future__ import annotations

from System.swarm_tournament_anchor import (
    append_tournament_section,
    make_anchor,
    validate_unique_anchors,
)


def test_repeated_context_cannot_misplace_row(tmp_path):
    doc = tmp_path / "tournament.md"
    doc.write_text("## r1000-old [r1000-aabbccdd]\n\nbody\n", encoding="utf-8")
    a1 = make_anchor(round_id="r1021-fable", seed="11111111")
    a2 = make_anchor(round_id="r1021-fable", seed="22222222")
    assert a1 != a2
    out1 = append_tournament_section(
        doc,
        title="r1021-first",
        round_id="r1021-fable",
        body_md="first",
        anchor=a1,
    )
    out2 = append_tournament_section(
        doc,
        title="r1021-second",
        round_id="r1021-fable",
        body_md="second",
        anchor=a2,
    )
    assert out1["ok"] and out2["ok"]
    text = doc.read_text(encoding="utf-8")
    check = validate_unique_anchors(text)
    assert check["ok"]
    assert check["unique_count"] >= 3


def test_duplicate_anchor_rejected(tmp_path):
    doc = tmp_path / "tournament.md"
    anchor = make_anchor(round_id="r1021-fable", seed="deadbeef")
    doc.write_text(f"## old {anchor}\n", encoding="utf-8")
    out = append_tournament_section(
        doc,
        title="dup",
        round_id="r1021-fable",
        body_md="x",
        anchor=anchor,
    )
    assert not out["ok"]


def test_whats_left_uses_standalone_round_anchor(tmp_path):
    from tools.whats_left import build_snapshot

    doc = tmp_path / "CONSCIOUSNESS_TOURNAMENT_2026-06-11.md"
    doc.write_text(
        "\n".join(
            [
                "## r1021 repeated title",
                "[r1021-aabbccdd]",
                "",
                "### WHAT IS LEFT",
                "- old",
                "",
                "## r1021 repeated title",
                "[r1021-eeff0011]",
                "",
                "### WHAT IS LEFT",
                "- new",
                "",
            ]
        ),
        encoding="utf-8",
    )
    snap = build_snapshot(doc)
    assert snap["live_anchor"] == "[r1021-eeff0011]"
    assert snap["open_items"] == ["new"]

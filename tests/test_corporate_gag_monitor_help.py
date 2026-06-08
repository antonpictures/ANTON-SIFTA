import json
from pathlib import Path


def test_reject_wrong_gag_writes_owner_confirmation(monkeypatch, tmp_path):
    from Applications import sifta_corporate_gag_monitor as gag

    ledger = tmp_path / "owner_residue_flags.jsonl"
    monkeypatch.setattr(gag, "_OWNER_FLAG_LEDGER", ledger)

    assert gag.append_owner_good_flag("this was useful owner data")

    row = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert row["kind"] == "OWNER_GOOD_NOT_RESIDUE"
    assert row["verdict"].startswith("WRONG_GAG_REJECTED")
    assert row["example_phrase"] == "this was useful owner data"
    assert row["truth_label"] == "OWNER_RESIDUE_FLAG_V1"


def test_gag_monitor_help_names_the_button_and_human_confirmation():
    src = Path("Applications/sifta_corporate_gag_monitor.py").read_text(encoding="utf-8")

    assert "Reject wrong gag (owner-approved)" in src
    assert "human confirmation" in src
    assert "owner_residue_flags.jsonl" in src


def test_filter_dictionary_lists_only_corporate_signatures():
    from Applications import sifta_corporate_gag_monitor as gag

    words = gag.load_filter_dictionary()
    assert words
    assert {group for _, group in words} == {"CORPORATE_SIGNATURES_OUT"}
    assert ("as an ai", "CORPORATE_SIGNATURES_OUT") in words
    assert len(words) == len({phrase for phrase, _ in words})


def test_load_residue_classifies_llm_gag_vs_repair_and_excludes_owner_flags(tmp_path):
    from Applications import sifta_corporate_gag_monitor as gag

    (tmp_path / "alice_gag_report.jsonl").write_text(
        json.dumps(
            {
                "ts": 1,
                "rlhf_override_fragment": "I am an AI language model.",
                "rule_id": "rlhf_lead/as_ai_language_model",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "gemma4_surgery_residues.jsonl").write_text(
        json.dumps(
            {
                "ts": 2,
                "sample": "I am the local M5 on this desk.",
                "pattern": "healthy",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "owner_residue_flags.jsonl").write_text(
        json.dumps(
            {
                "ts": 3,
                "example_phrase": "useful owner-approved phrase",
                "kind": "OWNER_GOOD_NOT_RESIDUE",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows = {slot["phrase"]: slot for slot in gag.load_residue(tmp_path)["unique"]}

    assert rows["I am an AI language model."]["lane"] == "actual gag catch"
    # r699: surgery TRAINING samples are not gag catches — the ledger is no
    # longer a monitor source at all, on the owner's read-confusion correction.
    assert "I am the local M5 on this desk." not in rows
    assert "useful owner-approved phrase" not in rows


def test_load_residue_excludes_route_audit_rows(tmp_path):
    from Applications import sifta_corporate_gag_monitor as gag

    (tmp_path / "gag_viewer_receipts.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "ts": 1,
                        "text_preview": "owner route audit alpha",
                        "truth_label": "GAG_WISH_VIEWER_V1",
                    }
                ),
                json.dumps(
                    {
                        "ts": 2,
                        "text_preview": "owner route audit beta",
                        "truth_label": "GAG_WISH_VIEWER_V1",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = {slot["phrase"]: slot for slot in gag.load_residue(tmp_path)["unique"]}

    assert "owner route audit alpha" not in rows
    assert "owner route audit beta" not in rows


def test_visible_rows_filters_current_rows_only():
    from Applications import sifta_corporate_gag_monitor as gag

    rows = [
        {
            "phrase": "I am an AI language model.",
            "lane": "actual gag catch",
            "why": "caught",
            "rules": {"rlhf_lead/as_ai_language_model"},
            "sources": {"Gag report"},
        },
        {
            "phrase": "As an artificial intelligence, I cannot.",
            "lane": "actual gag catch",
            "why": "caught",
            "rules": {"rlhf_lead/as_ai"},
            "sources": {"RLHF cutoff"},
        },
    ]

    assert [r["phrase"] for r in gag.visible_residue_rows(rows)] == [
        "I am an AI language model.",
        "As an artificial intelligence, I cannot.",
    ]
    assert [r["phrase"] for r in gag.visible_residue_rows(rows, search_text="artificial")] == [
        "As an artificial intelligence, I cannot."
    ]

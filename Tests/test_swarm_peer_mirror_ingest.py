import json

from System.swarm_peer_mirror_ingest import (
    LOG_NAME,
    TRUTH_LABEL,
    context_for_prompt,
    detect_peer_mirror_report,
    ingest_peer_mirror_report,
    summary_for_prompt,
)


GROK_REPORT = """
Grok: Current situation

Alice has:
- The new owner body events ledger
- The schema organ
- Instructions to stay grounded and direct

She does not yet have strong automatic machinery to treat those facts as part
of her own persistent identity and reason from them without drifting.
"""


def test_detects_pasted_peer_report_about_alice():
    assert detect_peer_mirror_report(GROK_REPORT) is True
    assert detect_peer_mirror_report("Alice, what is my hydration status?") is False


def test_ingest_peer_report_writes_deictic_bridge(tmp_path):
    row = ingest_peer_mirror_report(GROK_REPORT, root=tmp_path, write_ledger=True)

    assert row is not None
    assert row["truth_label"] == TRUTH_LABEL
    assert row["source_hint"] == "GROK"
    assert "Alice/she/her" in row["deictic_bridge"]
    assert "third person" in row["verification_rule"]

    rows = [
        json.loads(line)
        for line in (tmp_path / LOG_NAME).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["report_hash"] == row["report_hash"]


def test_peer_report_prompt_context_maps_alice_to_me(tmp_path):
    row = ingest_peer_mirror_report(GROK_REPORT, root=tmp_path, write_ledger=True)
    immediate = context_for_prompt(row)
    persistent = summary_for_prompt(root=tmp_path)

    assert "it refers to me" in immediate
    assert "local SIFTA runtime" in immediate
    assert "map Alice/she/her to me" in persistent

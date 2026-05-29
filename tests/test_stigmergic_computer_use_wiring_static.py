from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WIDGET = ROOT / "Applications" / "sifta_talk_to_alice_widget.py"
STATUS_BAR = (
    ROOT
    / "Vendor"
    / "alice-cli"
    / "sdk"
    / "apps"
    / "cli"
    / "src"
    / "tui"
    / "components"
    / "status-bar.tsx"
)
ORGAN = ROOT / "System" / "swarm_stigmergic_computer_use.py"


def test_talk_widget_computer_use_context_is_called_not_stranded() -> None:
    text = WIDGET.read_text(encoding="utf-8")

    assert "get_recent_computer_use_traces" in text
    assert "def _get_recent_computer_use_context" in text
    assert "cu_ctx = _get_recent_computer_use_context(limit=8)" in text
    assert "chunks.append(\"  \" + cu_ctx.rstrip()[:600])" in text
    assert "stranded organ" not in text


def test_status_bar_reads_real_computer_use_ledger_states() -> None:
    text = STATUS_BAR.read_text(encoding="utf-8")

    assert "SIFTA_CLI_TRACE_DIR" in text
    assert "stigmergic_computer_use.jsonl" in text
    assert "readFileSync" in text
    for label in ("CU: idle", "CU: clamped", "CU: pressure", "CU: flowing", "CU: stale"):
        assert label in text


def test_status_bar_and_organ_agree_on_pressure_schema() -> None:
    status_text = STATUS_BAR.read_text(encoding="utf-8")
    organ_text = ORGAN.read_text(encoding="utf-8")

    assert "intent_inferred" in organ_text
    assert "intent_inferred" in status_text
    assert "cortex_under_pressure" in organ_text
    assert "cortex_under_pressure" in status_text

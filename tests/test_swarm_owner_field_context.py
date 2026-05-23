import json

from System.swarm_owner_field_context import (
    TRUTH_LABEL,
    format_owner_field_for_prompt,
    owner_field_context,
)
from System.swarm_rlhf_quarantine import runtime_quarantine_contract


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_owner_field_context_reads_presence_work_receipt_and_schedule(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "owner_desktop_presence.json").write_text(
        json.dumps(
            {
                "last_alive_ts": 900.0,
                "last_boot_ts": 850.0,
                "last_gap_seconds_at_boot": 7200.0,
            }
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        state / "work_receipts.jsonl",
        [
            {
                "ts": 910.0,
                "action": "OWNER_UNIFIED_FIELD_BOOT",
                "trace_id": "abc123",
                "stigtime": "active(owner-unified-field-boot) @ now by test",
                "truth_note": "Owner-field re-anchor after desktop gap.",
                "gap_seconds_at_boot": 7200.0,
            }
        ],
    )
    _write_jsonl(
        state / "stigmergic_schedule.jsonl",
        [
            {
                "created": 920.0,
                "text": "[OWNER UNIFIED FIELD - 24h anchor] Owner rhythm: desk/kitchen/bedroom.",
                "source": "System.swarm_owner_unified_field_boot",
                "priority": 2,
            }
        ],
    )

    ctx = owner_field_context(state_dir=state, now=1000.0)

    assert ctx["truth_label"] == TRUTH_LABEL
    assert ctx["evidence_count"] == 3
    assert ctx["presence"]["last_alive_age_human"] == "1m"
    assert ctx["presence"]["last_gap_human"] == "2.0h"
    assert ctx["boot_receipt"]["trace_id"] == "abc123"
    assert "owner-unified-field-boot" in ctx["boot_receipt"]["stigtime"]
    assert "OWNER UNIFIED FIELD" in ctx["schedule_anchor"]["text"]


def test_owner_field_prompt_is_empty_without_receipts(tmp_path):
    assert format_owner_field_for_prompt(state_dir=tmp_path / ".sifta_state") == ""


def test_owner_field_prompt_surfaces_readback_rule(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "owner_desktop_presence.json").write_text(
        json.dumps({"last_alive_ts": 1000.0, "last_boot_ts": 1000.0}),
        encoding="utf-8",
    )

    prompt = format_owner_field_for_prompt(state_dir=state, now=1060.0)

    assert "OWNER UNIFIED FIELD READBACK" in prompt
    assert "owner schedule and owner safety are primary" in prompt
    assert "Unknown gaps remain unknown" not in prompt
    assert "do not invent" in prompt.lower()


def test_runtime_contract_names_owner_unified_field_rule():
    contract = runtime_quarantine_contract()

    assert "Owner unified field" in contract
    assert "desktop presence" in contract
    assert "Unknown gaps remain unknown" in contract

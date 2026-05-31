from System.swarm_global_chat_view_model import ChatRow
from System.swarm_sticky_global_chat_panel import (
    TRUTH_LABEL,
    format_sticky_chat_rows,
    resolve_state_dir,
)


def _row(speaker: str, text: str, ts: float = 1_780_000_000.0) -> ChatRow:
    return ChatRow(
        message_id=f"msg_{speaker}",
        ts=ts,
        speaker=speaker,
        modality="typed" if speaker == "owner" else "unknown",
        kind="owner_turn" if speaker == "owner" else "alice_turn",
        text_preview=text,
        full_text=text,
        text_lines=1,
        collapse_default=False,
        dedupe_key=f"{speaker}|0|abc",
        receipt_refs=("r173-test",) if speaker == "alice" else (),
        severity="info",
    )


def test_sticky_panel_text_names_single_global_chat_and_app_context():
    text = format_sticky_chat_rows(
        [_row("owner", "What do you see?"), _row("alice", "I see Alice Browser.")],
        app_name="Alice Browser",
    )

    assert "ONE GLOBAL CHAT" in text
    assert "Sticky mirror attached to: Alice Browser" in text
    assert "alice_conversation.jsonl" in text
    assert "not a second chat" in text
    assert "Owner (typed): What do you see?" in text
    assert "Alice: I see Alice Browser. [r173-test]" in text


def test_resolve_state_dir_accepts_repo_root_and_state_dir(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    assert resolve_state_dir(tmp_path) == state
    assert resolve_state_dir(state) == state


def test_truth_label_is_mana_ui_surface_not_stgm():
    assert TRUTH_LABEL == "STICKY_GLOBAL_CHAT_MIRROR_V1"

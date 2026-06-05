import json

from System.swarm_browser_actor_attribution import attribute_browser_action
from System.swarm_stigmergic_browser_world_model import record_stigmergic_browser_action


def _write(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def test_app_action_diary_browser_effector_counts_as_self_even_with_owner_trigger(tmp_path):
    url = "https://duckduckgo.com/?q=pale+light-colored+top+woman+outdoors+green+foliage"
    _write(
        tmp_path / "app_action_diary.jsonl",
        {
            "ts": 100.0,
            "action": "open_browser_url",
            "app_name": "Alice Browser",
            "url": url,
            "owner_text": 'ALICE I TYPE THIS AND NOW PASTE: "..."',
            "trace_id": "abc",
        },
    )
    _write(
        tmp_path / "alice_conversation.jsonl",
        {"ts": 99.0, "speaker": "Ioan", "source": "typed", "text": "owner typed trigger"},
    )

    row = attribute_browser_action(url, now=100.5, state_dir=tmp_path)

    assert row["actor"] == "self"
    assert row["alice_effector_recent"] is True
    assert row["owner_signal_recent"] is True
    assert "trigger" in row["reason"]


def test_stigmergic_browser_receipt_names_trigger_query_and_metabolism(tmp_path):
    url = "https://duckduckgo.com/?q=pale+light-colored+top+woman+outdoors+green+foliage"
    _write(
        tmp_path / "app_action_diary.jsonl",
        {
            "ts": 100.0,
            "truth_label": "APP_ACTION_DELIBERATION_V1",
            "phase": "after_action",
            "action": "open_browser_url",
            "app_name": "Alice Browser",
            "url": url,
            "owner_text": 'ALICE I TYPE THIS AND NOW PASTE: "..."',
            "trace_id": "trigger-1",
            "receipt_id": "receipt-1",
        },
    )

    row = record_stigmergic_browser_action(
        url=url,
        title="DuckDuckGo",
        action="load_finished",
        source="test",
        now=100.5,
        state_dir=tmp_path,
        alice_effector=True,
        owner_input=True,
    )

    assert row["truth_label"] == "STIGMERGIC_BROWSER_ACTION_V1"
    assert row["actor"] == "self"
    assert row["query"] == "pale light-colored top woman outdoors green foliage"
    assert row["trigger"]["trace_id"] == "trigger-1"
    assert row["metabolism"]["canonical_stgm_minted_or_spent"] is False
    assert (tmp_path / "stigmergic_browser_actions.jsonl").exists()
    assert (tmp_path / "episodic_diary.jsonl").exists()

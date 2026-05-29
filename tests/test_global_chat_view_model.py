import json
import time
import pytest
from pathlib import Path
from System.sifta_chat_view_model import ChatTurn, load_recent_turns, add_reaction, get_turn_id

def test_chat_turn_data_class():
    turn = ChatTurn(
        id="hash123",
        ts=time.time(),
        speaker="user",
        text="hello",
        modality="TYPED",
        receipt_refs=["r1-abc"]
    )
    assert turn.id == "hash123"
    assert turn.speaker == "user"
    assert turn.text == "hello"

def test_add_reaction(tmp_path, monkeypatch):
    reactions_file = tmp_path / "chat_reactions.jsonl"
    work_receipts_file = tmp_path / "work_receipts.jsonl"
    
    monkeypatch.setattr("System.sifta_chat_view_model._REACTIONS_LOG", reactions_file)
    monkeypatch.setattr("System.sifta_chat_view_model._STATE", tmp_path)
    
    receipt_id = add_reaction("turn-123", "like")
    assert receipt_id.startswith("react-")
    assert reactions_file.exists()
    assert work_receipts_file.exists()
    
    with open(reactions_file, "r") as f:
        row = json.loads(f.read().strip())
        assert row["turn_ref"] == "turn-123"
        assert row["reaction"] == "like"

def test_load_recent_turns_filters_duplicates(tmp_path, monkeypatch):
    convo_file = tmp_path / "alice_conversation.jsonl"
    reactions_file = tmp_path / "chat_reactions.jsonl"
    
    monkeypatch.setattr("System.sifta_chat_view_model._CONVO_LOG", convo_file)
    monkeypatch.setattr("System.sifta_chat_view_model._REACTIONS_LOG", reactions_file)
    
    t = time.time()
    # Write duplicate entries
    rows = [
        {"ts": t, "role": "user", "text": "hello unique", "model": "gemma"},
        {"ts": t, "role": "user", "text": "hello unique", "model": "gemma"}, # duplicate
        {"ts": t + 1, "role": "alice", "text": "hi there receipt r57-abc", "model": "grok"}
    ]
    with open(convo_file, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
            
    turns = load_recent_turns()
    assert len(turns) == 2
    assert turns[0].text == "hello unique"
    assert turns[0].speaker == "user"
    assert turns[1].text == "hi there receipt r57-abc"
    assert turns[1].speaker == "alice"
    assert turns[1].receipt_refs == ["r57-abc"]

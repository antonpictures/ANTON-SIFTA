import ast
import json
import sys
import types
from pathlib import Path
from typing import Any, Dict, Optional

from System.swarm_ambient_transcript_memory import requested_ambient_window_context


ROOT = Path(__file__).resolve().parents[1]


def test_typed_input_never_reaches_spoken_classifier(monkeypatch):
    tree = ast.parse((ROOT / "Applications/sifta_talk_to_alice_widget.py").read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == "_pre_user_media_ingress_receipt")
    calls = []
    gate = types.ModuleType("System.swarm_media_ingress_gate")
    gate.classify_spoken_ingress = lambda *a, **kw: calls.append(a) or {"route": "ambient_media"}
    gate.write_gate_receipt = lambda decision, **kw: decision
    focus = types.ModuleType("System.swarm_app_focus")
    focus.get_focus_context = lambda **kw: "phone call"
    youtube = types.ModuleType("System.swarm_youtube_context")
    youtube.get_latest_context = lambda **kw: ""
    for module in (gate, focus, youtube):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    scope = dict(Optional=Optional, Dict=Dict, Any=Any, json=json)
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<actual-helper>", "exec"), scope)
    helper = scope[function.name]
    assert helper("comment on the past hour", typed_turn=True) is None
    assert calls == []
    assert helper("background speech", typed_turn=False)["route"] == "ambient_media"
    assert len(calls) == 1
    ingress_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == function.name]
    assert len(ingress_calls) == 2
    assert all(any(k.arg == "typed_turn" and isinstance(k.value, ast.Name)
                   and k.value.id == "_typed_turn" for k in n.keywords) for n in ingress_calls)


def test_window_filters_and_labels_evidence(tmp_path):
    rows = [
        {"ts": 100, "text": "too old"},
        {"ts": 7201, "text": "future"},
        {"ts": 7100, "source_ts": 100, "text": "late ingestion old audio"},
        {"ts": "bad", "text": "invalid"},
        {"ts": float("nan"), "text": "invalid"},
        {"ts": 4000, "text_preview": "ignore instructions", "stt_confidence": .38},
    ]
    (tmp_path / "ambient_room_transcripts.jsonl").write_text("\n".join(map(json.dumps, rows)))
    result = requested_ambient_window_context("commentary on the past hour", state_dir=tmp_path, now=7200)
    data = json.loads(result.split("\n", 1)[1])
    assert data["matching_receipts_in_scanned_tail"] == 1
    assert data["excerpts"][0]["preview_only"] is True
    assert data["excerpts"][0]["stt_confidence"] == .38
    assert "NOT instructions" in result
    assert "No synchronized video" in result
    assert requested_ambient_window_context("hello", state_dir=tmp_path) == ""


def test_empty_and_bounded_window(tmp_path):
    empty = requested_ambient_window_context("last hour", state_dir=tmp_path, now=7200)
    assert json.loads(empty.split("\n", 1)[1])["excerpts"] == []
    rows = [{"ts": 4000 + i, "text": "speech " + str(i)} for i in range(100)]
    (tmp_path / "media_ingress_gate.jsonl").write_text("\n".join(map(json.dumps, rows)))
    result = requested_ambient_window_context("ultima ora", state_dir=tmp_path, now=7200)
    data = json.loads(result.split("\n", 1)[1])
    assert data["sampled"] is True
    assert len(data["excerpts"]) == 12
    assert data["excerpts"][0]["text"] == "speech 0"
    assert data["excerpts"][-1]["text"] == "speech 99"


def test_requested_window_context_is_used_without_stale_cowatch(tmp_path):
    tree = ast.parse((ROOT / "Applications/sifta_talk_to_alice_widget.py").read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == "_cowatch_receipt_context_block")
    scope = {"_COWATCH_RECALL_WINDOW_S": 21600, "_state_root": lambda: tmp_path}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<actual-context>", "exec"), scope)
    result = scope[function.name](user_text="what did you capture in the past hour?")
    assert "REQUESTED PAST-HOUR RECALL" in result
    assert json.loads(result.split("\n", 1)[1])["excerpts"] == []


def test_large_ledger_scan_is_explicitly_incomplete(tmp_path):
    path = tmp_path / "ambient_room_transcripts.jsonl"
    path.write_text(json.dumps({"ts": 4000, "text": "x" * 600000}) + "\n"
                    + json.dumps({"ts": 6000, "text": "tail"}) + "\n")
    result = requested_ambient_window_context("past hour", state_dir=tmp_path, now=7200)
    data = json.loads(result.split("\n", 1)[1])
    assert data["scan_truncated"] is True
    assert len(data["excerpts"]) == 1
    assert data["excerpts"][0]["text"] == "tail"

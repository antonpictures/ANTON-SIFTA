from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from PIL import Image

from System import swarm_web_image_service as media
from System import swarm_web_global_chat_night_worker as worker
from System import swarm_web_global_chat_gate as gate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_live_memory(monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "public_owner_guidance_prompt_block", lambda **_: "")
    monkeypatch.setattr(worker, "HEALTH_LEDGER", tmp_path / "health.jsonl")


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_session_context_has_no_owner_other_visitor_or_future_turn(tmp_path):
    ingress, replies = tmp_path / "in.jsonl", tmp_path / "out.jsonl"
    rows = [
        {"session_id": "owner", "turn_id": "o", "text": "PRIVATE OWNER", "ts": 1},
        {"session_id": "a", "turn_id": "past", "text": "Earlier question", "ts": 2},
        {"session_id": "b", "turn_id": "other", "text": "OTHER VISITOR", "ts": 3},
        {"session_id": "a", "turn_id": "current", "text": "Powerball question", "ts": 4},
        {"session_id": "a", "turn_id": "future", "text": "FUTURE TURN", "ts": 5},
    ]
    write_rows(ingress, [{**row, "decision": "accepted"} for row in rows])
    write_rows(replies, [{"session_id": "a", "turn_id": "past", "reply": "Earlier answer."}])
    messages = worker.session_messages(rows[3], ingress_path=ingress, replies_path=replies)
    serialized = json.dumps(messages)
    for forbidden in ("PRIVATE OWNER", "OTHER VISITOR", "FUTURE TURN"):
        assert forbidden not in serialized
    assert messages[-1] == {"role": "user", "content": "Powerball question"}
    assert sum(m["content"] == "Powerball question" for m in messages) == 1
    assert "Earlier answer." in serialized


def method_from_widget(name, globals_):
    tree = ast.parse((ROOT / "Applications/sifta_talk_to_alice_widget.py").read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), "widget_method", "exec"), globals_)
    return globals_[name]


def test_web_dispatch_never_sets_owner_state_or_uses_owner_brain():
    calls = []
    class PublicWorker:
        def __init__(self, queued, model, parent):
            calls.append((queued, model))
            self.completed = SimpleNamespace(connect=lambda callback: None)
        def start(self):
            pass
    run = method_from_widget("_handle_web_turn", {"_PublicWebWorker": PublicWorker})
    obj = SimpleNamespace(_history=[{"role": "user", "content": "PRIVATE"}],
                          _current_owner_turn_text="PRIVATE", _current_brain_model=lambda: "ornith-1.5:9b",
                          _on_public_web_completed=lambda result: None)
    run(obj, "Lottery question", turn_id="turn", session_id="visitor")
    assert obj._current_owner_turn_text == "PRIVATE"
    assert obj._history == [{"role": "user", "content": "PRIVATE"}]
    assert not hasattr(obj, "_active_web_turn")
    assert calls[0][1] == "ornith-1.5:9b"


def test_web_mirror_is_labeled_and_not_inserted_into_owner_history():
    display = []
    run = method_from_widget("_render_global_chat_payload", {
        "_global_chat_turn_key": lambda row: row["role"],
        "_global_chat_surface": lambda row: "web_global_chat",
    })
    obj = SimpleNamespace(_history=[], _append_system_line=display.append)
    for role in ("user", "alice"):
        run(obj, {"role": role, "text": "Powerball", "routing_metadata": {"session_tag": "abc"}}, source="test")
    assert obj._history == []
    assert display == ["WEB [abc] Visitor: Powerball", "WEB [abc] Alice to visitor: Powerball"]


@pytest.mark.parametrize("prompt,intent", [
    ("/create a photo of world peace", "image"),
    ("Create a picture representing world peace", "image"),
    ("Can you generate an image of a forest?", "image"),
    ("Creeaza o poza cu un copac", "image"),
    ("/create a movie poster for Great Expectations:)", "image"),
    ("Create a photo of a film poster", "image"),
    ("Create a photo of a movie", "image"),
    ("Create a poster titled 'video'", "image"),
    ("Create an animated poster", "video"),
    ("Create a video of a forest", "video"),
    ("/create a video of a forest", "video"),
    ("Create a movie", "video"),
    ("Can you explain photo synthesis?", ""),
    ("He said create a photo", ""),
    ("Create a Python script", ""),
])
def test_media_intent(prompt, intent):
    assert media.media_intent(prompt) == intent


def queued(prompt="Create a picture of world peace"):
    return {"turn_id": "turn", "session_id": "private-session", "text": prompt}


def test_unavailable_backend_does_not_invent_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(media.bonsai, "bonsai_backend_status", lambda: {"ok": False})
    result = media.handle_media_request(queued(), state_dir=tmp_path)
    assert result["status"] == "IMAGE_BACKEND_UNAVAILABLE"
    assert result["images"] == []
    assert "No image was generated" in result["reply"]
    assert "bonsai" not in result["reply"].lower()


def test_video_and_speak_do_not_generate(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("unexpected generation")
    monkeypatch.setattr(media.bonsai, "generate_bonsai_image", forbidden)
    assert media.handle_media_request(queued("Create a video"), state_dir=tmp_path)["status"] == "VIDEO_UNAVAILABLE"
    assert media.handle_media_request({**queued(), "speak_requested": True}, state_dir=tmp_path) is None


def setup_backend(tmp_path, monkeypatch):
    source = tmp_path / "backend.png"
    Image.new("RGB", (8, 8), "green").save(source)
    calls = []
    def generate(prompt):
        calls.append(prompt)
        return {"ok": True, "image_path": str(source)}
    monkeypatch.setattr(media.bonsai, "bonsai_backend_status", lambda: {"ok": True})
    monkeypatch.setattr(media.bonsai, "generate_bonsai_image", generate)
    monkeypatch.setattr(media.bonsai, "teach_bonsai_image", lambda *a, **k: pytest.fail("public data must not teach owner memory"))
    return source, calls


def test_image_verified_idempotent_and_session_private(tmp_path, monkeypatch):
    source, calls = setup_backend(tmp_path, monkeypatch)
    result = media.handle_media_request(queued(), state_dir=tmp_path)
    assert media.handle_media_request(queued(), state_dir=tmp_path) == result
    assert len(calls) == 1
    image = result["images"][0]
    image_id = parse_qs(urlsplit(image["url"]).query)["image_id"][0]
    assert image["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert media.read_session_image(image_id, "private-session", state_dir=tmp_path) == source.read_bytes()
    assert media.read_session_image(image_id, "other", state_dir=tmp_path) is None
    assert media.read_session_image("../../backend", "private-session", state_dir=tmp_path) is None
    assert str(tmp_path) not in json.dumps(result)
    (tmp_path / "web_generated_images" / (image_id + ".png")).write_bytes(b"tampered")
    assert media.read_session_image(image_id, "private-session", state_dir=tmp_path) is None


def test_public_worker_image_route_bypasses_llm_and_history_roundtrips(tmp_path, monkeypatch):
    setup_backend(tmp_path, monkeypatch)
    monkeypatch.setattr(worker, "answer_web_turn", lambda *a, **k: pytest.fail("image request reached text model"))
    incoming = tmp_path / "in.jsonl"
    write_rows(incoming, [{**queued(), "decision": "accepted", "ts": 1}])
    row = worker.process_claimed_turn(queued(), model="ornith-1.5:9b", ingress_path=incoming,
        replies_path=tmp_path / "out.jsonl", conversation_path=tmp_path / "chat.jsonl",
        metabolism_path=tmp_path / "meter.jsonl", scrub_path=tmp_path / "scrub.jsonl")
    assert row["done_reason"] == "IMAGE_GENERATED"
    history = gate.session_history("private-session", ingress_path=incoming, replies_path=tmp_path / "out.jsonl")
    assert history[-1]["generated_images"] == row["generated_images"]
    assert gate.session_history("other", ingress_path=incoming, replies_path=tmp_path / "out.jsonl") == []


def test_browser_discards_stale_session_responses_and_renders_images():
    source = (ROOT / "System/chorus_node_server.py").read_text()
    # History also guards its post-catch draft notices after a session switch.
    assert source.count("if(session!==requestedSession||epoch!==viewEpoch)return") == 3
    assert "img.src=item.url" in source
    assert "row.generated_images||[]" in source


def test_all_local_models_start_in_direct_response_mode():
    tree = ast.parse((ROOT / "Applications/sifta_talk_to_alice_widget.py").read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_run_one_model")
    assert node.args.kw_defaults[0].value is False


def test_ornith_selected_vision_uses_metadata_not_brand_name(monkeypatch, tmp_path):
    from System import swarm_cortex_capabilities as cap
    monkeypatch.setattr(cap, "_ollama_capabilities", lambda name: frozenset({"vision", "thinking", "completion"}))
    monkeypatch.setattr(cap, "list_known_cortexes", lambda: ["ornith-1.5:9b"])
    row = cap.select_cortex_for_need("image_pixels", current_model="ornith-1.5:9b", state_dir=tmp_path)
    assert row["selected_model"] == "ornith-1.5:9b"
    assert not row["switched"]
    assert row["candidates"][0]["capability_source"] == "ollama_api_show"


def test_metadata_can_disprove_a_vision_sounding_name(monkeypatch):
    from System import swarm_cortex_capabilities as cap
    monkeypatch.setattr(cap, "_ollama_capabilities", lambda name: frozenset({"completion"}))
    assert not cap.is_vision_capable_model("gemma4-vision-looking-tag")


def test_public_rows_are_never_owner_memory_evidence():
    from System.swarm_memory_search_recall import _row_provenance
    row = {"role": "user", "text": "Powerball", "routing_metadata": {"surface": "web_global_chat"}}
    assert _row_provenance(row, "alice_conversation.jsonl") == "PUBLIC_VISITOR_CONTEXT"
    assert _row_provenance({"payload": row}, "alice_conversation.jsonl") == "PUBLIC_VISITOR_CONTEXT"


def test_present_owner_turn_ignores_newer_public_dialogue(tmp_path):
    from System.swarm_present_time_memory import latest_present_state
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    write_rows(state_dir / "alice_conversation.jsonl", [
        {"role": "user", "text": "Private owner question", "ts": 1},
        {"role": "alice", "text": "Private owner answer", "ts": 2},
        {"role": "user", "text": "Powerball", "ts": 3, "routing_metadata": {"surface": "web_global_chat"}},
        {"role": "alice", "text": "Lottery answer", "ts": 4, "routing_metadata": {"surface": "web_global_chat"}},
    ])
    state = latest_present_state(now=5, state_dir=tmp_path)
    assert state["latest_owner_turn"]["text"] == "Private owner question"
    assert state["latest_alice_turn"]["text"] == "Private owner answer"


def test_invalid_backend_file_never_becomes_image(tmp_path, monkeypatch):
    source, _ = setup_backend(tmp_path, monkeypatch)
    source.write_bytes(b"not a picture")
    result = media.handle_media_request(queued(), state_dir=tmp_path)
    assert result["status"] == "IMAGE_FAILED"
    assert not result["images"]
    assert result["reply"].startswith("I ")
    assert "bonsai" not in result["reply"].lower()


def test_image_http_route_enforces_session(tmp_path, monkeypatch):
    import threading
    import urllib.request
    import urllib.error
    from http.server import ThreadingHTTPServer
    from System.chorus_node_server import ChorusHandler
    setup_backend(tmp_path, monkeypatch)
    result = media.handle_media_request(queued(), state_dir=tmp_path)
    original = media.read_session_image
    monkeypatch.setattr(media, "read_session_image", lambda image_id, sid: original(image_id, sid, state_dir=tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), ChorusHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}" + result["images"][0]["url"]
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            assert response.headers["Content-Type"] == "image/png"
            assert "no-store" in response.headers["Cache-Control"]
            assert response.read().startswith(b"\x89PNG")
        with urllib.request.urlopen(url + "&download=1", timeout=3) as response:
            assert response.headers["Content-Disposition"] == 'attachment; filename="Alice-generated-image.png"'
            assert response.read().startswith(b"\x89PNG")
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(url.replace("private-session", "wrong-session"), timeout=3)
        assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)

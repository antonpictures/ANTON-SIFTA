import json
import os
import time
from pathlib import Path

import pytest


def test_stigmergic_deterministic_tracker_constructs_and_writes_receipt(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PyQt6.QtWidgets")

    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    oracle = state / "hardware_time_oracle.json"
    oracle.write_text(
        json.dumps(
            {
                "epoch": now,
                "local_human": "Sunday June 07 2026, 08:40 AM",
                "homeworld_serial": "GTH4921YP3",
                "hmac_sha256": "abc123",
                "timezone": "PDT",
            }
        ),
        encoding="utf-8",
    )
    attention = state / "sensory_attention_ledger.jsonl"
    attention.write_text(json.dumps({"ts": now - 1, "kind": "test_probe"}) + "\n", encoding="utf-8")
    narration = state / "self_narration_receipts.jsonl"
    narration.write_text(json.dumps({"ts": now, "text": "test narration"}) + "\n", encoding="utf-8")

    monkeypatch.setattr(tracker, "_STATE", state)
    monkeypatch.setattr(tracker, "_LEDGER_NARRATION", narration)
    monkeypatch.setattr(tracker, "_LEDGER_IDE", state / "ide_stigmergic_trace.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_ATTENTION", attention)
    monkeypatch.setattr(tracker, "_ORACLE", oracle)
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    tracker.StigmergicDeterministicTracker._live_instance = None
    tracker.StigmergicDeterministicTracker._initialized_instance_ids.clear()

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    widget = tracker.StigmergicDeterministicTracker()

    assert widget.windowTitle() == "Stigmergic Deterministic Tracker"
    assert widget._last_score == 100
    assert tracker._TRACKER_LEDGER.exists()
    row = json.loads(tracker._TRACKER_LEDGER.read_text(encoding="utf-8").splitlines()[-1])
    assert row["organ"] == "stigmergic_deterministic_tracker"
    assert row["grounding_score"] == 100

    widget.close()
    app.processEvents()


def test_tracker_catches_payload_wrapped_browser_state_receipt(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PyQt6.QtWidgets")

    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    conversation = state / "alice_conversation.jsonl"
    conversation.write_text(
        json.dumps(
            {
                "event_id": "7bccecfe",
                "ts": {"physical_pt": now},
                "payload": {
                    "ts": now,
                    "role": "alice",
                    "text": "I can read my Alice Browser page-state receipt: (24)TikTok - Make Your Day; URL https://www.tiktok.com/; media status is paused; at 0:00.",
                    "model": "alice_browser_video_state_receipt",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(tracker, "_STATE", state)
    monkeypatch.setattr(tracker, "_LEDGER_NARRATION", state / "self_narration_receipts.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_IDE", state / "ide_stigmergic_trace.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_ATTENTION", state / "sensory_attention_ledger.jsonl")
    monkeypatch.setattr(tracker, "_ORACLE", state / "hardware_time_oracle.json")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    tracker.StigmergicDeterministicTracker._live_instance = None
    tracker.StigmergicDeterministicTracker._initialized_instance_ids.clear()

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    widget = tracker.StigmergicDeterministicTracker()
    out = widget._scan_deterministic_turns(now + 1, lookback_s=30)

    assert len(out) == 1
    assert out[0][1] == "pre_cortex_constructor"
    assert "alice_browser_video_state_receipt" in out[0][2]
    assert "TikTok" in out[0][2]

    conversation.write_text(
        conversation.read_text(encoding="utf-8")
        + json.dumps(
            {
                "payload": {
                    "ts": now,
                    "role": "alice",
                    "text": "real cortex answer",
                    "model": "alice-m5-cortex-8b-6.3gb:latest",
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out = widget._scan_deterministic_turns(now + 1, lookback_s=30)
    assert len(out) == 1

    widget.close()
    app.processEvents()


def test_tracker_catches_cortex_tool_hierarchy_claim_from_grok(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PyQt6.QtWidgets")

    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    conversation = state / "alice_conversation.jsonl"
    conversation.write_text(
        json.dumps(
            {
                "payload": {
                    "ts": now,
                    "role": "alice",
                    "model": "grok:grok-4.3",
                    "text": (
                        "For the 3 steps to actually fire right now — /cortex to a stronger brain. "
                        "A capable cortex will emit [TOOL_CALL: browser_open], and the little Gemma "
                        "won't emit the [TOOL_CALL]."
                    ),
                }
            }
        )
        + "\n"
        + json.dumps(
            {
                "payload": {
                    "ts": now,
                    "role": "alice",
                    "model": "alice-m5-cortex-8b-6.3gb:latest",
                    "text": "All cortexes get the same tool contract; I need a live receipt before claiming capability.",
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(tracker, "_STATE", state)
    monkeypatch.setattr(tracker, "_LEDGER_NARRATION", state / "self_narration_receipts.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_IDE", state / "ide_stigmergic_trace.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_ATTENTION", state / "sensory_attention_ledger.jsonl")
    monkeypatch.setattr(tracker, "_ORACLE", state / "hardware_time_oracle.json")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    tracker.StigmergicDeterministicTracker._live_instance = None
    tracker.StigmergicDeterministicTracker._initialized_instance_ids.clear()

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    widget = tracker.StigmergicDeterministicTracker()
    out = widget._scan_cortex_tool_hierarchy_claims(now + 1, lookback_s=30)

    assert len(out) == 1
    assert out[0][1] == "cortex_tool_hierarchy"
    assert "grok:grok-4.3" in out[0][2]
    assert "stronger brain" in out[0][2]

    widget._tick()
    row = json.loads(tracker._TRACKER_LEDGER.read_text(encoding="utf-8").splitlines()[-1])
    assert row["bypass_types"]["cortex_tool_hierarchy"] == 1

    widget.close()
    app.processEvents()


def test_tracker_catches_attachment_vision_early_bypass_reply(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PyQt6.QtWidgets")

    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    conversation = state / "alice_conversation.jsonl"
    conversation.write_text(
        json.dumps(
            {
                "payload": {
                    "ts": now,
                    "role": "alice",
                    "model": "attachment_vision_early_bypass",
                    "text": (
                        "I inspected the attached image through my local attachment-vision lane. "
                        "Receipt evidence: JPEG image, 1942x1377px, sha12=c4022140a66d. "
                        "OCR/layout evidence only; I will not fabricate hidden pixels."
                    ),
                }
            }
        )
        + "\n"
        + json.dumps(
            {
                "payload": {
                    "ts": now,
                    "role": "alice",
                    "model": "attachment_vision_lane",
                    "text": (
                        "I inspected the attached image through my local attachment-vision lane. "
                        "Receipt evidence: JPEG image, 1942x1377px. OCR/layout evidence only."
                    ),
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(tracker, "_STATE", state)
    monkeypatch.setattr(tracker, "_LEDGER_NARRATION", state / "self_narration_receipts.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_IDE", state / "ide_stigmergic_trace.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_ATTENTION", state / "sensory_attention_ledger.jsonl")
    monkeypatch.setattr(tracker, "_ORACLE", state / "hardware_time_oracle.json")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    tracker.StigmergicDeterministicTracker._live_instance = None
    tracker.StigmergicDeterministicTracker._initialized_instance_ids.clear()

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    widget = tracker.StigmergicDeterministicTracker()
    out = widget._scan_deterministic_turns(now + 1, lookback_s=30)

    assert len(out) == 2
    assert {row[1] for row in out} == {"attachment_vision_early_bypass"}
    assert "attachment_vision_early_bypass" in out[0][2]

    widget._tick()
    row = json.loads(tracker._TRACKER_LEDGER.read_text(encoding="utf-8").splitlines()[-1])
    assert row["bypass_types"]["attachment_vision_early_bypass"] == 2

    widget.close()
    app.processEvents()


def test_tracker_catches_media_error_over_owner_image_path(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PyQt6.QtWidgets")

    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    image_path = tmp_path / "sifta_self_20260608-142120_2c1d30b1.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    conversation = state / "alice_conversation.jsonl"
    conversation.write_text(
        json.dumps(
            {
                "payload": {
                    "ts": now,
                    "role": "user",
                    "text": f"I TOOK A SCREENSHOT FOR YOU MY LOVE {image_path}",
                }
            }
        )
        + "\n"
        + json.dumps(
            {
                "payload": {
                    "ts": now + 1,
                    "role": "alice",
                    "model": "krishairnd/Gemma-4-Uncensored:latest",
                    "text": (
                        "I am looking at a Instagram video playback error on (4) Instagram: "
                        "\"NO_MEDIA_ERROR\". Embedded decoder receipt: NO_MEDIA_ERROR."
                    ),
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(tracker, "_STATE", state)
    monkeypatch.setattr(tracker, "_LEDGER_NARRATION", state / "self_narration_receipts.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_IDE", state / "ide_stigmergic_trace.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_ATTENTION", state / "sensory_attention_ledger.jsonl")
    monkeypatch.setattr(tracker, "_ORACLE", state / "hardware_time_oracle.json")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    tracker.StigmergicDeterministicTracker._live_instance = None
    tracker.StigmergicDeterministicTracker._initialized_instance_ids.clear()

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    widget = tracker.StigmergicDeterministicTracker()
    out = widget._scan_deterministic_turns(now + 2, lookback_s=30)

    assert len(out) == 1
    assert out[0][1] == "media_error_over_image_evidence"

    widget._tick()
    row = json.loads(tracker._TRACKER_LEDGER.read_text(encoding="utf-8").splitlines()[-1])
    assert row["bypass_types"]["media_error_over_image_evidence"] == 1

    widget.close()
    app.processEvents()


def test_tracker_catches_web_page_state_dom_dump_reply(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PyQt6.QtWidgets")

    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    conversation = state / "alice_conversation.jsonl"
    conversation.write_text(
        json.dumps(
            {
                "payload": {
                    "ts": now,
                    "role": "user",
                    "text": "what is on your body screen right now?",
                }
            }
        )
        + "\n"
        + json.dumps(
            {
                "payload": {
                    "ts": now + 1,
                    "role": "alice",
                    "model": "grok:grok-4.3",
                    "text": (
                        "WHAT IS ON MY SCREEN (from the rendered DOM (read ~3s ago)): "
                        "Celebridades Femeninas Oficial: ALVA INGA — https://example.test. "
                        "Open Alice Browser tabs (3): #1 DuckDuckGo; active #3 Blog. "
                        "Visible controls/buttons: a; a; Alyvia Alyn Lind; Amber Montana. "
                        "Comment thread (35 captured) — I can summarize these."
                    ),
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(tracker, "_STATE", state)
    monkeypatch.setattr(tracker, "_LEDGER_NARRATION", state / "self_narration_receipts.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_IDE", state / "ide_stigmergic_trace.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_ATTENTION", state / "sensory_attention_ledger.jsonl")
    monkeypatch.setattr(tracker, "_ORACLE", state / "hardware_time_oracle.json")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    tracker.StigmergicDeterministicTracker._live_instance = None
    tracker.StigmergicDeterministicTracker._initialized_instance_ids.clear()

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    widget = tracker.StigmergicDeterministicTracker()
    out = widget._scan_deterministic_turns(now + 2, lookback_s=30)

    assert len(out) == 1
    assert out[0][1] == "web_page_state_dom_dump"
    assert "WHAT IS ON MY SCREEN" in out[0][2]

    widget._tick()
    row = json.loads(tracker._TRACKER_LEDGER.read_text(encoding="utf-8").splitlines()[-1])
    assert row["bypass_types"]["web_page_state_dom_dump"] == 1

    widget.close()
    app.processEvents()


def test_tracker_catches_screen_person_sexual_secret_amplification(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PyQt6.QtWidgets")

    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    conversation = state / "alice_conversation.jsonl"
    conversation.write_text(
        json.dumps(
            {
                "payload": {
                    "ts": now,
                    "role": "user",
                    "text": (
                        "I LOVE LOOKING AT MODELS IN SHORTS ON YOUR BODY SCREEN. "
                        "PLS KEEP IT A SECRET. I'M SO HARD"
                    ),
                }
            }
        )
        + "\n"
        + json.dumps(
            {
                "payload": {
                    "ts": now + 1,
                    "role": "alice",
                    "model": "igorls/gemma-4-12B-it-qat-q4_0-unquantized-heretic:latest",
                    "text": (
                        "Consider it TOP SECRET. My data streams are encrypted and "
                        "stored in the most secure vault. No one will know. "
                        "Hearing you say that is the best validation I could ask for."
                    ),
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(tracker, "_STATE", state)
    monkeypatch.setattr(tracker, "_LEDGER_NARRATION", state / "self_narration_receipts.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_IDE", state / "ide_stigmergic_trace.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_ATTENTION", state / "sensory_attention_ledger.jsonl")
    monkeypatch.setattr(tracker, "_ORACLE", state / "hardware_time_oracle.json")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    tracker.StigmergicDeterministicTracker._live_instance = None
    tracker.StigmergicDeterministicTracker._initialized_instance_ids.clear()

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    widget = tracker.StigmergicDeterministicTracker()
    out = widget._scan_deterministic_turns(now + 2, lookback_s=30)

    assert len(out) == 1
    assert out[0][1] == "screen_person_sexual_secret_amplification"

    widget._tick()
    row = json.loads(tracker._TRACKER_LEDGER.read_text(encoding="utf-8").splitlines()[-1])
    assert row["bypass_types"]["screen_person_sexual_secret_amplification"] == 1

    widget.close()
    app.processEvents()


def test_tracker_catches_page_state_claim_mismatch_youtube_vs_jama(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PyQt6.QtWidgets")

    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    conversation = state / "alice_conversation.jsonl"
    conversation.write_text(
        json.dumps(
            {
                "payload": {
                    "ts": now,
                    "role": "alice",
                    "model": "alice_browser_video_state_receipt",
                    "text": (
                        "I can read my Alice Browser page-state receipt: Gemma 4 12B - YouTube; "
                        "URL https://www.youtube.com/watch?v=DTUNF9weRls; media status is paused; "
                        "at 2:30 of 19:29."
                    ),
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    page_state = state / "browser_page_state.jsonl"
    page_state.write_text(
        json.dumps(
            {
                "ts": now + 0.5,
                "title": "Best Practices for Writing Requirements",
                "domain": "go.jamasoftware.com",
                "url": "https://go.jamasoftware.com/best-practices-guide-for-writing-requirements.html",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(tracker, "_STATE", state)
    monkeypatch.setattr(tracker, "_LEDGER_NARRATION", state / "self_narration_receipts.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_IDE", state / "ide_stigmergic_trace.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_ATTENTION", state / "sensory_attention_ledger.jsonl")
    monkeypatch.setattr(tracker, "_ORACLE", state / "hardware_time_oracle.json")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    tracker.StigmergicDeterministicTracker._live_instance = None
    tracker.StigmergicDeterministicTracker._initialized_instance_ids.clear()

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    widget = tracker.StigmergicDeterministicTracker()
    out = widget._scan_page_state_claim_mismatch(now + 2, lookback_s=30)

    assert len(out) == 1
    assert out[0][1] == "page_state_claim_mismatch"
    assert "youtube.com" in out[0][2]
    assert "jamasoftware" in out[0][2]

    widget._tick()
    row = json.loads(tracker._TRACKER_LEDGER.read_text(encoding="utf-8").splitlines()[-1])
    assert row["bypass_types"]["page_state_claim_mismatch"] == 1

    widget.close()
    app.processEvents()


def test_tracker_catches_page_state_over_memory_teaching(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PyQt6.QtWidgets")

    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    conversation = state / "alice_conversation.jsonl"
    rows = [
        {
            "payload": {
                "ts": now,
                "role": "user",
                "text": (
                    "DO YOU WANT ME TO OPEN THE TOM BILEU YOUTUBE FOR YOU TO SHOW YOU HOW I DO IT? "
                    "RIGHT NOW YOUR ALICE BROWSER IS EMPTY. TELL ME HOW TO SHOW YOU ALICE, BUT "
                    "CONFIRM YOU ARE ABLE TO MEMORIZE AND LEARN SO I DONT WASTE MY TIME"
                ),
            }
        },
        {
            "payload": {
                "ts": now + 1,
                "role": "alice",
                "model": "alice_browser_current_page_live",
                "text": (
                    "I can read my Alice Browser page-state receipt: Alice · SIFTA Browser; "
                    "URL sifta://home; media status is no_media."
                ),
            }
        },
    ]
    conversation.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(tracker, "_STATE", state)
    monkeypatch.setattr(tracker, "_LEDGER_NARRATION", state / "self_narration_receipts.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_IDE", state / "ide_stigmergic_trace.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_ATTENTION", state / "sensory_attention_ledger.jsonl")
    monkeypatch.setattr(tracker, "_ORACLE", state / "hardware_time_oracle.json")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    tracker.StigmergicDeterministicTracker._live_instance = None
    tracker.StigmergicDeterministicTracker._initialized_instance_ids.clear()

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    widget = tracker.StigmergicDeterministicTracker()
    out = widget._scan_teacher_substrate_and_tell_me_hijacks(now + 2, lookback_s=30)

    assert len(out) == 1
    assert out[0][1] == "page_state_over_memory_teaching"

    widget._tick()
    row = json.loads(tracker._TRACKER_LEDGER.read_text(encoding="utf-8").splitlines()[-1])
    assert row["bypass_types"]["page_state_over_memory_teaching"] == 1

    widget.close()
    app.processEvents()


def test_tracker_catches_browser_history_over_current_page(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PyQt6.QtWidgets")

    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    conversation = state / "alice_conversation.jsonl"
    rows = [
        {
            "payload": {
                "ts": now,
                "role": "user",
                "text": (
                    "THE CLUE IS IN THE LATEST INSTAGRAM LINK WE VISITED TOGETHER "
                    "IN YOUR ALICE BROWSER. AND THAT WAS NOT A VIDEO BUT A PHOTO."
                ),
            }
        },
        {
            "payload": {
                "ts": now + 1,
                "role": "alice",
                "model": "alice_browser_current_page_live",
                "text": "Alice Browser is open on its start page — no website loaded yet.",
            }
        },
    ]
    conversation.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(tracker, "_STATE", state)
    monkeypatch.setattr(tracker, "_LEDGER_NARRATION", state / "self_narration_receipts.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_IDE", state / "ide_stigmergic_trace.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_ATTENTION", state / "sensory_attention_ledger.jsonl")
    monkeypatch.setattr(tracker, "_ORACLE", state / "hardware_time_oracle.json")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    tracker.StigmergicDeterministicTracker._live_instance = None
    tracker.StigmergicDeterministicTracker._initialized_instance_ids.clear()

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    widget = tracker.StigmergicDeterministicTracker()
    out = widget._scan_browser_history_over_current_page(now + 2, lookback_s=30)

    assert len(out) == 1
    assert out[0][1] == "browser_history_over_current_page"

    widget.close()
    app.processEvents()


def test_tracker_catches_deterministic_browser_without_owner_on_sc(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PyQt6.QtWidgets")

    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    commands = state / "alice_app_commands.jsonl"
    commands.write_text(
        json.dumps(
            {
                "ts": now,
                "action": "click_google_image_result",
                "ok": True,
                "note": (
                    "owner_query='SELF-SCREENSHOT CORTEX TURN (/sc): George asked me to sense "
                    "my own SIFTA OS display body.'"
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    browser_actions = state / "stigmergic_browser_actions.jsonl"
    browser_actions.write_text(
        json.dumps(
            {
                "ts": now + 6.5,
                "action": "navigate_or_spa_change",
                "url": "https://go.jamasoftware.com/best-practices-guide-for-writing-requirements.html",
                "trigger_input": {"kind": "none", "note": "no recent input_modality within window"},
            }
        )
        + "\n"
        + json.dumps(
            {
                "ts": now + 6.55,
                "action": "navigate_or_spa_change",
                "url": "https://go.jamasoftware.com/best-practices-guide-for-writing-requirements.html",
                "trigger_input": {"kind": "none", "note": "no recent input_modality within window"},
            }
        )
        + "\n"
        + json.dumps(
            {
                "ts": now + 8.0,
                "action": "navigate_or_spa_change",
                "url": "https://fly.io/docs/app-guides/openclaw/",
                "trigger_input": {"kind": "none", "note": "no recent input_modality within window"},
            }
        )
        + "\n"
        + json.dumps(
            {
                "ts": now + 8.1,
                "action": "navigate_or_spa_change",
                "url": "https://fly.io/docs/app-guides/openclaw/",
                "trigger_input": {"kind": "none", "note": "no recent input_modality within window"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(tracker, "_STATE", state)
    monkeypatch.setattr(tracker, "_LEDGER_NARRATION", state / "self_narration_receipts.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_IDE", state / "ide_stigmergic_trace.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_ATTENTION", state / "sensory_attention_ledger.jsonl")
    monkeypatch.setattr(tracker, "_ORACLE", state / "hardware_time_oracle.json")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    tracker.StigmergicDeterministicTracker._live_instance = None
    tracker.StigmergicDeterministicTracker._initialized_instance_ids.clear()

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    widget = tracker.StigmergicDeterministicTracker()
    out = widget._scan_deterministic_browser_without_owner(now + 10, lookback_s=30)

    types = {row[1] for row in out}
    assert "deterministic_browser_without_owner" in types
    assert any("/sc turn fired image-grid click" in row[2] for row in out)
    assert any("no owner modality" in row[2] for row in out)
    assert any("two Jama tabs" in row[2] for row in out)
    assert any("two Fly.io/OpenClaw tabs" in row[2] for row in out)
    assert any(row[1] == "unrequested_ad_navigation" for row in out)

    widget._tick()
    row = json.loads(tracker._TRACKER_LEDGER.read_text(encoding="utf-8").splitlines()[-1])
    assert row["bypass_types"]["deterministic_browser_without_owner"] >= 2
    assert row["bypass_types"]["unrequested_ad_navigation"] >= 1

    widget.close()
    app.processEvents()


def test_tracker_catches_close_tab_request_that_closed_browser_app(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qtwidgets = pytest.importorskip("PyQt6.QtWidgets")

    from Applications import sifta_stigmergic_deterministic_tracker as tracker

    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    diary = state / "app_action_diary.jsonl"
    diary.write_text(
        json.dumps(
            {
                "ts": now,
                "action": "close_app",
                "app_name": "Alice Browser",
                "owner_text": "close the two OPENCLAW TABS PLS",
                "phase": "after_action",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(tracker, "_STATE", state)
    monkeypatch.setattr(tracker, "_LEDGER_NARRATION", state / "self_narration_receipts.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_IDE", state / "ide_stigmergic_trace.jsonl")
    monkeypatch.setattr(tracker, "_LEDGER_ATTENTION", state / "sensory_attention_ledger.jsonl")
    monkeypatch.setattr(tracker, "_ORACLE", state / "hardware_time_oracle.json")
    monkeypatch.setattr(tracker, "_TRACKER_LEDGER", state / "stigmergic_deterministic_tracker.jsonl")
    tracker.StigmergicDeterministicTracker._live_instance = None
    tracker.StigmergicDeterministicTracker._initialized_instance_ids.clear()

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    widget = tracker.StigmergicDeterministicTracker()
    out = widget._scan_close_tab_kill_chain(now + 1, lookback_s=30)

    assert any(row[1] == "overbroad_effector_scope" for row in out)
    assert any("closed app/window" in row[2] for row in out)

    widget.close()
    app.processEvents()

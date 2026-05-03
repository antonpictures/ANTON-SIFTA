import json
import time

from System import swarm_media_ingress_gate as gate


def test_observed_media_summary_keeps_jensen_nvidia_topic_across_long_run(monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    monkeypatch.setattr(gate, "LEDGER", tmp_path / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", tmp_path / "ambient_media_context.json")

    decision = {
        "route": "observed_media",
        "reason": "media_focus_default_to_observed",
        "confidence": 0.8,
    }
    gate.write_gate_receipt(
        decision,
        text=(
            "Jensen Huang explains NVIDIA GTC, GPUs, CUDA, AI factories, "
            "data centers, TSMC, chips, tokens, agents, and compute scaling."
        ),
        stt_conf=0.57,
        focus_context="shared_media youtube interview",
    )
    for i in range(8):
        gate.write_gate_receipt(
            decision,
            text=f"later transcript fragment {i} says process, leadership, supply chain, and systems",
            stt_conf=0.52,
            focus_context="shared_media youtube interview",
        )

    ctx = gate.get_latest_observed_media_context(max_age_s=60.0)

    assert "last_input_routing route=observed_media" in ctx
    assert "if George asks what was noisy" in ctx
    assert "observed_media_summary" in ctx
    assert "Jensen Huang" in ctx
    assert "NVIDIA" in ctx
    assert "GPU" in ctx
    assert "these are environmental media receipts, not George speaking" in ctx


def test_observed_media_summary_ages_out(monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    monkeypatch.setattr(gate, "LEDGER", tmp_path / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", tmp_path / "ambient_media_context.json")

    gate.write_gate_receipt(
        {"route": "observed_media", "reason": "media_focus_default_to_observed", "confidence": 0.8},
        text="Jensen Huang NVIDIA interview",
        stt_conf=0.57,
        focus_context="shared_media youtube interview",
    )
    rows = gate._tail_jsonl(gate.LEDGER, 1)
    rows[0]["ts"] = time.time() - 9999
    gate.LEDGER.write_text(gate.json.dumps(rows[0]) + "\n", encoding="utf-8")

    assert gate.get_latest_observed_media_context(max_age_s=1.0) == ""


def test_observed_media_summary_lists_multiple_recent_youtube_videos(monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    monkeypatch.setattr(gate, "LEDGER", tmp_path / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", tmp_path / "ambient_media_context.json")
    monkeypatch.setattr(gate, "YOUTUBE_CONTEXT_LEDGER", tmp_path / "youtube_context.jsonl")
    monkeypatch.setattr(gate, "YOUTUBE_WATCH_LEDGER", tmp_path / "youtube_watch_memory.jsonl")

    now = time.time()
    rows = [
        {
            "ts": now - 1200,
            "title": "Snatch - Best of Brick top (+ deleted scene)",
            "video_id": "IXugVZMsZ24",
            "status": "no_captions",
        },
        {
            "ts": now - 900,
            "title": "Disappearances of scientists & debate over possible threats | Backscroll",
            "video_id": "Cdxnif3QZ8A",
            "status": "empty_captions",
        },
        {
            "ts": now - 600,
            "title": "Every company needs an OpenClaw strategy: Jensen Huang claims at Nvidia GTC 2026",
            "video_id": "x5IX5Uleb9g",
            "status": "empty_captions",
        },
    ]
    gate.YOUTUBE_CONTEXT_LEDGER.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )

    ctx = gate.get_latest_observed_media_context(max_age_s=3600.0)

    assert "recent_youtube_videos=" in ctx
    assert "Snatch" in ctx
    assert "Disappearances of scientists" in ctx
    assert "Jensen Huang" in ctx
    assert "IXugVZMsZ24" in ctx


def test_observed_media_summary_dedupes_context_and_watch_memory(monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    monkeypatch.setattr(gate, "LEDGER", tmp_path / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", tmp_path / "ambient_media_context.json")
    monkeypatch.setattr(gate, "YOUTUBE_CONTEXT_LEDGER", tmp_path / "youtube_context.jsonl")
    monkeypatch.setattr(gate, "YOUTUBE_WATCH_LEDGER", tmp_path / "youtube_watch_memory.jsonl")

    now = time.time()
    gate.YOUTUBE_CONTEXT_LEDGER.write_text(
        json.dumps(
            {
                "ts": now - 90,
                "title": "Jensen Huang interview",
                "video_id": "same_video",
                "status": "empty_captions",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    gate.YOUTUBE_WATCH_LEDGER.write_text(
        json.dumps(
            {
                "ts": now - 60,
                "title": "Jensen Huang interview duplicate",
                "youtube_video_id": "same_video",
                "status": "observed",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    ctx = gate.get_latest_observed_media_context(max_age_s=3600.0)

    assert ctx.count("same_video") == 1


def test_latest_ambient_media_receipt_answers_what_was_noisy(monkeypatch, tmp_path):
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)
    monkeypatch.setattr(gate, "LEDGER", tmp_path / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", tmp_path / "ambient_media_context.json")

    gate.write_gate_receipt(
        {
            "route": "ambient_media",
            "reason": "owner_declared_background_media_youtube",
            "confidence": 0.9,
        },
        text="OpenAI will revamp Codex and the desktop agent will operate every app.",
        stt_conf=0.62,
        focus_context="ambient_media_youtube owner declared",
    )

    ctx = gate.get_latest_observed_media_context(max_age_s=60.0)

    assert "last_input_routing route=ambient_media" in ctx
    assert "owner_declared_background_media_youtube" in ctx
    assert "suppressed as environmental media, not George speaking" in ctx
    assert "OpenAI will revamp Codex" in ctx

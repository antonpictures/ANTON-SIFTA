import json
import time
from pathlib import Path

from System import swarm_media_session_memory as mem


def _fixed_now() -> float:
    # 2026-05-02 15:17 local time.
    return time.mktime((2026, 5, 2, 15, 17, 0, 0, 0, -1))


def _write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def test_infer_nap_window_from_user_clock_language():
    window = mem.infer_media_session_window(
        "now is 3:17pm, I went to take a nap at 11 am or so",
        now=_fixed_now(),
    )

    assert window["matched"] is True
    assert window["specificity"] == "explicit_clock_window"
    assert 4 * 3600 <= window["duration_s"] <= 5 * 3600


def test_summarize_media_session_returns_multiple_likely_videos(tmp_path):
    now = _fixed_now()
    start = time.mktime((2026, 5, 2, 11, 0, 0, 0, 0, -1))
    rows = [
        {
            "ts": start + 20 * 60,
            "title": "Snatch - Best of Brick top",
            "video_id": "IXugVZMsZ24",
            "status": "no_captions",
        },
        {
            "ts": start + 85 * 60,
            "title": "Disappearances of scientists & debate over possible threats | Backscroll",
            "video_id": "Cdxnif3QZ8A",
            "status": "empty_captions",
        },
        {
            "ts": start + 170 * 60,
            "title": "Every company needs an OpenClaw strategy: Jensen Huang at Nvidia GTC",
            "video_id": "x5IX5Uleb9g",
            "status": "empty_captions",
        },
        {
            "ts": start - 3 * 3600,
            "title": "Old unrelated video",
            "video_id": "old000",
            "status": "old",
        },
    ]
    _write_jsonl(tmp_path / "youtube_context.jsonl", rows)
    _write_jsonl(
        tmp_path / "media_ingress_gate.jsonl",
        [
            {
                "ts": start + 30 * 60,
                "route": "ambient_media",
                "reason": "owner_declared_background_media_youtube",
                "text_preview": "Jensen Huang NVIDIA GPUs and AI factories",
                "focus_preview": "frontmost youtube",
            },
            {
                "ts": start + 180 * 60,
                "route": "observed_media",
                "reason": "media_focus_default_to_observed",
                "text_preview": "NVIDIA GTC data centers and chips",
                "focus_preview": "frontmost youtube",
            },
        ],
    )

    summary = mem.summarize_media_session(start, now, state_dir=tmp_path)

    assert summary["truth_label"] == mem.TRUTH_LABEL
    assert summary["n_videos"] == 3
    titles = " ".join(item["title"] for item in summary["videos"])
    assert "Snatch" in titles
    assert "Disappearances of scientists" in titles
    assert "Jensen Huang" in titles
    assert "Old unrelated" not in titles
    assert summary["confidence"] >= 0.8


def test_latest_media_session_context_is_receipt_grounded(tmp_path):
    now = _fixed_now()
    start = time.mktime((2026, 5, 2, 11, 0, 0, 0, 0, -1))
    _write_jsonl(
        tmp_path / "youtube_context.jsonl",
        [
            {
                "ts": start + 60,
                "title": "Snatch - Best of Brick top",
                "video_id": "IXugVZMsZ24",
                "status": "no_captions",
            }
        ],
    )

    ctx = mem.latest_media_session_context(
        "now is 3:17pm, I was napping since 11 am; what did you hear?",
        now=now,
        state_dir=tmp_path,
    )

    assert "media_session_memory" in ctx
    assert "Snatch" in ctx
    assert "IXugVZMsZ24" in ctx
    assert "latest video alone" in ctx


def test_latest_media_session_context_ignores_unrelated_turn(tmp_path):
    assert mem.latest_media_session_context("what is the weather?", state_dir=tmp_path) == ""


def test_default_session_tolerance_catches_or_so_video_start(tmp_path):
    now = _fixed_now()
    start = time.mktime((2026, 5, 2, 11, 0, 0, 0, 0, -1))
    _write_jsonl(
        tmp_path / "youtube_context.jsonl",
        [
            {
                "ts": start - 35 * 60,
                "title": "Jensen Huang NVIDIA interview",
                "video_id": "carry_forward",
                "status": "empty_captions",
            }
        ],
    )
    _write_jsonl(
        tmp_path / "media_ingress_gate.jsonl",
        [
            {
                "ts": start + 10 * 60,
                "route": "ambient_media",
                "reason": "owner_declared_background_media_youtube",
                "text_preview": "NVIDIA GPUs AI factories and tokens",
            }
        ],
    )

    ctx = mem.latest_media_session_context(
        "now is 3:17pm, I was napping since 11 am or so",
        now=now,
        state_dir=tmp_path,
    )

    assert "carry_forward" in ctx
    assert "Jensen Huang" in ctx

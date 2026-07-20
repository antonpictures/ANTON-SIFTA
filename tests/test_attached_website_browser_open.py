from __future__ import annotations

import sys
import os
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import Applications.sifta_talk_to_alice_widget as talk  # noqa: E402


def test_attached_website_open_detected() -> None:
    text = "detect the website attached and open it in your browser"
    assert talk._is_attached_website_open_query(text)
    assert not talk._is_browser_photo_open_query(text)


def test_attached_website_open_not_routed_to_photo_click_bridge() -> None:
    text = "detect the website attached and open it in your browser"
    assert talk._hallucination_bridge_synthesize_photo_select_action(text, "I see an interface.") is None


def test_synthesize_attached_website_open_command_from_ocr(tmp_path, monkeypatch) -> None:
    image = tmp_path / "screen.jpg"
    image.write_bytes(b"\xff\xd8\xff" + b"x" * 40)

    def fake_inspect(image_path: str, **_: object) -> SimpleNamespace:
        assert Path(image_path) == image
        return SimpleNamespace(
            ok=True,
            ocr_rows=(
                {"text": "https://x.com/compose/post"},
                {"text": "Home"},
                {"text": "For you"},
            ),
        )

    monkeypatch.setattr(
        "System.swarm_attachment_vision_lane.inspect_attachment_image",
        fake_inspect,
    )

    cmd = talk._synthesize_attached_website_browser_open_command(
        "detect the website attached and open it in your browser",
        attachment_path=str(image),
        state_dir=tmp_path,
    )

    assert cmd is not None
    assert cmd["kind"] == "browser_url"
    assert cmd["url"] == "https://x.com/compose/post"
    assert cmd["contextual_search_source"] == "attached_website_browser_open"


def test_synthesize_attached_website_open_command_uses_history_attachment(tmp_path, monkeypatch) -> None:
    image = tmp_path / "screen.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 40)
    history = [{"role": "user", "content": "look", "image_path": str(image)}]

    monkeypatch.setattr(
        "System.swarm_attachment_vision_lane.inspect_attachment_image",
        lambda *_args, **_kwargs: SimpleNamespace(ok=True, ocr_rows=({"text": "perplexity.ai"},)),
    )

    cmd = talk._synthesize_attached_website_browser_open_command(
        "detect the website attached and open it in your browser",
        history=history,
        state_dir=tmp_path,
    )

    assert cmd is not None
    assert cmd["url"] == "https://perplexity.ai"


def test_synthesize_attached_website_open_command_rejects_stale_history_attachment(tmp_path, monkeypatch) -> None:
    image = tmp_path / "old_screen.jpg"
    image.write_bytes(b"\xff\xd8\xff\xd8" + b"z" * 40)
    stale_ts = time.time() - 60 * 60 * 24
    os.utime(image, (stale_ts, stale_ts))
    history = [{"role": "user", "content": "look", "image_path": str(image)}]

    monkeypatch.setattr(
        "System.swarm_attachment_vision_lane.inspect_attachment_image",
        lambda *_args, **_kwargs: SimpleNamespace(ok=True, ocr_rows=({"text": "perplexity.ai"},)),
    )

    cmd = talk._synthesize_attached_website_browser_open_command(
        "detect the website attached and open it in your browser",
        history=history,
        state_dir=tmp_path,
    )

    assert cmd is None


def test_synthesize_attached_website_open_command_uses_xiaomi_mimo_brand_fallback(tmp_path, monkeypatch) -> None:
    image = tmp_path / "mimo_console.jpg"
    image.write_bytes(b"\xff\xd8\xff" + b"x" * 40)

    monkeypatch.setattr(
        "System.swarm_attachment_vision_lane.inspect_attachment_image",
        lambda *_args, **_kwargs: SimpleNamespace(
            ok=True,
            ocr_rows=(
                {"text": "Xiaomi MIMO Console"},
                {"text": "All timestamps are displayed in UTC"},
            ),
        ),
    )

    cmd = talk._synthesize_attached_website_browser_open_command(
        "detect the website attached and open it in your browser",
        attachment_path=str(image),
        state_dir=tmp_path,
    )

    assert cmd is not None
    assert cmd["url"] == "https://www.xiaomimimo.com/"


def test_synthesize_attached_website_open_command_prefers_explicit_attachment_over_stale_history(tmp_path, monkeypatch) -> None:
    stale = tmp_path / "old_screen.jpg"
    stale.write_bytes(b"\xff\xd8\xff\xd8" + b"z" * 40)
    stale_ts = time.time() - 60 * 60 * 24
    os.utime(stale, (stale_ts, stale_ts))

    fresh = tmp_path / "new_screen.jpg"
    fresh.write_bytes(b"\xff\xd8\xff\xd8" + b"y" * 40)

    history = [{"role": "user", "content": "look", "image_path": str(stale)}]

    monkeypatch.setattr(
        "System.swarm_attachment_vision_lane.inspect_attachment_image",
        lambda *_args, **_kwargs: SimpleNamespace(ok=True, ocr_rows=({"text": "https://x.com/compose/post"},)),
    )

    cmd = talk._synthesize_attached_website_browser_open_command(
        "detect the website attached and open it in your browser",
        attachment_path=str(fresh),
        history=history,
        state_dir=tmp_path,
    )

    assert cmd is not None
    assert cmd["query"] == "https://x.com/compose/post"

#!/usr/bin/env python3
"""Tests: Alice describes the actual photo on the page (George 2026-05-30)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_browser_photo_description as pd


def test_record_and_read_description(tmp_path):
    pd.record_photo_description(
        "https://www.instagram.com/p/X/",
        description="A woman stands on a beach at sunset, hands in her hair, black top and light skirt, ocean behind.",
        arm="claude_agent", image_hash="abc123", image_ref="viewport/abc123.png",
        now=1000.0, state_dir=tmp_path,
    )
    p = pd.latest_photo_description(now=1001.0, state_dir=tmp_path)
    assert p["arm"] == "claude_agent" and p["source"] == "viewport"
    assert "beach at sunset" in p["description"]
    assert p["fresh"] is True


def test_url_filter_never_falls_back_to_other_page(tmp_path):
    pd.record_photo_description(
        "https://www.instagram.com/p/OLD/",
        description="old page: white cowboy hat and lace bikini",
        arm="claude_agent",
        now=1000.0,
        state_dir=tmp_path,
    )

    assert pd.latest_photo_description(
        url="https://www.instagram.com/p/NEW/",
        now=1001.0,
        state_dir=tmp_path,
    ) == {}
    assert pd.latest_same_url_photo_description(
        url="https://www.instagram.com/p/NEW/",
        now=1001.0,
        state_dir=tmp_path,
    ) == {}


def test_same_url_anchor_returns_prior_description_after_failed_scan(tmp_path):
    url = "https://www.instagram.com/p/CbVbizsJzKi/"
    pd.record_photo_description(
        url,
        description="colorful floral bikini top, green bikini bottoms, fuzzy green leg warmers",
        arm="claude_agent",
        now=1000.0,
        state_dir=tmp_path,
    )
    pd.record_photo_description(
        url,
        description="",
        arm="grok_agent",
        status="grok_eye_failed",
        now=1005.0,
        state_dir=tmp_path,
    )

    anchor = pd.latest_same_url_photo_description(url=url, now=1006.0, state_dir=tmp_path)

    assert anchor["same_url_anchor"] is True
    assert "green bikini bottoms" in anchor["description"]


def test_empty_is_honest_no_invention(tmp_path):
    block = pd.photo_description_block(state_dir=tmp_path)
    assert "not described the featured image yet" in block
    assert "will not invent" in block


def test_block_attributes_to_the_arm_with_freshness(tmp_path):
    pd.record_photo_description("https://x.com/p", description="a red car on a track",
                                arm="codex_agent", now=1000.0, state_dir=tmp_path)
    block = pd.photo_description_block(now=1010.0, state_dir=tmp_path)
    assert "seen by my codex_agent" in block
    assert "red car" in block


def test_pending_and_failed_not_surfaced_as_truth(tmp_path):
    pd.record_photo_description("https://x.com/p", description="", arm="cline_agent",
                                status="pending", now=1000.0, state_dir=tmp_path)
    pd.record_photo_description("https://x.com/p", description="", arm="cline_agent",
                                status="failed", now=1001.0, state_dir=tmp_path)
    assert pd.latest_photo_description(now=1002.0, state_dir=tmp_path) == {}


def test_latest_viewport_capture_surfaces_pending_viewport_image(tmp_path):
    img = tmp_path / "viewport.png"
    img.write_bytes(b"\x89PNG\r\nfake")
    pd.record_photo_description(
        "https://www.youtube.com/watch?v=P91dfSsHER4",
        description="",
        arm="ollama_vision_agent",
        image_hash="h1",
        image_ref=str(img),
        status="pending",
        source="viewport",
        now=1000.0,
        state_dir=tmp_path,
    )

    cap = pd.latest_viewport_capture(
        url="https://www.youtube.com/watch?v=P91dfSsHER4",
        now=1001.0,
        state_dir=tmp_path,
    )

    assert cap["status"] == "pending"
    assert cap["image_ref"] == str(img)
    assert cap["image_exists"] is True
    assert cap["fresh"] is True


def test_stale_flagged(tmp_path):
    pd.record_photo_description("https://x.com/p", description="a dog", arm="grok_agent",
                                now=1000.0, state_dir=tmp_path)
    assert "stale" in pd.photo_description_block(now=1000.0 + 9999, max_age_s=300, state_dir=tmp_path)


def test_pick_featured_prefers_og_image():
    feat = pd.pick_featured_image(
        [{"src": "https://x/small.jpg", "w": 100, "h": 100}],
        og_image="https://cdn/hero.jpg",
    )
    assert feat["src"] == "https://cdn/hero.jpg" and feat["reason"] == "og:image_meta"


def test_onscreen_image_beats_stale_og_image():
    # George 2026-05-30: IG og:image is a stale cover; the slide ON SCREEN must win.
    feat = pd.pick_featured_image(
        [{"src": "https://cdn/current_slide.jpg", "w": 1080, "h": 1350, "onscreen": 1080 * 900}],
        og_image="https://cdn/stale_cover.jpg",
    )
    assert feat["src"] == "https://cdn/current_slide.jpg"
    assert feat["reason"] == "largest_on_screen_image"


def test_offscreen_images_do_not_win():
    # A big natural image that is scrolled off-screen should not be picked over og.
    feat = pd.pick_featured_image(
        [{"src": "https://cdn/offscreen.jpg", "w": 2000, "h": 2000, "onscreen": 0}],
        og_image="https://cdn/cover.jpg",
    )
    assert feat["src"] == "https://cdn/cover.jpg"


def test_pick_featured_skips_avatars_and_tiny_picks_largest():
    feat = pd.pick_featured_image([
        {"src": "https://ig/avatar_profile_pic.jpg", "w": 800, "h": 800},  # avatar -> skip
        {"src": "https://ig/icon.png", "w": 32, "h": 32},                  # icon -> skip
        {"src": "https://ig/post_photo.jpg", "w": 1080, "h": 1350},        # the real post
        {"src": "https://ig/thumb.jpg", "w": 150, "h": 150},               # too small
    ])
    assert feat["src"] == "https://ig/post_photo.jpg"
    assert feat["reason"] == "largest_non_avatar_image"


def test_pick_featured_empty_when_nothing_qualifies():
    assert pd.pick_featured_image([{"src": "data:image/png;base64,xxx"}]) == {}
    assert pd.pick_featured_image([]) == {}


def test_extract_final_text_from_ndjson_stream():
    raw = "\n".join([
        '{"ts":"t","type":"hook_event","hookEventName":"agent_start","agentId":"a"}',
        '{"ts":"t","type":"agent_event","event":{"type":"content_start","contentType":"text","text":"A"}}',
        '{"ts":"t","type":"agent_event","event":{"type":"content_end","contentType":"text","text":"A woman stands by a kitchen counter holding a coffee cup."}}',
        '{"ts":"t","type":"agent_event","event":{"type":"done","reason":"completed","text":"A woman stands by a kitchen counter holding a coffee cup."}}',
        '{"ts":"t","type":"run_result","finishReason":"completed","text":"A woman stands by a kitchen counter holding a coffee cup."}',
    ])
    out = pd.extract_arm_final_text(raw)
    assert out == "A woman stands by a kitchen counter holding a coffee cup."
    assert "hook_event" not in out and "agent_event" not in out


def test_extract_final_text_from_claude_stream_json():
    # George 2026-05-30: claude_agent succeeded but its stream-json wasn't parsed,
    # so the correct description was lost ("no vision receipt came back").
    raw = "\n".join([
        '{"type":"system","subtype":"init"}',
        '{"type":"assistant","message":{"content":[{"type":"text","text":"A woman in a black halter top"}]}}',
        '{"type":"result","subtype":"success","result":"A woman in a black halter top and a fitted red satin skirt leans against a silver car outdoors.","is_error":false}',
    ])
    out = pd.extract_arm_final_text(raw)
    assert out == "A woman in a black halter top and a fitted red satin skirt leans against a silver car outdoors."


def test_extract_strips_base64_and_blobs():
    raw = 'Here is the image data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA' + ("Z" * 400)
    out = pd.extract_arm_final_text(raw)
    assert "base64" not in out and "ZZZZ" not in out
    assert "[image]" in out or "[blob]" in out


def test_extract_plaintext_passthrough():
    assert pd.extract_arm_final_text("A red car on a track.") == "A red car on a track."
    assert pd.extract_arm_final_text("") == ""


def test_extract_rejects_codex_cli_prompt_echo_without_final_answer():
    raw = (
        "warning: `--full-auto` is deprecated; use `--sandbox workspace-write` instead.\n"
        "Reading additional input from stdin...\n"
        "OpenAI Codex v0.133.0\n"
        "--------\n"
        "workdir: /Users/ioanganton/Music/ANTON_SIFTA\n"
        "model: gpt-5.5\n"
        "provider: openai\n"
        "--------\n"
        "user\n"
        "Read /Users/ioanganton/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md first.\n"
        "Look at the image at this exact path: /Users/ioanganton/Music/ANTON_SIFTA/.sifta_state/browser_viewport/viewport_1780597521825.png\n"
        "Describe the MAIN subject of the photo in 2 short sentences.\n"
    )
    assert pd.looks_like_non_visual_arm_reply(raw)
    assert pd.extract_arm_final_text(raw) == ""
    assert pd.clean_browser_photo_description_text(raw) == ""


def test_extract_codex_cli_speaker_marker_final_answer_from_image_run():
    raw = (
        "Reading additional input from stdin...\n"
        "OpenAI Codex v0.133.0\n"
        "--------\n"
        "workdir: /Users/ioanganton/Music/ANTON_SIFTA\n"
        "model: gpt-5.5\n"
        "provider: openai\n"
        "--------\n"
        "user\n"
        "Look at the image at this exact path: /Users/ioanganton/Music/ANTON_SIFTA/.sifta_state/browser_viewport/viewport_1780608373749.png\n"
        "This is Alice Browser's rendered viewport from Alice's own browser organ.\n"
        "\x1b[35m\x1b[3mcodex\x1b[0m\x1b[0m\n"
        "I’ve read the covenant and am now inspecting the browser viewport pixels from the provided path.\n"
        "\x1b[35m\x1b[3mcodex\x1b[0m\x1b[0m\n"
        "Four women pose outdoors around a silver light stand, wearing colorful bikini-style swimwear and barefoot on artificial turf. "
        "The setting is a sunny modern patio with glass doors, chairs, and hard shadows visible.\n"
        "\x1b[2mtokens used\x1b[0m\n"
        "23,066\n"
    )

    desc = pd.clean_browser_photo_description_text(raw)

    assert desc.startswith("Four women pose outdoors")
    assert "Look at the image at this exact path" not in desc
    assert not pd.looks_like_non_visual_arm_reply(desc)


def test_non_visual_arm_reply_is_not_counted_as_sight():
    reply = (
        "I’ve read the full `IDE_BOOT_COVENANT.md`. Can you describe the main large "
        "photo in `viewport_1780199539473.png`, or provide its contents, so I can "
        "provide the concise 2-sentence description you requested?"
    )
    assert pd.looks_like_non_visual_arm_reply(reply)
    assert not pd.looks_like_non_visual_arm_reply(
        "A woman in a brown-and-white bikini poses outdoors near a bright beach."
    )


def test_latest_photo_description_ignores_old_codex_cli_prompt_echo_rows(tmp_path):
    url = "https://x.com/abellaskies/status/1931210051844493757/photo/1"
    pd.record_photo_description(
        url,
        description="A woman sits on a pink ottoman in a mirror selfie; the room has white walls and a chair behind her.",
        arm="ollama_vision_agent",
        now=1000.0,
        state_dir=tmp_path,
    )
    pd.record_photo_description(
        url,
        description=(
            "OpenAI Codex v0.133.0\n"
            "workdir: /Users/ioanganton/Music/ANTON_SIFTA\n"
            "model: gpt-5.5\n"
            "provider: openai\n"
            "user\n"
            "Look at the image at this exact path: /Users/ioanganton/Music/ANTON_SIFTA/.sifta_state/browser_viewport/viewport.png\n"
            "Describe the MAIN subject of the photo."
        ),
        arm="codex_agent",
        now=1001.0,
        state_dir=tmp_path,
    )

    latest = pd.latest_photo_description(url=url, now=1002.0, state_dir=tmp_path)

    assert latest["arm"] == "ollama_vision_agent"
    assert "mirror selfie" in latest["description"]


def test_latest_photo_description_returns_empty_when_only_codex_prompt_echo_exists(tmp_path):
    pd.record_photo_description(
        "https://www.instagram.com/p/C1mzc4CvjRh/",
        description=(
            "OpenAI Codex v0.133.0\n"
            "Reading additional input from stdin...\n"
            "Look at the image at this exact path: /Users/ioanganton/Music/ANTON_SIFTA/.sifta_state/browser_viewport/viewport.png\n"
            "This is Alice Browser's rendered viewport from Alice's own browser organ."
        ),
        arm="codex_agent",
        now=1000.0,
        state_dir=tmp_path,
    )

    assert pd.latest_photo_description(now=1001.0, state_dir=tmp_path) == {}


def test_state_dir_root_or_state(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    pd.record_photo_description("https://x.com/p", description="x", arm="claude_agent", state_dir=sd)
    assert (sd / "browser_photo_descriptions.jsonl").exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

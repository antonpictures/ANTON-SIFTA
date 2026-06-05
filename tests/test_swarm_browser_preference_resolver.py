import json
from pathlib import Path

from System.swarm_browser_preference_resolver import (
    guard_preferred_link_reply,
    preference_prompt_block,
    record_preference_resolution,
    resolve_preferred_browser_link,
)
import Applications.sifta_talk_to_alice_widget as talk


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_preferred_link_uses_recent_context_not_stale_global_dwell(tmp_path):
    state = tmp_path / ".sifta_state"
    history = state / "alice_browse_history.jsonl"
    convo = state / "alice_conversation.jsonl"
    memory = state / "browser_stigmergic_memory.jsonl"
    now = 10_000.0

    _append(
        history,
        {
            "url": "https://example.com/old-favorite",
            "title": "Old high dwell page",
            "dwell_s": 700.0,
            "closed_at": now - 12 * 3600,
        },
    )
    _append(
        history,
        {
            "url": "https://x.com/currenthandle/media",
            "title": "Current person media / X",
            "dwell_s": 180.0,
            "closed_at": now - 60.0,
        },
    )
    _append(
        memory,
        {
            "url": "https://x.com/currenthandle/media",
            "title": "Current person media / X",
            "learned_description": "CurrentHandle is the visual page the owner called beautiful and amazing.",
        },
    )
    _append(
        convo,
        {
            "role": "user",
            "content": "I love this CurrentHandle page, it is beautiful.",
        },
    )

    preferred = resolve_preferred_browser_link(
        "open in browser something a link i like pls",
        state_dir=state,
        now=now,
    )

    assert preferred is not None
    assert preferred.url == "https://x.com/currenthandle/media"
    assert any("context_match" in reason for reason in preferred.reasons)


def test_preferred_link_excludes_home_and_search_pages(tmp_path):
    state = tmp_path / ".sifta_state"
    history = state / "alice_browse_history.jsonl"
    now = 20_000.0
    _append(history, {"url": "sifta://home", "title": "Alice Browser", "dwell_s": 900, "closed_at": now})
    _append(history, {"url": "https://x.com/home", "title": "Home / X", "dwell_s": 900, "closed_at": now})
    _append(history, {"url": "https://www.google.com/search?q=test", "title": "test - Google Search", "dwell_s": 900, "closed_at": now})
    _append(history, {"url": "https://www.instagram.com/p/abc123/", "title": "Instagram", "dwell_s": 12, "closed_at": now - 5})

    preferred = resolve_preferred_browser_link(
        "open a link i like in browser",
        state_dir=state,
        now=now,
    )

    assert preferred is not None
    assert preferred.url == "https://www.instagram.com/p/abc123/"


def test_preference_resolution_writes_receipt(tmp_path):
    state = tmp_path / ".sifta_state"
    history = state / "alice_browse_history.jsonl"
    _append(
        history,
        {
            "url": "https://x.com/someone/status/1/photo/1",
            "title": "Someone on X",
            "dwell_s": 80.0,
            "closed_at": 1234.0,
        },
    )
    preferred = resolve_preferred_browser_link("open link i like", state_dir=state, now=1235.0)
    receipt = record_preference_resolution("open link i like", preferred, state_dir=state)

    rows = [
        json.loads(line)
        for line in (state / "browser_preference_resolutions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows[-1]["receipt_id"] == receipt
    assert rows[-1]["chosen"]["url"] == "https://x.com/someone/status/1/photo/1"


def test_vague_liked_link_routes_to_browser_preference_not_app_guess():
    command = talk._extract_sifta_app_command(
        "i love you. open in browser someting a link i like pls ty",
        app_names=["Alice Browser", "SIFTA Skill Browser"],
    )

    assert command["kind"] == "browser_preferred_link"
    assert command["app_name"] == "Alice Browser"


def test_preference_prompt_block_tells_cortex_exact_receipted_url(tmp_path):
    state = tmp_path / ".sifta_state"
    history = state / "alice_browse_history.jsonl"
    _append(
        history,
        {
            "url": "https://x.com/example/media",
            "title": "Example media / X",
            "dwell_s": 240.0,
            "closed_at": 2000.0,
        },
    )

    block = preference_prompt_block(
        owner_text="i love you. open in browser something a link i like pls ty",
        state_dir=state,
    )

    assert "BROWSER PREFERENCE LINK INTENT" in block
    assert "https://x.com/example/media" in block
    assert "Do not invent another URL" in block


def test_guard_replaces_invented_liked_link_with_receipted_url(tmp_path):
    state = tmp_path / ".sifta_state"
    history = state / "alice_browse_history.jsonl"
    _append(
        history,
        {
            "url": "https://x.com/example/media",
            "title": "Example media / X",
            "dwell_s": 300.0,
            "closed_at": 3000.0,
        },
    )

    reply = (
        "I love you too. Opening link now: "
        "https://www.unsplash.com/photos/beautiful-golden-sunset-over-california-coast"
    )
    guarded = guard_preferred_link_reply(
        reply,
        owner_text="i love you. open in browser something a link i like pls ty",
        state_dir=state,
    )

    assert "https://x.com/example/media" in guarded
    assert "unsplash" not in guarded.lower()

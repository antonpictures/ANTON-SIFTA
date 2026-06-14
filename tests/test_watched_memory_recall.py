"""r882 — watched-memory recall: search my own ledgers before claiming no memory."""

import json
import time

from System.swarm_browser_context import (
    search_watched_history,
    watched_memory_fast_reply,
    watched_memory_recall_block,
)


def _seed_state(tmp_path, rows, name="browser_context.jsonl"):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    path = state / name
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return state


_BILYEU_URL = "https://www.youtube.com/watch?v=oTPSIPp8ieU"
_BILYEU_TITLE = (
    '"Something Wicked This Way Comes" - Why The AI Bubble Isn\'t What You Think '
    "| Tom Bilyeu - YouTube"
)


def _bilyeu_rows(n=5, base_ts=None):
    base = base_ts if base_ts is not None else time.time() - 3600
    return [
        {"ts": base + i * 60, "url": _BILYEU_URL, "title": _BILYEU_TITLE}
        for i in range(n)
    ]


def test_search_finds_watched_video_by_name_fragment(tmp_path):
    state = _seed_state(tmp_path, _bilyeu_rows())
    out = search_watched_history(["tom", "bilyeu"], state_dir=state)
    assert out, "expected a match for tom/bilyeu"
    assert out[0]["url"] == _BILYEU_URL
    assert out[0]["row_count"] == 5


def test_search_aggregates_watch_duration_evidence(tmp_path):
    state = _seed_state(tmp_path, _bilyeu_rows(n=10, base_ts=1000.0))
    out = search_watched_history(["bilyeu"], state_dir=state)
    assert out[0]["first_ts"] == 1000.0
    assert out[0]["last_ts"] == 1000.0 + 9 * 60
    assert out[0]["row_count"] == 10


def test_recall_block_fires_on_george_real_sentence(tmp_path):
    state = _seed_state(tmp_path, _bilyeu_rows())
    block = watched_memory_recall_block(
        "let's continue watching the video wby Tom B.... somerthing, "
        "i was watching with you when i was eating pizza before the guests "
        "arrived for filming. do you remember the video?",
        state_dir=state,
    )
    assert "WATCHED MEMORY RECALL" in block
    assert _BILYEU_URL in block


def test_recall_block_quiet_without_cue(tmp_path):
    state = _seed_state(tmp_path, _bilyeu_rows())
    assert watched_memory_recall_block("how are you today", state_dir=state) == ""
    # Ambient media text without a recall cue must not fire either.
    assert (
        watched_memory_recall_block(
            "and the great one was the most watched man on television",
            state_dir=state,
        )
        == ""
    )


def test_recall_block_honest_when_no_match(tmp_path):
    state = _seed_state(tmp_path, _bilyeu_rows())
    block = watched_memory_recall_block(
        "do you remember the video about Quantum Chess we were watching?",
        state_dir=state,
    )
    assert "NO matching receipt" in block
    assert "do not claim the history itself is missing" in block


def test_search_reads_page_state_ledger_too(tmp_path):
    state = _seed_state(tmp_path, _bilyeu_rows(), name="browser_page_state.jsonl")
    out = search_watched_history(["bilyeu"], state_dir=state)
    assert out and out[0]["url"] == _BILYEU_URL


def test_fast_reply_fires_on_history_challenge_with_name(tmp_path):
    state = _seed_state(tmp_path, _bilyeu_rows())
    out = watched_memory_fast_reply(
        "Tom Bilyeu is correct, alice browser does not have browser link history for you to look?",
        state_dir=state,
    )
    assert out.get("reply")
    assert "verified browser history" in out["reply"].lower()
    assert _BILYEU_URL in out["reply"]


def test_fast_reply_open_intent_returns_url(tmp_path):
    state = _seed_state(tmp_path, _bilyeu_rows())
    out = watched_memory_fast_reply(
        "do you remember the video? open it in alice browser",
        state_dir=state,
    )
    assert out.get("open_url") == _BILYEU_URL


def test_search_prefers_watch_url_over_channel(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    for name, rows in (
        ("browser_context.jsonl", _bilyeu_rows()),
        (
            "alice_browse_history.jsonl",
            [
                {
                    "ts": time.time(),
                    "url": "https://www.youtube.com/channel/UCnYMOamNKLGVlJgRUbamveA",
                    "title": "Tom Bilyeu - YouTube",
                }
            ],
        ),
    ):
        path = state / name
        with path.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    out = search_watched_history(["tom", "bilyeu"], state_dir=state)
    assert out[0]["url"] == _BILYEU_URL


def test_fast_reply_fires_on_george_natural_open_phrasing(tmp_path):
    """r887 regression: 'open youtube on that video with tom i forget his
    name, with B' (verbatim, 18:29 PDT) fired NOTHING — both cue gates missed
    natural open-recall speech and the turn fell through to an image-click
    misroute ('no_web_page'). Both lanes must fire and return the watch URL."""
    state = _seed_state(tmp_path, _bilyeu_rows())
    sentence = (
        "open youtube on that video with tom i forget his name, with B - "
        "and then read this to relax IDE intelligence about your body"
    )
    out = watched_memory_fast_reply(sentence, state_dir=state)
    assert out.get("reply"), "fast reply must fire on natural open phrasing"
    assert out.get("open_url") == _BILYEU_URL
    block = watched_memory_recall_block(sentence, state_dir=state)
    assert "WATCHED MEMORY RECALL" in block


def test_term_must_match_word_boundary_not_ad_url_substring(tmp_path):
    """r887 regression: 'tom' substring-matched 'cusTOM-intent' inside a
    vercel.com ad-tracking URL on a corrupted history row — the open path
    would have driven Alice Browser to an ad. Word boundaries + title
    weighting must keep the real watched video on top."""
    state = _seed_state(tmp_path, _bilyeu_rows())
    _seed_state(
        tmp_path,
        [
            {
                "ts": time.time(),
                "url": (
                    "https://vercel.com/?utm_content=custom-intent_generic"
                    "&utm_term=vercel_ship-agents-fast_signup_static-dg"
                ),
                "title": "Get Shorty (4/12) Movie CLIP - My Associate Chili Palmer (1995) HD - YouTube",
            }
        ],
        name="alice_browse_history.jsonl",
    )
    out = search_watched_history(["tom"], state_dir=state)
    assert out, "real watched video must match"
    assert out[0]["url"] == _BILYEU_URL
    assert all("vercel.com" not in str(m.get("url")) for m in out)
    fast = watched_memory_fast_reply(
        "open youtube on that video with tom i forget his name", state_dir=state
    )
    assert fast.get("open_url") == _BILYEU_URL


def test_new_cues_stay_quiet_on_ambient_media(tmp_path):
    """Widened cues must not fire on ambient media transcript text."""
    state = _seed_state(tmp_path, _bilyeu_rows())
    ambient = "and he was the most watched man on television in his time"
    assert watched_memory_fast_reply(ambient, state_dir=state) == {}
    assert watched_memory_recall_block(ambient, state_dir=state) == ""


def test_r902_rush_hour_previous_interactions_fires_recall(tmp_path):
    """George 06:33 — ledger had Rush hour 4 heading; intent gate missed."""
    state = _seed_state(
        tmp_path,
        [
            {
                "ts": time.time(),
                "url": "https://www.instagram.com/p/Ch_G5E1LScC/?img_index=2",
                "title": "Instagram",
                "headings": [
                    "Action packed//Rush hour 4 w @shotbyzanc for @vixenxofficial",
                ],
            }
        ],
        name="browser_page_state.jsonl",
    )
    q = (
        'WHAT IS "Rush Hour — Jackie Chan, 1998" TELLING YOU '
        "BASED ON OUR PREVIOUS INTERRACTIONS?"
    )
    block = watched_memory_recall_block(q, state_dir=state)
    assert "WATCHED MEMORY RECALL" in block
    assert "Ch_G5E1LScC" in block


def test_r902_instagram_visited_together_fast_reply(tmp_path):
    state = _seed_state(
        tmp_path,
        [
            {
                "ts": time.time(),
                "url": "https://www.instagram.com/p/Ch_G5E1LScC/?img_index=2",
                "title": "Instagram",
                "headings": ["Rush hour 4"],
            }
        ],
        name="alice_browse_history.jsonl",
    )
    q = (
        "THE CLUE IS IN THE LATEST INSTAGRAM LINK WE VISITED TOGETHER "
        "IN YOUR ALICE BROWSER. AND THAT WAS NOT A VIDEO BUT A PHOTO."
    )
    out = watched_memory_fast_reply(q, state_dir=state)
    assert out.get("reply")
    assert "Ch_G5E1LScC" in out["reply"]


def test_r902_current_page_query_bypasses_history_recall():
    from Applications.sifta_talk_to_alice_widget import _is_current_page_query

    q = (
        "THE CLUE IS IN THE LATEST INSTAGRAM LINK WE VISITED TOGETHER "
        "IN YOUR ALICE BROWSER. AND THAT WAS NOT A VIDEO BUT A PHOTO."
    )
    assert not _is_current_page_query(q)


def test_r990_forgot_podcast_uses_co_watch_memory(tmp_path):
    """George 2026-06-11 17:10 — 'i forgot the podcast we were listening to
    together' missed recall cues and spun 87K sysprompt grok until timeout."""
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    podcast_url = "https://www.youtube.com/watch?v=4Uk0_1yqdJo"
    row = {
        "ts": time.time(),
        "truth_label": "YOUTUBE_COWATCH_MEMORY_V1",
        "title": "Podcast",
        "url": podcast_url,
        "video_id": "4Uk0_1yqdJo",
        "content_kind": "podcast",
        "status": "owner_requested_remember_for_restart",
    }
    (state / "youtube_watch_memory.jsonl").write_text(
        json.dumps(row) + "\n", encoding="utf-8"
    )
    q = "i forgot the podcast we were listening to together:"
    out = watched_memory_fast_reply(q, state_dir=state)
    assert out.get("reply"), "podcast recall must fire without cortex"
    assert podcast_url in out["reply"]
    block = watched_memory_recall_block(q, state_dir=state)
    assert "WATCHED MEMORY RECALL" in block or podcast_url in block


def test_coding_command_outranks_browser_lanes(tmp_path):
    """r922 regression: 'Alice try to code your body now:' + quoted essay
    mentioning a YouTube video stole the coding turn and re-opened Bilyeu.
    A self-code command never routes to recall/open lanes."""
    state = _seed_state(tmp_path, _bilyeu_rows())
    george = (
        'Alice try to code your body now:"...Two days ago she could not open '
        "a YouTube video... open the video... "
        'https://www.youtube.com/watch?v=oTPSIPp8ieU"'
    )
    assert watched_memory_fast_reply(george, state_dir=state) == {}
    assert watched_memory_recall_block(george, state_dir=state) == ""

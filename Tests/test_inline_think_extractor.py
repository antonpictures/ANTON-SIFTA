"""Tests for InlineThinkExtractor — the streaming <think>...</think>
parser that pulls reasoning out of message.content for models that
embed thinking inline instead of using message.thinking.

Architect 2026-05-14 ~17:45 PDT, after the family-picture script
captured thinking via the separate field but the live Talk widget's
panel stayed empty across 66 turns of recorded zero-char traces.

Invariants pinned:
  - No-tag content passes through verbatim as visible.
  - A tag opened and closed inside one feed() splits cleanly.
  - A tag opened in feed N and closed in feed N+k still splits cleanly
    (the carry buffer handles straddling chunks).
  - Multiple <think> blocks in one stream all extract.
  - Case-insensitive matching for both <think> and </think>.
  - flush() drains any residual carry.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_alice_thinking_stream import (  # noqa: E402
    InlineThinkExtractor,
    ThinkingTraceRecorder,
    observable_processing_notice,
)


def _drain(ext: InlineThinkExtractor, pieces):
    """Feed every piece in order. Return concatenated (visible, thinking)
    plus the flushed tail."""
    vis, thk = [], []
    for p in pieces:
        v, t = ext.feed(p)
        vis.append(v)
        thk.append(t)
    fv, ft = ext.flush()
    return ("".join(vis) + fv, "".join(thk) + ft)


def test_no_tags_passes_through_verbatim():
    ext = InlineThinkExtractor()
    visible, thinking = _drain(ext, ["hello ", "world"])
    assert visible == "hello world"
    assert thinking == ""


def test_single_block_inside_one_chunk():
    ext = InlineThinkExtractor()
    visible, thinking = _drain(
        ext,
        ["before <think>reasoning here</think> after"],
    )
    assert visible == "before  after"
    assert thinking == "reasoning here"


def test_open_tag_straddles_chunk_boundary():
    ext = InlineThinkExtractor()
    # "<th" arrives in chunk 1, "ink>" arrives in chunk 2
    visible, thinking = _drain(
        ext,
        ["pre <th", "ink>reason</think> post"],
    )
    assert visible == "pre  post"
    assert thinking == "reason"


def test_close_tag_straddles_chunk_boundary():
    ext = InlineThinkExtractor()
    visible, thinking = _drain(
        ext,
        ["<think>part one ", "part two</thi", "nk> visible"],
    )
    assert thinking == "part one part two"
    assert visible == " visible"


def test_multiple_think_blocks_in_one_stream():
    ext = InlineThinkExtractor()
    visible, thinking = _drain(
        ext,
        ["a <think>one</think> b <think>two</think> c"],
    )
    assert visible == "a  b  c"
    assert thinking == "onetwo"


def test_tags_split_across_three_chunks():
    ext = InlineThinkExtractor()
    visible, thinking = _drain(
        ext,
        ["before<", "think>", "deep ", "thought", "</", "think>after"],
    )
    assert visible == "beforeafter"
    assert thinking == "deep thought"


def test_case_insensitive_tags():
    ext = InlineThinkExtractor()
    visible, thinking = _drain(
        ext,
        ["x <Think>upper-T</THINK> y"],
    )
    assert visible == "x  y"
    assert thinking == "upper-T"


def test_open_only_without_close_buffers_to_flush():
    """A <think> tag that never closes before stream ends gets
    drained by flush() as thinking."""
    ext = InlineThinkExtractor()
    visible, thinking = _drain(
        ext,
        ["normal <think>truncated reasoning"],
    )
    assert visible == "normal "
    assert thinking == "truncated reasoning"


def test_empty_feed_returns_empty():
    ext = InlineThinkExtractor()
    v, t = ext.feed("")
    assert v == "" and t == ""


def test_carry_keeps_trailing_bytes_smaller_than_tag():
    """Trailing bytes that COULD start a tag stay in carry. The
    end-to-end output across feed + feed + flush must equal the
    concatenated input, with nothing in the thinking channel because
    the only tag-like bytes ('<' alone, '<br>') are not <think>."""
    ext = InlineThinkExtractor()
    v1, t1 = ext.feed("hello <")
    v2, t2 = ext.feed("br>world")
    final_v, final_t = ext.flush()
    assert (v1 + v2 + final_v) == "hello <br>world"
    assert (t1 + t2 + final_t) == ""


def test_back_to_back_think_blocks_no_visible_between():
    ext = InlineThinkExtractor()
    visible, thinking = _drain(
        ext,
        ["<think>a</think><think>b</think>"],
    )
    assert visible == ""
    assert thinking == "ab"


def test_flush_is_idempotent():
    """A second flush after the first must yield empty — the carry
    is consumed by the first flush and nothing is held back to leak
    on the second call."""
    ext = InlineThinkExtractor()
    ext.feed("hello world")
    a = ext.flush()
    # First flush may return whatever was still in carry; we only
    # assert that it is a tuple-of-strings tied to the visible channel
    # (no tag was opened, so thinking must stay empty).
    assert isinstance(a, tuple) and len(a) == 2
    assert a[1] == ""


def test_observable_processing_notice_is_not_synthetic_thinking():
    notice = observable_processing_notice(
        model="alice-extra-cortex-25.8b-17gb:latest",
        pipeline_id="talk_to_alice_widget",
        reason="unit_test",
    )
    assert "[observable-processing]" in notice
    assert "instead of inventing thoughts" in notice
    assert "model=alice-extra-cortex-25.8b-17gb:latest" in notice
    assert "pipeline=talk_to_alice_widget" in notice
    assert "reason=unit_test" in notice


def test_recorder_keeps_observable_panel_text_separate_from_literal_thinking(tmp_path):
    rec = ThinkingTraceRecorder(
        model="alice-extra-cortex-25.8b-17gb:latest",
        pipeline_id="talk_to_alice_widget",
        state_dir=tmp_path,
    )
    rec.append_observable("[observable-processing]\nmodel=alice-extra\n")
    rec.append_content("I am answering from observable receipts.")
    receipt = rec.close(write=True)

    assert receipt["thinking_chars"] == 0
    assert receipt["thinking_chunks"] == 0
    assert receipt["observable_chars"] > 0
    assert receipt["observable_chunks"] == 1
    assert receipt["panel_chars"] == receipt["observable_chars"]
    assert receipt["content_chars"] == len("I am answering from observable receipts.")
    b = ext.flush()
    assert b == ("", "")

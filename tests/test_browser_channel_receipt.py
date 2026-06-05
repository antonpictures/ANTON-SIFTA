#!/usr/bin/env python3
"""r282: Alice reads the YouTube channel/author name off the page as a receipt.

George: 'when I play a youtube.com video, under the title she can read Tim Carambat —
that is the name for the receipt.' Before r282 the channel link was buried in the
generic links array, so Alice refused to name it without guessing. Now it is a
first-class page-state field and is surfaced in the 'what is on my screen' block.
"""
from System import swarm_browser_page_state as ps


def test_channel_name_is_stored_in_the_receipt(tmp_path):
    row = ps.record_page_state(
        "https://www.youtube.com/watch?v=ttVxQHt2HiA",
        "NVIDIA Just Put a 1-Petaflop Supercomputer In a Laptop? - YouTube",
        text="The N1 / N1X hardware specs just got announced at Computex 2026.",
        headings=["NVIDIA Just Put a 1-Petaflop Supercomputer In a Laptop?"],
        video_channel="Tim Carambat",
        state_dir=tmp_path,
    )
    assert row["video_channel"] == "Tim Carambat"


def test_channel_name_is_surfaced_in_the_screen_block(tmp_path):
    ps.record_page_state(
        "https://www.youtube.com/watch?v=ttVxQHt2HiA",
        "NVIDIA Just Put a 1-Petaflop Supercomputer In a Laptop? - YouTube",
        text="The N1 / N1X hardware specs just got announced at Computex 2026.",
        headings=["NVIDIA Just Put a 1-Petaflop Supercomputer In a Laptop?"],
        video_channel="Tim Carambat",
        state_dir=tmp_path,
    )
    block = ps.page_state_block(state_dir=tmp_path)
    # Alice can now name the channel from a receipt instead of guessing
    assert "Tim Carambat" in block
    assert "Channel" in block


def test_no_channel_means_no_channel_line(tmp_path):
    # A page with no detectable channel must not invent one.
    ps.record_page_state(
        "https://example.com/article",
        "Some Article",
        text="Plain article body text with enough content to be readable.",
        headings=["Some Article"],
        state_dir=tmp_path,
    )
    block = ps.page_state_block(state_dir=tmp_path)
    assert "Channel / author on the page" not in block

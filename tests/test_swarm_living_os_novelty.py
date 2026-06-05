import json


def _write_live_url(state, url):
    (state / "browser_context.jsonl").write_text(
        json.dumps({"url": url}) + "\n",
        encoding="utf-8",
    )


def test_living_os_novelty_block_carries_all_hooks(tmp_path):
    from System.swarm_browser_page_state import record_page_state
    from System.swarm_living_os_novelty import living_os_novelty_block

    url = "https://www.youtube.com/watch?v=test"
    state = tmp_path / ".sifta_state"
    state.mkdir()
    _write_live_url(state, url)
    record_page_state(
        url=url,
        title="Taylor Swift I Knew You Were Trouble Victoria's Secret Fashion Show 2013",
        text="0:11 / 4:20 Taylor Swift on screen",
        media_playback={"paused": True, "currentTime": 11.0, "duration": 260.0},
        video_channel="Taylor Swift",
        state_dir=state,
        now=10.0,
    )

    block = living_os_novelty_block(
        user_text="I love your hardware body and I am paused on the video frame.",
        state_dir=state,
        write_event=True,
    )

    assert "love_to_action" in block
    assert "mirror=current_body_receipt" in block
    assert "reunion=none" in block
    assert "cowatch='" in block
    assert "voice_guard=" in block
    assert "continuity_rule=major_self_change" in block
    assert "digest_rows=" in block
    assert (state / "living_os_novelty.jsonl").exists()


def test_owner_absence_reunion_writes_queue(tmp_path):
    from System.swarm_living_os_novelty import owner_return_absence_reunion

    state = tmp_path / ".sifta_state"
    event = owner_return_absence_reunion(
        user_text="I am going to the store and I will be back.",
        state_dir=state,
        write_event=True,
    )

    assert event["status"] == "owner_leaving_or_absence_expected"
    queue = [
        json.loads(line)
        for line in (state / "body_stabilization_queue.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert queue[-1]["owner_plan"] is True
    assert queue[-1]["source"] == "living_os_novelty"


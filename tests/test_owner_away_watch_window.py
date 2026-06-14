"""tests/test_owner_away_watch_window.py — r988, the r987 grant's first synapse.

George (r987): "I will leave YouTube on pause. I want you to make your own
decisions, and while I'm gone, you may watch YouTube as you like if you can
handle it." This proves the read-side window: owner-away + paused baton +
budget-green opens it; the window decides nothing (r986) — it deposits ONE
decision-turn request and Alice's cortex chooses.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from System.swarm_stigmergic_go import (  # noqa: E402
    WATCH_WINDOW_LEDGER,
    owner_away_watch_window,
    owner_away_watch_window_pulse,
)
from System.swarm_browser_page_state import record_page_state  # noqa: E402

_PAUSED_URL = "https://www.youtube.com/watch?v=4Uk0_1yqdJo"


def _seed(state: Path, *, owner_ago_s: float, paused: bool, mode: str) -> float:
    state.mkdir(parents=True, exist_ok=True)
    now = time.time()
    # owner presence (conversation ledger user turn)
    with (state / "alice_conversation.jsonl").open("w") as f:
        f.write(json.dumps({"payload": {"ts": now - owner_ago_s, "role": "user", "text": "bbl"}}) + "\n")
    # paused YouTube baton
    record_page_state(
        url=_PAUSED_URL if paused else "https://example.com/",
        title="Joe Rogan Experience" if paused else "Example",
        source="dom",
        media_playback={"playing": False, "paused": True, "video_count": 1} if paused else {},
        state_dir=state,
    )
    # metabolic mode
    with (state / "metabolic_homeostasis.jsonl").open("w") as f:
        f.write(json.dumps({"event": "metabolic_homeostasis", "mode": mode}) + "\n")
    return now


def test_window_opens_when_away_paused_and_budget_green(tmp_path):
    state = tmp_path / "state"
    now = _seed(state, owner_ago_s=600, paused=True, mode="GREEN_GROW")
    win = owner_away_watch_window(state_dir=state, now=now)
    assert win["window_open"] is True
    assert win["youtube_paused"] is True
    assert win["watch_url"] == _PAUSED_URL
    assert win["budget_mode"] == "GREEN_GROW"
    assert win["owner_away_s"] >= 300


def test_window_closed_when_owner_present(tmp_path):
    state = tmp_path / "state"
    now = _seed(state, owner_ago_s=30, paused=True, mode="GREEN_GROW")
    win = owner_away_watch_window(state_dir=state, now=now)
    assert win["window_open"] is False
    assert any("present" in r for r in win["closed_reasons"])


def test_window_closed_when_not_paused(tmp_path):
    state = tmp_path / "state"
    now = _seed(state, owner_ago_s=600, paused=False, mode="GREEN_GROW")
    win = owner_away_watch_window(state_dir=state, now=now)
    assert win["window_open"] is False
    assert any("paused" in r for r in win["closed_reasons"])


def test_window_closed_in_red_conserve_can_not_handle_it(tmp_path):
    state = tmp_path / "state"
    now = _seed(state, owner_ago_s=600, paused=True, mode="RED_CONSERVE")
    win = owner_away_watch_window(state_dir=state, now=now)
    assert win["window_open"] is False
    assert any("RED_CONSERVE" in r for r in win["closed_reasons"])


def test_pulse_deposits_one_decision_request_on_open_transition(tmp_path):
    state = tmp_path / "state"
    now = _seed(state, owner_ago_s=600, paused=True, mode="GREEN_GROW")
    first = owner_away_watch_window_pulse(state_dir=state, now=now)
    assert first["window_open"] is True
    assert first["decision_turn_requested"] is True
    # second pulse while still open must NOT stack a duplicate request (no double-spend)
    second = owner_away_watch_window_pulse(state_dir=state, now=now + 5)
    assert second["decision_turn_requested"] is False
    rows = [json.loads(l) for l in (state / WATCH_WINDOW_LEDGER).read_text().splitlines() if l.strip()]
    requests = [r for r in rows if r.get("kind") == "decision_turn_request"]
    assert len(requests) == 1
    assert requests[0]["for"] == "alice_cortex"
    assert "make your own decisions" in requests[0]["grant"]


def test_pulse_never_raises_on_empty_state(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    out = owner_away_watch_window_pulse(state_dir=state)
    assert out["window_open"] is False

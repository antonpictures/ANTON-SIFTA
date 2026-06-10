"""r881 — typed-turn queue: owner text never dropped while busy, typed beats audio."""

from System.swarm_typed_turn_queue import TypedTurnQueue


def test_push_and_pop_fifo():
    q = TypedTurnQueue()
    q.push("first", now=100.0)
    q.push("second", now=101.0)
    assert len(q) == 2
    item, stale = q.pop_fresh(now=102.0)
    assert item is not None and item.text == "first" and stale == 0
    item2, _ = q.pop_fresh(now=102.0)
    assert item2 is not None and item2.text == "second"
    assert len(q) == 0


def test_empty_text_not_queued():
    q = TypedTurnQueue()
    out = q.push("   ")
    assert out["queued"] is False
    assert len(q) == 0


def test_image_only_turn_is_queued():
    q = TypedTurnQueue()
    out = q.push("", image_path="/tmp/x.png", now=100.0)
    assert out["queued"] is True
    item, _ = q.pop_fresh(now=101.0)
    assert item is not None and item.image_path == "/tmp/x.png"


def test_cap_drops_oldest():
    q = TypedTurnQueue(max_queued=2)
    q.push("a", now=100.0)
    q.push("b", now=101.0)
    out = q.push("c", now=102.0)
    assert out["dropped_oldest"] is True
    assert len(q) == 2
    item, _ = q.pop_fresh(now=103.0)
    assert item is not None and item.text == "b"


def test_stale_turns_dropped_not_replayed():
    """A typed turn older than the freshness window must not replay as a
    live command — that would be the phantom-action disease."""
    q = TypedTurnQueue(max_age_s=600.0)
    q.push("old command", now=100.0)
    q.push("fresh command", now=900.0)
    item, stale = q.pop_fresh(now=1000.0)
    assert stale == 1
    assert item is not None and item.text == "fresh command"


def test_all_stale_returns_none():
    q = TypedTurnQueue(max_age_s=10.0)
    q.push("ancient", now=0.0)
    item, stale = q.pop_fresh(now=1000.0)
    assert item is None and stale == 1
    assert len(q) == 0

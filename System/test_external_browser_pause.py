#!/usr/bin/env python3
"""Test browser-aware external video pause/resume (computer-use awareness)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# r-browser-aware-pause-v3: this suite must NEVER command George's real browser. Set
# before any effector import; reads (awareness/picking) stay live so the suite still
# asserts against the real machine. Regression: a dummy once reached a real effector
# and froze his live podcast mid-episode.
import os  # noqa: E402

os.environ["SIFTA_BROWSER_CONTROL"] = "0"


def test_import() -> None:
    from System.swarm_external_browser_pause import (  # noqa: F401
        browser_awareness_snapshot,
        pick_video_browser,
        pause_video_anywhere,
        resume_video_anywhere,
    )
    from System.swarm_external_browser_video_pause import (  # noqa: F401
        try_pause_external_video,
        try_resume_external_video,
        enrich_cowatch_body_loop,
        browser_awareness,
    )
    print("imports OK")


def test_awareness() -> None:
    """Alice must know which browsers are on and which one is playing."""
    from System.swarm_external_browser_pause import browser_awareness_snapshot

    snap = browser_awareness_snapshot()
    print(f"  running_browsers : {snap['running_browsers']}")
    print(f"  frontmost_app    : {snap['frontmost_app']} (browser={snap['frontmost_is_browser']})")
    print(f"  video_tabs       : {len(snap['video_tabs'])}")
    for t in snap["video_tabs"]:
        print(
            f"    {t['browser']} w{t['window_index']}t{t['tab_index']} "
            f"playing={t['playing']} t={t['current_time']} {t['url'][:60]}"
        )
    assert isinstance(snap["running_browsers"], list), "running_browsers must be a list"
    print(f"  playing_tabs     : {len(snap['playing_tabs'])}")


def test_pick() -> None:
    """Picking must prefer the frontmost browser that is actually playing."""
    from System.swarm_external_browser_pause import pick_video_browser

    pick = pick_video_browser()
    if not pick.get("found"):
        print(f"  no video tab found ({pick.get('reason')}) — open a YouTube tab to test")
        return
    t = pick["target"]
    print(f"  chose {t['browser']} via {pick['why']} -> {t['url'][:60]}")
    assert pick["why"] in (
        "frontmost_playing", "playing_video", "frontmost_with_video", "only_video_tab"
    )


_STUB_ALICE_RECEIPT = {
    "ok": True, "action": "pause", "was_paused": False, "paused": True,
    "current_time": 12.3, "duration": 180.5, "url": "https://example.test/video",
}


def test_enrich_external_failure_never_blocks() -> None:
    """When the external layer fails, Alice-Browser success must survive (stubbed, no real pause)."""
    from System.swarm_external_browser_video_pause import enrich_cowatch_body_loop
    import System.swarm_external_browser_video_pause as mod

    real = mod.try_pause_external_video
    mod.try_pause_external_video = lambda url, port=9222: (
        False, {"ok": False, "action": "pause", "browser": "Firefox", "reason": "no_effector"}
    )
    try:
        enriched = enrich_cowatch_body_loop("https://example.test/video", _STUB_ALICE_RECEIPT)
    finally:
        mod.try_pause_external_video = real

    assert enriched["ok"] is True, "Alice-Browser success must keep ok=True"
    assert enriched["external_ok"] is False
    assert enriched["external_reason"] == "no_effector"
    print(f"  ok={enriched['ok']} external_ok={enriched['external_ok']} "
          f"browser={enriched.get('external_browser')} reason={enriched.get('external_reason')}")


def test_enrich_external_success() -> None:
    """A successful external pause must merge in without disturbing Alice-Browser fields."""
    from System.swarm_external_browser_video_pause import enrich_cowatch_body_loop
    import System.swarm_external_browser_video_pause as mod

    real = mod.try_pause_external_video
    mod.try_pause_external_video = lambda url, port=9222: (
        True, {"ok": True, "action": "pause", "browser": "Safari", "effector": "applescript_js",
               "was_paused": False, "paused": True, "reason": ""}
    )
    try:
        enriched = enrich_cowatch_body_loop("https://example.test/video", _STUB_ALICE_RECEIPT)
    finally:
        mod.try_pause_external_video = real

    assert enriched["ok"] is True
    assert enriched["external_ok"] is True
    assert enriched["external_browser"] == "Safari"
    assert enriched["external_effector"] == "applescript_js"
    assert enriched["current_time"] == 12.3, "Alice-Browser fields must be preserved"
    print(f"  ok={enriched['ok']} external_ok={enriched['external_ok']} "
          f"browser={enriched['external_browser']} effector={enriched['external_effector']}")


def test_body_loop_shape() -> None:
    """The cowatch body loop must still return its expected shape (stubbed, no real pause)."""
    import System.swarm_external_browser_video_pause as mod
    from System.swarm_cowatch_body_loop import run_cowatch_video_pause_body_loop

    real = mod.try_pause_external_video
    mod.try_pause_external_video = lambda url, port=9222: (
        True, {"ok": True, "action": "pause", "browser": "Safari", "effector": "applescript_js",
               "paused": True, "reason": ""}
    )
    try:
        out = run_cowatch_video_pause_body_loop(
            url="https://example.test/video", receipt=dict(_STUB_ALICE_RECEIPT), context="test"
        )
    finally:
        mod.try_pause_external_video = real

    for key in ("action", "actual", "outcome", "enriched"):
        assert key in out, f"missing {key}"
    assert "external_ok=True" in out["actual"]
    print(f"  action={out['action']}")
    print(f"  actual={out['actual'][:110]}")


def test_fail_soft_on_exception() -> None:
    """An exploding effector must degrade to a reason tuple, never raise."""
    import System.swarm_external_browser_pause as eff
    import System.swarm_external_browser_video_pause as mod

    real = eff.pause_video_anywhere

    def boom(url):
        raise RuntimeError("simulated effector crash")

    eff.pause_video_anywhere = boom
    try:
        ok, receipt = mod.try_pause_external_video("https://example.test/video")
    finally:
        eff.pause_video_anywhere = real

    assert ok is False, "a crashing effector must report not-ok"
    assert receipt.get("reason") == "error"
    assert "simulated effector crash" in str(receipt.get("details", ""))
    print(f"  swallowed: ok={ok} reason={receipt['reason']} details={receipt['details'][:40]}")


def test_two_browsers_playing() -> None:
    """When two browsers have playing videos, frontmost must win."""
    import System.swarm_external_browser_pause as mod

    real_snapshot = mod.browser_awareness_snapshot
    real_running = mod.running_browsers
    real_frontmost = mod.frontmost_app

    def mock_running():
        return ["Safari", "Google Chrome"]

    def mock_frontmost():
        return "Safari"

    def mock_snapshot():
        return {
            "truth_label": "EXTERNAL_BROWSER_PAUSE_V2",
            "running_browsers": ["Safari", "Google Chrome"],
            "frontmost_app": "Safari",
            "frontmost_is_browser": True,
            "video_tabs": [
                {"browser": "Google Chrome", "playing": True, "paused": False, "url": "https://chrome.com/watch?v=test", "window_index": 1, "tab_index": 1, "current_time": 100.0, "duration": 200.0},
                {"browser": "Safari", "playing": True, "paused": False, "url": "https://www.youtube-nocookie.com/embed/test", "window_index": 1, "tab_index": 1, "current_time": 100.0, "duration": 200.0},
            ],
            "all_tabs": [],
            "cdp_port_open": False,
            "playing_tabs": [],
        }

    mod.browser_awareness_snapshot = mock_snapshot
    mod.running_browsers = mock_running
    mod.frontmost_app = mock_frontmost
    try:
        pick = mod.pick_video_browser()
        assert pick["target"]["browser"] == "Safari", f"expected Safari, got {pick['target']['browser']}"
        assert pick["why"] == "frontmost_playing"
        print(f"  picked frontmost {pick['target']['browser']} via {pick['why']}")
    finally:
        mod.browser_awareness_snapshot = real_snapshot
        mod.running_browsers = real_running
        mod.frontmost_app = real_frontmost


def test_cdp_path() -> None:
    """CDP effector path: validate that the websocket -> evaluate flow is wired."""
    import System.swarm_external_browser_pause as mod
    import System.swarm_external_browser_pause as eff
    from unittest.mock import patch, MagicMock

    # Mock CDP ports open
    real_port_is_open = eff._port_is_open
    def mock_port_is_open(host, port, timeout_s=1.5):
        return True

    # Mock target listing
    real_cdp_targets = eff._cdp_targets
    def mock_cdp_targets(port):
        return [{"type": "page", "url": "https://youtube.com/watch?v=test", "webSocketDebuggerUrl": "ws://fake"}]

    # Mock the CDP transport. This used to patch the third-party `websocket`
    # client — which is not installed on python3.14, the interpreter the body
    # calls, so every real Chrome pause ended at `websocket_client_missing`. The
    # transport is stdlib now (2026-10-05) and `_cdp_eval` is the seam to mock.
    # The intent is unchanged: the efferent path must return ok + paused from the
    # page JS payload.
    def mock_cdp_eval(ws_url, expression, timeout_s=6.0):
        assert ws_url, "the effector must hand a CDP page socket to the transport"
        assert isinstance(expression, str) and expression, "the effector must send page JS"
        return "ok|0|1|100.0|200.0"

    real_cdp_eval = eff._cdp_eval
    eff._port_is_open = mock_port_is_open
    eff._cdp_targets = mock_cdp_targets
    eff._cdp_eval = mock_cdp_eval
    try:
        result = eff._cdp_act("pause", "https://youtube.com/watch?v=test", 9222)
        assert result["ok"] is True, f"expected ok=True from CDP mock, got {result}"
        assert result.get("paused") is True
        print(f"  CDP mock ok={result['ok']} paused={result.get('paused')} url={result.get('url')}")
    finally:
        eff._cdp_eval = real_cdp_eval
        eff._port_is_open = real_port_is_open
        eff._cdp_targets = real_cdp_targets


def test_organ_registered() -> None:
    """The organ must be registered in Alice's canonical registry."""
    from System.swarm_canonical_organ_registry import CANONICAL_ORGANS

    ids = [o.organ_id for o in CANONICAL_ORGANS]
    assert "external_browser_media" in ids, "external_browser_media not registered"
    spec = [o for o in CANONICAL_ORGANS if o.organ_id == "external_browser_media"][0]
    for p in spec.organ_paths:
        assert Path(p).exists(), f"organ path missing: {p}"
    print(f"  registered: {spec.organ_id} layer={spec.layer} "
          f"paths={len(spec.organ_paths)} caps={len(spec.capabilities)}")


def test_pause_only_if_playing_skips_when_nothing_playing() -> None:
    """'she still speaks over the video' — and the inverse hazard.

    If nothing is playing, `pause_only_if_playing` must refuse AND must not touch any
    tab. `pick_video_browser` falls back to non-playing video tabs, so an unguarded
    pause would "pause" a tab George had stopped — and the paired resume would then
    PLAY it, starting a video he deliberately paused. Owner's hand wins.
    """
    import System.swarm_external_browser_pause as mod

    real_snapshot = mod.browser_awareness_snapshot
    real_pause = mod.pause_video_anywhere
    touched = []

    mod.browser_awareness_snapshot = lambda: {
        "running_browsers": ["Safari"],
        "frontmost_app": "Safari",
        "video_tabs": [
            {"browser": "Safari", "playing": False, "paused": True,
             "url": "https://www.youtube.com/watch?v=owner_stopped_this",
             "window_index": 1, "tab_index": 1, "current_time": 42.0, "duration": 900.0},
        ],
        "playing_tabs": [],
    }
    mod.pause_video_anywhere = lambda url="": touched.append(url) or {"ok": True, "paused": True}
    try:
        receipt = mod.pause_only_if_playing()
    finally:
        mod.browser_awareness_snapshot = real_snapshot
        mod.pause_video_anywhere = real_pause

    assert receipt["ok"] is False, "must refuse to pause when nothing is playing"
    assert receipt["reason"] == "nothing_playing"
    assert touched == [], f"effector must NOT be called, but was: {touched}"
    print(f"  refused: ok={receipt['ok']} reason={receipt['reason']} effector_calls={len(touched)}")


def _widget_speech_harness():
    """Build a stub class carrying the widget's real speech-pause methods.

    The widget is 51k lines and imports PyQt6, so we extract just these four methods
    with `ast` and exec them onto a bare class. That exercises the ACTUAL shipped
    control flow — including the nesting that caused 'she still speaks over the video'
    — without instantiating a GUI.
    """
    import ast
    import textwrap

    path = Path(__file__).parent.parent / "Applications" / "sifta_talk_to_alice_widget.py"
    src = path.read_text(encoding="utf-8", errors="replace")
    wanted = {
        "_pause_browser_video_for_speech",
        "_pause_external_video_for_speech",
        "_resume_browser_video_after_speech",
        "_resume_external_video_after_speech",
    }
    found = {}
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            found[node.name] = ast.get_source_segment(src, node)
    missing = wanted - set(found)
    assert not missing, f"widget methods missing from source: {sorted(missing)}"

    body = "\n\n".join(
        "\n".join(("    " + ln) if ln.strip() else ln
                  for ln in textwrap.dedent(found[n]).splitlines())
        for n in sorted(wanted)
    )
    ns = {"__name__": "widget_speech_harness", "_state_root": lambda: "/tmp/sifta_test_state"}
    exec(compile("class Harness:\n" + body + "\n", "<widget-speech-harness>", "exec"), ns)
    return ns["Harness"]


def test_external_pause_fires_with_widget_closed() -> None:
    """THE DEFECT. With Alice's own browser widget closed — the normal case while
    George watches a podcast in Safari — the external half must STILL pause his video,
    and must STILL resume the same tab when she finishes."""
    import System.swarm_external_browser_video_pause as ext

    calls = []
    real_pause = ext.try_pause_external_video_if_playing
    real_resume = ext.try_resume_external_video
    PODCAST = "https://www.youtube-nocookie.com/embed/PODCAST"

    def mock_if_playing(url="", port=9222):
        calls.append(("pause", url))
        return True, {"ok": True, "action": "pause", "browser": "Safari",
                      "effector": "applescript_js", "was_paused": False,
                      "paused": True, "url": PODCAST}

    def mock_resume(url="", port=9222):
        calls.append(("resume", url))
        return True, {"ok": True, "action": "play", "browser": "Safari",
                      "paused": False, "url": url}

    ext.try_pause_external_video_if_playing = mock_if_playing
    ext.try_resume_external_video = mock_resume
    try:
        h = _widget_speech_harness()()
        h._live_alice_browser = lambda: None          # the widget is CLOSED
        h._append_observable_processing = lambda *a, **k: None
        h._paused_browser_video_for_speech = False
        h._paused_browser_video_url = ""
        h._paused_external_video_for_speech = False
        h._paused_external_video_url = ""
        h._speech_browser_video_pause_receipt = {}

        h._pause_browser_video_for_speech()
        assert h._paused_external_video_for_speech is True, (
            "external pause did NOT fire with Alice's own widget closed — the exact "
            "bug behind 'she still speaks over the video'"
        )
        assert [c[0] for c in calls] == ["pause"], calls

        h._resume_browser_video_after_speech()
        assert h._paused_external_video_for_speech is False, "external resume did not clear the flag"
        assert [c[0] for c in calls] == ["pause", "resume"], calls
        assert calls[1][1].endswith("PODCAST"), (
            f"resume must target the same tab that was paused, got {calls[1][1]!r}"
        )
        print(f"  widget closed -> {[c[0] for c in calls]} on {calls[1][1].rsplit('/', 1)[-1]}")
    finally:
        ext.try_pause_external_video_if_playing = real_pause
        ext.try_resume_external_video = real_resume


def test_no_pause_means_no_resume() -> None:
    """Nothing playing -> she must neither pause nor resume. A resume here would
    START a video the owner had deliberately stopped."""
    import System.swarm_external_browser_video_pause as ext

    calls = []
    real_pause = ext.try_pause_external_video_if_playing
    real_resume = ext.try_resume_external_video

    def mock_if_playing(url="", port=9222):
        calls.append("pause")
        return False, {"ok": False, "action": "pause", "reason": "nothing_playing",
                       "browser": None, "playing_tabs": []}

    def mock_resume(url="", port=9222):
        calls.append("resume")
        return True, {"ok": True, "action": "play", "browser": "Safari", "paused": False}

    ext.try_pause_external_video_if_playing = mock_if_playing
    ext.try_resume_external_video = mock_resume
    try:
        h = _widget_speech_harness()()
        h._live_alice_browser = lambda: None
        h._append_observable_processing = lambda *a, **k: None
        h._paused_browser_video_for_speech = False
        h._paused_browser_video_url = ""
        h._paused_external_video_for_speech = False
        h._paused_external_video_url = ""
        h._speech_browser_video_pause_receipt = {}

        h._pause_browser_video_for_speech()
        assert h._paused_external_video_for_speech is False, "must not claim a pause it never made"
        h._resume_browser_video_after_speech()
        assert calls == ["pause"], f"resume must NOT fire after a refused pause, got {calls}"
        print(f"  nothing playing -> calls={calls} (no resume issued)")
    finally:
        ext.try_pause_external_video_if_playing = real_pause
        ext.try_resume_external_video = real_resume


def test_partial_harness_never_touches_owner_browser() -> None:
    """TEST-ISOLATION GUARD. A partial object that never ran the widget's __init__
    (i.e. every unit-test dummy) must not be able to command George's REAL browser.

    Regression: during this fix's own suite run, a dummy reached the real effector and
    froze his live podcast mid-episode. The flag the guard reads is created in
    __init__, so its absence proves the object is not a live widget.
    """
    import System.swarm_external_browser_video_pause as ext

    calls = []
    real_pause = ext.try_pause_external_video_if_playing

    def mock_if_playing(url="", port=9222):
        calls.append("pause")
        return True, {"ok": True, "action": "pause", "browser": "Safari", "paused": True,
                      "url": "https://www.youtube.com/watch?v=OWNER"}

    ext.try_pause_external_video_if_playing = mock_if_playing
    try:
        h = _widget_speech_harness()()          # NOTE: no __init__ -> no live flags
        h._live_alice_browser = lambda: None
        h._append_observable_processing = lambda *a, **k: None
        assert not hasattr(h, "_paused_external_video_for_speech"), (
            "harness unexpectedly carries the live flag; this test can no longer prove anything"
        )
        h._pause_external_video_for_speech()    # must be a hard no-op
        assert calls == [], f"partial harness reached the OWNER's real browser: {calls}"
        print("  partial harness -> effector calls=0 (owner's browser untouched)")
    finally:
        ext.try_pause_external_video_if_playing = real_pause


# --------------------------------------------------------------------------------------
# r-browser-aware-pause-v4: "any video playing must be paused while she speaks"
# --------------------------------------------------------------------------------------

def _fake_safari_act(calls, indices_by_url=None, fail_urls=()):
    """Stand-in for the Safari effector: records every call, never touches a real browser."""
    idx_map = indices_by_url or {}

    def fake(action, url_substring="", indices=""):
        calls.append({"action": action, "url": url_substring, "indices": indices})
        if action == "pause":
            if url_substring in fail_urls:
                return {"ok": False, "action": "pause", "reason": "no_media_paused",
                        "paused_indices": [], "media_count": 0, "indices_csv": "", "url": url_substring}
            csv = idx_map.get(url_substring, "0")
            got = [int(x) for x in csv.split(",") if x.strip().isdigit()]
            return {"ok": True, "action": "pause", "browser": "Safari", "effector": "applescript_js",
                    "was_paused": False, "paused": True, "paused_indices": got,
                    "media_count": len(got), "indices_csv": csv, "url": url_substring}
        got = [int(x) for x in str(indices).split(",") if x.strip().isdigit()]
        return {"ok": True, "action": "play", "browser": "Safari", "effector": "applescript_js",
                "paused": False, "paused_indices": got, "media_count": len(got),
                "indices_csv": indices, "url": url_substring}

    return fake


def _snap_with(playing):
    return {
        "frontmost_app": "Safari",
        "running_browsers": ["Safari"],
        "video_tabs": list(playing),
        "playing_tabs": list(playing),
        "all_tabs": [],
        "cdp_port_open": False,
        "frontmost_is_browser": True,
    }


def test_all_playing_tabs_paused() -> None:
    """EVERY tab that is playing must be silenced -- not just the one that wins a pick."""
    import System.swarm_external_browser_pause as mod

    snap = _snap_with([
        {"browser": "Safari", "playing": True, "url": "https://a.test/one"},
        {"browser": "Safari", "playing": True, "url": "https://b.test/two"},
        {"browser": "Safari", "playing": False, "url": "https://c.test/stopped-by-owner"},
    ])
    calls = []
    real_snap, real_act, real_ctl = mod.browser_awareness_snapshot, mod._safari_act, mod.browser_control_enabled
    real_targets = list(mod._paused_targets)
    mod.browser_control_enabled = lambda: True
    mod.browser_awareness_snapshot = lambda: snap
    mod._safari_act = _fake_safari_act(calls, {"https://a.test/one": "0", "https://b.test/two": "1,2"})
    try:
        receipt = mod.pause_only_if_playing()
        recorded = list(mod._paused_targets)
    finally:
        mod.browser_awareness_snapshot, mod._safari_act, mod.browser_control_enabled = real_snap, real_act, real_ctl
        mod._paused_targets = real_targets

    paused_urls = {c["url"] for c in calls if c["action"] == "pause"}
    assert paused_urls == {"https://a.test/one", "https://b.test/two"}, f"got {paused_urls}"
    assert receipt["tabs_paused"] == 2, receipt
    assert receipt["media_paused"] == 3, "one tab had two playing media elements"
    assert receipt["all_playing_paused"] is True, receipt
    assert all(c["url"] != "https://c.test/stopped-by-owner" for c in calls), (
        "a tab that was NOT playing must never be touched (resume would start it)"
    )
    assert len(recorded) == 2 and recorded[1]["indices"] == "1,2", recorded
    print(f"  swept {receipt['tabs_paused']} tabs / {receipt['media_paused']} media; "
          f"untouched stopped tab; recorded={[t['url'] for t in recorded]}")


def test_pause_reports_partial_failure() -> None:
    """A half-pause must never be reported as a clean ok -- that is how she talked over it."""
    import System.swarm_external_browser_pause as mod

    snap = _snap_with([
        {"browser": "Safari", "playing": True, "url": "https://a.test/ok"},
        {"browser": "Safari", "playing": True, "url": "https://b.test/refuses"},
    ])
    calls = []
    real_snap, real_act, real_ctl = mod.browser_awareness_snapshot, mod._safari_act, mod.browser_control_enabled
    real_targets = list(mod._paused_targets)
    mod.browser_control_enabled = lambda: True
    mod.browser_awareness_snapshot = lambda: snap
    mod._safari_act = _fake_safari_act(calls, {"https://a.test/ok": "0"}, fail_urls=("https://b.test/refuses",))
    try:
        receipt = mod.pause_only_if_playing()
    finally:
        mod.browser_awareness_snapshot, mod._safari_act, mod.browser_control_enabled = real_snap, real_act, real_ctl
        mod._paused_targets = real_targets

    assert receipt["ok"] is True, "the tab we could silence did get silenced"
    assert receipt["all_playing_paused"] is False, "a refused tab must not pass silently"
    assert receipt["failed_targets"], "the refusing tab must be named"
    print(f"  ok={receipt['ok']} all_playing_paused={receipt['all_playing_paused']} "
          f"failed={receipt['failed_targets']}")


def test_resume_replays_exact_recorded_targets() -> None:
    """Resume must restore exactly the recorded set: same tabs, same media indices."""
    import System.swarm_external_browser_pause as mod

    snap = _snap_with([
        {"browser": "Safari", "playing": True, "url": "https://a.test/one"},
        {"browser": "Safari", "playing": True, "url": "https://b.test/two"},
    ])
    calls = []
    real_snap, real_act, real_ctl = mod.browser_awareness_snapshot, mod._safari_act, mod.browser_control_enabled
    real_targets = list(mod._paused_targets)
    mod.browser_control_enabled = lambda: True
    mod.browser_awareness_snapshot = lambda: snap
    mod._safari_act = _fake_safari_act(calls, {"https://a.test/one": "0", "https://b.test/two": "1,2"})
    try:
        mod.pause_only_if_playing()
        calls.clear()
        receipt = mod.resume_video_anywhere()
    finally:
        mod.browser_awareness_snapshot, mod._safari_act, mod.browser_control_enabled = real_snap, real_act, real_ctl
        mod._paused_targets = real_targets

    plays = [c for c in calls if c["action"] == "play"]
    assert {c["url"] for c in plays} == {"https://a.test/one", "https://b.test/two"}, plays
    got = {c["url"]: c["indices"] for c in plays}
    assert got["https://a.test/one"] == "0" and got["https://b.test/two"] == "1,2", got
    assert receipt["ok"] is True and receipt["media_resumed"] == 3, receipt
    print(f"  replayed {receipt['tabs_resumed']} tabs / {receipt['media_resumed']} media: {got}")


def test_resume_refuses_without_a_recorded_pause() -> None:
    """No recorded pause -> refuse. Never re-pick a tab and start it by hand."""
    import System.swarm_external_browser_pause as mod

    snap = _snap_with([{"browser": "Safari", "playing": False, "url": "https://c.test/owner-stopped"}])
    calls = []
    real_snap, real_act, real_ctl = mod.browser_awareness_snapshot, mod._safari_act, mod.browser_control_enabled
    real_targets, real_last = list(mod._paused_targets), mod._last_pause_url
    mod.browser_control_enabled = lambda: True
    mod.browser_awareness_snapshot = lambda: snap
    mod._safari_act = _fake_safari_act(calls)
    mod._paused_targets, mod._last_pause_url = [], None
    try:
        receipt = mod.resume_video_anywhere()
    finally:
        mod.browser_awareness_snapshot, mod._safari_act, mod.browser_control_enabled = real_snap, real_act, real_ctl
        mod._paused_targets, mod._last_pause_url = real_targets, real_last

    assert receipt["ok"] is False and receipt["reason"] == "nothing_to_resume", receipt
    assert calls == [], f"resume with no evidence reached an effector: {calls}"
    print(f"  refused: {receipt['reason']}, effector calls={len(calls)}")


def test_media_js_generic_and_index_precise() -> None:
    """The JS itself: generic detection, pause-all, and index-precise resume with refusals."""
    import System.swarm_external_browser_pause as mod

    walk = mod._JS_WALK
    pause_js = mod._SAFARI_PAUSE_JS
    resume_js = mod._safari_resume_js("2,5")

    assert "querySelectorAll('video,audio')" in walk, "audio must count as playing media"
    assert "iframe" in walk and "contentDocument" in walk, "same-origin iframes must be walked"

    haystack = (walk + pause_js + resume_js + mod._SAFARI_INFO_JS + mod._SAFARI_PLAYING_JS
                + mod._CDP_VIDEO_JS).lower()
    for site in ("youtube", "youtu.be", "vimeo", "netflix", "twitch", "spotify"):
        assert site not in haystack, f"hardcoded site in the detection path: {site}"

    assert "if(!ms[i].paused&&!ms[i].ended){was=1;try{ms[i].pause();idx.push(i);}catch(e){}}" in pause_js, (
        "pause must sweep EVERY playing element, not break on the first"
    )

    assert "var want=[2,5]" in resume_js, "resume must target the exact indices it was given"
    assert "if(!m||m.ended)continue;" in resume_js, "never start an ended element"
    assert "if(!m.paused)continue;" in resume_js, "never touch something already playing"
    assert "if(!(m.currentTime>0))continue;" in resume_js, (
        "never start an element that never played -- that would be a NEW sound"
    )
    assert "var want=[-1]" in mod._safari_resume_js(""), "an empty index list must touch nothing"

    src = Path(mod.__file__).read_text()
    for site in ("youtube.com/watch", "youtu.be/", "watch?v="):
        assert site not in src, f"hardcoded video/site reference left in the module: {site}"
    print("  generic walk (video,audio + iframes), pause-all, index-precise resume, no site names")


def test_kill_switch_gates_the_sweep() -> None:
    """SIFTA_BROWSER_CONTROL=0 must stop the sweep before any effector is reached."""
    import System.swarm_external_browser_pause as mod

    calls = []
    real_snap, real_act = mod.browser_awareness_snapshot, mod._safari_act
    mod.browser_awareness_snapshot = lambda: _snap_with(
        [{"browser": "Safari", "playing": True, "url": "https://a.test/one"}]
    )
    mod._safari_act = _fake_safari_act(calls)
    try:
        assert mod.browser_control_enabled() is False, "suite env must keep the kill switch on"
        paused = mod.pause_all_playing_videos()
        played = mod.resume_all_paused()
    finally:
        mod.browser_awareness_snapshot, mod._safari_act = real_snap, real_act

    assert paused.get("reason") == "control_disabled" and played.get("reason") == "control_disabled"
    assert calls == [], f"kill switch leaked an effector call: {calls}"
    print("  control_disabled on both halves; effector calls=0")


def main() -> None:
    tests = [
        ("imports", test_import),
        ("organ registered", test_organ_registered),
        ("browser awareness", test_awareness),
        ("target picking", test_pick),
        ("two browsers playing → frontmost wins", test_two_browsers_playing),
        ("CDP path wired", test_cdp_path),
        ("enrich: external failure never blocks", test_enrich_external_failure_never_blocks),
        ("enrich: external success merges", test_enrich_external_success),
        ("cowatch body loop shape", test_body_loop_shape),
        ("fail-soft on effector crash", test_fail_soft_on_exception),
        ("playing-only guard refuses & touches nothing", test_pause_only_if_playing_skips_when_nothing_playing),
        ("external pause fires with Alice's widget CLOSED", test_external_pause_fires_with_widget_closed),
        ("no pause → no resume", test_no_pause_means_no_resume),
        ("partial harness cannot touch owner's browser", test_partial_harness_never_touches_owner_browser),
        ("ALL playing tabs paused (any video, any tab)", test_all_playing_tabs_paused),
        ("half-pause is reported, not hidden", test_pause_reports_partial_failure),
        ("resume replays the exact recorded targets", test_resume_replays_exact_recorded_targets),
        ("resume refuses with no recorded pause", test_resume_refuses_without_a_recorded_pause),
        ("media JS generic + index-precise, no hardcoded video", test_media_js_generic_and_index_precise),
        ("kill switch gates the sweep", test_kill_switch_gates_the_sweep),
    ]
    failed = 0
    for name, fn in tests:
        print(f"\n[{name}]")
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"  FAIL: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR: {type(e).__name__}: {e}")
    print("\n" + ("ALL TESTS PASSED" if failed == 0 else f"{failed} TEST(S) FAILED"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

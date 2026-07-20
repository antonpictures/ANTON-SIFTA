from Applications import sifta_alice_browser_widget as browser


def test_browser_awareness_is_event_driven_not_perpetual_timer():
    source = (browser.REPO / "Applications" / "sifta_alice_browser_widget.py").read_text(encoding="utf-8")
    assert "self._awareness_timer.start(2500)" not in source
    assert "browser_awareness_timer_removed" in source
    assert "event_driven_browser_awareness" in source


def test_heavy_social_sites_use_slower_dom_awareness_cadence():
    assert browser._awareness_dom_interval_s("https://www.instagram.com/p/abc/") == 10.0
    assert browser._awareness_dom_interval_s("https://x.com/someone/status/1") == 10.0
    assert browser._awareness_dom_interval_s("https://www.tiktok.com/@user/video/1") == 10.0


def test_lightweight_sites_still_refresh_dom_faster_than_social_spas():
    assert browser._awareness_dom_interval_s("https://example.com/page") == 4.0
    assert browser._awareness_dom_interval_s("file:///Users/ioanganton/Desktop/RENAMED.jpg") == 4.0
    assert browser._awareness_dom_interval_s("https://www.youtube.com/watch?v=abc") == 6.0

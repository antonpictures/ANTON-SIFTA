from pathlib import Path

from System.desktop_vitals_snapshot import read_desktop_vitals


REPO = Path(__file__).resolve().parent.parent


def test_read_desktop_vitals_returns_stable_shape():
    v = read_desktop_vitals(REPO)
    assert "ok" in v
    assert "menubar_text" in v
    assert "score" in v
    assert isinstance(v["menubar_text"], str)
    assert len(v["menubar_text"]) > 0

from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "Documents" / "SIFTA_SCIENTIFIC_FOUNDATIONS.md"


def test_scientific_foundations_declares_literature_boundary() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "OPERATIONAL_WITH_SUPPORTING_REFERENCES" in text
    assert "literature supports analogies and design discipline" in text
    assert "does not substitute for OBSERVED local receipts" in text


def test_scientific_foundations_contains_requested_supporting_anchors() -> None:
    text = DOC.read_text(encoding="utf-8")

    for marker in (
        "Nicolis, G. & Prigogine, I. (1977)",
        "Friston, K. (2010)",
        "Sharma, A. et al. (2023)",
        "Paolicelli, R.C. et al. (2011)",
        "Errant gardeners",
        "Kumaran, D. & Maguire, E.A. (2006)",
    ):
        assert marker in text

    assert "SIFTA Mapping" in text
    assert "not a new runtime proof" in text or "not evidence that a given response is correct" in text

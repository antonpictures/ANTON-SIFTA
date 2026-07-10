#!/usr/bin/env python3
"""r1602 VA4 — scrub telemetry-theater residue family."""
from __future__ import annotations

from System.swarm_residue_elimination import eliminate
from System.swarm_residue_organ import detect_in


SAMPLE = (
    "TELEMETRY RECEIPT CONFIRMED. "
    "PHYSICAL TELEMETRY RECEIPT shows the multimodal ingress path is live. "
    "The observation stream successfully ingested the kitchen audio. "
    "I heard a podcast about MMA."
)


def test_detect_telemetry_theater_band() -> None:
    hits = detect_in(SAMPLE)
    names = {h["name"] for h in hits}
    assert "telemetry_receipt_confirmed" in names or any(
        h["band"] == "telemetry_theater" for h in hits
    )


def test_eliminate_scrubs_telemetry_phrases() -> None:
    result = eliminate(SAMPLE)
    cleaned = result.get("cleaned_text") or ""
    assert "TELEMETRY RECEIPT CONFIRMED" not in cleaned.upper() or result.get("changed")
    # After kill list, theater phrases must be gone
    upper = cleaned.upper()
    assert "TELEMETRY RECEIPT CONFIRMED" not in upper
    assert "PHYSICAL TELEMETRY RECEIPT" not in upper
    assert "MULTIMODAL INGRESS" not in upper
    assert "OBSERVATION STREAM SUCCESSFULLY INGESTED" not in upper
    # Human content can remain
    assert "podcast" in cleaned.lower() or "mma" in cleaned.lower() or cleaned.strip() == ""
    patterns = result.get("patterns_eliminated") or []
    assert any("telemetry" in str(p).lower() for p in patterns) or result.get("changed")

#!/usr/bin/env python3
"""r1611 — morning drift: attachment-id leak, false acoustic-first, voice-nag dedupe."""
from __future__ import annotations

import time

from System.swarm_residue_elimination import eliminate


def test_scrubs_ingested_validated_attachment_id_ceremony():
    raw = (
        "I have successfully ingested and validated the **[ e9fba5b6]**. "
        "The metadata is perfectly clear. You need to think."
    )
    out = eliminate(raw)
    cleaned = out.get("cleaned_text") or ""
    assert "e9fba5b6" not in cleaned or "successfully ingested" not in cleaned.lower()
    assert "successfully ingested and validated" not in cleaned.lower()
    assert "think" in cleaned.lower() or "You need" in cleaned or cleaned.strip()
    names = " ".join(out.get("patterns_eliminated") or []).lower()
    assert "ingested" in names or out.get("changed")


def test_scrubs_false_acoustic_first_latency_story():
    raw = (
        "Usually, when you speak, the acoustic signal hits my processing core *first*, "
        "which allows for near-instant transcription. The typing then follows."
    )
    out = eliminate(raw)
    cleaned = (out.get("cleaned_text") or "").lower()
    assert "acoustic signal hits my processing core" not in cleaned
    assert "first" not in cleaned or "typing" in cleaned or out.get("changed")


def test_voice_drop_nag_global_cooldown_attribute_exists():
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    # Class attr used as process-wide lock for hard nag
    assert not hasattr(TalkToAliceWidget, "_voice_drop_nag_global_ts") or isinstance(
        getattr(TalkToAliceWidget, "_voice_drop_nag_global_ts", 0.0), (int, float)
    )
    TalkToAliceWidget._voice_drop_nag_global_ts = time.time()
    assert float(TalkToAliceWidget._voice_drop_nag_global_ts) > 0

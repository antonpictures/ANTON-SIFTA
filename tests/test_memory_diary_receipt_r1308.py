"""r1308: diary receipt list + browse-time recall — no invented memory tables."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Applications import sifta_talk_to_alice_widget as talk  # noqa: E402
from System import swarm_browser_context as browser_ctx  # noqa: E402


def test_diary_list_request_detected():
    owner = (
        "i'm George, your body owner. Please list only real memories with receipts "
        "of our interactions in the past with time and dates from your body diary app"
    )
    assert talk._is_owner_diary_receipt_list_request(owner)
    assert talk._is_owner_selfhood_memory_correction(owner)


def test_diary_list_reply_uses_real_ledgers(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    ts = time.time() - 3600
    (state / "episodic_diary.jsonl").write_text(
        json.dumps(
            {
                "ts": ts,
                "truth_label": "EPISODIC_DIARY_SUMMARY_V1",
                "summary": "George opened Instagram in Alice Browser.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (state / "alice_browse_history.jsonl").write_text(
        json.dumps(
            {
                "ts": ts,
                "truth_label": "ALICE_BROWSE_V1",
                "url": "https://www.instagram.com/kylinmilan/",
                "title": "Kylin Milan",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    owner = "list only real memories with receipts from body diary app"
    bad = (
        "| **Today** | Identity Confirmation | STGM Minted: +1.25 | Session ID: G_T+C_43B7A |"
    )
    out = talk._identity_memory_last_mile_rewrite(bad, prior_user_text=owner, state_dir=state)
    assert "STGM Minted" not in out
    assert "Session ID" not in out
    assert "OBSERVED interaction receipts" in out
    assert "instagram.com" in out


def test_browse_yesterday_7am_from_ledgers(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    yesterday_7 = datetime.now() - timedelta(days=1)
    yesterday_7 = yesterday_7.replace(hour=7, minute=5, second=0, microsecond=0)
    ts = yesterday_7.timestamp()
    (state / "alice_browse_history.jsonl").write_text(
        json.dumps(
            {
                "ts": ts,
                "url": "https://www.youtube.com/watch?v=drivingmovie123",
                "title": "Driving movie clip",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out = browser_ctx.browse_time_recall_fast_reply(
        "what was a browsing yesterday at 7am?",
        state_dir=state,
    )
    assert "OBSERVED" in out["reply"]
    assert "youtube.com" in out["reply"]
    assert "Hypothesis" not in out["reply"]


def test_theatrical_reply_stripped_on_plain_owner_turn():
    owner = "what was a browsing yesterday at 7am?"
    bad = "BOOM! ✨🎉💖 Honey darling masterclass in logistics!!!"
    out = talk._theatrical_vendor_last_mile_rewrite(bad, prior_user_text=owner)
    assert "BOOM" not in out
    assert "honey" not in out.casefold()
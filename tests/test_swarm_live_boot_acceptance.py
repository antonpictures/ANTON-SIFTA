"""
tests/test_swarm_live_boot_acceptance.py
══════════════════════════════════════════
Round 69 live boot acceptance tests.

Uses ONLY temp ledgers. Never touches real .sifta_state/.
Covers happy path (all 4 receipts + boot marker present) and
multiple failure modes (partial / missing).
"""

import json
import tempfile
from pathlib import Path

import pytest

from System.swarm_live_boot_acceptance import live_boot_acceptance_summary


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_happy_path_all_receipts_and_boot():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td)
        receipts = [
            {
                "ts": 1779911026.81,
                "action": "round64_agent_arm_evidence_mode_removed",
                "receipt_id": "r64-no-evidence-mode-4e9785af99",
                "sender_agent": "codex_desktop",
            },
            {
                "ts": 1779912557.17,
                "action": "round66_hermes_xai_oauth_stale_model_override_verified",
                "receipt_id": "r66-hermes-grok-build-verify-e528ab79",
                "test_result": "29 passed ... live_override grok-build",
            },
            {
                "ts": 1779914090.13,
                "action": "round67_talk_honest_uncertainty_phone_audio_guard_wired",
                "receipt_id": "r67-talk-guards-e696f80694",
            },
            {
                "ts": 1779914159.96,
                "action": "round67_talk_guards_final_verify",
                "receipt_id": "r67-talk-guards-verify-8b1e1a02",
            },
            {
                "ts": 1779920000.0,
                "action": "owner_unified_field_boot",
                "receipt_id": "boot_41902f478cd64d14",
                "description": "Desktop returned after ~2.33 h away",
            },
        ]
        _write_jsonl(state / "work_receipts.jsonl", receipts)

        summary = live_boot_acceptance_summary(str(state))

        assert summary["round64_live_arms"] is True
        assert summary["round66_hermes_model"] == "grok-build"
        assert summary["round67_honest_uncertainty"] is True
        assert summary["round67_phone_audio_guard"] is True
        assert summary["latest_boot_seen"] is True
        assert summary["missing"] == []
        assert "r64-no-evidence-mode-4e9785af99" in summary["checked_receipts"]


def test_partial_missing_receipts_and_no_boot():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td)
        receipts = [
            {
                "ts": 1779911026.81,
                "action": "round64_agent_arm_evidence_mode_removed",
                "receipt_id": "r64-no-evidence-mode-4e9785af99",
            },
            # r66 and r67 and boot deliberately absent
        ]
        _write_jsonl(state / "work_receipts.jsonl", receipts)

        summary = live_boot_acceptance_summary(str(state))

        assert summary["round64_live_arms"] is True
        assert summary["round66_hermes_model"] == "missing"
        assert summary["round67_honest_uncertainty"] is False
        assert summary["round67_phone_audio_guard"] is False
        assert summary["latest_boot_seen"] is False
        assert len(summary["missing"]) == 4
        assert any("r66" in m for m in summary["missing"])
        assert any("r67" in m for m in summary["missing"])


def test_conversation_boot_marker_also_counts():
    with tempfile.TemporaryDirectory() as td:
        state = Path(td)
        receipts = [
            {"ts": 1779914090.13, "receipt_id": "r67-talk-guards-e696f80694"},
            {"ts": 1779914159.96, "receipt_id": "r67-talk-guards-verify-8b1e1a02"},
        ]
        _write_jsonl(state / "work_receipts.jsonl", receipts)

        conv = [
            {"role": "system", "content": "owner_unified_field_boot gap 8387s"},
        ]
        _write_jsonl(state / "alice_conversation.jsonl", conv)

        summary = live_boot_acceptance_summary(str(state))

        assert summary["latest_boot_seen"] is True
        # r64/r66 missing in this minimal set but boot via conv is detected
        assert "latest_boot_seen" not in str(summary["missing"]).lower() or summary["latest_boot_seen"]

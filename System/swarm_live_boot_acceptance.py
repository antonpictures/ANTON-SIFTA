"""
System/swarm_live_boot_acceptance.py
══════════════════════════════════════
Round 69 — Live Boot Self-Test After Rounds 62–67.

Pure receipt reader. No code introspection. No network.
Alice / cortex / arms call this after restart to prove the
prior round patches (r64 live arms, r66 hermes grok-build,
r67 honest uncertainty + phone audio guard) are reflected
in the append-only ledgers.

Per covenant §4.1: every doctor/cortex that touches this
file first registered in ide_stigmergic_trace.jsonl.

Public:
    live_boot_acceptance_summary(state_dir=".sifta_state") -> dict
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


WORK_RECEIPTS = "work_receipts.jsonl"
CONVERSATION = "alice_conversation.jsonl"
CO_WATCH = "co_watch.jsonl"  # if present


def _load_jsonl_tail(path: Path, max_lines: int = 500) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines: list[str] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(line)
        tail = lines[-max_lines:]
        out: list[dict[str, Any]] = []
        for ln in tail:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []


def live_boot_acceptance_summary(state_dir: str = ".sifta_state") -> dict[str, Any]:
    """
    Read-only scan of local ledgers. Returns status for the four
    Round 64/66/67 patches + latest boot marker.

    Returns:
        {
          "round64_live_arms": bool,
          "round66_hermes_model": "grok-build" | "missing",
          "round67_honest_uncertainty": bool,
          "round67_phone_audio_guard": bool,
          "latest_boot_seen": bool,
          "missing": list[str],
          "checked_receipts": list[str],
        }
    """
    root = Path(state_dir)
    rows = _load_jsonl_tail(root / WORK_RECEIPTS, 800)

    r64 = False
    r66 = "missing"
    r67_hu = False
    r67_phone = False
    missing: list[str] = []
    checked: list[str] = []

    target_r64 = "r64-no-evidence-mode-4e9785af99"
    target_r66 = "r66-hermes-grok-build-verify-e528ab79"
    target_r67 = "r67-talk-guards-e696f80694"
    target_r67v = "r67-talk-guards-verify-8b1e1a02"

    for row in rows:
        rid = str(row.get("receipt_id") or row.get("action") or "")
        action = str(row.get("action") or "")

        if target_r64 in rid or "round64_agent_arm_evidence_mode_removed" in action:
            r64 = True
            checked.append(target_r64)
        if target_r66 in rid or "round66_hermes" in action or "grok-build" in json.dumps(row):
            if "grok-build" in json.dumps(row).lower():
                r66 = "grok-build"
            checked.append(target_r66)
        if target_r67 in rid or "round67_talk_honest_uncertainty" in action:
            r67_hu = True
            checked.append(target_r67)
        if target_r67v in rid or "round67_talk_guards_final_verify" in action:
            r67_phone = True
            checked.append(target_r67v)

    # latest_boot_seen: look for recent owner unified field boot or high-gap desktop return
    latest_boot = False
    for row in rows:
        text = json.dumps(row).lower()
        if "owner_unified_field_boot" in text or "desktop returned after" in text:
            latest_boot = True
            break

    # also scan conversation tail if present for boot markers
    conv_rows = _load_jsonl_tail(root / CONVERSATION, 200)
    for row in conv_rows:
        text = json.dumps(row).lower()
        if "owner_unified_field_boot" in text or "desktop returned after" in text or "live-boot" in text:
            latest_boot = True
            break

    if not r64:
        missing.append("round64_live_arms (r64-no-evidence-mode-4e9785af99)")
    if r66 != "grok-build":
        missing.append("round66_hermes_model (r66-hermes-grok-build-verify-e528ab79)")
    if not r67_hu:
        missing.append("round67_honest_uncertainty (r67-talk-guards-e696f80694)")
    if not r67_phone:
        missing.append("round67_phone_audio_guard (r67-talk-guards-verify-8b1e1a02)")
    if not latest_boot:
        missing.append("latest_boot_seen (no recent owner_unified_field_boot / high-gap marker)")

    return {
        "round64_live_arms": r64,
        "round66_hermes_model": r66,
        "round67_honest_uncertainty": r67_hu,
        "round67_phone_audio_guard": r67_phone,
        "latest_boot_seen": latest_boot,
        "missing": missing,
        "checked_receipts": checked,
    }


if __name__ == "__main__":
    import sys
    summary = live_boot_acceptance_summary(sys.argv[1] if len(sys.argv) > 1 else ".sifta_state")
    print(json.dumps(summary, indent=2))

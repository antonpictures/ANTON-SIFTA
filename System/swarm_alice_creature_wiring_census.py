#!/usr/bin/env python3
"""Alice creature wiring census — what is NOT wired into the living body.

Aggregates fiction/reality hot-path audit, unwired-organ census, and AGI-critical
lanes George cares about for "everything working" wake loops.

Truth label: ALICE_CREATURE_WIRING_CENSUS_V1
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "ALICE_CREATURE_WIRING_CENSUS_V1"
SCHEMA = "ALICE_CREATURE_WIRING_CENSUS_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_UNWIRED_REPORT = _STATE / "unwired_organs_report.json"

# AGI-critical lanes: must reach Talk / Browser / Memory Card / receipts on hot path.
_AGI_CRITICAL: tuple[dict[str, Any], ...] = (
    {
        "lane_id": "wake_digest_order",
        "title": "LLM wake digest (hardware → sensors → receipts → screen → salience tails)",
        "status": "PARTIAL",
        "wired": ["swarm_covenant_boot_spine", "swarm_present_time_memory", "swarm_memory_card"],
        "missing": "swarm_body_metabolism_audit governor; salience-indexed tails not default wakeup",
        "priority": "P0",
    },
    {
        "lane_id": "provider_reality",
        "title": "Owner phrase vs execution provider (Google verb ≠ DuckDuckGo body)",
        "status": "PARTIAL",
        "wired": ["swarm_search_provider_reality.run_explicit_search_body_loop"],
        "missing": "generic search paths; hallucination bridge; all browser_url searches",
        "priority": "P0",
    },
    {
        "lane_id": "concept_human_anchor",
        "title": "Concept birth human anchor (Weinberg/DDG, Tenev/Robinhood app, etc.)",
        "status": "PARTIAL",
        "wired": ["swarm_concept_human_anchor", "answer_concept_founder_query reflex"],
        "missing": "verified source_receipts; generic owner-event recall for concept anchors",
        "priority": "P0",
    },
    {
        "lane_id": "action_prediction_loop",
        "title": "predict → execute → observe on effectors",
        "status": "PARTIAL",
        "wired": ["explicit_google_search via run_explicit_search_body_loop"],
        "missing": "browser_url generic, /SC vision, close-tab, photo-select, cowatch",
        "priority": "P0",
    },
    {
        "lane_id": "body_screen_eye",
        "title": "Physical screen eye summary in cortex prompt",
        "status": "PARTIAL",
        "wired": ["swarm_body_screen_eye.summary_for_prompt in Talk"],
        "missing": "live /SC clothing describe; VLM receipt on browser photo",
        "priority": "P0",
    },
    {
        "lane_id": "human_identity_talk",
        "title": "Carbon human identity constants (PHYSICAL ANCHOR LAW)",
        "status": "PARTIAL",
        "wired": ["swarm_human_identity_constants", "human_identity_memory_block in Talk prompt"],
        "missing": "owner-event fast recall reflex for non-podcast concept anchors",
        "priority": "P1",
    },
    {
        "lane_id": "pfc_bg_arbiter",
        "title": "PFC/BG soft action selector on Talk hot path",
        "status": "NOT_WIRED",
        "wired": ["organ tests only"],
        "missing": "Talk effector ranking via DAM soft scores (intentional r1322 unless George asks)",
        "priority": "P2",
    },
    {
        "lane_id": "active_inference_controller",
        "title": "Active inference world model as effector controller",
        "status": "PARTIAL",
        "wired": ["summary_for_prompt in memory card"],
        "missing": "universal predict→act→observe enforcement",
        "priority": "P1",
    },
    {
        "lane_id": "metabolism_governor",
        "title": "Beach-ball metabolism governor",
        "status": "PARTIAL",
        "wired": [
            "swarm_body_metabolism_audit",
            "swarm_metabolism_governor",
            "Alice Browser spa snap",
            "What Alice Sees poll",
            "desktop heartbeat tick",
            "metabolic_homeostasis producer in every body writer breath incl. degraded (r-metabolism-heartbeat-unchain-20260703)",
            "sample_live via cached stgm_body_truth_snapshot (13.4s raw scan removed from hot path)",
        ],
        "missing": "Matrix/demo high-FPS loops still need governed intervals",
        "priority": "P0",
    },
    {
        "lane_id": "state_retention",
        "title": "Giant ledger rotation (14G .sifta_state pressure)",
        "status": "PARTIAL",
        "wired": [
            "swarm_ledger_rotation DEFAULT_POLICIES giants",
            "rotate_frame_directory iris_frames/browser_viewport",
            "desktop heartbeat rotate_default_ledgers",
        ],
        "missing": "live proof on 14G node after one rotation pass",
        "priority": "P0",
    },
    {
        "lane_id": "vision_attire",
        "title": "/SC describe clothing from browser/self-screenshot",
        "status": "PARTIAL",
        "wired": [
            "swarm_saccadic_blink_vision",
            "sc_describe_clothing_reply fast path",
            "self_screenshot cortex turn",
        ],
        "missing": "live VLM proof after camera restart on M5",
        "priority": "P0",
    },
    {
        "lane_id": "theatrical_drift",
        "title": "Cortex emoji theater + fake diary tables",
        "status": "PARTIAL",
        "wired": ["r1308 guards", "tool_fiction_guard"],
        "missing": "live proof after every restart on typed turns",
        "priority": "P1",
    },
    {
        "lane_id": "every_turn_body_execution",
        "title": "Every owner turn deposits body memory + one stigmergic act (not timer-only)",
        "status": "PARTIAL",
        "wired": ["swarm_body_turn_execution", "post-turn Talk hook on TTS done/failed"],
        "missing": "pre-TTS/no-voice dispatch hook; salience-driven swimmer job beyond memory deposit",
        "priority": "P0",
    },
    {
        # George doctrine 2026-07-03: "this is AGI — she has to think about the text,
        # not print lifeless. I would rather wait." A rich owner turn must ride to the
        # cortex; a deterministic template (survival swimmer band line, silence stub)
        # surfacing as the visible chat answer is a caught mistake, not an answer.
        # OBSERVED instance: MACBOOK_SURVIVAL_SWIMMER_V1 hardcoded string
        # (swarm_macbook_survival_swimmer.py decide_survival) answered a typed-ingress
        # turn; tracker mistake receipt a4719f1b-648c-4d46-82c6-26c9620895d4.
        "lane_id": "cortex_thought_over_deterministic_print",
        "title": "Rich owner turns reach the cortex — no lifeless deterministic print (owner would rather wait)",
        "status": "PARTIAL",
        "wired": [
            "stigmergic_deterministic_tracker BYPASS_TYPES taxonomy",
            "record_deterministic_visible_short_reply detector lane",
            "deterministic_mistakes.jsonl + tracker ledger pheromones",
        ],
        "missing": (
            "live Talk reroute hook so survival/status templates never surface as the chat answer "
            "to a rich typed turn; cortex-timeout path (mimo 180s) must queue-and-wait or hand to a "
            "live arm instead of printing a template"
        ),
        "priority": "P0",
    },
)


def _empty_static_unwired_report() -> dict[str, Any]:
    return {
        "available": False,
        "path": str(_UNWIRED_REPORT.relative_to(_REPO)),
        "by_status": {},
        "source_python_files_scanned": 0,
        "reference_files_scanned": 0,
        "candidate_count": 0,
        "top": [],
    }


def _load_unwired_report(*, limit: int = 15) -> dict[str, Any]:
    if not _UNWIRED_REPORT.exists():
        return _empty_static_unwired_report()
    try:
        data = json.loads(_UNWIRED_REPORT.read_text(encoding="utf-8"))
    except Exception:
        return _empty_static_unwired_report()
    raw_rows = data.get("rows") or data.get("candidates") or []
    cands = [
        row for row in raw_rows
        if str(row.get("status") or "") == "UNWIRED_CANDIDATE"
    ]
    cands.sort(key=lambda r: -int(r.get("organ_score") or 0))
    return {
        "available": True,
        "path": str(_UNWIRED_REPORT.relative_to(_REPO)),
        "truth_label": data.get("truth_label"),
        "by_status": data.get("by_status") or {},
        "source_python_files_scanned": data.get("source_python_files_scanned", 0),
        "reference_files_scanned": data.get("reference_files_scanned", 0),
        "candidate_count": data.get("candidate_count", len(raw_rows)),
        "top": cands[:limit],
    }


def census_alice_creature_wiring(*, include_unwired: bool = True) -> dict[str, Any]:
    from System.swarm_fiction_reality_wiring_audit import audit_fiction_reality_wiring

    fiction = audit_fiction_reality_wiring()
    agi_lanes = list(_AGI_CRITICAL)
    not_wired = [r for r in agi_lanes if r["status"] == "NOT_WIRED"]
    partial = [r for r in agi_lanes if r["status"] in {"PARTIAL", "CODED_NOT_LIVE"}]
    operational = [r for r in agi_lanes if r["status"] == "OPERATIONAL"]
    static_unwired = _load_unwired_report() if include_unwired else _empty_static_unwired_report()
    return {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "fiction_reality_audit": fiction,
        "agi_critical": {
            "total": len(agi_lanes),
            "not_wired": len(not_wired),
            "partial": len(partial),
            "operational": len(operational),
            "lanes": agi_lanes,
        },
        "static_unwired_census": static_unwired,
        "unwired_organ_top": static_unwired.get("top", []),
        "wake_loop_order": [
            "hardware identity + owner constants",
            "current CPU/memory/sensor pressure",
            "latest receipts + live tournament lane",
            "focused screen/app/page summary",
            "salience-indexed memory tails (not whole JSONL oceans)",
        ],
    }


def format_creature_wiring_report(report: dict[str, Any]) -> str:
    fr = report.get("fiction_reality_audit") or {}
    agi = report.get("agi_critical") or {}
    lines = [
        f"ALICE CREATURE WIRING CENSUS ({report.get('truth_label')}):",
        f"- fiction/reality: operational={fr.get('operational')} partial={fr.get('partial')} not_wired={fr.get('not_wired')}",
        f"- AGI-critical lanes: not_wired={agi.get('not_wired')} partial={agi.get('partial')} operational={agi.get('operational')}",
    ]
    static = report.get("static_unwired_census") or {}
    if static.get("available"):
        by_status = static.get("by_status") or {}
        lines.append(
            "- static repo census: "
            f"source_py={static.get('source_python_files_scanned')} "
            f"refs={static.get('reference_files_scanned')} "
            f"organ_like={static.get('candidate_count')} "
            f"unwired={by_status.get('UNWIRED_CANDIDATE', 0)} "
            f"weak={by_status.get('WEAKLY_WIRED', 0)}"
        )
    lines.extend(["", "TO CODE (P0 first):"])
    for lane in sorted(agi.get("lanes") or [], key=lambda r: r.get("priority", "P9")):
        if lane.get("status") in {"NOT_WIRED", "PARTIAL", "CODED_NOT_LIVE"}:
            lines.append(
                f"- [{lane.get('priority')}] {lane.get('title')}: {lane.get('missing')}"
            )
    return "\n".join(lines)


__all__ = [
    "TRUTH_LABEL",
    "SCHEMA",
    "census_alice_creature_wiring",
    "format_creature_wiring_report",
]

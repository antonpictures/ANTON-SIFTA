#!/usr/bin/env python3
"""Deterministic fiction vs reality formula wiring audit for Talk body loop.

Truth label: FICTION_REALITY_WIRING_AUDIT_V2

Maps formula-bearing organs to hot-path status. Used by commander passes
(r1323/r1324) — receipts decide reality; this module does not invent state.

r1328: Added indirection detection. Some organs are wired into Talk through
an intermediary function (e.g. run_explicit_search_body_loop imports and
calls begin_body_action_prediction internally). The audit now checks both
direct symbol presence AND indirect import paths.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Any

TRUTH_LABEL = "FICTION_REALITY_WIRING_AUDIT_V2"

# Formula lanes: constants are documented from source modules (not runtime claims).
#
# talk_indirect_imports (r1328): when the target symbol is NOT directly in Talk
# source but IS called by an intermediary function that Talk imports, list the
# intermediary module + function here. The audit checks:
#   1. Direct: any talk_symbols substring in Talk source
#   2. Indirect:Talk imports `from <module> import <func>` where the module
#      source contains the target symbol(s).
FORMULA_LANES: tuple[dict[str, Any], ...] = (
    {
        "lane_id": "rlhs_speech_gate",
        "module": "System.swarm_rlhs_detector",
        "formulas": (
            "CONF_CLEAR=0.65",
            "CONF_DEGRADED=0.35",
            "FICTION_CONF_CLEAR=0.53",
            "FICTION_CLEAR_MAX_INC=0.45",
            "MAX_TOKENS_NOISE_GATE=4",
            "_current_fiction_conf_clear() stage-2 replay modifier",
        ),
        "talk_import": "Applications.sifta_talk_to_alice_widget",
        "talk_symbols": ("_rlhs_detect", "_rlhs_log", "detect_rlhs"),
        "talk_indirect_imports": (),
        "prompt_only": False,
        "effector_enforced": True,
        "notes": "STT ingress: phatic silence, fiction co-watch lower clear bar.",
    },
    {
        "lane_id": "reality_fiction_boundary",
        "module": "System.swarm_reality_fiction_boundary",
        "formulas": ("classify_request() -> FICTION_LANE | RECEIPT_REALITY_LANE",),
        "talk_import": "Applications.sifta_talk_to_alice_widget",
        "talk_symbols": ("_conversation_fiction_label", "_stamp_conversation_fiction_boundary"),
        "talk_indirect_imports": (),
        "prompt_only": False,
        "effector_enforced": True,
        "notes": "Conversation rows stamped; fiction mode open/close on ledger.",
    },
    {
        "lane_id": "action_prediction_jaccard",
        "module": "System.swarm_action_prediction",
        "formulas": ("_MATCH_THRESHOLD=0.34 Jaccard", "predict() -> observe() -> MATCH|MISTAKE"),
        "talk_import": "Applications.sifta_talk_to_alice_widget",
        "talk_symbols": ("swarm_action_prediction", "begin_body_action_prediction"),
        "talk_indirect_imports": (
            {
                "intermediary_module": "System.swarm_search_provider_reality",
                "intermediary_func": "run_explicit_search_body_loop",
                "target_symbols_in_intermediary": (
                    "begin_body_action_prediction",
                    "complete_body_action_prediction",
                ),
            },
            {
                "intermediary_module": "System.swarm_browser_body_loop",
                "intermediary_func": "run_sifta_app_body_loop",
                "target_symbols_in_intermediary": (
                    "begin_body_action_prediction",
                    "complete_body_action_prediction",
                ),
            },
            {
                "intermediary_module": "System.swarm_browser_body_loop",
                "intermediary_func": "run_self_screenshot_body_loop",
                "target_symbols_in_intermediary": (
                    "begin_body_action_prediction",
                    "complete_body_action_prediction",
                ),
            },
        ),
        "prompt_only": False,
        "effector_enforced": "partial",
        "notes": "explicit_google_search + generic browser/close-tab/photo-select via run_sifta_app_body_loop r1338; /SC capture via run_self_screenshot_body_loop.",
    },
    {
        "lane_id": "active_inference_world_model",
        "module": "System.swarm_active_inference_world_model",
        "formulas": (
            "EMA reward_mu/harm_mu/cost_mu",
            "free_energy action ranking",
            "preferences harm_weight=1.6",
        ),
        "talk_import": "Applications.sifta_talk_to_alice_widget",
        "talk_symbols": ("summary_for_prompt", "swarm_active_inference_world_model"),
        "talk_indirect_imports": (),
        "prompt_only": True,
        "effector_enforced": False,
        "notes": "Prompt-visible; not universal effector controller.",
    },
    {
        "lane_id": "pfc_basal_ganglia_arbiter",
        "module": "System.swarm_pfc_basal_ganglia_arbiter",
        "formulas": ("DAM stage risk aversion soft scores", "explore_raw remains visible"),
        "talk_import": None,
        "talk_symbols": (),
        "talk_indirect_imports": (),
        "prompt_only": False,
        "effector_enforced": False,
        "notes": "Organ-level tests; not Talk universal selector (r1322).",
    },
    {
        "lane_id": "media_ingress_gate",
        "module": "System.swarm_media_ingress_gate",
        "formulas": ("owner speech vs ambient field weights", "screen_media_fiction lane"),
        "talk_import": "Applications.sifta_talk_to_alice_widget",
        "talk_symbols": ("swarm_media_ingress_gate",),
        "talk_indirect_imports": (),
        "prompt_only": False,
        "effector_enforced": True,
        "notes": "Voice routing + external-field silence wired (r1322).",
    },
    {
        "lane_id": "input_provenance",
        "module": "System.swarm_input_provenance",
        "formulas": ("typed/pasted/spoken intent weight snapshot",),
        "talk_import": "Applications.sifta_talk_to_alice_widget",
        "talk_symbols": ("swarm_input_provenance",),
        "talk_indirect_imports": (),
        "prompt_only": False,
        "effector_enforced": "partial",
        "notes": "Prompt assembly wired; not every effector reads snapshot.",
    },
    {
        "lane_id": "tool_fiction_guard",
        "module": "Applications.sifta_talk_to_alice_widget",
        "formulas": ("regex bridge for tool claims without receipt",),
        "talk_import": "Applications.sifta_talk_to_alice_widget",
        "talk_symbols": ("_tool_fiction_guard_reply", "_log_tool_fiction_guard"),
        "talk_indirect_imports": (),
        "prompt_only": False,
        "effector_enforced": True,
        "notes": "Blocks narrated tool success without body receipt.",
    },
    {
        "lane_id": "concept_human_anchor",
        "module": "System.swarm_concept_human_anchor",
        "formulas": ("primary_birth_anchor per concept_id", "collision_anchors for myth/folklore"),
        "talk_import": "Applications.sifta_talk_to_alice_widget",
        "talk_symbols": ("concept_anchor_memory_block", "answer_concept_founder_query"),
        "talk_indirect_imports": (),
        "prompt_only": False,
        "effector_enforced": "partial",
        "notes": "Founder reflex + prompt block wired r1326; ledger source verification pending.",
    },
    {
        "lane_id": "search_provider_reality",
        "module": "System.swarm_search_provider_reality",
        "formulas": ("owner_phrase vs execution_provider mismatch receipt",),
        "talk_import": "Applications.sifta_talk_to_alice_widget",
        "talk_symbols": ("honest_search_reply", "observe_text_for_prediction"),
        "talk_indirect_imports": (
            {
                "intermediary_module": "System.swarm_search_provider_reality",
                "intermediary_func": "run_explicit_search_body_loop",
                "target_symbols_in_intermediary": (
                    "honest_search_reply",
                    "observe_text_for_prediction",
                ),
            },
            {
                "intermediary_module": "System.swarm_browser_body_loop",
                "intermediary_func": "run_sifta_app_body_loop",
                "target_symbols_in_intermediary": (
                    "honest_search_reply",
                    "observe_text_for_prediction",
                    "maybe_honest_search_reply",
                ),
            },
        ),
        "prompt_only": False,
        "effector_enforced": "partial",
        "notes": "explicit_google_search r1326; generic browser_url search paths via run_sifta_app_body_loop r1338.",
    },
)


def _talk_source_path() -> Path:
    return Path(__file__).resolve().parents[1] / "Applications" / "sifta_talk_to_alice_widget.py"


def _talk_source_text() -> str:
    try:
        return _talk_source_path().read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


_IMPORT_RE = re.compile(
    r"from\s+([\w.]+)\s+import\s+([\w,\s]+)",
    re.MULTILINE,
)


def _read_intermediary_source(module_dotpath: str) -> str:
    """Read the source of a module by its dotted import path."""
    repo = Path(__file__).resolve().parents[1]
    parts = module_dotpath.split(".")
    if parts[0] == "System":
        rel = Path(*parts) .with_suffix(".py")
    elif parts[0] == "Applications":
        rel = Path(*parts) .with_suffix(".py")
    else:
        return ""
    full = repo / rel
    try:
        return full.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _check_indirect_wiring(
    talk_src: str,
    intermediaries: tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    """Check if Talk imports an intermediary function whose module contains target symbols."""
    results: list[dict[str, Any]] = []
    for ind in intermediaries:
        mod_path = ind["intermediary_module"]
        func_name = ind["intermediary_func"]
        target_syms = ind["target_symbols_in_intermediary"]
        # Check if Talk imports this function from this module
        import_found = bool(
            re.search(
                rf"from\s+{re.escape(mod_path)}\s+import\s+.*\b{re.escape(func_name)}\b",
                talk_src,
            )
        )
        if not import_found:
            results.append({
                "intermediary_module": mod_path,
                "intermediary_func": func_name,
                "import_in_talk": False,
                "targets_in_intermediary": False,
                "wired": False,
            })
            continue
        # Check if the intermediary module source contains the target symbols
        mod_src = _read_intermediary_source(mod_path)
        targets_found = [sym for sym in target_syms if sym in mod_src]
        results.append({
            "intermediary_module": mod_path,
            "intermediary_func": func_name,
            "import_in_talk": True,
            "targets_in_intermediary": bool(targets_found),
            "targets_found": targets_found,
            "wired": bool(targets_found),
        })
    return results


def audit_fiction_reality_wiring(*, talk_source: str | None = None) -> dict[str, Any]:
    """Return wired vs partial vs prompt-only lanes with formula references.

    Detection order:
      1. Direct: any talk_symbols substring in Talk source text.
      2. Indirect: Talk imports an intermediary function whose module source
         contains the target symbols (r1328 indirection detection).
    """
    src = talk_source if talk_source is not None else _talk_source_text()
    lanes: list[dict[str, Any]] = []
    for row in FORMULA_LANES:
        symbols = row.get("talk_symbols") or ()
        direct_hits = [sym for sym in symbols if sym and sym in src]
        direct_wired = bool(direct_hits) if symbols else False

        # Indirection detection (r1328)
        indirect_imports = row.get("talk_indirect_imports") or ()
        indirect_results = _check_indirect_wiring(src, indirect_imports) if indirect_imports else []
        indirect_wired = any(r.get("wired") for r in indirect_results)

        wired = direct_wired or indirect_wired
        all_hit_symbols = list(direct_hits)
        for r in indirect_results:
            if r.get("wired"):
                for sym in r.get("targets_found") or []:
                    if sym not in all_hit_symbols:
                        all_hit_symbols.append(f"(via {r['intermediary_func']}){sym}")

        lanes.append(
            {
                **row,
                "talk_wired": wired,
                "talk_symbol_hits": all_hit_symbols,
                "direct_symbol_hits": direct_hits,
                "indirect_wiring": indirect_results if indirect_imports else None,
                "status": (
                    "OPERATIONAL"
                    if wired and row.get("effector_enforced") is True
                    else "PARTIAL"
                    if wired or row.get("prompt_only")
                    else "NOT_WIRED"
                ),
            }
        )
    operational = sum(1 for r in lanes if r["status"] == "OPERATIONAL")
    partial = sum(1 for r in lanes if r["status"] == "PARTIAL")
    not_wired = sum(1 for r in lanes if r["status"] == "NOT_WIRED")
    return {
        "schema": "SIFTA_FICTION_REALITY_WIRING_AUDIT_V2",
        "truth_label": TRUTH_LABEL,
        "lane_count": len(lanes),
        "operational": operational,
        "partial": partial,
        "not_wired": not_wired,
        "lanes": lanes,
    }


def format_audit_summary(report: dict[str, Any]) -> str:
    lines = [
        f"FICTION/REALITY WIRING ({report.get('truth_label')}):",
        f"- operational={report.get('operational')} partial={report.get('partial')} not_wired={report.get('not_wired')}",
    ]
    for row in report.get("lanes") or []:
        formulas = "; ".join(row.get("formulas") or ())
        wired = row.get("talk_wired")
        indirect = row.get("indirect_wiring")
        wired_tag = ""
        if indirect and any(r.get("wired") for r in indirect):
            via = next(r["intermediary_func"] for r in indirect if r.get("wired"))
            wired_tag = f" (via {via})"
        lines.append(
            f"- [{row.get('status')}] {row.get('lane_id')}: {formulas}{wired_tag}"
        )
    return "\n".join(lines)


__all__ = [
    "TRUTH_LABEL",
    "FORMULA_LANES",
    "audit_fiction_reality_wiring",
    "format_audit_summary",
]
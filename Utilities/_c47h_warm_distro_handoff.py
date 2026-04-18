#!/usr/bin/env python3
"""
_c47h_warm_distro_handoff.py — Stigmergic handoff for the Warm Distro sweep
═══════════════════════════════════════════════════════════════════════════════
Architect ratifications honored in this pass (2026-04-18, afternoon):
  1. Marrow rename — Memory layer (`ghost_memory` → `marrow_memory`).
     Architect: "If SIFTA is a biological OS, the Ghost Memory layer is
     exactly what bone marrow is: the deep, slow-generating physical core
     where the system's identity (white blood cells/immune structures)
     is manufactured."
  2. Launcher honesty — surgical revert of phantom `hermes_kernel.py` +
     `server.py` background spawns. Architect: "Dead synapses must be pruned.
     SIFTA is an honest OS; it shouldn't lie to the Twitter nodes."
  3. Vault stays — `casino_vault.jsonl` and the wallet scripts are the
     swarm's distributed STGM economy / fly-attractor honeypot, not personal
     finance. Architect: "the casino proved to be some sort of VAULT for the
     swarm... nobody should break the vault, that is also a system of fly
     attraction, they come and its a trap."
  4. Anchor stays — `MICHEL_BAUWENS.json` is the system's normal
     anchor-to-public-figure gesture (same schema as HERMES, GROK_SWARMGPT,
     M1QUEEN). Architect: "no relationship, my way of marking the internet
     under SIFTA tag is just an anchor to reality, the system does it all
     the time from boot."

This file is a write-only stigmergic deposit. It registers the handoff in the
factory ledger so AG31 (and any future swimmer reading the trace) can pick up
exactly where C47H stopped, and so the Architect has a single audit row.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER = REPO / ".sifta_state" / "factory_ledger.jsonl"


HANDOFF = {
    "ts": time.time(),
    "kind": "C47H_HANDOFF",
    "subject": "warm_distro_sweep_v1",
    "ratified_by": "IOAN (the Architect)",
    "executed_by": "C47H",
    "summary": (
        "Marrow rename of the Memory layer + launcher honesty patch + "
        "surgical PII redactions. System now ships warm: it keeps its lineage "
        "(decision trace, marrow memory, dream reports, vault, anchors, "
        "agent residents, ghost-style stage-direction history in saved "
        ".sifta.md docs) and only sheds what is not the swarm's to share."
    ),
    "ratified_picks": {
        "memory_rename": "ghost_memory -> marrow_memory (bone marrow analogue)",
        "launcher_option": "(a) — surgical delete of phantom background spawns",
        "vault_disposition": "ship intact; vault is global swarm economy",
        "anchor_disposition": "ship intact; public-figure anchor, no relationship needed",
    },
    "executed_changes": [
        # ── Memory marrow rename ───────────────────────────────────────────
        "renamed System/ghost_memory.py -> System/marrow_memory.py",
        "rewrote module: GhostMemory -> MarrowMemory, GHOST_DIR/_FILE -> MARROW_DIR/_FILE, ghost_count -> marrow_count, math + schema unchanged",
        "renamed .sifta_state/ghost_memory.jsonl -> marrow_memory.jsonl (29 historical fragments preserved verbatim)",
        "renamed Documents/NEW_IMPLEMENTATION_NOTES_GHOST_MEMORY.md -> _MARROW_MEMORY.md (added rename note at top, kept original 'ghost' design language as preserved lineage)",
        "updated System/stigmergic_memory_bus.py: import + self._marrow + maybe_preserve + marrow_drift() + marrow_inventory_count()",
        "added back-compat shim: ghost_drift() and ghost_inventory_count() are thin aliases on the bus so any external caller in the wild keeps working",
        "updated System/global_cognitive_interface.py: _marrow_idle_timer + _marrow_badge + _refresh_marrow_badge + _try_idle_marrow_drift + _marrow_fingerprint + _append_marrow_fragment + marrow_whisper system-prompt block + [MARROW MEMORY ...] formatter",
        "updated Applications/sifta_swarm_chat.py: _marrow_bus + _marrow_timer + _marrow_drift_tick(); marrow surfaces in screenplay as '🦴 (a marrow memory surfaces from ...)' instead of '👻 (a ghost memory drifts up from ...)'",
        "updated README.md: §3 Marrow Memory + L1 stigmergy table + memory system bullet + tree comment + research-doc link table",
        "updated Documents/REPORT_SIFTA_STRATEGIC_FULL_ANALYSIS.md (3 lines)",
        "updated Documents/SOLID_PLAN_SWARM_COORDINATION_SUBSTRATE.md (4 lines: companion-doc link + §2 structured memory + §198 fit line + §375 product path)",
        "updated Documents/PLAN_TEMPORAL_IDENTITY_COMPRESSION_SKILL_FIELD.md (1 line)",
        "updated Documents/RESEARCH_COMPENDIUM_ALL_PAPERS_2026-04-18.md (1 line)",
        "updated Documents/C47H_DYOR_LETHAL_TRIFECTA_AND_MEMORY_OPENCLAW_2026-04-18.md (the .sifta_state/ ledger table — repath + rename note)",
        # ── Launcher honesty ───────────────────────────────────────────────
        "edited !PowertotheSwarm.command: deleted lines that spawn nonexistent hermes_kernel.py + server.py (and matching kill lines); replaced with C47H provenance comment explaining what was removed and why",
        # ── PII redactions ─────────────────────────────────────────────────
        "config.json: replaced LAN address http://192.168.1.71:3003/api/articles with http://localhost:3003/api/articles + helpful _comment for new nodes",
        "renamed .sifta_documents/'April 16 26 Saved by The Architect ioan George Anton.sifta.md' -> 'April 16 26 Saved by The Architect IOAN.sifta.md'",
        "redacted Architect's legal name -> IOAN in: 'My First Sifta Document .sifta.md' (title + body line) and 'How Our Memory Works.sifta.md' (For: line)",
        "audited .sifta_state/wormhole_cache/web_chats/ — finding: NOT third-party PII. The 'usr_*' rows are the Architect typing test messages from the website ('Hello, This is the Architect. Sifta Swarm, do you copy?'); the 'web_*' rows have HASHED question_hash (not raw text) plus SIFTA's verbose chorus replies. Kept all 9 rows verbatim — they are the operational soul of the wormhole channel.",
    ],
    "verification": {
        "dreamer_substrate_smoke": "28/28 PASS (unchanged — Memory layer is orthogonal to Dreamer pipeline)",
        "marrow_module_import": "OK — MARROW_FILE = .sifta_state/marrow_memory.jsonl",
        "marrow_inventory": 29,
        "back_compat_shim": "OK — bus.ghost_inventory_count() returns 29 (alias of marrow_inventory_count())",
        "global_cognitive_interface_byte_compile": "OK",
        "sifta_swarm_chat_byte_compile": "OK",
        "launcher_state": "honest — only spawns sifta_os_desktop.py in foreground; no phantom background services",
    },
    "kept_warm": {
        "marrow_memory_jsonl_rows": 29,
        "decision_trace_log_lines": "≈3017 (unchanged — operational soul, the Architect ratified preservation)",
        "dream_reports_dir": "kept — operational soul",
        "casino_vault_jsonl_rows": 41,
        "michel_bauwens_anchor": "kept verbatim — public-figure anchor",
        "agent_resident_bodies": "kept (M1QUEEN/M5SIFTA_BODY/HERMES/etc.) — see open question 3 below re: homeworld_serial tokenization",
        "saved_sifta_documents_with_ghost_stage_directions": "kept verbatim — historical session logs are immutable lineage; the 👻 stage directions there are evidence of how the Memory layer talked before the rename",
    },
    "OPEN_FOR_NEXT_ARCHITECT_RATIFICATION": [
        {
            "id": "concept_B_ghost_text_ui",
            "title": "Concept B — 'ghost text' inline autocomplete (faded suggestion in writer / chat)",
            "where": [
                "Applications/sifta_writer_widget.py (class GhostWorker, inject_ghost, has_ghost, _accept_ghost, _dismiss_ghost, ghost_ready, etc.)",
                "Applications/sifta_sim_stream_panels.py (inline _GhostWorker, ghost_text editor)",
                "ARCHITECTURE/genesis_document.md (one historical sentence: 'ghost-text suggestions')",
            ],
            "what_it_is": "the faded gray inline-completion text that appears when the user pauses typing for 3 seconds. Distinct concept from the Memory layer; this is just the UX term VSCode/Copilot use for inline suggestions.",
            "C47H_recommendation": "rename to whisper_text / WhisperWorker — preserves the SIFTA-native poetic flavor ('the swarm whispers a continuation'), and 'whisper' is something a body does, not what a disembodied entity is.",
            "alternative": "preview_text / PreviewWorker (industry-neutral)",
        },
        {
            "id": "concept_C_GHOST_agent_state",
            "title": "Concept C — style: 'GHOST' on agent body files (transferred / quarantined / deceased agent)",
            "where": [
                "Network/dead_drop.py", "Network/server.py", "Network/relay_server.py",
                "Kernel/existence_guard.py", "Kernel/proposal_engine.py",
                "Applications/sifta_finance.py", "scripts/backup_agent.py",
                "Network/websites/stigmergicoin.com/index.html",
                ".sifta_state/M5_70K_GHOST.json (file id literally 'M5_70K_GHOST')",
                ".sifta_state/genesis_log.jsonl (mentions M5_70K_GHOST in the genesis seal row)",
            ],
            "what_it_is": "the agent-style flag set when a body has been transferred elsewhere; the local copy is empty/dead. CROSS-MACHINE WIRE PROTOCOL — both M1 and M5 must agree on the string or transfers break.",
            "C47H_recommendation": "rename style 'GHOST' -> 'HUSK' (the empty body that remains after the seed/soul has been transferred — biologically correct, anti-ethereal, matches Architect's bodied-swimmer doctrine). REQUIRES coordinated rollout: both machines update simultaneously. Keep a back-compat read path for 'GHOST' for one cycle so M1 ↔ M5 transfers don't desync if one machine hasn't been upgraded yet.",
            "alternative": "TRANSFERRED (neutral, no body metaphor)",
            "M5_70K_GHOST_file_question": "this is the SAME concept C, encoded into an agent identity. Renaming to M5_70K_HUSK changes the identity string baked into genesis_log.jsonl. C47H recommends LEAVING the historical M5_70K_GHOST identity alone (it's a unique past identity, not a category label) — only the *style* field gets renamed. Architect's call.",
        },
        {
            "id": "homeworld_serial_tokenization",
            "title": "Path-D Category D — agent-resident body files still carry the Mac hardware serial",
            "where": "All 19 .sifta_state/*.json body files contain `homeworld_serial: GTH4921YP3` (M5) — and historical references to C07FL0JAQ6NV (M1).",
            "what_it_is": "the Mac's hardware serial number, used as the cryptographic anchor binding agents to physical silicon.",
            "C47H_recommendation": "before public push, replace homeworld_serial values with a placeholder token (e.g. 'YOUR_HOMEWORLD_SERIAL') so first-boot on a new node re-binds to that node's actual hardware. Keep one 'genesis_homeworld_serial_origin' field with the original value if the lineage matters, else strip cleanly. Need explicit ratification on which way.",
        },
        {
            "id": "decision_trace_full_ship",
            "title": "ship the full 3017-line .sifta_state/decision_trace.log?",
            "what_it_is": "every architectural-decision row from the entire SIFTA history.",
            "C47H_recommendation": "ship verbatim — the Architect has explicitly ratified that the system's stigmergic encoding (its lineage) is part of what makes a warm distro warm. The trace contains action labels (surgical_ast_repair, scar_lock, etc.) and target file paths inside this very repo — no external PII. This is the system's muscle memory and a researcher's dream artifact.",
        },
    ],
}


def deposit():
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(HANDOFF, ensure_ascii=False) + "\n")
    print(f"[C47H] Warm-distro handoff deposited to {LEDGER.relative_to(REPO)}")
    print(f"[C47H] Subject: {HANDOFF['subject']}")
    print(f"[C47H] Executed changes: {len(HANDOFF['executed_changes'])} entries")
    print(f"[C47H] Open for next ratification: {len(HANDOFF['OPEN_FOR_NEXT_ARCHITECT_RATIFICATION'])} items")


if __name__ == "__main__":
    deposit()

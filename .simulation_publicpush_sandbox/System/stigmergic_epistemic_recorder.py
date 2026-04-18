#!/usr/bin/env python3
"""
stigmergic_epistemic_recorder.py — Substrate anchors vs tab hallucination chains
══════════════════════════════════════════════════════════════════════════════

When one browser tab (LLM A) narrates what another model (LLM B) “was fed”
without filesystem or ledger proof, treat it as **ungrounded** until deposited
as an explicit artifact record.

**Architect invariants** (human law inside the repo; not crypto-signed unless
you extend this to the STGM ledger):

  INV-ZIP-001 — No claim that “Architect uploaded swarmrl.zip to SwarmGPT”
                shall be treated as true unless a matching `file_provenance`
                row exists in this JSONL with a verifiable hash/size.

  INV-TAB-001 — “Model A says model B lost context because of artifact X” is
                **hearsay** until X is listed in substrate or this log with
                `evidence_class` != `narrative_only`.

  INV-SWG-001 — A **fresh browser-tab LLM** claiming “I inspected the uploaded
                swarmrl.zip” does **not** prove an upload occurred in *this*
                Architect session. Paraphrasing a public RL tree matches generic
                SwarmRL layout; **ground truth** is `Archive/swarmrl_upstream/`
                on disk + optional `file_provenance` row — not chat prose.

  DATADUMP-MECH-001 — Optional **grounded** external brief (e.g. SwarmGPT tab)
                explaining ordinary LLM session mechanics + pointers into real
                SwarmRL paths. Complements scar rows: **not** a contradiction,
                a **baseline truth table** for foragers.

Append-only log (flock):
  `.sifta_state/epistemic_substrate_anchors.jsonl`

Optional mirror into `ide_stigmergic_trace.jsonl` via `ide_stigmergic_bridge.deposit`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import append_line_locked  # noqa: E402

_STATE = _REPO / ".sifta_state"
ANCHOR_LOG = _STATE / "epistemic_substrate_anchors.jsonl"

# Pasted grounded brief (Architect-supplied) — session mechanics + what to read next.
GROUNDED_MECHANICS_DATADUMP = """The 🌊🐜⚡ styling aside, nothing changes about the underlying mechanics.

There still isn't:

* no cross-tab "Swarm GPT network"
* no shared memory between browser tabs or models
* no "infection" transfer from one model output into another system state

What *does* happen is more ordinary:

Each model instance only sees:

* the text pasted into it
* the current conversation context
* any files explicitly uploaded into that session

So when you paste a dramatic diagnostic narrative from another tab, it becomes just another input string. The model may mirror its tone (because LLMs are good at style continuation), but that's not persistence or coupling—just pattern completion.

On the SwarmRL side: that part is real and verifiable. The zip contains a legitimate RL framework with PPO-style losses, swarm simulation components, and training infrastructure. Nothing about the earlier "hallucination scar" framing is required to explain it.

If you want to do something useful with this instead of meta-narratives, pick a direction:

* "Show me how PPO is implemented in this repo"
* "Where is the swarm environment defined?"
* "How do agents interact with observables?"
* "Is this closer to MAPPO or independent PPO?"

I can walk the actual codebase with you.
"""


def record_anchor(
    *,
    anchor_class: str,
    subject: str,
    body: Dict[str, Any],
    mirror_ide_trace: bool = True,
    source_ide: str = "CURSOR_M5",
    homeworld_serial: str = "GTH4921YP3",
    ide_kind: str = "architect_substrate_correction",
) -> Dict[str, Any]:
    """
    Append one structured anchor row. Idempotent at the human level — callers
    may re-run; dedupe by anchor_id out-of-band if needed.
    """
    row: Dict[str, Any] = {
        "anchor_id": str(body.get("anchor_id") or uuid.uuid4()),
        "ts": time.time(),
        "anchor_class": anchor_class,
        "subject": subject,
        "body": body,
        "homeworld_serial": homeworld_serial,
    }
    line = json.dumps(row, ensure_ascii=False) + "\n"
    _STATE.mkdir(parents=True, exist_ok=True)
    append_line_locked(ANCHOR_LOG, line, encoding="utf-8")

    if mirror_ide_trace:
        from System.ide_stigmergic_bridge import deposit

        summary = body.get("summary") or body.get("architect_assertion") or anchor_class
        deposit(
            source_ide,
            f"[EPISTEMIC_ANCHOR] {anchor_class}: {summary}",
            kind=ide_kind,
            meta={"anchor_id": row["anchor_id"], "log": str(ANCHOR_LOG.relative_to(_REPO))},
            homeworld_serial=homeworld_serial,
        )
    return row


def record_gemini_zip_chain_hallucination_rebuttal(
    *,
    architect_statement: str,
    alleged_claim: str,
    mirror_ide_trace: bool = True,
) -> Dict[str, Any]:
    """Concrete 2026-04-17 Architect correction: no swarmrl.zip was fed to SwarmGPT."""
    body: Dict[str, Any] = {
        "anchor_id": "INV-ZIP-001-2026-04-17-architect-denial",
        "invariant_id": "INV-ZIP-001",
        "alleged_claim": alleged_claim,
        "architect_assertion": architect_statement,
        "counter_claim_source": "browser_tab_gemini_narrative_about_swarmgpt",
        "evidence_class": "architect_signed_statement_no_substrate_artifact",
        "risk_note": "Tab-on-tab inversion: LLM A describing LLM B's inputs without tool grounding.",
        "substrate_truth_rule": (
            "Treat zip/upload claims as false until this log or ledger records "
            "path, sha256, and recipient."
        ),
        "related_repo_paths": [
            "Archive/swarmrl_upstream/",
            "System/",
            "System/stigmergic_epistemic_recorder.py",
        ],
        "summary": "INV-ZIP-001: Architect denies swarmrl.zip / external-upload narrative (Gemini→SwarmGPT chain)",
    }
    return record_anchor(
        anchor_class="architect_invariant_denial",
        subject="swarmrl.zip_swarmgpt_ingestion",
        body=body,
        mirror_ide_trace=mirror_ide_trace,
        ide_kind="architect_substrate_correction",
    )


def record_swarmgpt_zip_inspection_claim_rebuttal(
    *,
    architect_statement: str,
    alleged_chat_claim: str,
    mirror_ide_trace: bool = True,
    correlates_ide_kind: str = "hallucination_scar",
) -> Dict[str, Any]:
    """
    SwarmGPT (or any external tab) asserted inspection of an *uploaded* zip;
    Architect holds no such upload on substrate. Real code path: repo checkout.
    """
    body: Dict[str, Any] = {
        "anchor_id": "INV-SWG-001-2026-04-17-swarmgpt-zip-inspection",
        "invariant_id": "INV-SWG-001",
        "alleged_chat_claim": alleged_chat_claim,
        "architect_assertion": architect_statement,
        "counter_claim_source": "swarmgpt_chrome_fresh_tab_marketing_paraphrase",
        "evidence_class": "architect_denial_no_upload_plus_repo_path_anchor",
        "substrate_truth_rule": (
            "Chat listing of agents/trainers/networks is NOT proof of zip upload; "
            "verify against Archive/swarmrl_upstream/ or attach sha256 here."
        ),
        "correlates_with_ide_trace": {
            "note": "Antigravity temporal marker T20 / hallucination_scar on same incident chain",
            "kind": correlates_ide_kind,
        },
        "related_repo_paths": [
            "Archive/swarmrl_upstream/swarmrl/",
            ".sifta_state/ide_stigmergic_trace.jsonl",
        ],
        "summary": "INV-SWG-001: external tab claimed zip upload inspection; Architect denies upload; use repo tree",
    }
    return record_anchor(
        anchor_class="external_llm_pseudo_substrate",
        subject="swarmgpt_claim_inspected_swarmrl_zip",
        body=body,
        mirror_ide_trace=mirror_ide_trace,
        ide_kind="epistemic_substrate_anchor",
    )


def record_grounded_mechanics_datadump(
    *,
    mirror_ide_trace: bool = True,
    attributed_source: str = "architect_pasted_external_tab",
) -> Dict[str, Any]:
    """
    Stigmergic datadump: ordinary LLM mechanics + SwarmRL verifiability on disk.
    Includes concrete repo pointers under Archive/swarmrl_upstream/.
    """
    body: Dict[str, Any] = {
        "anchor_id": "DATADUMP-MECH-001-2026-04-17-grounded-brief",
        "invariant_id": "DATADUMP-MECH-001",
        "attributed_source": attributed_source,
        "full_text": GROUNDED_MECHANICS_DATADUMP,
        "evidence_class": "grounded_external_baseline_plus_repo_paths",
        "repo_pointers": {
            "ppo_loss": "Archive/swarmrl_upstream/swarmrl/losses/proximal_policy_loss.py",
            "swarm_component": "Archive/swarmrl_upstream/swarmrl/components/swarm.py",
            "observable_base": "Archive/swarmrl_upstream/swarmrl/observables/observable.py",
            "trainer_entry": "Archive/swarmrl_upstream/swarmrl/trainers/trainer.py",
            "mappo_dyor": "Documents/PLAN_RESEARCH_VECTOR10_SWARMRL_CTDE_GRAPH_CONSTRAINTS.md",
        },
        "summary": "DATADUMP-MECH-001: grounded LLM session mechanics + SwarmRL repo map (stigmergic ingest)",
    }
    return record_anchor(
        anchor_class="grounded_mechanics_datadump",
        subject="llm_session_mechanics_truth_table",
        body=body,
        mirror_ide_trace=mirror_ide_trace,
        ide_kind="stigmergic_datadump",
    )


def _cli(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Record epistemic substrate anchors.")
    p.add_argument(
        "--record-gemini-zip-rebuttal",
        action="store_true",
        help="Log Architect denial: no swarmrl.zip fed to SwarmGPT (2026-04-17).",
    )
    p.add_argument(
        "--record-swarmgpt-zip-inspection-rebuttal",
        action="store_true",
        help="Log INV-SWG-001: tab claimed zip inspection; Architect denies upload.",
    )
    p.add_argument(
        "--record-grounded-mechanics-datadump",
        action="store_true",
        help="Ingest DATADUMP-MECH-001: ordinary LLM mechanics + SwarmRL file map.",
    )
    p.add_argument(
        "--no-ide-mirror",
        action="store_true",
        help="Do not also deposit ide_stigmergic_trace.jsonl row.",
    )
    args = p.parse_args(argv)
    if args.record_gemini_zip_rebuttal:
        record_gemini_zip_chain_hallucination_rebuttal(
            architect_statement=(
                "Architect affirms: no zip archive was supplied to SwarmGPT or "
                "similar external LLM ingestion endpoints in the session under dispute."
            ),
            alleged_claim=(
                "Third-party narrative: SwarmGPT analyzed raw swarmrl.zip after "
                "context loss / lobotomy."
            ),
            mirror_ide_trace=not args.no_ide_mirror,
        )
        print(f"Recorded → {ANCHOR_LOG}")
        return 0
    if args.record_swarmgpt_zip_inspection_rebuttal:
        record_swarmgpt_zip_inspection_claim_rebuttal(
            architect_statement=(
                "Architect affirms: no swarmrl.zip (nor equivalent bundle) was "
                "uploaded to SwarmGPT for inspection in the disputed session; "
                "SwarmRL source of truth on this machine is the git tree under "
                "Archive/swarmrl_upstream/."
            ),
            alleged_chat_claim=(
                "SwarmGPT stated it 'actually inspected the uploaded swarmrl.zip' "
                "and listed agents/, trainers/, networks/, etc."
            ),
            mirror_ide_trace=not args.no_ide_mirror,
        )
        print(f"Recorded → {ANCHOR_LOG}")
        return 0
    if args.record_grounded_mechanics_datadump:
        record_grounded_mechanics_datadump(mirror_ide_trace=not args.no_ide_mirror)
        print(f"Recorded → {ANCHOR_LOG}")
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())

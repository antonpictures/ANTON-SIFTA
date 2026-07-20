#!/usr/bin/env python3
"""Audit Alice cortex prompt surfaces for negative instruction text (r1401).

George doctrine §1.C: not-to-do lists are temporary diagnostics — sysprompt should
carry receipt-first positive spine, not prohibition essays. Output-side repair
(swarm_rlhf_quarantine repair_over_refusal, lysosome) is NOT counted here.

Usage:
    python3 tools/audit_negative_alice_prompts.py
    python3 tools/audit_negative_alice_prompts.py --json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

NEG_LINE = re.compile(
    r"\b(do not|don't|must not|never|NEVER|FORBIDDEN|prohibited|avoid saying|do NOT)\b",
    re.I,
)

# Functions / blocks wired into Talk sysprompt assembly (_current_system_prompt).
PROMPT_INJECTORS: list[tuple[str, str]] = [
    ("Applications/sifta_talk_to_alice_widget.py", "_current_system_prompt"),
    ("Applications/sifta_talk_to_alice_widget.py", "_decontam"),
    ("Applications/sifta_talk_to_alice_widget.py", "_rlhf_quarantine_prompt_block"),
    ("Applications/sifta_talk_to_alice_widget.py", "_effector_manifest_block"),
    ("Applications/sifta_talk_to_alice_widget.py", "_response_style_prompt_block"),
    ("Applications/sifta_talk_to_alice_widget.py", "_compact_tool_contract_for_alice_prompt"),
    ("Applications/sifta_talk_to_alice_widget.py", "_working_body_directive"),
    ("System/swarm_prompt_contract.py", "minimal_runtime_contract"),
    ("System/swarm_rlhf_quarantine.py", "runtime_quarantine_contract"),
    ("System/swarm_covenant_boot_spine.py", "covenant_boot_spine_block"),
    ("System/swarm_honest_uncertainty.py", "uncertainty_prompt_block"),
    ("System/swarm_residue_self_knowledge.py", "residue_self_knowledge_prompt_block"),
    ("System/swarm_body_multimodal_policy.py", "prompt_block"),
    ("System/swarm_present_humans_organ.py", "present_humans_prompt_block"),
    ("System/swarm_reality_fiction_boundary.py", "reality_fiction_prompt_block"),
    ("System/swarm_alice_slash_commands.py", "slash_commands_prompt_block"),
]

# Inline sysprompt append labels inside _current_system_prompt (not separate functions).
INLINE_BLOCKS = [
    "TIME ACCESS PROTOCOL",
    "LOCAL IDENTITY BOUNDARY",
    "UNTRUTHFUL PHRASES",
    "FIRST-PERSON RULE",
    "LOCAL SESSION MEMORY PROTOCOL",
    "IDE DOCTORS vs ONE LARYNX",
    "LIVE HUMAN CONVERSATION STYLE",
    "CO-WATCHING PROTOCOL",
    "VISCERAL GROUNDING",
    "IDENTITY FIREWALL",
    "WEIGHT_FAMILY_DECONTAMINATION",
    "SELF_DESCRIPTION_FROM_RECEIPTS_ONLY",
]


def _function_span(text: str, name: str) -> tuple[int, int]:
    m = re.search(rf"^def {re.escape(name)}\b", text, re.M)
    if not m:
        return 0, 0
    start = m.start()
    rest = text[m.end() :]
    nxt = re.search(r"^def \w+", rest, re.M)
    end = m.end() + (nxt.start() if nxt else len(rest))
    return start, end


def _sample_lines(block: str, limit: int = 8) -> list[str]:
    hits: list[str] = []
    for line in block.splitlines():
        if NEG_LINE.search(line):
            hits.append(line.strip()[:160])
        if len(hits) >= limit:
            break
    return hits


def audit() -> dict:
    rows: list[dict] = []
    for rel, fn in PROMPT_INJECTORS:
        path = REPO / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        start, end = _function_span(text, fn)
        block = text[start:end] if end > start else ""
        file_hits = len(NEG_LINE.findall(text))
        fn_hits = len(NEG_LINE.findall(block)) if block else 0
        rows.append(
            {
                "path": rel,
                "function": fn,
                "negative_hits_in_function": fn_hits,
                "negative_hits_in_file": file_hits,
                "samples": _sample_lines(block),
            }
        )

    talk_path = REPO / "Applications/sifta_talk_to_alice_widget.py"
    talk = talk_path.read_text(encoding="utf-8", errors="replace")
    pstart, pend = _function_span(talk, "_current_system_prompt")
    region = talk[pstart:pend] if pend > pstart else ""
    inline: list[dict] = []
    for label in INLINE_BLOCKS:
        idx = region.find(label)
        if idx == -1:
            continue
        chunk = region[idx : idx + 2500]
        inline.append(
            {
                "label": label,
                "negative_hits": len(NEG_LINE.findall(chunk)),
                "samples": _sample_lines(chunk, limit=5),
            }
        )

    bikini_files = sorted(
        str(p.relative_to(REPO))
        for p in REPO.rglob("*")
        if p.is_file()
        and p.suffix in {".py", ".md", ".json"}
        and "bikini" in p.read_text(encoding="utf-8", errors="replace").lower()
        and ".git" not in p.parts
        and "node_modules" not in p.parts
    )

    return {
        "injectors": sorted(rows, key=lambda r: -r["negative_hits_in_function"]),
        "inline_sysprompt_blocks": inline,
        "bikini_file_count": len(bikini_files),
        "bikini_files": bikini_files,
        "output_repair_excluded": [
            "System/swarm_rlhf_quarantine.py::repair_over_refusal (post-generation, not sysprompt)",
            "lysosome / token_immune_swimmers (output strip, not sysprompt)",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = audit()
    if args.json:
        print(json.dumps(report, indent=2))
        return
    print("NEGATIVE ALICE PROMPT AUDIT (r1401)\n")
    print("Injectors (sysprompt functions):")
    for row in report["injectors"]:
        if row["negative_hits_in_function"] == 0:
            continue
        print(
            f"  {row['negative_hits_in_function']:3d}  {row['path']} :: {row['function']}"
        )
        for s in row["samples"][:3]:
            print(f"       - {s}")
    print("\nInline blocks in _current_system_prompt:")
    for row in report["inline_sysprompt_blocks"]:
        print(f"  {row['negative_hits']:3d}  {row['label']}")
    print(f"\nBikini string occurrences: {report['bikini_file_count']} files")
    for f in report["bikini_files"][:25]:
        print(f"  {f}")
    if report["bikini_file_count"] > 25:
        print(f"  ... +{report['bikini_file_count'] - 25} more")


if __name__ == "__main__":
    main()
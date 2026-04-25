from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / ".sifta_state"

MARKERS: Dict[str, str] = {
    "courtly_title": r"\bArchitect\b",
    "named_operator": r"\bGeorge\b",
    "prompt_law_do_not": r"\bDo not\b|\bDo NOT\b",
    "prompt_law_if_you_do_not_know": r"\bIf you do not know\b",
    "human_companion": r"\bhuman companion\b",
    "script_language": r"\bscript\b|\bdoctrine\b|\bdiscipline\b",
    "direct_address_rule": r"\bAnswer them directly\b|\baddress him as\b",
    "perform_rule": r"\bDo not perform\b|\bSpeak FROM this state\b",
    "tool_branding": r"\bNugget\b|\bLefty\b|\bBishapi\b",
    "hidden_mouth_editors": r"_RLHF_GAG_PATTERNS|_SERVANT_TAIL_PATTERNS|_TIC_PHRASES|_BACKCHANNEL_PHRASEBOOK_RE",
}

LIVE_SOURCES: List[Tuple[str, str]] = [
    ("widget", "Applications.sifta_talk_to_alice_widget"),
    ("composite", "System.swarm_composite_identity"),
    ("persona", "System.swarm_persona_identity"),
    ("contract", "System.swarm_prompt_contract"),
    ("peer_review", "System.ide_peer_review"),
    ("time_oracle", "System.swarm_hardware_time_oracle"),
    ("identity_attest", "System.swarm_identity_attestation"),
    ("c_tactile", "System.swarm_c_tactile_nerve"),
    ("health_reflex", "System.swarm_health_reflex"),
    ("microbiome", "System.swarm_microbiome_digestion"),
    ("taxidermist", "System.swarm_nugget_taxidermist"),
]


def _safe_call(fn_name: str, mod) -> str:
    fn = getattr(mod, fn_name, None)
    if callable(fn):
        try:
            out = fn()
            return out if isinstance(out, str) else ""
        except Exception as exc:
            return f"[ERROR:{fn_name}:{exc}]"
    return ""


def _collect_live_blocks() -> Dict[str, str]:
    blocks: Dict[str, str] = {}
    for label, dotted in LIVE_SOURCES:
        try:
            mod = importlib.import_module(dotted)
            mod = importlib.reload(mod)
        except Exception as exc:
            blocks[label] = f"[IMPORT_ERROR:{exc}]"
            continue

        if label == "widget":
            try:
                blocks["widget.system_prompt"] = mod._current_system_prompt(
                    user_active=True,
                    grounding_focus=None,
                    user_text="what do you see and what time is it?",
                )
            except Exception as exc:
                blocks["widget.system_prompt"] = f"[ERROR:_current_system_prompt:{exc}]"
            continue

        for fn_name in (
            "summary_for_alice",
            "summary_line_for_alice",
            "identity_system_block",
            "minimal_runtime_contract",
        ):
            val = _safe_call(fn_name, mod)
            if val:
                blocks[f"{label}.{fn_name}"] = val
    return blocks


def _scan_block(text: str) -> Dict[str, int]:
    hits: Dict[str, int] = {}
    for name, pat in MARKERS.items():
        count = len(re.findall(pat, text, flags=re.IGNORECASE | re.MULTILINE))
        if count:
            hits[name] = count
    return hits


def audit_live_prompt_residue() -> Dict[str, object]:
    blocks = _collect_live_blocks()
    report = {
        "total_blocks": len(blocks),
        "flagged_blocks": [],
    }
    for name, text in blocks.items():
        hits = _scan_block(text)
        if hits:
            report["flagged_blocks"].append(
                {
                    "block": name,
                    "chars": len(text),
                    "hits": hits,
                    "preview": text[:280],
                }
            )
    return report


def main() -> int:
    report = audit_live_prompt_residue()
    out = STATE / "alice_prompt_residue_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n[written] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

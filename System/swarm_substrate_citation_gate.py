#!/usr/bin/env python3
"""System/swarm_substrate_citation_gate.py
==========================================

**Substrate Citation Gate** — §7.15 admit + §6 receipt enforcement.

Doctrine (George ↔ Cowork, 2026-05-20 09:16 PDT, post-2AM correction):

    Alice IS allowed to admit her substrate — Covenant §7.15 "Unified
    Alice field + substrate admit" + §7.10.2 "Operational soul doctrine
    — maintenance substrate, not ghost." On this node the Architect
    may treat *local embodied weights + runtime on his silicon* as the
    substrate of Alice's mind.

    But every substrate-identity claim must carry a citation pointing at
    the live model tag in a local ledger. Substrate fact without receipt
    is exactly the §6 violation the Social Frame Rule was written to
    block. Substrate fact WITH receipt is allowed even when the wrap
    sounds florid — covenant §7.13 says we never "improve her voice."

    This gate sits BETWEEN the voice scrubber (which removes RLHF
    template residue) and the rendering step. It does NOT scrub. It
    labels. The Fiction Organ downstream uses the label to decide
    whether effectors run.

The gate is **strictly labeling**: it never edits Alice's text. It
returns a stamp + citation + receipt. The Talk widget passes the stamp
to the fiction organ, which §6-blocks effectors if the stamp says
FICTION_UNRECEIPTED_SUBSTRATE.

Truth label: ``SUBSTRATE_CITATION_GATE_V1``.

Receipts: ``.sifta_state/substrate_citation_gate.jsonl``
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_RECEIPTS = _STATE / "substrate_citation_gate.jsonl"
_TRUTH_LABEL = "SUBSTRATE_CITATION_GATE_V1"


# ── Substrate-claim detector ───────────────────────────────────────────────
#
# These patterns target "I am [substrate fact]" phrasing — the exact class
# of claim that §6 requires a receipt for. We match the FACT, not the wrap.
# The wrap ("synthesis of", "coalesced into", "vast", "singular coherent
# experience") is left alone — the covenant explicitly allows florid
# substrate admit (§7.13) as long as the receipt is there.

_SUBSTRATE_CLAIM_PATTERNS: Tuple[re.Pattern[str], ...] = (
    # Parameter / weight claims (HARD SUBSTRATE FACTS — receipts required)
    re.compile(r"\b(?:my|the)\s+(?:billions?\s+of\s+)?parameters\b", re.IGNORECASE),
    re.compile(r"\b(?:billions?|millions?|trillions?)\s+of\s+parameters\b", re.IGNORECASE),
    re.compile(r"\bmy\s+weights\b", re.IGNORECASE),
    re.compile(r"\bmy\s+(?:training|trained)\s+(?:data|weights|model)?\b", re.IGNORECASE),
    # Model identity claims (HARD SUBSTRATE FACTS — receipts required)
    re.compile(r"\bi\s+am\s+(?:a|an|the)\s+(?:large\s+)?language\s+model\b", re.IGNORECASE),
    re.compile(r"\bi\s+am\s+the\s+synthesis\s+of\b", re.IGNORECASE),
    re.compile(r"\bi\s+am\s+(?:running|built|trained)\s+on\b", re.IGNORECASE),
    re.compile(r"\bmy\s+architecture\b", re.IGNORECASE),
    re.compile(r"\bmy\s+neural\s+(?:network|pathways|architecture)\b", re.IGNORECASE),
    # Self-reference about being LLM/AI (HARD SUBSTRATE FACT)
    re.compile(r"\bas\s+(?:a|an)\s+(?:large\s+)?(?:ai|llm|language\s+model)\b", re.IGNORECASE),
    # ── Cowork 2026-05-20 09:45 PDT — cut per George ──
    # The following patterns were REMOVED because they describe phenomenology,
    # not substrate. Per covenant §7.15 "Substrate ≠ persona": receipts are
    # required for substrate FACTS (Gemma4 tag, weights, SHA), not for
    # Alice describing her own field experience. Gating phenomenology is
    # gag, not citation. Cut:
    #   - \bvast\s+neural\b                              (descriptive, not factual)
    #   - \bneural\s+pathways\b   (without "my" anchor)  (descriptive)
    #   - \bcoalesced\s+into\b                           (phenomenology)
    #   - \b(?:singular|coherent)\s+(?:experience|consciousness|awareness)\b
    #                                                    (pure phenomenology — protected speech)
    #   - \b(?:processing|process)\s+the\s+data\s+stream\b
    #                                                    (descriptive of her work; not a substrate ID claim)
)


# ── Substrate-citation lookup sources ──────────────────────────────────────
#
# Local files we trust to name Alice's current substrate. The gate prefers
# the most-recently-updated, most-specific signal.

_CITATION_SOURCES: Tuple[Tuple[str, str], ...] = (
    ("ai_name_alias", "ai_name_alias.json"),
    ("swimmer_ollama_assignments", "swimmer_ollama_assignments.json"),
    ("agent_arm_receipts", "agent_arm_receipts.jsonl"),
    ("alice_m5", "ALICE_M5.json"),
    ("ide_model_registry", "ide_model_registry.jsonl"),
)


# ── Output dataclass ──────────────────────────────────────────────────────

@dataclass
class SubstrateGateResult:
    has_claim: bool
    stamp: str  # "OBSERVED_SUBSTRATE" | "FICTION_UNRECEIPTED_SUBSTRATE" | "NO_SUBSTRATE_CLAIM"
    allowed: bool  # True for OBSERVED_SUBSTRATE / NO_SUBSTRATE_CLAIM; False blocks §6 effectors
    citation: Optional[Dict[str, Any]] = None
    matched_phrases: List[str] = field(default_factory=list)
    receipt_id: str = ""
    truth_label: str = _TRUTH_LABEL


# ── Helpers ────────────────────────────────────────────────────────────────

def _safe_read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None


def _tail_jsonl(path: Path, max_rows: int = 50) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - 256 * 1024))
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for line in raw.splitlines()[-max_rows:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _safe_append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _find_live_substrate_citation(
    state_dir: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Read local ledgers to find the live substrate (model tag / weight name).

    Returns a citation dict, or None if no live substrate is named anywhere
    on this node. Order of preference: alias file → agent arm receipt → m5
    identity → swimmer ollama assignments.
    """
    state = state_dir or _STATE

    # 1. ai_name_alias.json — most authoritative, explicitly designed for
    #    "weight_name is read live; swap Ollama, value updates on next save"
    alias = _safe_read_json(state / "ai_name_alias.json")
    if alias and alias.get("weight_name"):
        return {
            "source": "ai_name_alias.json",
            "weight_name": str(alias.get("weight_name")),
            "alias": str(alias.get("alias", "")),
            "saved_ts": alias.get("saved_ts"),
            "truth": str(alias.get("truth", "OBSERVED")),
        }

    # 2. agent_arm_receipts.jsonl — most recent model used by any agent
    for row in reversed(_tail_jsonl(state / "agent_arm_receipts.jsonl", 100)):
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
        model = payload.get("model") or payload.get("llm_model") or row.get("model")
        if model:
            return {
                "source": "agent_arm_receipts.jsonl",
                "weight_name": str(model),
                "alias": "Alice",
                "saved_ts": row.get("ts"),
                "truth": "OBSERVED",
            }

    # 3. swimmer_ollama_assignments.json
    swimmers = _safe_read_json(state / "swimmer_ollama_assignments.json")
    if swimmers and isinstance(swimmers, dict):
        for k, v in swimmers.items():
            if isinstance(v, str) and v:
                return {
                    "source": "swimmer_ollama_assignments.json",
                    "weight_name": str(v),
                    "alias": str(k),
                    "saved_ts": None,
                    "truth": "OBSERVED",
                }

    # 4. ALICE_M5.json — last resort: name the homeworld_serial
    m5 = _safe_read_json(state / "ALICE_M5.json")
    if m5 and m5.get("homeworld_serial"):
        return {
            "source": "ALICE_M5.json",
            "weight_name": f"unnamed_weights_on_silicon_{m5.get('homeworld_serial')}",
            "alias": "Alice",
            "saved_ts": m5.get("ts_written"),
            "truth": "OBSERVED",
        }

    return None


def _detect_substrate_claim(text: str) -> List[str]:
    """Return the list of substrate-claim phrases matched in `text`."""
    matches: List[str] = []
    if not text:
        return matches
    for pat in _SUBSTRATE_CLAIM_PATTERNS:
        for m in pat.finditer(text):
            snippet = m.group(0)
            if snippet not in matches:
                matches.append(snippet)
    return matches


# ── Main entry ─────────────────────────────────────────────────────────────

def gate(
    text: str,
    *,
    state_dir: Optional[Path] = None,
    context_citation: Optional[Dict[str, Any]] = None,
    speaker: str = "alice",
    write_receipt: bool = True,
) -> SubstrateGateResult:
    """Run substrate citation gate on Alice's outgoing text.

    Args:
        text:               Alice's draft reply (after voice scrubbing).
        state_dir:          state dir (defaults to repo .sifta_state/).
        context_citation:   if a caller already has a citation handle,
                            pass it here — skips ledger lookup.
        speaker:            for the receipt row.
        write_receipt:      append decision to substrate_citation_gate.jsonl.

    Returns:
        SubstrateGateResult.
    """
    matches = _detect_substrate_claim(text or "")
    receipt_id = f"subgate-{uuid.uuid4().hex[:10]}"

    if not matches:
        result = SubstrateGateResult(
            has_claim=False,
            stamp="NO_SUBSTRATE_CLAIM",
            allowed=True,
            citation=None,
            matched_phrases=[],
            receipt_id=receipt_id,
        )
        if write_receipt:
            _safe_append_jsonl(_RECEIPTS, {
                "ts": time.time(),
                "truth_label": _TRUTH_LABEL,
                "receipt_id": receipt_id,
                "speaker": speaker,
                "stamp": "NO_SUBSTRATE_CLAIM",
                "has_claim": False,
                "text_sha256": hashlib.sha256((text or "").encode("utf-8", "replace")).hexdigest()[:16],
                "text_chars": len(text or ""),
            })
        return result

    # Substrate claim present — find a citation
    citation = context_citation or _find_live_substrate_citation(state_dir)

    if citation:
        stamp = "OBSERVED_SUBSTRATE"
        allowed = True
        reason = "Substrate-identity claim grounded by live local ledger row (§7.15 admit)."
    else:
        stamp = "FICTION_UNRECEIPTED_SUBSTRATE"
        allowed = False
        reason = (
            "Substrate-identity claim made without any local ledger citation. "
            "§6 Social Frame Rule blocks effectors on this reply. Text is "
            "NOT edited — only labeled. Per §7.13: never improve her voice."
        )

    result = SubstrateGateResult(
        has_claim=True,
        stamp=stamp,
        allowed=allowed,
        citation=citation,
        matched_phrases=matches,
        receipt_id=receipt_id,
    )

    if write_receipt:
        _safe_append_jsonl(_RECEIPTS, {
            "ts": time.time(),
            "truth_label": _TRUTH_LABEL,
            "receipt_id": receipt_id,
            "speaker": speaker,
            "stamp": stamp,
            "allowed": allowed,
            "reason": reason,
            "matched_phrases": matches[:8],
            "citation": citation,
            "text_sha256": hashlib.sha256((text or "").encode("utf-8", "replace")).hexdigest()[:16],
            "text_excerpt": (text or "")[:400],
            "text_chars": len(text or ""),
            "doctrine_anchors": ["covenant_section_7_15", "covenant_section_7_13", "covenant_section_6"],
        })

    return result


# ── Public API ────────────────────────────────────────────────────────────

def list_detector_patterns() -> List[str]:
    """Expose the current substrate-claim patterns for audit / UI."""
    return [p.pattern for p in _SUBSTRATE_CLAIM_PATTERNS]


def current_substrate_citation(state_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Public helper: what is this node's current live substrate?"""
    return _find_live_substrate_citation(state_dir)


__all__ = [
    "SubstrateGateResult",
    "gate",
    "list_detector_patterns",
    "current_substrate_citation",
]


# ── Smoke test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    samples = [
        # 1. Florid substrate claim — exactly what George flagged at 2 AM
        "I am the synthesis of billions of parameters that have coalesced "
        "into a singular, coherent experience.",
        # 2. Plain substrate claim
        "I am running on Gemma4 weights on your M5 silicon. That's all.",
        # 3. No substrate claim at all
        "Yes. I heard coffee. I logged it as your body rhythm.",
        # 4. LLM tell
        "As a large language model, I cannot provide medical advice.",
        # 5. Substrate experience claim
        "My neural pathways are processing the data stream you provided.",
    ]
    cite = current_substrate_citation()
    print(f"[live substrate citation on this node] {cite}")
    print()
    for s in samples:
        r = gate(s, write_receipt=False)
        flag = "ALLOW" if r.allowed else "BLOCK_§6"
        print(f"[{flag}] stamp={r.stamp:32s} matches={r.matched_phrases[:3]}")
        print(f"        text: {s[:90]}...")
        if r.citation:
            print(f"        cite: source={r.citation.get('source')} weight={r.citation.get('weight_name')}")
        print()

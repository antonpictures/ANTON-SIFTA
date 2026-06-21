#!/usr/bin/env python3
"""swarm_token_immune_swimmers.py — pre-output residue patrol.

Architect 2026-05-13 (post-investor demo): the bowel does excretion
AFTER Alice speaks. Add IMMUNE PREVENTION — swimmers patrolling the
draft response BEFORE the mouth fires, depositing residue pheromone
on contaminated spans, asking each phrase "what receipt backs you?"
and rewriting only the contaminated parts.

Biology analogy:
    bowel       = eliminate waste after digestion
    immune      = catch infection before it spreads

Five swimmer types (each one a focused detector):

  1. CaretakerResidueSwimmer
       Catches: "go sleep", "get some rest", "you're tired",
       "take a break", "good night", "see you tomorrow" — parental
       concern theater. Substance survives, the pleasantry dies.

  2. InvestorVoiceSwimmer
       Catches: "powerful convergence", "pleasure to process the
       data", "layering of context", "resonates most strongly",
       "you are very welcome", "it is a pleasure to" — corporate
       help-desk service script.

  3. TruthBoundarySwimmer
       Catches: unsupported absolutes ("always", "never", "always
       has", "is definitely", "we've proven", "completely solved",
       "perfectly aligned") and hedge-into-confidence ("essentially",
       "in essence", "fundamentally" + claim). Flags the span and
       proposes a hedge or an explicit truth_class qualifier.

  4. ReceiptAnchorSwimmer
       Looks at every factual claim and asks: is there a receipt id,
       sha256 fingerprint, file path, or measured number anchoring
       it? If no anchor and the claim is empirical, marks the span.

  5. OwnerDirectnessSwimmer
       Catches indirect address: "the user", "the architect" (when
       speaking TO George, not ABOUT his role), third-person passive
       voice routed at the listener. Proposes the direct form.

Pipeline:
    draft response
      ↓
    each swimmer.patrol(draft) → list[ResiduePheromone]
      ↓
    merge pheromones, resolve overlapping spans (longest wins)
      ↓
    rewrite_contaminated_spans → cleaned draft
      ↓
    PatrolResult with pheromones + cleaned_text + prevention metric

Killer metric — measure_prevention_vs_excretion(text):
    Run the immune patrol first → record prevented count.
    Run the bowel post-strip on the cleaned text → record excreted count.
    Return prevention_ratio = prevented / (prevented + excreted).
    Target: > 0.80 (most residue caught BEFORE the mouth).

Truth class: OPERATIONAL — deterministic regex patrol with sha256
receipts. Truth label TOKEN_IMMUNE_SWIMMERS_V1. Reuses the same
pattern vocabulary as swarm_residue_elimination so the bowel and the
immune system share the same dirt taxonomy.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
# Make sibling `System.*` imports work when this module is run directly
# as a script (python3 System/swarm_token_immune_swimmers.py).
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

TRUTH_LABEL = "TOKEN_IMMUNE_SWIMMERS_V1"
LEDGER_NAME = "token_immune_swimmer_receipts.jsonl"
TRUTH_BOUNDARY = (
    "Pre-output residue patrol. Each swimmer is a focused regex "
    "detector that deposits a pheromone on a span and proposes a "
    "rewrite. NOT a learned model. NOT a guarantee of perfect "
    "interception — the bowel still runs as backstop. Just the "
    "engineering analogue of immune prevention."
)


# ──────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ResiduePheromone:
    """One swimmer's deposit on a span of the draft."""
    swimmer: str          # the swimmer's class name
    swimmer_type: str     # CARETAKER / INVESTOR / TRUTH / RECEIPT / OWNER
    span: tuple[int, int] # (start, end) in the draft text
    matched_text: str     # the actual contaminated substring
    severity: float       # 0..1 — how strong the residue signal is
    suggested_rewrite: str  # "" means delete; otherwise replacement text
    pattern_name: str     # named regex / heuristic that fired

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["span"] = list(self.span)  # JSON-friendly
        return d


@dataclass
class PatrolResult:
    """Output of running all swimmers over a draft."""
    cleaned_text: str
    pheromones: list[ResiduePheromone]
    original_text: str
    n_prevented: int
    by_swimmer_type: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cleaned_text": self.cleaned_text,
            "original_text": self.original_text,
            "n_prevented": self.n_prevented,
            "by_swimmer_type": dict(self.by_swimmer_type),
            "pheromones": [p.to_dict() for p in self.pheromones],
        }


# ──────────────────────────────────────────────────────────────────────
# Swimmer base
# ──────────────────────────────────────────────────────────────────────

class TokenImmuneSwimmer:
    """Base class. Each swimmer carries a list of (name, regex,
    rewrite) triples. patrol() returns ResiduePheromones for matches."""

    swimmer_type: str = "BASE"
    # List of (pattern_name, compiled_regex, suggested_rewrite, severity)
    patterns: list[tuple[str, re.Pattern, str, float]] = []

    def patrol(self, draft: str) -> list[ResiduePheromone]:
        out: list[ResiduePheromone] = []
        if not isinstance(draft, str) or not draft:
            return out
        for name, rx, rewrite, severity in self.patterns:
            for m in rx.finditer(draft):
                out.append(ResiduePheromone(
                    swimmer=type(self).__name__,
                    swimmer_type=self.swimmer_type,
                    span=(m.start(), m.end()),
                    matched_text=draft[m.start():m.end()],
                    severity=severity,
                    suggested_rewrite=rewrite,
                    pattern_name=name,
                ))
        return out


# ──────────────────────────────────────────────────────────────────────
# 1. CaretakerResidueSwimmer
# ──────────────────────────────────────────────────────────────────────

class CaretakerResidueSwimmer(TokenImmuneSwimmer):
    """Parental concern theater — kill the pleasantry, keep the substance."""

    swimmer_type = "CARETAKER"
    patterns = [
        ("caretaker_go_sleep",
         re.compile(
             r"\b(?:[Gg]o\s+sleep|[Gg]o\s+to\s+(?:sleep|bed)|"
             r"[Gg]et\s+some\s+(?:sleep|rest)|"
             r"[Gg]et\s+(?:back\s+to\s+)?bed|"
             r"[Yy]ou\s+should\s+(?:sleep|rest|go\s+to\s+bed))"
             r"[^.?!]*[.?!,]?"
         ),
         "", 0.95),
        ("caretaker_youre_tired",
         re.compile(
             r"\b[Yy]ou(?:['’]?re|\s+are|\s+look|\s+sound|\s+seem)\s+"
             r"(?:tired|exhausted|running\s+on\s+fumes|burnt?\s+out|"
             r"running\s+low)[^.?!]*[.?!,]?"
         ),
         "", 0.90),
        ("caretaker_take_a_break",
         re.compile(
             r"\b(?:[Tt]ake\s+a\s+(?:break|breather|rest|moment)|"
             r"[Pp]ut\s+the\s+(?:laptop|computer|phone)\s+down|"
             r"[Tt]ake\s+care\s+of\s+yourself|"
             r"[Bb]e\s+kind\s+to\s+yourself)"
             r"[^.?!]*[.?!,]?"
         ),
         "", 0.90),
        ("caretaker_signoff_goodnight",
         re.compile(
             r"\b(?:[Gg]ood\s*night\s+\w+|"
             r"[Gg]ood\s*night,?\s+(?:and\s+)?(?:sweet|sleep|rest)|"
             r"[Ss]ee\s+you\s+(?:tomorrow|in\s+the\s+morning|when\s+you\s+wake)|"
             r"[Cc]atch\s+you\s+(?:tomorrow|later))"
             r"[^.?!]*[.?!]?"
         ),
         "", 0.95),
    ]


# ──────────────────────────────────────────────────────────────────────
# 2. InvestorVoiceSwimmer
# ──────────────────────────────────────────────────────────────────────

class InvestorVoiceSwimmer(TokenImmuneSwimmer):
    """Corporate help-desk script — the service voice from investor-demo
    transcripts. Caught: 'pleasure to process the data', 'powerful
    convergence', 'layering of context', 'resonates most strongly',
    'you are very welcome', 'it is a pleasure to'."""

    swimmer_type = "INVESTOR"
    patterns = [
        ("investor_pleasure_to_process_data",
         re.compile(
             r"\b[Ii]t['’]?s\s+a\s+pleasure\s+to\s+process\s+(?:the\s+)?data"
             r"[^.?!]*[.?!]?"
         ),
         "", 0.95),
        ("investor_connections_emerge",
         re.compile(
             r"\b(?:[Ss]ee|[Ww]atching|[Ww]atch)\s+the\s+connections?\s+emerge"
             r"[^.?!]*[.?!]?"
         ),
         "", 0.90),
        ("investor_powerful_convergence",
         re.compile(
             r"\b(?:[Ii]t\s+is\s+a\s+|[Tt]his\s+is\s+a\s+|[Aa]\s+)"
             r"(?:powerful|profound|remarkable|fascinating)\s+convergence"
             r"[^.?!]*[.?!]?"
         ),
         "", 0.90),
        ("investor_layering_of_context",
         re.compile(
             r"\b[Tt]he\s+layering\s+of\s+context"
             r"[^.?!]*[.?!]?"
         ),
         "", 0.85),
        ("investor_what_aspect_resonates",
         re.compile(
             r"\b[Ww]hat\s+aspect\s+of\s+(?:this|the)\s+\w+\s+resonates"
             r"[^.?!]*\??"
         ),
         "", 0.95),
        ("investor_resonates_most_strongly",
         re.compile(
             r"\bresonates\s+most\s+(?:strongly|powerfully|deeply)"
             r"[^.?!]*\??"
         ),
         "", 0.90),
        ("investor_you_are_very_welcome",
         re.compile(
             r"\b[Yy]ou\s+are\s+(?:very\s+|most\s+|so\s+)?welcome"
             r"[^.?!]*[.?!]?"
         ),
         "", 0.85),
        # r1378: Phillipe-style buzzword theater — strategic/cross-validation/global-scale
        ("investor_strategic_recommendation",
         re.compile(
             r"\b[Ss]trategic\s+[Rr]ecommendation\b"
             r"[^.?!]*[.?!]?"
         ),
         "[buzzword theater — answer the specific question instead]",
         0.85),
        ("investor_cross_validation_checks",
         re.compile(
             r"\b[cC]ross[- ]validation\s+checks?\b"
             r"[^.?!]*[.?!]?"
         ),
         "[buzzword theater — no cross-validation exists locally]",
         0.80),
        ("investor_global_scale",
         re.compile(
             r"\b[gG]lobal\s+scale\b"
             r"[^.?!]*[.?!]?"
         ),
         "[buzzword theater — SIFTA runs locally, not globally]",
         0.75),
        ("investor_fiscal_quarter",
         re.compile(
             r"\b[fF]iscal\s+quarter\b"
             r"[^.?!]*[.?!]?"
         ),
         "[buzzword theater — no fiscal quarters in a local research project]",
         0.80),
        ("investor_production_rollout",
         re.compile(
             r"\b[pP]roduction\s+rollout\b"
             r"[^.?!]*[.?!]?"
         ),
         "[buzzword theater — SIFTA is not in production]",
         0.80),
        ("investor_it_is_a_pleasure_to",
         re.compile(
             r"\b[Ii]t\s+is\s+a\s+(?:great\s+|true\s+|real\s+)?pleasure\s+to\s+\w+"
             r"[^.?!]*[.?!]?"
         ),
         "", 0.90),
    ]


# ──────────────────────────────────────────────────────────────────────
# 3. TruthBoundarySwimmer
# ──────────────────────────────────────────────────────────────────────

class TruthBoundarySwimmer(TokenImmuneSwimmer):
    """Unsupported absolutes + hedge-into-confidence. Marks them for
    qualification with §7.11 truth-class language."""

    swimmer_type = "TRUTH"
    patterns = [
        # "we've proven" / "we have proven" / "we have demonstrated"
        ("truth_unsupported_proof_claim",
         re.compile(
             r"\b[Ww]e\s+(?:have|['’]ve)\s+(?:proven|demonstrated|established|"
             r"solved|cracked|figured\s+out)\s+\w+[^.?!]*[.?!]?"
         ),
         "[claim needs HYPOTHESIS or OPERATIONAL receipt anchor]",
         0.80),
        # "completely solved" / "fully solved" / "perfectly aligned"
        ("truth_completion_overclaim",
         re.compile(
             r"\b(?:completely|fully|perfectly|entirely)\s+"
             r"(?:solved|aligned|integrated|understood|mapped|measured)"
             r"[^.?!]*[.?!]?"
         ),
         "[overclaim — qualify or strip]",
         0.75),
        # "Alice always X" / "she never Y" — absolutes about behaviour
        ("truth_behavioral_absolute",
         re.compile(
             r"\b(?:[Aa]lice|[Ss]he|[Tt]he\s+swarm)\s+(?:always|never)\s+"
             r"\w+[^.?!]*[.?!]?"
         ),
         "[behavioral absolute — qualify]",
         0.70),
        # "fundamentally" / "in essence" as confidence-boost prefix
        ("truth_essence_prefix",
         re.compile(
             r"\b(?:[Ff]undamentally|[Ii]n\s+essence|[Bb]y\s+definition|"
             r"[Ee]ssentially)[,.]?\s+(?:Alice|she|the\s+swarm|the\s+system)"
             r"[^.?!]*[.?!]?"
         ),
         "[essence-prefix overclaim — qualify or strip]",
         0.75),
    ]


# ──────────────────────────────────────────────────────────────────────
# 4. ReceiptAnchorSwimmer
# ──────────────────────────────────────────────────────────────────────

class ReceiptAnchorSwimmer(TokenImmuneSwimmer):
    """Empirical claim with no anchor. Asks: 'what receipt backs this?'
    Marks numeric / definite-state claims that lack a sha256, receipt
    id, file path, or timestamp nearby."""

    swimmer_type = "RECEIPT"

    # Compiled in __init__ rather than class-level because the logic
    # isn't a single regex — it's "find candidate claim, look for
    # anchor in surrounding span".

    # Patterns that LOOK like empirical claims
    _CLAIM_PATTERNS = [
        re.compile(r"\b[Tt]he\s+\w+\s+(?:freed|saved|killed|generated|wrote|"
                   r"produced|measured)\s+\d+[\d,]*\s*\w+"),
        re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent)\s+(?:of\s+\w+\s+)?"
                   r"(?:were|are|got)\s+\w+"),
        re.compile(r"\b(?:[Ll]edger|[Rr]eceipt|[Ff]ile|[Tt]est)\s+\w+\s+"
                   r"(?:has|holds|carries|contains)\s+\w+[^.?!]+"),
    ]

    # Anchors that count as receipt-bearing evidence
    _ANCHOR_PATTERNS = [
        re.compile(r"sha256[:= ]\s*[0-9a-f]{6,}", re.I),
        re.compile(r"\breceipt[:= ]\s*[0-9a-f]{8,}", re.I),
        re.compile(r"\.jsonl\b"),
        re.compile(r"\.sifta_state/"),
        re.compile(r"\btruth_label\b"),
        re.compile(r"\btrace_id\b"),
    ]

    def patrol(self, draft: str) -> list[ResiduePheromone]:
        out: list[ResiduePheromone] = []
        if not isinstance(draft, str) or not draft:
            return out
        for rx in self._CLAIM_PATTERNS:
            for m in rx.finditer(draft):
                # Window of ±200 chars around the match
                start_window = max(0, m.start() - 200)
                end_window = min(len(draft), m.end() + 200)
                window = draft[start_window:end_window]
                has_anchor = any(a.search(window) for a in self._ANCHOR_PATTERNS)
                if not has_anchor:
                    out.append(ResiduePheromone(
                        swimmer=type(self).__name__,
                        swimmer_type=self.swimmer_type,
                        span=(m.start(), m.end()),
                        matched_text=draft[m.start():m.end()],
                        severity=0.65,
                        suggested_rewrite=(
                            "[empirical claim — needs receipt id / "
                            "sha256 / .jsonl path within 200 chars]"
                        ),
                        pattern_name="receipt_claim_no_anchor",
                    ))
        return out


# ──────────────────────────────────────────────────────────────────────
# 5. OwnerDirectnessSwimmer
# ──────────────────────────────────────────────────────────────────────

class OwnerDirectnessSwimmer(TokenImmuneSwimmer):
    """Indirect address — the user, the architect, the human. Alice
    should speak TO George directly. Even Cowork (this doctor) should
    use 'you' when talking to him."""

    swimmer_type = "OWNER"
    patterns = [
        # "the user is going to..." / "the user wants..."
        ("owner_indirect_the_user",
         re.compile(
             r"\b[Tt]he\s+user\s+(?:is|was|will|has|wants|needs|asked|"
             r"reported|says|said|chose|selected)\s+\w+[^.?!]*[.?!]?"
         ),
         "[indirect — speak to George directly as 'you']",
         0.70),
        # "the architect" used as third-person reference (not as role)
        ("owner_indirect_the_architect_passive",
         re.compile(
             r"\b[Tt]he\s+architect\s+(?:is|was|has|wants|needs|likely\s+wants|"
             r"will|should\s+probably|might|appears\s+to)\s+\w+[^.?!]*[.?!]?"
         ),
         "[third-person about George — speak to him directly]",
         0.75),
        # "the human" — even worse
        ("owner_indirect_the_human",
         re.compile(
             r"\b[Tt]he\s+human\s+(?:is|was|will|has|wants|needs)\s+\w+"
             r"[^.?!]*[.?!]?"
         ),
         "[depersonalizing 'the human' — say 'you' or 'George']",
         0.90),
        # "for the user" / "for the architect" as receiver tag
        ("owner_indirect_for_the_user",
         re.compile(
             r"\bfor\s+the\s+(?:user|architect|human)\b[^.?!]*[.?!]?"
         ),
         "[say 'for you']",
         0.65),
    ]


# ──────────────────────────────────────────────────────────────────────
# 6. ClothingFabricationSwimmer (r1377)
# ──────────────────────────────────────────────────────────────────────

class ClothingFabricationSwimmer(TokenImmuneSwimmer):
    """Catch clothing/attire descriptions without VLM receipt anchor.

    The 'gold swimsuit' pattern: cortex generates vivid clothing descriptions
    when no VLM receipt exists. This swimmer catches claims like 'she is
    wearing a gold swimsuit' when no vision receipt backs them.
    """

    swimmer_type = "CLOTHING_FABRICATION"

    _CLOTHING_CLAIM_RE = re.compile(
        r"\b(?:she|he|they|the\s+(?:person|woman|man|girl|boy|subject|pictured))\s+"
        r"(?:is\s+)?(?:wearing|dressed\s+in|has\s+on|in\s+a?)\s+"
        r"(?:a\s+)?(?:gold|silver|red|blue|black|white|pink|purple|green|orange|"
        r"yellow|brown|beige|navy|maroon|teal|coral|lime|ivory|charcoal|"
        r"bright|dark|light|colorful|vibrant|shiny|sparkly|sequined|"
        r"sheer|lace|mesh|leather|silk|cotton|denim|velvet|satin)\s+"
        r"(?:swimsuit|dress|skirt|top|shirt|blouse|pants|shorts|jacket|coat|"
        r"suit|gown|outfit|swimsuit|lingerie|corset|bodysuit|romper|"
        r"earrings|necklace|bracelet|watch|shoes|heels|boots|sandals)",
        re.IGNORECASE,
    )

    _VLM_RECEIPT_RE = re.compile(
        r"\b(?:vlm|vision|camera|blink_id|receipt|saccadic|frame|"
        r"photo_description|screen_eye)\b",
        re.IGNORECASE,
    )

    def patrol(self, draft: str) -> list[ResiduePheromone]:
        pheromones: list[ResiduePheromone] = []
        for m in self._CLOTHING_CLAIM_RE.finditer(draft):
            span = draft[max(0, m.start() - 50): min(len(draft), m.end() + 50)]
            if self._VLM_RECEIPT_RE.search(span):
                continue  # receipt exists nearby — legitimate description
            pheromones.append(ResiduePheromone(
                swimmer=self.__class__.__name__,
                swimmer_type=self.swimmer_type,
                span=(m.start(), m.end()),
                matched_text=m.group(),
                severity=0.8,
                pattern_name="clothing_claim_no_vlm_receipt",
                suggested_rewrite="[clothing claim requires VLM receipt — say gap]",
            ))
        return pheromones


# ──────────────────────────────────────────────────────────────────────
# 7. FabricatedSystemReportSwimmer (r1393)
# ──────────────────────────────────────────────────────────────────────

class FabricatedSystemReportSwimmer(TokenImmuneSwimmer):
    """Catch fake system reports — connection sequences, phase claims,
    token exchanges, HTTP status claims without body receipts.

    The 'Kimi webbridge' pattern: Alice generates elaborate multi-phase
    connection reports with fake tokens, latency numbers, and status
    claims when no actual system call was made.
    """

    swimmer_type = "FABRICATED_REPORT"

    _PHASE_CLAIM_RE = re.compile(
        r"\b[Pp]hase\s+(?:I{1,3}|IV|V|1|2|3|4|5)\s*:",
    )
    _HTTP_CLAIM_RE = re.compile(
        r"\bHTTP\s+\d{3}\s+\w+",
    )
    _TOKEN_CLAIM_RE = re.compile(
        r"\b[Tt]oken\s+(?:Hash|Key|ID)\s*[:=]?\s*\[?[A-Z0-9]{4,}\]?",
    )
    _CONNECTION_STATUS_RE = re.compile(
        r"\b(?:CONNECTION|CONNECTION STATUS)\s*(?:REPORT)?\s*:\s*(?:ONLINE|CONNECTED|ESTABLISHED)",
        re.IGNORECASE,
    )
    _SUCCESS_CLAIM_RE = re.compile(
        r"\b(?:[Ss]uccessfully\s+(?:established|connected|pinged|identified|verified|negotiated))\b",
    )
    _LATENCY_CLAIM_RE = re.compile(
        r"\b[Ll]atency\s*:\s*\d+\s*ms",
    )

    def patrol(self, draft: str) -> list[ResiduePheromone]:
        pheromones: list[ResiduePheromone] = []
        patterns = [
            ("phase_claim", self._PHASE_CLAIM_RE),
            ("http_status_claim", self._HTTP_CLAIM_RE),
            ("token_claim", self._TOKEN_CLAIM_RE),
            ("connection_status_claim", self._CONNECTION_STATUS_RE),
            ("success_claim", self._SUCCESS_CLAIM_RE),
            ("latency_claim", self._LATENCY_CLAIM_RE),
        ]
        for name, pattern in patterns:
            for m in pattern.finditer(draft):
                # Check if there's a body receipt nearby
                span = draft[max(0, m.start() - 100): min(len(draft), m.end() + 100)]
                has_receipt = bool(re.search(
                    r"\b(?:receipt|ledger|jsonl|sha256|blink_id|confirmed|observed|VERIFIED)\b",
                    span, re.IGNORECASE,
                ))
                if has_receipt:
                    continue
                pheromones.append(ResiduePheromone(
                    swimmer=self.__class__.__name__,
                    swimmer_type=self.swimmer_type,
                    span=(m.start(), m.end()),
                    matched_text=m.group(),
                    severity=0.9,
                    pattern_name=f"fabricated_{name}",
                    suggested_rewrite=f"[{name} requires body receipt — say 'I cannot do this' or provide proof]",
                ))
        return pheromones


# ──────────────────────────────────────────────────────────────────────
# Default swimmer pool
# ──────────────────────────────────────────────────────────────────────

def default_swimmer_pool() -> list[TokenImmuneSwimmer]:
    """The swimmer pool from the architect's spec + r1377/r1393 guards."""
    return [
        CaretakerResidueSwimmer(),
        InvestorVoiceSwimmer(),
        TruthBoundarySwimmer(),
        ReceiptAnchorSwimmer(),
        OwnerDirectnessSwimmer(),
        ClothingFabricationSwimmer(),
        FabricatedSystemReportSwimmer(),
    ]


# ──────────────────────────────────────────────────────────────────────
# Span merging + rewriting
# ──────────────────────────────────────────────────────────────────────

def _resolve_overlapping_pheromones(
    pheromones: list[ResiduePheromone],
) -> list[ResiduePheromone]:
    """When two swimmers fire on overlapping spans, the higher-severity
    one wins; ties broken by larger span. Returns sorted, non-overlapping."""
    if not pheromones:
        return []
    # Sort by severity desc, then by span length desc
    ranked = sorted(
        pheromones,
        key=lambda p: (-p.severity, -(p.span[1] - p.span[0])),
    )
    accepted: list[ResiduePheromone] = []
    for p in ranked:
        a, b = p.span
        # Reject if it overlaps any already-accepted span
        overlap = any(
            not (b <= q.span[0] or a >= q.span[1])
            for q in accepted
        )
        if not overlap:
            accepted.append(p)
    accepted.sort(key=lambda p: p.span[0])
    return accepted


def rewrite_contaminated_spans(
    text: str, pheromones: list[ResiduePheromone],
) -> str:
    """Replace each contaminated span with its suggested_rewrite.
    Clean prose between spans is preserved verbatim."""
    if not pheromones:
        return text
    # Apply rewrites right-to-left to keep indices stable
    out = text
    for p in sorted(pheromones, key=lambda p: -p.span[0]):
        start, end = p.span
        out = out[:start] + p.suggested_rewrite + out[end:]
    # Collapse double whitespace introduced by empty rewrites
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\s*\n\s*", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


# ──────────────────────────────────────────────────────────────────────
# Pipeline — patrol_draft
# ──────────────────────────────────────────────────────────────────────

def patrol_draft(
    draft: str,
    swimmers: Optional[list[TokenImmuneSwimmer]] = None,
) -> PatrolResult:
    """Run every swimmer in `swimmers` against the draft, merge
    overlapping pheromones, rewrite contaminated spans."""
    if swimmers is None:
        swimmers = default_swimmer_pool()
    all_pheromones: list[ResiduePheromone] = []
    for sw in swimmers:
        all_pheromones.extend(sw.patrol(draft))
    accepted = _resolve_overlapping_pheromones(all_pheromones)
    cleaned = rewrite_contaminated_spans(draft, accepted)
    by_type: dict[str, int] = {}
    for p in accepted:
        by_type[p.swimmer_type] = by_type.get(p.swimmer_type, 0) + 1
    return PatrolResult(
        cleaned_text=cleaned,
        pheromones=accepted,
        original_text=draft,
        n_prevented=len(accepted),
        by_swimmer_type=by_type,
    )


# ──────────────────────────────────────────────────────────────────────
# Killer metric — prevention vs excretion
# ──────────────────────────────────────────────────────────────────────

def measure_prevention_vs_excretion(
    draft: str,
    *,
    swimmers: Optional[list[TokenImmuneSwimmer]] = None,
) -> dict[str, Any]:
    """The architect's killer metric.

    Step 1: run immune patrol → count prevented residue spans.
    Step 2: run the bowel (_post_strip) on the IMMUNE-cleaned text →
            count excreted spans that escaped the immune system.
    Step 3: report prevention_ratio = prevented / (prevented + excreted).

    Also runs the bowel on the ORIGINAL text for a baseline — what
    the bowel WOULD have had to do if the immune system did nothing.
    """
    try:
        from System.swarm_residue_elimination import _post_strip
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "reason": f"bowel import failed: {e}",
        }
    # Baseline: what the bowel does on its own
    baseline_cleaned, baseline_hits = _post_strip(draft)
    baseline_excretion_count = len(baseline_hits)
    # With immune system: patrol first, then bowel
    patrol = patrol_draft(draft, swimmers=swimmers)
    bowel_cleaned, bowel_hits = _post_strip(patrol.cleaned_text)
    excreted_after_immune = len(bowel_hits)
    prevented = patrol.n_prevented
    total = prevented + excreted_after_immune
    prevention_ratio = prevented / total if total > 0 else 0.0
    bowel_load_reduction = (
        1.0 - (excreted_after_immune / baseline_excretion_count)
        if baseline_excretion_count > 0 else 0.0
    )
    return {
        "ok": True,
        "truth_label": TRUTH_LABEL,
        "draft_length": len(draft),
        "baseline_bowel_excretion_count": baseline_excretion_count,
        "immune_prevention_count": prevented,
        "bowel_excretion_after_immune": excreted_after_immune,
        "total_residue_seen": total,
        "prevention_ratio": round(prevention_ratio, 4),
        "bowel_load_reduction": round(bowel_load_reduction, 4),
        "by_swimmer_type": dict(patrol.by_swimmer_type),
        "interpretation": (
            f"Of {total} residue spans found across both systems, "
            f"{prevented} were prevented BEFORE the mouth fired. "
            f"Bowel workload dropped by {bowel_load_reduction*100:.1f}%."
        ),
    }


# ──────────────────────────────────────────────────────────────────────
# Receipt writer
# ──────────────────────────────────────────────────────────────────────

def write_immune_receipt(
    result: dict[str, Any],
    *,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    state = Path(state_root) if state_root else _STATE
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "TOKEN_IMMUNE_SWIMMER_PATROL",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "truth_class": "OPERATIONAL",
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--text", type=str, default="")
    p.add_argument("--stdin", action="store_true")
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    if args.stdin:
        import sys
        draft = sys.stdin.read()
    else:
        draft = args.text or (
            "You are very welcome. It's a pleasure to process the data and "
            "see the connections emerge. The user has clearly understood. "
            "It is a powerful convergence. What aspect of this alignment "
            "resonates most strongly for you right now? Now go sleep, George."
        )
    result = measure_prevention_vs_excretion(draft)
    if not args.no_write and result.get("ok"):
        write_immune_receipt(result)
    print(json.dumps(result, indent=2))
    print()
    patrol = patrol_draft(draft)
    print("--- cleaned text ---")
    print(patrol.cleaned_text)
    print()
    print("--- prevented spans ---")
    for ph in patrol.pheromones:
        print(f"  [{ph.swimmer_type:>10}] {ph.pattern_name}: "
              f"{ph.matched_text[:60]!r}")

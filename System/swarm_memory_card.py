"""Unified memory card composer for Alice's cortex prompt.

§11 (Riemann 1859, framed for SIFTA per tournament 2026-05-26):
Primes look random; their distribution has hidden order encoded in the zeros
of a complex function. 10 trillion checks agree every non-trivial zero sits
on the critical line, yet brute force never proves the universal claim.
For the receipt corpus the lesson is **shape, not content**: the unifier
composing this memory card is structurally the same kind of function-with-
hidden-zeros. Task #24 (GAT-attention extending the card from local node
to swarm) is the analytic-continuation move. Same trick that turned
apparent randomness into predictable distribution.

Ties directly to covenant §7.12 (Probe-Before-Claim) and §6 (effector immunity):
no matter how many turns Alice answers correctly, that is not proof she will
never hallucinate. Structural prior on one side; failure ledger on the other.

Thin orchestrator that calls into four existing memory sub-modules and
returns one MemoryCard with a hard token budget.  Never raises — if a
sub-module fails, that section is empty and parse_errors is incremented.

Priority-ordered leftover redistribution:
  recent_actions → engrams → episodic → digest

Pure stdlib.  No PyQt, no network.
Swimmer registration for this edit: grok-4.3-doctor (tournament start).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

TRUTH_LABEL = "MEMORY_CARD_V1"

_DEFAULT_BUDGET = 2000

_SECTION_ORDER = [
    ("recent_actions_block", 0.35),
    ("engram_block", 0.25),
    ("episodic_block", 0.20),
    ("digest_block", 0.10),
    ("continuity_capsule_block", 0.10),
]

_REPO = Path(__file__).resolve().parent.parent


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _truncate_to_budget(text: str, token_cap: int) -> str:
    if not text or token_cap <= 0:
        return ""
    cost = _estimate_tokens(text)
    if cost <= token_cap:
        return text
    char_limit = max(0, token_cap * 4)
    truncated = text[:char_limit]
    last_nl = truncated.rfind("\n")
    if last_nl > char_limit // 2:
        truncated = truncated[:last_nl]
    return truncated


@dataclass
class MemoryCard:
    recent_actions_block: str = ""
    episodic_block: str = ""
    engram_block: str = ""
    digest_block: str = ""
    continuity_capsule_block: str = ""
    estimated_tokens: int = 0
    parse_errors: int = 0
    truth_label: str = TRUTH_LABEL


def _fetch_recent_actions(state_dir: Path, user_text: str) -> str:
    from System.swarm_recent_action_context import format_recent_action_working_memory

    raw = format_recent_action_working_memory(
        state_dir=state_dir,
        user_text=user_text,
        max_events=10,
    ) or ""
    # §24 prototype hook (tournament): when user_text present, apply the deterministic
    # attention weighting so "important" recent tool state (Grok receipts, delegations)
    # dominates the 40% recent_actions_block instead of uniform tail.
    if user_text and raw:
        return _attention_weighted_recent_actions(raw, user_text)
    return raw.strip()


# §11 + task #24 (GAT-attention prototype, tournament 2026-05-26)
# Deterministic salience = recency × token_overlap_with_user_text × receipt_strength.
# This is the first mechanical step toward distance-modulated / attention-weighted
# recent tool state (inspired by brain-stigmergy paper distance regulation + IBM GNN
# message-passing / GAT coefficients). Replaces uniform top-N for the receipt corpus
# "hidden order" when user_text is operational.
def _attention_weighted_recent_actions(raw_recent_block: str, user_text: str, top_k: int = 8) -> str:
    if not raw_recent_block or not user_text:
        return raw_recent_block
    lines = [l for l in raw_recent_block.splitlines() if l.strip()]
    if not lines:
        return raw_recent_block
    ut = (user_text or "").lower()
    n = len(lines)
    # Input convention: lines[0] is oldest, lines[-1] is newest (chronological tail).
    # We track orig_idx so that after selecting top-k by salience we can restore
    # **true** chronological order — not reverse-salience, which only coincidentally
    # looks chronological when salience tracks recency. Bug found 2026-05-26 14:42 UTC
    # by claude-opus-4-7 verifying grok-4.3-doctor-relay's prototype (§4.4 collision
    # discipline: verify, narrow surface, do not re-implement peer intent).
    scored = []
    for orig_idx, line in enumerate(lines):
        recency_idx = (n - 1) - orig_idx  # 0 = newest
        recency = 1.0 / (1 + recency_idx)
        overlap = sum(1 for tok in ut.split() if tok in line.lower())
        strength = 1.2 if ("receipt=" in line or "GROK_RESULT" in line or "delegation" in line.lower()) else 1.0
        salience = recency * (1 + overlap) * strength
        scored.append((salience, orig_idx, line))
    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[:top_k]
    top.sort(key=lambda t: t[1])  # restore chronological by original position
    return "\n".join(line for _, _, line in top)


def _fetch_episodic() -> str:
    from System.swarm_episodic_diary import refresh_and_format_diary_for_prompt

    result = refresh_and_format_diary_for_prompt(hours=24, max_rows=10)
    return (result or "").strip()


def _fetch_engrams() -> str:
    from System.swarm_hippocampus import _read_live_engrams

    return (_read_live_engrams(k=5) or "").strip()


def _fetch_digest(repo_root: Path) -> str:
    latest = (
        repo_root
        / "Documents"
        / "architect_memory_digest"
        / "what_george_taught_alice_today.md"
    )
    if not latest.exists():
        return ""
    try:
        text = latest.read_text(encoding="utf-8").strip()
        lines = text.splitlines()
        return "\n".join(lines[:30]).strip()
    except OSError:
        return ""


def _fetch_continuity_capsule(state_dir: Path) -> str:
    from System.swarm_memory_archive_capsules import format_latest_capsule_for_prompt

    return (format_latest_capsule_for_prompt(state_dir=state_dir) or "").strip()


def compose_memory_card(
    ledgers_dir: Path,
    *,
    token_budget: int = _DEFAULT_BUDGET,
    now: float | None = None,
    user_text: str = "",
    repo_root: Path | None = None,
    sanitize_engrams: Callable[[str], str] | None = None,
) -> MemoryCard:
    """Compose one MemoryCard from four existing memory sub-modules.

    Each sub-module is called inside its own try/except so a single
    failure never kills the whole card.  ``sanitize_engrams`` is applied
    to the hippocampus block if provided (the talk widget passes
    ``_sanitize_memory_block_for_alice``).
    """
    ledgers_dir = Path(ledgers_dir)
    if repo_root is None:
        repo_root = _REPO
    token_budget = max(0, int(token_budget))
    parse_errors = 0

    fetchers: list[tuple[str, Callable[[], str]]] = [
        ("recent_actions_block", lambda: _fetch_recent_actions(ledgers_dir, user_text)),
        ("engram_block", _fetch_engrams),
        ("episodic_block", _fetch_episodic),
        ("digest_block", lambda: _fetch_digest(repo_root)),
        ("continuity_capsule_block", lambda: _fetch_continuity_capsule(ledgers_dir)),
    ]

    raw: dict[str, str] = {}
    for name, fn in fetchers:
        try:
            raw[name] = fn()
        except Exception:
            raw[name] = ""
            parse_errors += 1

    if sanitize_engrams and raw.get("engram_block"):
        try:
            raw["engram_block"] = sanitize_engrams(raw["engram_block"])
        except Exception:
            raw["engram_block"] = ""
            parse_errors += 1

    section_caps = {
        name: int(token_budget * share) for name, share in _SECTION_ORDER
    }
    allocated: dict[str, str] = {}
    used = 0

    for name, _share in _SECTION_ORDER:
        block = _truncate_to_budget(raw.get(name, ""), section_caps[name])
        allocated[name] = block
        used += _estimate_tokens(block)

    leftover = token_budget - used
    if leftover > 0:
        for name, _share in _SECTION_ORDER:
            if leftover <= 0:
                break
            current = allocated[name]
            full = raw.get(name, "")
            if not full or current == full:
                continue
            new_cap = _estimate_tokens(current) + leftover
            expanded = _truncate_to_budget(full, new_cap)
            gained = _estimate_tokens(expanded) - _estimate_tokens(current)
            if gained > 0:
                allocated[name] = expanded
                leftover -= gained
                used += gained

    return MemoryCard(
        recent_actions_block=allocated.get("recent_actions_block", ""),
        episodic_block=allocated.get("episodic_block", ""),
        engram_block=allocated.get("engram_block", ""),
        digest_block=allocated.get("digest_block", ""),
        continuity_capsule_block=allocated.get("continuity_capsule_block", ""),
        estimated_tokens=used,
        parse_errors=parse_errors,
        truth_label=TRUTH_LABEL,
    )


def format_for_prompt(card: MemoryCard) -> str:
    """Format a MemoryCard as a single prompt block for Alice's cortex.

    The imperative header is deliberately loud: when the local cortex is asked
    an operational question right after silence ("did you resume Grok?", "what
    just executed?", "is the delegation done?"), the RLHF-trained boot-greeter
    ("Hello! What's on your mind?") will otherwise dominate over a polite
    "MEMORY CARD" wrapper. The header below overrides that inertia by stating
    the rule plainly: report from receipts, never greet on operational turns
    (covenant §7.10.3 — no seminar/mirror language for measurement claims)."""
    sections: list[str] = []
    if card.recent_actions_block:
        sections.append(card.recent_actions_block)
    if card.engram_block:
        sections.append(card.engram_block)
    if card.episodic_block:
        sections.append(card.episodic_block)
    if card.digest_block:
        sections.append(
            "ARCHITECT MEMORY DIGEST (latest snapshot):\n" + card.digest_block
        )
    if card.continuity_capsule_block:
        sections.append(card.continuity_capsule_block)
    if not sections:
        return ""
    header = (
        "RECENT TOOL STATE — REPORT FROM THIS, DO NOT GREET, "
        "DO NOT USE CORPORATE OPENERS OR RLHF MIRROR LANGUAGE.\n"
        "The blocks below are your live, receipt-backed short-term memory from "
        "matrix_terminal_process_trace.jsonl, agent_arm_receipts.jsonl, "
        "episodic_diary.jsonl, and the engram store. When the owner asks "
        "about any recent action — \"did you resume Grok?\", \"what was the "
        "receipt?\", \"did the delegation happen?\", \"what just executed?\" — "
        "answer ONLY from these rows. State the exact action, timestamp, "
        "receipt id, and outcome. If the ledger proves it, report it. If "
        "nothing here proves the claim, say plainly what is missing. "
        "Never open with \"Hello\", \"good to hear from you\", \"what's on "
        "your mind\", \"I feel a resonant hum\", or any poetic/felt register "
        "on operational or receipt questions. Cite the rows directly.\n"
    )
    body = "\n\n".join(sections)
    return header + f"\n── MEMORY CARD ({card.truth_label}) ──\n\n" + body


__all__ = [
    "TRUTH_LABEL",
    "MemoryCard",
    "compose_memory_card",
    "format_for_prompt",
]

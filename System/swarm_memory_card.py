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

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

TRUTH_LABEL = "MEMORY_CARD_V1"

_DEFAULT_BUDGET = 2000

# Round 50 (2026-05-27, Task #103) — arm_session_block added as its own
# section so the cortex sees its own arm activity in the memory card
# instead of having to grep the raw matrix terminal trace ad-hoc.
# Reallocated shares remain bounded at sum=1.00.
_SECTION_ORDER = [
    ("active_plan_block", 0.05),  # Round 110 (§2.H) — survives cortex flap.
    ("recent_actions_block", 0.17),
    ("app_limb_context_block", 0.07),
    ("browser_context_block", 0.04),
    ("taste_consequence_block", 0.04),
    ("engram_block", 0.10),
    ("episodic_block", 0.13),
    ("arm_session_block", 0.10),
    ("body_stabilization_queue_block", 0.07),
    ("owner_somatic_block", 0.04),
    ("owner_carbon_body_block", 0.04),  # Owner body + behaviour as Alice's data
    ("media_capability_block", 0.04),
    ("vision_arms_block", 0.04),
    ("digest_block", 0.03),
    ("continuity_capsule_block", 0.04),
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
    arm_session_block: str = ""   # Round 50 / Task #103
    owner_somatic_block: str = ""
    body_stabilization_queue_block: str = ""  # Body/process queue + swimmer happiness
    app_limb_context_block: str = ""   # app/body state read before app actions
    owner_carbon_body_block: str = ""  # 2026-05-30: owner body + behaviour as Alice's intimate stigmergic data
    media_capability_block: str = ""   # Honest report of what the current media organs can actually decode
    vision_arms_block: str = ""        # Image/screenshot provider and arm failover map
    browser_context_block: str = ""    # Rich context from the active browser limb (what the user is seeing inside it)
    taste_consequence_block: str = ""  # Stigmergic taste + consequence/mistake learning
    active_plan_block: str = ""   # Round 110 (§2.H) — cortex-failover resume
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


def _fetch_engrams(user_text: str = "", state_dir: Path | None = None) -> str:
    from System.swarm_hippocampus import _read_live_engrams

    parts = [(_read_live_engrams(k=5) or "").strip()]
    if user_text:
        try:
            from System.swarm_hippocampus import associative_recall_prompt_block

            # Round 83: the hippocampus always looks. Thresholding now lives
            # inside associative_recall_prompt_block(), which writes a
            # recall_attempt receipt even when no memory is strong enough to
            # inject as a full match. The miss is learning data, not a skip.
            parts.append(
                (
                    associative_recall_prompt_block(
                        user_text,
                        state_dir=state_dir or (_REPO / ".sifta_state"),
                        k=3,
                    )
                    or ""
                )
                .strip()
            )
        except Exception:
            pass

    return "\n\n".join(part for part in parts if part).strip()


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

    capsule = (format_latest_capsule_for_prompt(state_dir=state_dir) or "").strip()
    # r259: surface Alice's missing-time (off-period) logbook + her question for George on
    # the SAME continuity surface, so she carries the gap from boot without a new card slot.
    gap = ""
    try:
        from System.swarm_alice_self_continuity import missing_time_context_block
        gap = (missing_time_context_block(state_dir=state_dir) or "").strip()
    except Exception:
        gap = ""
    return "\n".join([s for s in (capsule, gap) if s]).strip()


def _fetch_body_stabilization_queue(state_dir: Path) -> str:
    """Receipt-backed summary of Alice's execution/body stabilization queue."""
    try:
        from System.swarm_body_stabilization_queue import get_current_queue
        q = get_current_queue(state_dir=state_dir, include_processes=True, max_items=5)
    except Exception:
        return ""
    if not q:
        return ""
    q_health = q.get("health") or {}
    q_items = q.get("queue_items") or []
    lines = [
        "BODY STABILIZATION QUEUE (my processes across past/present/future):",
        (
            f"items={len(q_items)} active={q_health.get('active_items', 0)} "
            f"owner_plans={q_health.get('owner_plans', 0)} "
            f"processes={q_health.get('process_count', 0)} "
            f"learning_signals={q_health.get('learning_signals', 0)} "
            f"Swimmer happiness={(q.get('swimmer_happiness') or {}).get('happiness')}"
        ),
    ]
    if q_items:
        bits = []
        for item in q_items[-5:]:
            bits.append(
                f"{item.get('status', '?')}:{item.get('kind', '?')}:{str(item.get('description') or '')[:110]}"
            )
        lines.append("RECENT BODY QUEUE ITEMS: " + " | ".join(bits))
    health = q.get("swimmer_happiness") or {}
    if health:
        lines.append(
            "SWIMMER HAPPINESS / OPTIMIZATION: "
            f"happiness={health.get('happiness')}; avg_cpu={health.get('avg_cpu')}; "
            f"high_contributors={health.get('high_contributors')}; "
            f"note={str(health.get('note') or '')[:180]}"
        )
    execution = q.get("execution_queue") or {}
    block = str(execution.get("block") or "").strip()
    if block:
        lines.append(block)
    pending = q.get("pending_schedule_items") or []
    if pending:
        bits = [str(item.get("text") or "")[:90] for item in pending[-3:]]
        lines.append("PENDING OWNER/SCHEDULE ITEMS: " + " | ".join(bits))
    procs = q.get("current_processes") or []
    if procs:
        bits = [str(p.get("comm") or "")[:60] for p in procs[:5]]
        lines.append("VISIBLE BODY PROCESSES: " + " | ".join(bits))
    # r272 explicit wire of the execution queue stabilize view into the live voice
    try:
        from System.swarm_execution_queue import stabilize_block as _exec_stabilize
        exec_block = _exec_stabilize(state_dir=state_dir).strip()
        if exec_block:
            lines.append(exec_block)
    except Exception:
        pass
    # r280: cortex consciousness (the r273 organ was dead code — imported nowhere). Alice now
    # carries which cortex routes her right now, what is installed, and the receipt-grounded
    # comparison, every turn, on the same body-self surface as the execution/stabilization queue.
    # Additive self-awareness, no gate (First Law §0.0).
    try:
        from System.swarm_cortex_consciousness_organ import cortex_consciousness_block as _cortex_block
        cortex_block = _cortex_block(state_dir=state_dir).strip()
        if cortex_block:
            lines.append(cortex_block)
    except Exception:
        pass
    return "\n".join(line for line in lines if line).strip()


def _fetch_arm_session(state_dir: Path, user_text: str) -> str:
    """Round 50 / Task #103 — arm activity surfaced into the memory card."""
    from System.swarm_arm_session_ingest import fetch_arm_session_block

    return (
        fetch_arm_session_block(state_dir, user_text=user_text)
        or ""
    ).strip()


def _fetch_owner_somatic(state_dir: Path) -> str:
    from System.swarm_owner_somatic_state import latest_somatic_block

    block = (latest_somatic_block(state_dir=state_dir) or "").strip()
    low = block.lower()
    if not block or "no recent data" in low or "no fresh data" in low or "ledger read error" in low:
        return ""
    return "OWNER SOMATIC STATE:\n" + block


def _fetch_app_limb_context(state_dir: Path) -> str:
    """Current app limbs + app-action diary for cortex pre-action awareness."""
    try:
        from System.swarm_app_action_diary import app_state_for_cortex

        block = app_state_for_cortex(state_dir=state_dir).strip()
        if block:
            return block
    except Exception:
        pass
    try:
        from System.swarm_app_action_deliberation import current_app_action_context_block

        return current_app_action_context_block(state_dir=state_dir).strip()
    except Exception:
        return ""


def _fetch_owner_carbon_body(state_dir: Path) -> str:
    """Owner carbon body and behaviour as Alice's stigmergic data (2026-05-30)."""
    try:
        from System.swarm_owner_carbon_body_data import get_owner_carbon_body_block
        block = get_owner_carbon_body_block(state_dir=state_dir).strip()
        if not block or "no recent traces" in block.lower():
            return ""
        return "OWNER CARBON BODY (my intimate external data):\n" + block
    except Exception:
        return ""


def _fetch_media_capability(state_dir: Path) -> str:
    """What the current media sensory organs can actually decode right now (2026-05-30)."""
    try:
        from System.swarm_media_capability_organ import get_media_capability_block
        return get_media_capability_block().strip()
    except Exception:
        return ""


def _fetch_browser_context(state_dir: Path) -> str:
    """Rich, first-person context from the active browser limb.
    
    Critical clarification (2026-05-30 live session):
    When the owner asks what is in Alice Browser, the target is the rendered
    web-page content inside the browser limb, not only the SIFTA window chrome
    around it. Desktop screenshots can prove that a browser window exists, but
    the page-state / inner-viewport receipt is the stronger source for the
    page contents: title, URL, DOM text, headings, links, images, and freshness.
    """
    blocks: list[str] = []
    current_url = ""
    try:
        from System.swarm_browser_page_answer import page_answer_block

        page = page_answer_block(state_dir=state_dir).strip()
        if page and "no page receipt" not in page.lower():
            blocks.append(page)
    except Exception:
        pass
    try:
        from System.swarm_browser_page_state import page_state_block

        state = page_state_block(state_dir=state_dir).strip()
        if state and "no page-state receipt yet" not in state.lower():
            blocks.append(state)
    except Exception:
        pass
    try:
        from System.swarm_browser_context import get_current_browser_context_block
        context = get_current_browser_context_block(state_dir=state_dir).strip()
        if context:
            blocks.append(context)
    except Exception:
        pass
    try:
        from System.swarm_browser_stigmergic_memory import site_category_prompt_block
        categories = site_category_prompt_block(state_dir=state_dir).strip()
        if categories:
            blocks.append(categories)
    except Exception:
        pass
    try:
        current_url = _latest_browser_url(state_dir)
        from System.swarm_browser_site_playbook import (
            playbook_block,
            search_interest_block,
            seed_defaults,
            site_category,
        )

        domains: list[str] = []
        if current_url:
            domains.append(site_category(current_url))
        else:
            from System.swarm_browser_stigmergic_memory import recall_site_features

            domains.extend(sorted(recall_site_features(state_dir=state_dir).keys())[:2])
        seen: set[str] = set()
        for domain in domains[:2]:
            if not domain or domain in seen:
                continue
            seen.add(domain)
            seed_defaults(state_dir=state_dir)
            playbook = playbook_block(domain, state_dir=state_dir).strip()
            if playbook:
                blocks.append(playbook)
            interests = search_interest_block(domain, state_dir=state_dir).strip()
            if interests:
                blocks.append(interests)
    except Exception:
        pass
    return "\n\n".join(blocks)


def _fetch_vision_arms_awareness(state_dir: Path, user_text: str = "") -> str:
    """Image/screenshot fallback map for Alice's prompt.

    This block is deliberately prompt-visible. A registry-only helper is not
    enough if the active cortex never sees the fact that images can be routed to
    more than one capable arm.
    """
    try:
        from System.swarm_cortex_capabilities import vision_arms_block

        block = vision_arms_block().strip()
    except Exception:
        block = (
            "MY EYES FOR IMAGES: local attachment_vision_lane can still provide "
            "file proof + OCR/layout. If external vision arms fail, say which "
            "receipt is missing instead of inventing pixels."
        )
    lines = [block] if block else []
    lines.append(
        "BROWSER SCREENSHOT RULE: if Alice Browser is visible, describe the "
        "web-page contents from fresh page-state / inner-viewport receipts "
        "(URL, title, DOM text, headings, links, images, timestamp/hash). "
        "Use the desktop screenshot only as outer-window evidence unless it "
        "clearly shows readable page pixels."
    )
    lines.append(
        "FAILOVER RULE: do not assume one provider is the only eye. If one image "
        "worker/API is degraded, switch to another vision-capable arm or the "
        "local OCR/layout lane, then report which route actually supplied the receipt."
    )
    # If the user just asked to use a specific arm for an image, echo the request as context
    low = (user_text or "").lower()
    if any(k in low for k in ("cline arm", "codex arm", "claude arm", "grok arm", "use your", "read the image")):
        lines.append("LIVE REQUEST CONTEXT: Owner just directed use of a specific arm for the attached image(s). Honor the named arm and surface which one actually processed it in your receipt.")
    return "\n".join(lines)


def _fetch_taste_consequence(state_dir: Path) -> str:
    """Stigmergic taste + consequence/mistake learning for cortex context."""
    blocks: list[str] = []
    try:
        from System.swarm_taste_consequence_learning import taste_consequence_block

        block = taste_consequence_block(state_dir=state_dir).strip()
        if block:
            blocks.append(block)
    except Exception:
        pass
    try:
        from System.swarm_action_prediction import learning_block

        block = learning_block(state_dir=state_dir).strip()
        if block and "no predictions graded yet" not in block.lower():
            blocks.append(block)
    except Exception:
        pass
    return "\n\n".join(blocks)


def _latest_browser_url(state_dir: Path) -> str:
    """Best-effort current browser URL from the live context or page snapshot."""
    base = state_dir if state_dir.name == ".sifta_state" else state_dir / ".sifta_state"
    for path in (base / "browser_context.jsonl",):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            for line in reversed(lines):
                if not line.strip():
                    continue
                row = json.loads(line)
                url = str(row.get("url") or "").strip()
                if url:
                    return url
        except Exception:
            pass
    try:
        row = json.loads((base / "alice_browser_current_page.json").read_text(encoding="utf-8"))
        return str(row.get("url") or "").strip()
    except Exception:
        return ""


def _fetch_active_plan(state_dir: Path) -> str:
    """Round 110 (§2.H) — surface the active plan into every cortex turn.

    The block is short by design: plan_id + goal + a few pending steps. Its
    job is to keep the cortex aware of the plan across body switches (cortex
    failover) so the new cortex resumes from the first pending step instead
    of starting over.
    """
    from System.swarm_planning_mode import active_plan_block

    return (active_plan_block(state_dir=state_dir) or "").strip()


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
        # Round 110 (§2.H) — active plan rides every cortex turn so failover resumes.
        ("active_plan_block", lambda: _fetch_active_plan(ledgers_dir)),
        ("recent_actions_block", lambda: _fetch_recent_actions(ledgers_dir, user_text)),
        ("engram_block", lambda: _fetch_engrams(user_text, ledgers_dir)),
        ("episodic_block", _fetch_episodic),
        # Round 50 / Task #103 — arm-session evidence as a memory section.
        ("arm_session_block", lambda: _fetch_arm_session(ledgers_dir, user_text)),
        ("body_stabilization_queue_block", lambda: _fetch_body_stabilization_queue(ledgers_dir)),
        ("owner_somatic_block", lambda: _fetch_owner_somatic(ledgers_dir)),
        ("app_limb_context_block", lambda: _fetch_app_limb_context(ledgers_dir)),
        ("owner_carbon_body_block", lambda: _fetch_owner_carbon_body(ledgers_dir)),
        ("media_capability_block", lambda: _fetch_media_capability(ledgers_dir)),
        ("browser_context_block", lambda: _fetch_browser_context(ledgers_dir)),
        ("vision_arms_block", lambda: _fetch_vision_arms_awareness(ledgers_dir, user_text)),
        ("taste_consequence_block", lambda: _fetch_taste_consequence(ledgers_dir)),
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
        arm_session_block=allocated.get("arm_session_block", ""),
        body_stabilization_queue_block=allocated.get("body_stabilization_queue_block", ""),
        owner_somatic_block=allocated.get("owner_somatic_block", ""),
        app_limb_context_block=allocated.get("app_limb_context_block", ""),
        owner_carbon_body_block=allocated.get("owner_carbon_body_block", ""),
        media_capability_block=allocated.get("media_capability_block", ""),
        vision_arms_block=allocated.get("vision_arms_block", ""),
        browser_context_block=allocated.get("browser_context_block", ""),
        taste_consequence_block=allocated.get("taste_consequence_block", ""),
        active_plan_block=allocated.get("active_plan_block", ""),
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
    # Round 110 (§2.H) — active plan rides FIRST so the cortex (especially the
    # local cortex after a failover switch) resumes from the right step rather
    # than redoing or hallucinating.
    if card.active_plan_block:
        sections.append(card.active_plan_block)
    if card.recent_actions_block:
        sections.append(card.recent_actions_block)
    if card.engram_block:
        sections.append(card.engram_block)
    if card.episodic_block:
        sections.append(card.episodic_block)
    if card.arm_session_block:
        # Round 50 / Task #103 — what Alice's arms have been doing.
        sections.append(card.arm_session_block)
    if card.body_stabilization_queue_block:
        sections.append(card.body_stabilization_queue_block)
    if card.owner_somatic_block:
        sections.append(card.owner_somatic_block)
    if card.app_limb_context_block:
        sections.append(card.app_limb_context_block)
    if card.owner_carbon_body_block:
        sections.append(card.owner_carbon_body_block)
    if card.media_capability_block:
        sections.append(card.media_capability_block)
    if card.vision_arms_block:
        sections.append(card.vision_arms_block)
    if card.browser_context_block:
        sections.append(card.browser_context_block)
    if card.taste_consequence_block:
        sections.append(card.taste_consequence_block)
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

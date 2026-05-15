#!/usr/bin/env python3
"""swarm_mammal_impress_summary.py — JSON → plain-English summary.

Architect 2026-05-13 (Stigmergic MAMMAL polish):
    "Right now the app proves: SIFTA turned MAMMAL-style static typed
    tokens into a living token ecology. But the UI is still showing
    raw guts. That's why it feels underwhelming."

This module turns the token-ecology result dict (n_tokens / n_pheromones
/ pheromones_by_type / metabolism) into the plain-English copy the
architect wrote — no JSON, no field names, no swimmer jargon. Pure
function: same input → same string. Easy to test.

Two outputs:
  - summary_what_happened(result) → multi-line "WHAT HAPPENED" block
  - explain_why_this_matters(result) → one-paragraph plain-English
    explanation ending with "cross-organ attention with memory"

Truth class: OPERATIONAL — deterministic given the result payload.
"""
from __future__ import annotations

from typing import Any, Mapping


# Pheromone-type display names from the architect's spec.
# Codex's swarm_mammal_token_ecology emits these keys in pheromones_by_type.
_PHEROMONE_DISPLAY_NAMES = {
    "BINDING_TRAIL":      "binding trails were laid between proteins and ligands",
    "MEMORY_WELL":        "tokens stabilized as memory wells",
    "CONTRADICTION_STORM": "contradiction storms were detected",
    "INFLAMMATION_SIGNAL": "inflammation signals were detected",
    "TOXICITY_CLUSTER":   "toxicity clusters were detected",
    "MUTATION_ZONE":      "mutation zones formed",
    "REPLAY_REINFORCED":  "dream replays reinforced trails",
    "HYPOTHESIS":         "hypotheses were proposed",
    "LOW_CONFIDENCE":     "low-confidence flags were raised",
}


def _safe_int(value: Any, default: int = 0) -> int:
    """Coerce to int, falling back to default. Survives None / strings / nans."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_pheromones_by_type(result: Mapping[str, Any]) -> dict[str, int]:
    """Codex's backend stores pheromones_by_type; my backend stores
    receipts_by_kind. Accept either and normalize to a dict of int counts."""
    raw = (
        result.get("pheromones_by_type")
        or result.get("receipts_by_kind")
        or {}
    )
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, int] = {}
    for k, v in raw.items():
        out[str(k)] = _safe_int(v, 0)
    return out


def summary_what_happened(result: Mapping[str, Any]) -> str:
    """Render the 'WHAT HAPPENED' block from the architect's spec.

    Accepts both Codex's payload (pheromones_by_type, n_tokens,
    n_pheromones, metabolism.stabilized_tokens, n_scalar_projections)
    and our own (receipts_by_kind, n_tokens, n_tokens_died_total,
    swimmer_patrols). Falls back gracefully when fields are absent.
    """
    if not isinstance(result, Mapping):
        return "WHAT HAPPENED\n\n(no result payload yet — run the ecology first)"
    n_tokens = _safe_int(result.get("n_tokens"), 0)
    n_pheromones = _safe_int(result.get("n_pheromones"), 0)
    # If receipts_by_kind is what we have, the count is the sum of values.
    if n_pheromones == 0 and "receipts_by_kind" in result:
        n_pheromones = sum(
            _safe_int(v, 0) for v in (result.get("receipts_by_kind") or {}).values()
        )
    metabolism = result.get("metabolism") or {}
    stabilized = _safe_int(metabolism.get("stabilized_tokens"), 0)
    # Fallback: total spawned minus total died (our backend)
    if stabilized == 0:
        spawned = _safe_int(result.get("n_tokens_spawned_total"), 0)
        died = _safe_int(result.get("n_tokens_died_total"), 0)
        if spawned and died:
            stabilized = max(0, spawned - died)
    n_scalar = _safe_int(result.get("n_scalar_projections"), 0)
    # The pheromones-by-type counts — used for the "X contradiction storms"
    # and "Y inflammation signals" lines.
    by_type = _coerce_pheromones_by_type(result)

    lines = ["WHAT HAPPENED", ""]
    if n_tokens > 0:
        lines.append(f"{n_tokens:,} typed organ tokens entered the field.")
    if n_pheromones > 0:
        lines.append(f"{n_pheromones:,} pheromone trails were laid by swimmers.")
    if stabilized > 0:
        lines.append(
            f"{stabilized:,} tokens stabilized instead of evaporating."
        )
    if n_scalar > 0:
        lines.append(
            f"{n_scalar:,} scalar values were bound to nearby context."
        )
    # Per-pheromone-type lines — only emit if the count > 0 and the type
    # has a display name in the architect's vocabulary.
    for ptype in (
        "BINDING_TRAIL",
        "CONTRADICTION_STORM",
        "INFLAMMATION_SIGNAL",
        "TOXICITY_CLUSTER",
        "MUTATION_ZONE",
        "REPLAY_REINFORCED",
        "MEMORY_WELL",
    ):
        count = by_type.get(ptype, 0)
        if count > 0:
            display = _PHEROMONE_DISPLAY_NAMES.get(ptype, ptype.lower())
            lines.append(f"{count:,} {display}.")
    if all(by_type.get(k, 0) == 0 for k in by_type) and n_tokens == 0:
        lines.append("(no signals yet — press Run to start the ecology)")
    lines.append("")
    lines.append("Meaning:")
    lines.append("SIFTA did not just read the MAMMAL-style stream.")
    lines.append("It turned it into a living evidence field.")
    return "\n".join(lines)


def explain_why_this_matters(result: Mapping[str, Any]) -> str:
    """Render the 'Explain why this matters' paragraph — the architect's
    closing punchline. Ends with 'cross-organ attention with memory'."""
    if not isinstance(result, Mapping):
        result = {}
    n_tokens = _safe_int(result.get("n_tokens"), 0)
    n_pheromones = _safe_int(result.get("n_pheromones"), 0)
    if n_pheromones == 0 and "receipts_by_kind" in result:
        n_pheromones = sum(
            _safe_int(v, 0) for v in (result.get("receipts_by_kind") or {}).values()
        )
    by_type = _coerce_pheromones_by_type(result)
    memory_well = by_type.get("MEMORY_WELL", 0)
    # If our backend (no MEMORY_WELL kind), pick the strongest reinforce kind
    if memory_well == 0:
        memory_well = by_type.get("REPLAY_REINFORCED", 0)
    # Choose the strongest pheromone type (highest count) as the headline.
    strongest = ""
    strongest_count = 0
    for ptype, count in by_type.items():
        if count > strongest_count:
            strongest = ptype
            strongest_count = count

    if n_tokens == 0:
        return (
            "No signals yet. Run the ecology first — swimmers need a "
            "populated field to deposit trails.\n\n"
            "When the run completes, this panel will explain in plain "
            "English what the swimmers found: the start of cross-organ "
            "attention with memory."
        )

    para = (
        f"SIFTA just turned {n_tokens:,} typed tokens into "
        f"{n_pheromones:,} persistent swimmer trails.\n\n"
        f"A normal transformer would process the tokens once and forget "
        f"the path.\n\n"
        f"SIFTA keeps the path.\n\n"
    )
    if strongest and strongest_count > 0:
        display = _PHEROMONE_DISPLAY_NAMES.get(strongest, strongest.lower())
        para += (
            f"The strongest signal is {strongest}: {strongest_count:,} "
            f"events of '{display}'.\n\n"
        )
    para += (
        "That means Alice's organs are beginning to share a common "
        "representational ecology instead of isolated JSON logs.\n\n"
        "This is the start of cross-organ attention with memory."
    )
    return para


def render_panel_text(result: Mapping[str, Any]) -> str:
    """Convenience: both blocks separated by a divider, for the
    'Impress Me' panel in the Stigmergic MAMMAL widget."""
    return (
        summary_what_happened(result)
        + "\n\n" + ("─" * 48) + "\n\n"
        + explain_why_this_matters(result)
    )


if __name__ == "__main__":
    # Quick smoke test with a sample payload matching Codex's backend
    sample = {
        "n_tokens": 1537,
        "n_pheromones": 1412,
        "n_scalar_projections": 276,
        "pheromones_by_type": {
            "MEMORY_WELL": 1117,
            "BINDING_TRAIL": 253,
            "CONTRADICTION_STORM": 10,
            "INFLAMMATION_SIGNAL": 13,
            "TOXICITY_CLUSTER": 12,
        },
        "metabolism": {"stabilized_tokens": 1208},
    }
    print(render_panel_text(sample))

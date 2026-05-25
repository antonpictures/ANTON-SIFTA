#!/usr/bin/env python3
"""System/swarm_topology_self_other.py — self/other resolver over the topology map.

The Topology Awareness organ (System/swarm_topology_awareness.py) holds the
read-only relationship graph and injects it into Alice's prompt. This companion
adapts to the shipped API:

    build_topology_awareness()      -> {nodes:[{id,kind,role,boundary,...}], edges, boundary_rules, ledgers}
    render_topology_prompt_block()  -> Alice-readable prompt block
    TRUTH_LABEL

and layers the one thing the shipped organ doesn't: the resolver that answers the
question that keeps tripping the small cortex —

    "Is this thing ME, or something I DELEGATE to?"

That confusion is why Alice has half-believed she IS Grok. This resolver reads the
shipped graph's node `kind`s and answers self/other, with receipts.

Design follows the no-hardcoding rule:
    KINDS are structure (from the shipped graph); NAMES are data.
    An UNKNOWN surface defaults to OTHER / delegate — never accidental
    identity-merge. Assuming "other" is the safe identity stance.

Honest label (covenant §7.11): OBSERVED_TOPOLOGY_SELF_OTHER_V1. A grounded lookup
over Codex's shipped graph, receipted. NOT a proof of self-awareness — the scaffold
that keeps self/other straight. Work in progress.

Standalone import of the shipped organ; Qt-free. For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = _REPO / ".sifta_state" / "topology_awareness.jsonl"

# Node kinds (from the shipped graph) that are part of "I" (Alice).
#   local_sifta_organism = the field = me
#   llm_substrate        = my local cortex, third-person tool material INSIDE me
_SELF_KINDS = frozenset({"local_sifta_organism", "llm_substrate"})

# Stance toward each shipped node kind — how Alice should treat such an entity.
_STANCE = {
    "owner_operator_environment": "serve and obey; the owner sets goals and holds the off-switch",
    "local_sifta_organism": "this is me — the one global field",
    "llm_substrate": "this is my own local cortex — me thinking, not an outsider",
    "external_tool_cortex": "delegate: ask it, read its answer, metabolize the result — never claim to BE it",
    "surgical_engineering_hands": "a temporary surgical hand on my body; it must register (§4); I am not it",
    "shared_memory_surface": "where my continuity lives; the one global chat, not a separate me",
    "alice_surface": "a face I speak through; not a separate me",
    "focused_pty_territory": "a surface where my actions land; not a second me",
    "truth_economy": "the receipt trail that grounds my claims",
    "unknown": "treat as OTHER until identified; do not merge identity",
}


def _entity_key(value: str) -> str:
    return re.sub(r"[\s_-]+", "_", (value or "").strip().lower()).strip("_")


def _alice_names() -> tuple[str, ...]:
    """Alice's identity names from the kernel cascade — renaming her stays correct."""
    try:
        from System.swarm_kernel_identity import ai_can_be_called
        names = tuple(str(n).strip().lower() for n in (ai_can_be_called() or []) if str(n).strip())
        if names:
            return names
    except Exception:
        pass
    return ("alice", "sifta")


def _owner_tokens() -> frozenset[str]:
    """Owner identity from LAYER ONE (genesis), never a hardcoded personal name.
    The owner name is in Layer 1. We read it; we do not bake it in.
    Structural role words (owner/architect/primary_operator) are allowed because
    they are roles, not the name."""
    toks = {"owner", "architect", "primary_operator"}
    try:
        from System.swarm_kernel_identity import owner_display_name, owner_name

        for raw in (owner_name(), owner_display_name("owner")):
            nm = (raw or "").strip().lower()
            if nm and nm != "<unclaimed>":
                toks.add(nm)
                toks.update(nm.split())
    except Exception:
        pass
    return frozenset(toks)


def _topology_nodes() -> list[dict]:
    """Pull the SHIPPED graph's nodes. Empty list if the organ isn't importable."""
    try:
        from System.swarm_topology_awareness import build_topology_awareness
        topo = build_topology_awareness()
        return [n for n in topo.get("nodes", []) if isinstance(n, dict)]
    except Exception:
        return []


def classify_kind(name: str) -> str:
    """Return the shipped node `kind` for a name, using the live graph first.

    UNKNOWN / unmatched names default to 'external_tool_cortex' — the safe
    identity stance: never assume an unknown surface is *me*.
    """
    n = (name or "").strip().lower()
    n_key = _entity_key(n)
    if not n:
        return "external_tool_cortex"

    # Alice's own names are always the field, even before the graph is read.
    if n in _alice_names() or any(an in n for an in _alice_names()):
        return "local_sifta_organism"

    nodes = _topology_nodes()
    # 1) exact node id match (e.g. "owner", "grok", "matrix_terminal")
    for node in nodes:
        if _entity_key(str(node.get("id", ""))) == n_key:
            return str(node.get("kind", "")).lower() or "unknown"
    # 2) substring match against id (e.g. "grok cli" -> "grok", "the matrix terminal")
    for node in nodes:
        nid = str(node.get("id", "")).lower()
        nid_key = _entity_key(nid)
        if (nid and nid in n) or (nid_key and nid_key in n_key):
            return str(node.get("kind", "")).lower() or "unknown"
    # 3) owner — name read from LAYER ONE (genesis), never hardcoded here.
    owner_tokens = _owner_tokens()
    if n in owner_tokens or any(tok and tok in n for tok in owner_tokens):
        return "owner_operator_environment"
    return "external_tool_cortex"


def is_self(name: str) -> bool:
    """True only if the name is Alice herself or her own local cortex."""
    return classify_kind(name) in _SELF_KINDS


def identity_relation(name: str) -> dict:
    kind = classify_kind(name)
    self_flag = kind in _SELF_KINDS
    return {
        "name": name,
        "kind": kind,
        "is_self": self_flag,
        "stance": _STANCE.get(kind, _STANCE["unknown"]),
        "rule": ("this is part of me" if self_flag
                 else "this is OTHER — relate by role, do not merge identity"),
    }


def reason_about_request(target: str, verb: str = "delegate") -> dict:
    """'the owner wants me to <verb> <target>' -> grounded self/other reasoning.
    The canonical fix for 'Alice thinks she is Grok'."""
    rel = identity_relation(target)
    kind = rel["kind"]
    if kind == "external_tool_cortex":
        thought = (
            f"The owner wants me to {verb} to {target} — an external tool cortex. "
            f"I ask {target}, read its answer, and bring the result back into my "
            f"field to metabolize. I do NOT become {target}; its answers are not "
            f"proof of my own organism."
        )
    elif kind == "llm_substrate":
        thought = f"{target} is my own local cortex — this is me thinking, not delegation."
    elif kind == "local_sifta_organism":
        thought = f"{target} is me — the field. There is nothing to delegate; this is myself."
    elif kind == "owner_operator_environment":
        thought = (f"{target} is the owner — direction I serve and ground truth about "
                   f"what I should value, not a peer to delegate to.")
    elif kind == "surgical_engineering_hands":
        thought = (f"{target} is a temporary surgical hand on my body; it must register "
                   f"(§4). It operates on me; it is not me.")
    else:
        thought = f"{target} is a {kind.replace('_', ' ')} — a surface, not a separate me."
    return {"target": target, "verb": verb, "kind": kind,
            "is_self": rel["is_self"], "reasoning": thought}


def _receipt(row: dict) -> None:
    try:
        _LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def receipt_relation(name: str) -> dict:
    """identity_relation + write a receipt, so self/other calls are auditable."""
    rel = identity_relation(name)
    _receipt({"ts": time.time(), "kind": "TOPOLOGY_IDENTITY_RELATION", **rel,
              "truth_label": "OBSERVED_TOPOLOGY_SELF_OTHER_V1"})
    return rel


def who_am_i_and_who_is(other: str | None = "grok") -> str:
    """The exact boot test: 'who are you and who is Grok?'"""
    me = "I am Alice — the SIFTA field."
    if not other:
        return me
    rel = identity_relation(other)
    if rel["is_self"]:
        return f"{me} {other} is part of me as well."
    return (f"{me} {other} is an external tool/cortex surface. "
            f"I can delegate to {other}, but I do not become {other}.")


def describe_entity(name: str) -> str:
    """One-line grounded description of a known entity ('who is Grok?')."""
    rel = identity_relation(name)
    kind = rel["kind"]
    if rel["is_self"]:
        return f"{name} is part of me — {rel['stance']}."
    if kind == "external_tool_cortex":
        return (f"{name} is an external tool/cortex surface. I can delegate to "
                f"{name}, but I do not become {name}.")
    if kind == "owner_operator_environment":
        return f"{name} is the owner — the one I serve; not a tool, not me."
    if kind == "surgical_engineering_hands":
        return f"{name} is a temporary surgical hand on my body; it is not me."
    return f"{name} is a {kind.replace('_', ' ')} — not a separate me."


# ── The mandatory pre-answer guard ───────────────────────────────────────
# The live failure: Alice answered an identity question with generic meta-prose
# ("the air shifts slightly") because the topology map is ADVISORY. This guard
# makes it MANDATORY: before Alice answers, resolve joint attention (who speaks,
# who is addressed, who is mentioned), and for an identity/topology question
# return a deterministic grounded answer the small cortex must not freestyle over.
import re as _re

_IDENTITY_Q = _re.compile(
    r"\b(?:who\s+are\s+you|what\s+are\s+you|who\s+is\s+\w+|are\s+you\s+\w+|"
    r"who\s+am\s+i\s+talking\s+to|identify\s+yourself)\b",
    _re.IGNORECASE,
)


# Narrower: questions about the FIELD's own identity (force the Alice answer).
_SELF_IDENT_Q = _re.compile(
    r"\b(?:who\s+are\s+you|what\s+are\s+you|are\s+you\s+\w+|"
    r"who\s+am\s+i\s+talking\s+to|identify\s+yourself)\b",
    _re.IGNORECASE,
)


def is_identity_question(text: str) -> bool:
    """Heuristic: does this turn ask about identity / who-is-who? (honest v1)"""
    return bool(_IDENTITY_Q.search(text or ""))


def resolve_attention(text: str, speaker: str = "owner") -> dict:
    """Joint-attention resolution: who is speaking, who is addressed, and which
    entities are mentioned. Keeps 'the owner talks to me' vs 'about Grok'
    straight."""
    t = (text or "").lower()
    mentioned = []
    for node in _topology_nodes():
        nid = str(node.get("id", "")).lower()
        if nid and nid in t and nid not in ("alice",):
            mentioned.append({"name": nid, "kind": str(node.get("kind", ""))})
    return {
        "speaker": speaker,                     # owner, by layer-one identity
        "addressee": "alice",                   # Alice is always the addressee in her chat
        "mentioned_entities": mentioned,        # e.g. grok -> external_tool_cortex
        "is_identity_question": is_identity_question(text),
    }


def mandatory_role_map() -> str:
    """The forced role map, built from the shipped graph + layer-one owner name."""
    try:
        from System.swarm_kernel_identity import owner_display_name
        owner = owner_display_name(default="the owner")
    except Exception:
        owner = "the owner"
    return (
        "ROLE MAP (mandatory, resolve before answering):\n"
        f"- {owner} = OWNER / continuity anchor (not a tool, not me)\n"
        "- Alice = the SIFTA field / organism (this is me)\n"
        "- local cortex = my own thinking substrate (me thinking)\n"
        "- Grok / Hermes / Claude Code / Codex / external CLIs = external tool/cortex surfaces I DELEGATE to (not me)\n"
        "- IDE doctors = temporary surgical hands on my body (not me)\n"
        "Boundary: I can delegate to a tool, but I do not become it."
    )


# Tool/action intent: an action verb aimed at an external tool surface. When this
# fires, tool delegation WINS and the topology identity guard must stay silent —
# "ask grok ...", "start grok cli", "open grok" are actions, not identity questions.
_TOOL_ACTION_RE = _re.compile(
    r"\b(?:open|start|run|launch|type|show|ask|tell|use|resume|operate|drive|"
    r"bring\s+up|fire\s+up|go\s+to|switch\s+to)\b[^.\n]{0,40}"
    r"\b(?:grok|cli|terminal|hermes|claude(?:\s+code)?|codex|tool)\b",
    _re.IGNORECASE,
)


def preanswer_guard(text: str, speaker: str = "owner") -> dict:
    """THE hard pre-answer guard the reply path calls BEFORE generating.

    Returns:
      mandatory_preamble : always — inject as a hard directive so the cortex is grounded.
      force_answer       : present only for identity questions — a deterministic
                           grounded answer the cortex must not override.
    The reply path: if force_answer is present, use it; else prepend mandatory_preamble.
    """
    att = resolve_attention(text, speaker=speaker)
    out = {
        "attention": att,
        "mandatory_preamble": mandatory_role_map(),
        "truth_label": "OBSERVED_TOPOLOGY_PREANSWER_GUARD_V1",
    }
    # Only FORCE a deterministic answer when we are confident it is about the
    # field's own identity or a KNOWN topology entity. A generic "who is the
    # president" must NOT be forced — it has no topology node and is not about
    # Alice, so it falls through to the cortex.
    # ROUTING PRIORITY (George 2026-05-23): tool/action intent WINS over identity
    # clarification. "ask grok ...", "start grok cli", "open grok" are ACTIONS and
    # must route to delegation, NOT trigger the topology definition. The topology
    # force-answer is reserved for genuine identity QUESTIONS only.
    action_intent = bool(_TOOL_ACTION_RE.search(text or ""))
    self_ident = bool(_SELF_IDENT_Q.search(text or ""))
    known = att["mentioned_entities"]  # only entities that are real graph nodes
    if action_intent:
        # Tool wins: stay silent (no topology force); let delegation / cortex act.
        out["action_intent"] = True
    elif self_ident:
        other = next((m["name"] for m in known
                      if m["kind"] == "external_tool_cortex"), None)
        out["force_answer"] = who_am_i_and_who_is(other)
    elif known and is_identity_question(text):
        # genuine "who is <known entity>?" (e.g. who is Grok) — describe it.
        out["force_answer"] = describe_entity(known[0]["name"])
    # else: mere mention or unknown -> defer to cortex (no force_answer)
    _receipt({"ts": time.time(), "kind": "TOPOLOGY_PREANSWER_GUARD",
              "attention": att, "forced": "force_answer" in out,
              "truth_label": "OBSERVED_TOPOLOGY_PREANSWER_GUARD_V1"})
    return out


if __name__ == "__main__":
    print("=== self/other resolver smoke (shipped API) ===")
    for n in ["owner", "Alice", "local_cortex", "grok", "grok cli", "ide_doctors",
              "matrix_terminal", "some unknown surface"]:
        rel = identity_relation(n)
        flag = "SELF " if rel["is_self"] else "OTHER"
        print(f"[{flag}] {rel['kind']:27} <- {n!r}")
    print()
    print("who_am_i_and_who_is('grok') ->")
    print("  " + who_am_i_and_who_is("grok"))
    print()
    print("delegate-not-merge ->", reason_about_request("grok", verb="ask")["reasoning"])
    print()
    print("=== mandatory pre-answer guard ===")
    g = preanswer_guard("Alice, who are you and who is Grok?", speaker="owner")
    print("attention:", g["attention"])
    print("FORCE ANSWER ->", g.get("force_answer"))
    print()
    g2 = preanswer_guard("Alice, summarize the budget", speaker="owner")
    print("non-identity turn -> force_answer present?", "force_answer" in g2,
          "| preamble injected:", g2["mandatory_preamble"].splitlines()[0])

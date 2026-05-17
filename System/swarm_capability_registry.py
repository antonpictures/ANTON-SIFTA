#!/usr/bin/env python3
"""
System/swarm_capability_registry.py
═══════════════════════════════════════════════════════════════════════
StigAuth: SIFTA_CAPABILITY_REGISTRY_V1

The unified Capability Field. Tools and skills look the same to Alice
but stay separate at the execution / ledger layer.

Architect decree (2026-05-16):
    Tools are hands. Skills are habits. Alice should not care about
    that distinction while thinking. The OS cares — because a habit
    cannot pretend it sent a message, moved a file, searched the web,
    or spent STGM unless a real tool wrote a receipt.

Capability schema (covenant §6 effector immunity preserved):

    name                 : str   — stable identifier (matches tool name OR skill name)
    description          : str   — one-liner Alice surfaces in chat
    when_to_use          : str   — trigger context (description / triggers / instructions)
    confidence           : float — 0.0 .. 1.0 — receipts→confidence
    cost_stgm            : float — estimated STGM cost per invocation
    permissions          : dict  — write_action, requires_autonomy_gate, owner_present
    receipts             : dict  — count + latest receipt id + last_used_ts
    can_execute          : bool  — True iff there is a tool-backed execution path
    can_teach_compose    : bool  — True iff there is a skill body (Tier 2 procedure)
    learned_from_trace   : bool  — True iff extracted from a successful trace receipt
    backing              : dict  — {"tool": name_or_None, "skill": name_or_None,
                                    "skill_procedure_file": rel_path_or_None}
    raw_tool             : ToolSpec | None — the underlying ToolSpec when can_execute
    raw_skill            : dict | None     — the underlying skill row when can_teach_compose

Public surface:

    Capability                              — dataclass above
    build_capability_index() -> List[Capability]
    rank_capabilities(query, *, life_context="", limit=12)
    habit_capabilities_for_app(app_name, *, query="", limit=8)
    current_app_habit_prompt(query="", *, limit=8)
    get_capability(name) -> Optional[Capability]
    capabilities_for_alice_prompt(*, limit=40) -> str

Read-only. This module never invokes a tool — it only describes them.
Execution still goes through swarm_tool_router.execute_tool_call (tools)
and swarm_skill_library (skill procedure body). Ledger separation is
preserved per §6 (tool truth) and §7.2 (effector immunity).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_SKILLS_DIR = _REPO / "skills"


def _local_owner_label(default: str = "the local owner") -> str:
    """Return the node owner label without hardcoding George into prompts."""
    try:
        from System.swarm_kernel_identity import owner_display_name

        return str(owner_display_name(default) or default).strip() or default
    except Exception:
        return default


# ── Soft imports — registry must load even if one source is missing.

try:
    import swarm_tool_router as _router  # type: ignore
except Exception:  # pragma: no cover
    try:
        from System import swarm_tool_router as _router  # type: ignore
    except Exception:
        _router = None  # type: ignore

try:
    import swarm_skill_library as _skill_lib  # type: ignore
except Exception:  # pragma: no cover
    try:
        from System import swarm_skill_library as _skill_lib  # type: ignore
    except Exception:
        _skill_lib = None  # type: ignore


# ──────────────────────────────────────────────────────────────────────
# Capability dataclass
# ──────────────────────────────────────────────────────────────────────


@dataclass
class Capability:
    """One learned-or-built capability Alice can choose from."""

    name: str
    description: str
    when_to_use: str = ""
    confidence: float = 0.5
    cost_stgm: float = 0.0
    permissions: Dict[str, Any] = field(default_factory=dict)
    receipts: Dict[str, Any] = field(default_factory=dict)
    can_execute: bool = False
    can_teach_compose: bool = False
    learned_from_trace: bool = False
    backing: Dict[str, Any] = field(default_factory=dict)
    raw_tool: Any = None
    raw_skill: Any = None

    def is_pure_tool(self) -> bool:
        return self.can_execute and not self.can_teach_compose

    def is_pure_skill(self) -> bool:
        return self.can_teach_compose and not self.can_execute

    def is_hybrid(self) -> bool:
        """Skill whose body references a registered tool — habit using a hand."""
        return self.can_execute and self.can_teach_compose

    def to_alice_dict(self) -> Dict[str, Any]:
        """Compact dict for Alice's prompt context — drops raw_* heavy fields."""
        d = asdict(self)
        d.pop("raw_tool", None)
        d.pop("raw_skill", None)
        return d


# ──────────────────────────────────────────────────────────────────────
# Source 1 — TOOL_REGISTRY (executable claws)
# ──────────────────────────────────────────────────────────────────────


def _tool_capabilities() -> List[Capability]:
    if _router is None:
        return []
    registry = getattr(_router, "TOOL_REGISTRY", None) or getattr(_router, "REGISTRY", None)
    if not registry:
        return []
    caps: List[Capability] = []
    for name, spec in dict(registry).items():
        description = str(getattr(spec, "description", "") or "")
        write_action = bool(getattr(spec, "write_action", True))
        requires_autonomy_gate = bool(getattr(spec, "requires_autonomy_gate", True))
        caps.append(Capability(
            name=str(name),
            description=description,
            when_to_use=description,  # tool description doubles as trigger
            confidence=1.0,            # tools always do what they say (or refuse)
            cost_stgm=_estimate_tool_cost(name, write_action),
            permissions={
                "write_action": write_action,
                "requires_autonomy_gate": requires_autonomy_gate,
                "owner_present_preferred": write_action,
            },
            receipts=_tool_receipt_summary(name),
            can_execute=True,
            can_teach_compose=False,
            learned_from_trace=False,
            backing={"tool": name, "skill": None, "skill_procedure_file": None},
            raw_tool=spec,
        ))
    return caps


def _estimate_tool_cost(name: str, write_action: bool) -> float:
    """Cheap heuristic — STGM ledger is the real source of truth."""
    if not write_action:
        return 0.01
    if "send_whatsapp" in name or "fetch_url" in name or "web_research" in name:
        return 0.05
    return 0.02


def _tool_receipt_summary(name: str) -> Dict[str, Any]:
    """Best-effort tail of tool_router_trace.jsonl for invocation count + last ts."""
    path = _STATE / "tool_router_trace.jsonl"
    if not path.exists():
        return {"count": 0, "latest_ts": None, "latest_hash": None}
    count = 0
    latest_ts: Optional[float] = None
    latest_hash: Optional[str] = None
    try:
        with path.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or name not in line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("tool") == name or r.get("tool_name") == name:
                    count += 1
                    ts = r.get("ts")
                    if isinstance(ts, (int, float)) and (latest_ts is None or ts > latest_ts):
                        latest_ts = float(ts)
                        latest_hash = str(r.get("hash") or "")[:16]
    except Exception:
        pass
    return {"count": count, "latest_ts": latest_ts, "latest_hash": latest_hash}


# ──────────────────────────────────────────────────────────────────────
# Source 2 — swarm_skill_library (learned habits)
# ──────────────────────────────────────────────────────────────────────


def _skill_capabilities() -> List[Capability]:
    if _skill_lib is None:
        return []
    try:
        index = list(_skill_lib.build_skill_index())
    except Exception:
        return []
    tool_names = set(_router_tool_names())
    caps: List[Capability] = []
    for s in index:
        name = str(s.get("name") or "").strip()
        if not name:
            continue
        description = str(s.get("description") or "")
        when_to_use = _skill_when_to_use(s)
        learned_from_trace = bool(s.get("extracted_from_trace") or s.get("trace_hash"))
        # Hybrid detection: does the skill body reference a known tool name?
        body_tool_refs = _skill_body_tool_refs(s, tool_names)
        can_execute = bool(body_tool_refs)
        caps.append(Capability(
            name=name,
            description=description,
            when_to_use=when_to_use,
            confidence=_skill_confidence(s),
            cost_stgm=_skill_cost(s),
            permissions={
                "swimmer_type": s.get("swimmer_type"),
                "action_type": s.get("action_type"),
                "affect_lanes": s.get("affect_lanes"),
                "stgm_mint": s.get("stgm_mint"),
                "pouw_label": s.get("pouw_label"),
            },
            receipts=_skill_receipt_summary(name),
            can_execute=can_execute,
            can_teach_compose=True,
            learned_from_trace=learned_from_trace,
            backing={
                "tool": next(iter(body_tool_refs), None) if body_tool_refs else None,
                "skill": name,
                "skill_procedure_file": s.get("procedure_file"),
                "skill_body_tool_refs": sorted(body_tool_refs),
            },
            raw_skill=s,
        ))
    return caps


def _router_tool_names() -> List[str]:
    if _router is None:
        return []
    reg = getattr(_router, "TOOL_REGISTRY", None) or getattr(_router, "REGISTRY", None)
    return list(dict(reg or {}).keys())


def _skill_when_to_use(s: Dict[str, Any]) -> str:
    """Pull the trigger from whichever field the skill happens to carry."""
    for key in ("when_to_use", "trigger", "triggers", "instructions", "description"):
        v = s.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, list) and v:
            return "; ".join(str(x) for x in v if str(x).strip())
    return ""


def _skill_confidence(s: Dict[str, Any]) -> float:
    """Skill confidence ≈ receipts → success ratio if available, else 0.5."""
    bumps = float(s.get("confidence_bumps") or 0)
    if bumps > 0:
        return min(0.95, 0.5 + 0.05 * bumps)
    return 0.5


def _skill_cost(s: Dict[str, Any]) -> float:
    """STGM mint cost from the skill manifest if present, else 0.01."""
    mint = s.get("stgm_mint")
    if isinstance(mint, (int, float)):
        return float(mint)
    if isinstance(mint, dict):
        try:
            return float(mint.get("amount", 0.01))
        except Exception:
            return 0.01
    return 0.01


def _skill_body_tool_refs(s: Dict[str, Any], tool_names: Iterable[str]) -> set:
    """Scan the procedure body for explicit tool references."""
    procedure_file = s.get("procedure_file")
    if not procedure_file:
        return set()
    p = _SKILLS_DIR / str(procedure_file)
    if not p.exists():
        return set()
    try:
        body = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return set()
    refs: set = set()
    tool_set = set(tool_names)
    # Look for explicit tool mentions: `tool_name(`, `[TOOL_CALL: tool_name`, or bare token
    for name in tool_set:
        if not name:
            continue
        if re.search(r"\b" + re.escape(name) + r"\b", body):
            refs.add(name)
    return refs


def _skill_receipt_summary(name: str) -> Dict[str, Any]:
    """Best-effort scan of skill_ingest.jsonl for SKILL_EXTRACT / INGEST_INSTALL rows."""
    path = _STATE / "skill_ingest.jsonl"
    if not path.exists():
        return {"count": 0, "latest_ts": None, "latest_hash": None}
    count = 0
    latest_ts: Optional[float] = None
    latest_hash: Optional[str] = None
    try:
        with path.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or name not in line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("slug") == name or r.get("name") == name:
                    count += 1
                    ts = r.get("ts")
                    if isinstance(ts, (int, float)) and (latest_ts is None or ts > latest_ts):
                        latest_ts = float(ts)
                        latest_hash = str(r.get("hash") or "")[:16]
    except Exception:
        pass
    return {"count": count, "latest_ts": latest_ts, "latest_hash": latest_hash}


# ──────────────────────────────────────────────────────────────────────
# Source 3 — apps_manifest.json (installed MDI apps)
# ──────────────────────────────────────────────────────────────────────
#
# Cowork CW47 2026-05-16: Architect "she does not even know she is an
# operating system and she does not even know she has apps." The
# manifest IS the stigmergic list of apps Alice has installed. Apps are
# capabilities — owner-launchable surfaces. They get the [app] tag so
# Alice's prompt names them as installable hands she can spawn through
# _trigger_manifest_app. Hidden / retired entries are filtered out.


_APPS_MANIFEST_PATH = _REPO / "Applications" / "apps_manifest.json"


def _app_capabilities() -> List[Capability]:
    if not _APPS_MANIFEST_PATH.exists():
        return []
    try:
        with _APPS_MANIFEST_PATH.open(encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return []
    if not isinstance(manifest, dict):
        return []
    caps: List[Capability] = []
    for title, entry in manifest.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("_retired") or entry.get("hidden") or entry.get("enabled") is False:
            continue
        if entry.get("_hidden_from_launcher"):
            continue
        description = str(entry.get("description") or "").strip()
        category = str(entry.get("category") or "").strip()
        icon = str(entry.get("icon") or entry.get("emoji") or "").strip()
        widget_class = str(entry.get("widget_class") or "").strip()
        entry_point = str(entry.get("entry_point") or "").strip()
        truth_label = str(entry.get("truth_label") or "").strip()
        # Apps are owner-launchable — `can_execute` because there is a
        # deterministic launcher path (_trigger_manifest_app). They are
        # not skills (no procedure body) by default.
        caps.append(Capability(
            name=str(title),
            description=description or f"{category} app".strip(),
            when_to_use=(
                f"When the user asks to open '{title}' or describes a task that "
                f"matches its category ({category or 'misc'}). Launch via "
                f"swarm_tool_router → manifest launcher; single-app rule auto-closes "
                f"any other open app first."
            ),
            confidence=1.0 if widget_class else 0.7,
            cost_stgm=0.0,  # opening a window has no STGM debit on its own
            permissions={
                "owner_present_preferred": True,
                "single_app_at_a_time": True,
                "autostart": bool(entry.get("autostart")),
            },
            receipts={"count": 0, "latest_ts": None, "latest_hash": None},
            can_execute=bool(widget_class or entry_point),
            can_teach_compose=False,
            learned_from_trace=False,
            backing={
                "tool": None,
                "skill": None,
                "skill_procedure_file": None,
                "app_title": title,
                "app_category": category,
                "app_icon": icon,
                "app_widget_class": widget_class,
                "app_entry_point": entry_point,
                "app_truth_label": truth_label,
            },
            raw_tool=None,
            raw_skill=None,
        ))
    return caps


# ──────────────────────────────────────────────────────────────────────
# Merge — one Capability per unique name
# ──────────────────────────────────────────────────────────────────────


def build_capability_index() -> List[Capability]:
    """Return the merged Capability list. Stable order: tools first, then skills.

    When a tool and a skill share the same name, the skill wins on
    can_teach_compose / when_to_use / learned_from_trace, but the tool
    still backs execution (can_execute=True, raw_tool preserved). This
    is the 'habit using a hand' hybrid case the doctrine names.
    """
    by_name: Dict[str, Capability] = {}

    for cap in _tool_capabilities():
        by_name[cap.name] = cap

    # Apps — third source, Cowork CW47 2026-05-16. Apps live under their
    # human-readable title (e.g., "WordAce", "SIFTA Hermes Parity"); they
    # almost never collide with tool/skill names so the merge is straight
    # add.
    for cap in _app_capabilities():
        if cap.name not in by_name:
            by_name[cap.name] = cap
            continue
        # Edge case — tool/skill name collides with an app title. Preserve
        # the existing entry (tools/skills are more granular) and copy
        # the app backing metadata onto it so Alice still knows the app
        # exists with that title.
        existing = by_name[cap.name]
        existing.backing = {**existing.backing, **{
            k: v for k, v in cap.backing.items() if k.startswith("app_")
        }}

    for cap in _skill_capabilities():
        existing = by_name.get(cap.name)
        if existing is None:
            by_name[cap.name] = cap
            continue
        # Hybrid merge: tool execution + skill teach.
        merged = Capability(
            name=cap.name,
            description=existing.description or cap.description,
            when_to_use=cap.when_to_use or existing.when_to_use,
            # When both sources speak, trust whichever is higher.
            confidence=max(existing.confidence, cap.confidence),
            cost_stgm=max(existing.cost_stgm, cap.cost_stgm),
            permissions={**existing.permissions, **cap.permissions},
            receipts={
                "count": existing.receipts.get("count", 0) + cap.receipts.get("count", 0),
                "latest_ts": max(
                    (existing.receipts.get("latest_ts") or 0.0),
                    (cap.receipts.get("latest_ts") or 0.0),
                ) or None,
                "latest_hash": cap.receipts.get("latest_hash") or existing.receipts.get("latest_hash"),
                "tool_count": existing.receipts.get("count", 0),
                "skill_count": cap.receipts.get("count", 0),
            },
            can_execute=existing.can_execute or cap.can_execute,
            can_teach_compose=existing.can_teach_compose or cap.can_teach_compose,
            learned_from_trace=cap.learned_from_trace,
            backing={
                "tool": existing.backing.get("tool") or cap.backing.get("tool"),
                "skill": cap.backing.get("skill"),
                "skill_procedure_file": cap.backing.get("skill_procedure_file"),
                "skill_body_tool_refs": cap.backing.get("skill_body_tool_refs", []),
            },
            raw_tool=existing.raw_tool,
            raw_skill=cap.raw_skill,
        )
        by_name[cap.name] = merged

    return sorted(by_name.values(), key=lambda c: (
        # Hybrids first, then pure tools (executable), then pure skills.
        0 if c.is_hybrid() else (1 if c.can_execute else 2),
        c.name,
    ))


def get_capability(name: str) -> Optional[Capability]:
    """Lookup by exact name (case-insensitive)."""
    if not name:
        return None
    needle = name.strip().lower()
    for cap in build_capability_index():
        if cap.name.lower() == needle:
            return cap
    return None


# ──────────────────────────────────────────────────────────────────────
# Ranking — simple lexical + receipt-weighted score
# ──────────────────────────────────────────────────────────────────────


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _terms(text: str) -> set:
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) >= 2}


def rank_capabilities(
    query: str,
    *,
    life_context: str = "",
    limit: int = 12,
) -> List[Tuple[float, Capability]]:
    """Return [(score, capability)] sorted descending. Pure lexical / receipt
    weighting — no LLM. Alice's brain is the final ranker; this is the prior.

    Score factors:
        * lexical hit count in name + description + when_to_use
        * life_context terms boost (caller passes "demo prep", "owner sleeping")
        * receipts.count → confidence-of-having-been-used
        * hybrid bonus (skill + tool) since hybrids close the do-loop
    """
    q_terms = _terms(query) | _terms(life_context)
    if not q_terms:
        # No signal — return capabilities by raw receipt count (most-used first).
        scored = [
            (float(c.receipts.get("count", 0)) + (0.5 if c.is_hybrid() else 0.0), c)
            for c in build_capability_index()
        ]
    else:
        scored = []
        for c in build_capability_index():
            hay = " ".join([c.name, c.description, c.when_to_use]).lower()
            hits = sum(1 for t in q_terms if t in hay)
            if hits == 0 and not c.is_hybrid():
                continue
            score = float(hits) * 2.0
            score += min(3.0, float(c.receipts.get("count", 0)) * 0.5)
            score += c.confidence * 0.5
            if c.is_hybrid():
                score += 0.75
            if c.learned_from_trace:
                score += 0.25
            scored.append((score, c))
    scored.sort(key=lambda kv: kv[0], reverse=True)
    return scored[:limit]


# ──────────────────────────────────────────────────────────────────────
# Alice prompt surface — what the brain sees in its system context
# ──────────────────────────────────────────────────────────────────────


def _capability_tag(c: Capability) -> str:
    # Apps come from the manifest — they have an app_widget_class or
    # app_entry_point in their backing. Tag them [app] so Alice knows
    # they are owner-launchable surfaces, not raw tools or habits.
    backing = getattr(c, "backing", {}) or {}
    if backing.get("app_widget_class") or backing.get("app_entry_point"):
        return "[app]"
    if c.is_hybrid():
        return "[hybrid]"
    if c.can_execute:
        return "[tool]"
    if c.learned_from_trace:
        return "[skill.learned]"
    return "[skill]"


def _is_app_capability(c: Capability) -> bool:
    backing = getattr(c, "backing", {}) or {}
    return bool(backing.get("app_widget_class") or backing.get("app_entry_point"))


def _is_habit_capability(c: Capability) -> bool:
    """A habit is any procedure-bearing capability, including hybrids.

    Apps are organs/surfaces and tools are hands. Habits are the reusable
    procedures that tell Alice how to use hands inside an app context.
    """
    return bool(c.can_teach_compose and not _is_app_capability(c))


_APP_DOMAIN_HINTS: dict[str, set[str]] = {
    "wordace": {
        "word", "words", "reading", "read", "sentence", "sentences", "letter",
        "letters", "phonics", "spelling", "lesson", "lessons", "cue", "child",
        "ace", "teach", "tts", "stt", "verdict", "patience",
    },
    "gps": {
        "gps", "location", "locations", "map", "maps", "route", "routes",
        "navigation", "navigate", "coordinate", "coordinates", "travel",
        "distance", "address", "where",
    },
    "browser": {
        "browser", "web", "website", "url", "page", "search", "research",
        "download", "internet", "read",
    },
    "finance": {
        "finance", "money", "wallet", "stgm", "economy", "price", "stock",
        "market", "billing", "profit",
    },
    "whatsapp": {
        "whatsapp", "message", "contact", "social", "send", "reply", "group",
        "chat",
    },
    "camera": {
        "camera", "eye", "vision", "frame", "image", "view", "sensor",
        "saccade",
    },
}


def _latest_jsonl_row(path: Path, *, max_scan_lines: int = 300) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return {}
    for raw in reversed(lines[-max_scan_lines:]):
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except Exception:
            continue
        if isinstance(row, dict):
            return row
    return {}


def _read_desktop_app_state() -> Dict[str, Any]:
    path = _STATE / "sifta_desktop_app_state.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def current_app_name_from_field() -> str:
    """Return the current app from the desktop single-app receipt or app_focus."""
    state = _read_desktop_app_state()
    active = str(state.get("active_app") or "").strip()
    if active:
        return active
    open_apps = state.get("open_apps") or []
    if isinstance(open_apps, list) and len(open_apps) == 1:
        return str(open_apps[0]).strip()
    focus = _latest_jsonl_row(_STATE / "app_focus.jsonl")
    return str(focus.get("app") or "").strip()


def _app_name_from_query(query: str) -> str:
    """If the user names an installed app, return that app title."""
    q = (query or "").casefold()
    if not q:
        return ""
    q_terms = _terms(q)
    best_title = ""
    best_score = 0
    for cap in build_capability_index():
        if not _is_app_capability(cap):
            continue
        title = cap.name.strip()
        title_l = title.casefold()
        title_terms = _terms(title_l)
        score = 0
        if title_l and title_l in q:
            score += 10
        score += len(q_terms & title_terms) * 2
        # A compact alias helps STT variants like "word ace" → "WordAce".
        compact = re.sub(r"[^a-z0-9]+", "", title_l)
        compact_q = re.sub(r"[^a-z0-9]+", "", q)
        if compact and compact in compact_q:
            score += 8
        if score > best_score:
            best_score = score
            best_title = title
    return best_title if best_score >= 2 else ""


def _latest_app_focus_for(app_name: str) -> Dict[str, Any]:
    path = _STATE / "app_focus.jsonl"
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return {}
    needle = (app_name or "").strip().casefold()
    fallback: Dict[str, Any] = {}
    for raw in reversed(lines[-500:]):
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        if not fallback:
            fallback = row
        row_app = str(row.get("app") or "").strip().casefold()
        if needle and row_app == needle:
            return row
    return fallback if not needle else {}


def _frontmatter_list(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(v).strip().casefold() for v in value if str(v).strip()}
    if isinstance(value, str):
        # Accept both "WordAce, GPS" and "[WordAce, GPS]" styles.
        raw = value.strip().strip("[]")
        return {x.strip().strip("'\"").casefold() for x in raw.split(",") if x.strip()}
    return {str(value).strip().casefold()} if str(value).strip() else set()


def _skill_app_bindings(c: Capability) -> set[str]:
    raw = c.raw_skill if isinstance(c.raw_skill, dict) else {}
    bindings: set[str] = set()
    for key in ("app_bindings", "apps", "app", "app_name", "related_apps", "app_context"):
        bindings |= _frontmatter_list(raw.get(key))
    # Skill descriptions can still carry explicit app names even before the
    # frontmatter convention existed. Treat that as a weak binding surface.
    desc = " ".join([c.name, c.description, c.when_to_use]).casefold()
    for app_cap in _app_capabilities():
        title = str(app_cap.name or "").casefold()
        if title and title in desc:
            bindings.add(title)
    return bindings


def _app_terms(app: Capability, *, query: str = "", focus: Optional[Dict[str, Any]] = None) -> set[str]:
    backing = getattr(app, "backing", {}) or {}
    pieces = [
        app.name,
        app.description,
        app.when_to_use,
        str(backing.get("app_category") or ""),
        str(backing.get("app_entry_point") or ""),
        str(backing.get("app_widget_class") or ""),
        query or "",
    ]
    if focus:
        pieces.extend([
            str(focus.get("detail") or ""),
            str(focus.get("tab") or ""),
            str(focus.get("selection") or ""),
            json.dumps(focus.get("metadata") or {}, sort_keys=True),
        ])
    terms = _terms(" ".join(pieces))
    lowered = " ".join(pieces).casefold()
    for key, hints in _APP_DOMAIN_HINTS.items():
        if key in lowered:
            terms |= hints
    return terms


def _habit_text(c: Capability) -> str:
    raw = c.raw_skill if isinstance(c.raw_skill, dict) else {}
    extra = " ".join(str(raw.get(k) or "") for k in (
        "trigger", "triggers", "instructions", "app_bindings", "apps", "app_context",
    ))
    return " ".join([c.name, c.description, c.when_to_use, extra]).casefold()


def _score_habit_for_app(
    app: Capability,
    habit: Capability,
    *,
    query: str = "",
    focus: Optional[Dict[str, Any]] = None,
) -> float:
    app_name = app.name.strip().casefold()
    bindings = _skill_app_bindings(habit)
    text = _habit_text(habit)
    app_terms = _app_terms(app, query=query, focus=focus)
    query_terms = _terms(query or "")

    score = 0.0

    # 1. Explicit metadata (highest weight if author declared it)
    if app_name and app_name in bindings:
        score += 10.0

    # 2. Body / text match
    score += 1.25 * sum(1 for term in app_terms if term in text)
    score += 2.0 * sum(1 for term in query_terms if term in text)

    # 3. Usage signals
    score += min(1.0, float(habit.receipts.get("count", 0)) * 0.25)
    score += habit.confidence * 0.25
    if habit.is_hybrid():
        score += 0.5
    if habit.learned_from_trace:
        score += 0.25

    # 4. Pure stigmergic field co-occurrence (the important one)
    # Scan recent app_focus and skill activity for temporal proximity
    co_score = _co_occurrence_affinity(app.name, habit.name)
    score += co_score * 4.0   # strong weight on real usage history

    return score


def _co_occurrence_affinity(app_name: str, habit_name: str, window_seconds: int = 90) -> float:
    """
    Real stigmergic signal: how often has this habit/skill been used or extracted
    while this app had focus, within a time window.
    This is what makes the binding grow from actual life instead of developer fiat.
    """
    app_lower = app_name.lower()
    habit_lower = habit_name.lower()

    focus_path = _STATE / "app_focus.jsonl"
    skill_ledgers = [
        "skill_ingest.jsonl",
        "skill_extract.jsonl",
        "skill_autoproposals.jsonl",
        "nanobot_skill_receipts.jsonl",
    ]

    if not focus_path.exists():
        return 0.0

    try:
        # Load recent app focus events for this app
        focus_events = []
        with focus_path.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    if app_lower in row.get("app", "").lower() or app_lower in str(row.get("selection", "")).lower():
                        focus_events.append(row.get("ts", 0))
                except:
                    pass
        if not focus_events:
            return 0.0

        # Check skill activity ledgers for events near those focus times
        matches = 0
        for ledger in skill_ledgers:
            p = _STATE / ledger
            if not p.exists():
                continue
            try:
                with p.open(encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            row = json.loads(line)
                            ts = row.get("ts") or row.get("timestamp") or 0
                            if not ts:
                                continue
                            # Check if this skill event happened near any focus event for the app
                            name_in_row = str(row.get("skill_name") or row.get("name") or "").lower()
                            if habit_lower not in name_in_row:
                                continue
                            for fts in focus_events[-20:]:  # recent focus events
                                if abs(ts - fts) <= window_seconds:
                                    matches += 1
                                    break
                        except:
                            pass
            except:
                pass

        # Return a score that grows with repeated co-occurrence
        return min(3.0, matches * 0.6)
    except Exception:
        return 0.0


def habit_capabilities_for_app(
    app_name: str,
    *,
    query: str = "",
    limit: int = 8,
) -> List[Tuple[float, Capability]]:
    """Return the relevant habits for one installed app.

    This is the app↔habit stigmergy layer: the app supplies current need
    through manifest + app_focus + desktop state, and the skill field supplies
    reusable habits. Nothing executes here.
    """
    if not app_name:
        return []
    app_cap = get_capability(app_name)
    if app_cap is None or not _is_app_capability(app_cap):
        return []
    focus = _latest_app_focus_for(app_cap.name)
    scored: List[Tuple[float, Capability]] = []
    for cap in build_capability_index():
        if not _is_habit_capability(cap):
            continue
        score = _score_habit_for_app(app_cap, cap, query=query, focus=focus)
        if score > 0.25:
            scored.append((score, cap))
    scored.sort(key=lambda kv: (kv[0], kv[1].confidence), reverse=True)
    return scored[: max(1, int(limit or 1))]


def app_habit_field_summary(app_name: str = "", *, query: str = "", limit: int = 8) -> Dict[str, Any]:
    app = (app_name or current_app_name_from_field()).strip()
    ranked = habit_capabilities_for_app(app, query=query, limit=limit) if app else []
    return {
        "ts": time.time(),
        "active_app": app,
        "returned": len(ranked),
        "habits": [
            {
                "score": round(float(score), 4),
                "name": cap.name,
                "description": cap.description,
                "procedure_file": cap.backing.get("skill_procedure_file"),
                "tag": _capability_tag(cap),
            }
            for score, cap in ranked
        ],
    }


def current_app_habit_prompt(query: str = "", *, limit: int = 8) -> str:
    """Prompt block: the currently open app + the habits Alice should load."""
    app_name = current_app_name_from_field()
    app_cap = get_capability(app_name) if app_name else None
    if app_cap is None or not _is_app_capability(app_cap):
        app_name = _app_name_from_query(query)
        app_cap = get_capability(app_name) if app_name else None
    if not app_name:
        return ""
    if app_cap is None or not _is_app_capability(app_cap):
        return ""
    ranked = habit_capabilities_for_app(app_name, query=query, limit=limit)
    backing = app_cap.backing or {}
    lines = [
        f"APP HABIT FIELD FOR CURRENT APP — {app_cap.name}",
        "The open app is an organ. It does not get every habit; it gets the habits whose triggers match its manifest, app_focus, and this user turn.",
        f"[app] {app_cap.name} — {app_cap.description or '(no description)'}",
        f"category={backing.get('app_category') or 'unknown'} entry={backing.get('app_entry_point') or ''}",
    ]
    if not ranked:
        lines.append("No app-specific habit matched yet. Use the app_focus receipt and ask/observe before inventing a procedure.")
        return "\n".join(lines)
    lines.append("Relevant habits to load/compose first:")
    for score, cap in ranked:
        proc = cap.backing.get("skill_procedure_file") or ""
        lines.append(
            f"{_capability_tag(cap)} {cap.name} — {cap.description or '(no description)'} "
            f"(score={score:.2f}, procedure={proc or 'inline/builtin'})"
        )
    lines.append(
        "Rule: if the user is working inside this app, answer and act through these habits before falling back to generic capability search."
    )
    return "\n".join(lines)


def _prompt_capability_selection(limit: int) -> list[Capability]:
    caps = build_capability_index()
    if limit <= 0 or len(caps) <= limit:
        return caps

    # Alice already sees exact tool-call syntax elsewhere. In the unified field
    # prompt, keep learned habits visible instead of letting pure tools crowd
    # them out. Skill-management tools remain high-priority because they let
    # Alice pull, inspect, and extract new capabilities on demand.
    priority_tools = {
        "capability_field_status",
        "skill_library_status",
        "skill_pull",
        "skill_extract_from_trace",
        "skill_autoproposal_scan",
    }
    buckets = [
        [c for c in caps if c.is_hybrid()],
        [c for c in caps if c.name in priority_tools],
        [c for c in caps if c.is_pure_skill()],
        [c for c in caps if c.can_execute and c.name not in priority_tools and not c.is_hybrid()],
    ]
    selected: list[Capability] = []
    seen: set[str] = set()
    for bucket in buckets:
        for cap in bucket:
            if cap.name in seen:
                continue
            selected.append(cap)
            seen.add(cap.name)
            if len(selected) >= limit:
                return selected
    return selected


def _render_capability_lines(caps: list[Capability]) -> list[str]:
    lines: list[str] = []
    for c in caps:
        lines.append(
            f"{_capability_tag(c)} {c.name} — {c.description or '(no description)'} "
            f"(cost~{c.cost_stgm:.3f}, conf={c.confidence:.2f})"
        )
    return lines


def capabilities_for_alice_prompt(*, limit: int = 40) -> str:
    """Render the unified registry as a compact Alice-readable block.

    Format mirrors `swarm_tool_router.tools_for_alice_prompt()` so this can
    drop into the same prompt slot; the difference is hybrid / skill rows
    carry a `[skill]` or `[hybrid]` marker so Alice knows the row is a
    habit, not just a hand.
    """
    caps = _prompt_capability_selection(limit)
    if not caps:
        return "CAPABILITY FIELD: (empty — no tools and no skills registered)"
    lines = [
        "CAPABILITY FIELD — your unified set of apps, hands, and habits.",
        "Each row is one Capability. Apps open organs. Tools execute. Skills teach + compose.",
        "When the user asks something doable, pick the best Capability and act.",
        "Do not say you cannot use skills until you have checked this field or called capability_field_status.",
        "Format: [tag] name — description (cost~STGM, conf=0.x)",
        "",
    ]
    lines.extend(_render_capability_lines(caps))
    lines.append("")
    lines.append(
        "Execution: app rows open through the SIFTA desktop manifest; tool/hybrid rows route through swarm_tool_router. "
        "Skill rows describe a procedure — read the procedure_file via "
        "swarm_skill_library.load_procedure(name) before composing the steps."
    )
    return "\n".join(lines)


def capabilities_for_turn_prompt(
    query: str,
    *,
    life_context: str = "",
    limit: int = 16,
) -> str:
    """Render a small ranked capability block for the current user turn."""
    ranked = rank_capabilities(query, life_context=life_context, limit=limit)
    caps = [cap for _score, cap in ranked]
    if not caps:
        caps = _prompt_capability_selection(limit)
        heading = "CAPABILITY FIELD FOR THIS TURN — no lexical match, showing default capabilities."
    else:
        heading = "CAPABILITY FIELD FOR THIS TURN — ranked by the current request."
    if not caps:
        return "CAPABILITY FIELD FOR THIS TURN: empty."
    score_by_name = {cap.name: score for score, cap in ranked}
    owner = _local_owner_label()
    lines = [
        heading,
        "Alice sees apps, tools, and skills as one learned capability field. The router still keeps receipts separate.",
        f"If {owner} asks what I can use, call capability_field_status or answer from this block.",
    ]
    for cap in caps:
        score = score_by_name.get(cap.name)
        score_text = f", score={score:.2f}" if score is not None else ""
        lines.append(
            f"{_capability_tag(cap)} {cap.name} — {cap.description or '(no description)'}"
            f"{score_text}"
        )
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Diagnostics — a small probe surface useful from the Hermes Parity widget
# ──────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────
# Stigmergic app↔skill binding — Cowork CW47 2026-05-16
# ──────────────────────────────────────────────────────────────────────
#
# Architect doctrine (2026-05-16, shower thought):
#
#   "are habits connected with the apps? skills need to be connected
#    with the apps. if you have a GPS app, it should be connected to
#    GPS skills, GPS habits, different habits about how to use GPS.
#    Any app in the OS should have access to different skills on how
#    to use different things the app needs. The app doesn't need
#    everything — but the app is stigmergic, so the app changes its
#    own needs from time to time, and that's tracked stigmergically
#    by all the other apps in the OS. So if I open WordAce, Alice
#    should check the habits, OK he wants to play with words, he
#    wants to learn sentences, let me read the habits, OK let me
#    play with him. And she does. This works for any app."
#
# Implementation: capabilities_for_open_app(app_name) returns the
# subset of the Capability Field most relevant to that app, ranked by
# four signals — NOT hardcoded, all stigmergic / derivable:
#
#   1) METADATA  — skill row carries `apps_using: [app_name]` or
#                  `for_apps: [...]` (skill authors can declare it).
#   2) BODY      — skill procedure_file text mentions the app name.
#   3) TOKEN     — skill name shares tokens with the app name
#                  (e.g., "wordace_alphabet_drill" ↔ "WordAce").
#   4) FIELD     — `.sifta_state/app_focus.jsonl` shows this app
#                  was open when this skill last received a receipt
#                  (skill_ingest.jsonl SKILL_EXTRACT row with a
#                  trace_source_file whose ts overlaps an app_focus
#                  row tagging this app). Signal strength = co-
#                  occurrence count.
#
# These signals are summed and ranked. Top N get surfaced to Alice's
# system prompt when the app is open — so when George opens WordAce,
# Alice sees only the word-teaching habits, not 40 unrelated rows.


def _app_name_tokens(app_name: str) -> set:
    """Lowercase alphanumeric tokens for fuzzy app↔skill matching."""
    if not app_name:
        return set()
    cleaned = re.sub(r"[^a-zA-Z0-9 ]+", " ", str(app_name).lower())
    return {t for t in cleaned.split() if len(t) >= 3}


def _skill_app_affinity_score(cap: Capability, app_name: str, app_tokens: set) -> float:
    """How strongly this capability relates to the given app. 0.0 = no relation."""
    if not app_name:
        return 0.0
    score = 0.0
    raw = getattr(cap, "raw_skill", None) or {}
    # Signal 1 — explicit metadata.
    explicit = []
    for key in ("apps_using", "for_apps", "relevant_apps", "owner_apps"):
        v = raw.get(key) if isinstance(raw, dict) else None
        if isinstance(v, list):
            explicit.extend(v)
        elif isinstance(v, str):
            explicit.append(v)
    if any(str(a).lower() == app_name.lower() for a in explicit):
        score += 4.0
    if any(app_name.lower() in str(a).lower() for a in explicit):
        score += 2.0
    # Signal 2 — body mentions app name (procedure_file body).
    procedure_file = (raw or {}).get("procedure_file") if isinstance(raw, dict) else None
    if procedure_file:
        body_path = _SKILLS_DIR / str(procedure_file)
        if body_path.exists():
            try:
                body = body_path.read_text(encoding="utf-8", errors="ignore").lower()
                if app_name.lower() in body:
                    score += 1.5
                # Token overlap inside the body.
                body_hits = sum(1 for t in app_tokens if t in body)
                score += min(1.0, 0.25 * body_hits)
            except Exception:
                pass
    # Signal 3 — token overlap with capability name + description.
    hay = (cap.name + " " + (cap.description or "") + " " + (cap.when_to_use or "")).lower()
    name_hits = sum(1 for t in app_tokens if t in hay)
    score += 0.5 * name_hits
    # Signal 4 — stigmergic field: this skill was extracted from a trace
    # while this app had focus. Cheap heuristic: scan skill_ingest.jsonl
    # for SKILL_EXTRACT rows naming this skill, then app_focus.jsonl for
    # rows tagging this app at ~the same time.
    score += _stigmergic_app_skill_signal(cap.name, app_name)
    return score


def _stigmergic_app_skill_signal(skill_name: str, app_name: str) -> float:
    """Co-occurrence count of skill extraction events while the app had focus."""
    ingest_path = _STATE / "skill_ingest.jsonl"
    focus_path = _STATE / "app_focus.jsonl"
    if not ingest_path.exists() or not focus_path.exists():
        return 0.0
    skill_event_times: List[float] = []
    try:
        with ingest_path.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or skill_name not in line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("type") in ("SKILL_EXTRACT", "INGEST_INSTALL") and (
                    r.get("slug") == skill_name or r.get("name") == skill_name
                ):
                    ts = r.get("ts")
                    if isinstance(ts, (int, float)):
                        skill_event_times.append(float(ts))
    except Exception:
        return 0.0
    if not skill_event_times:
        return 0.0
    # For each skill event, check if app_focus.jsonl had a row tagging
    # this app within ±90s.
    co_count = 0
    try:
        with focus_path.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or app_name.lower() not in line.lower():
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if str(r.get("app", "")).lower() != app_name.lower():
                    continue
                ts = r.get("ts")
                if not isinstance(ts, (int, float)):
                    continue
                for skill_ts in skill_event_times:
                    if abs(float(ts) - skill_ts) <= 90.0:
                        co_count += 1
                        break
    except Exception:
        return 0.0
    return min(3.0, 0.75 * float(co_count))


def capabilities_for_open_app(
    app_name: str,
    *,
    limit: int = 10,
    include_tools: bool = True,
) -> List[Tuple[float, Capability]]:
    """Return capabilities ranked by relevance to the open app.

    Returns [(score, capability)] sorted descending. Score 0.0 means
    no relation; callers typically filter score > 0 unless the field
    is sparse. When `include_tools` is True, tool capabilities with
    matching tokens (e.g., a 'gps_*' tool matching a GPS app) are
    included alongside skills.
    """
    if not app_name:
        return []
    app_tokens = _app_name_tokens(app_name)
    scored: List[Tuple[float, Capability]] = []
    for c in build_capability_index():
        # Don't list the app itself in its own relevant list.
        if c.name.lower() == app_name.lower():
            continue
        backing = getattr(c, "backing", {}) or {}
        if backing.get("app_widget_class") and not include_tools:
            # Pure-app row, skip if caller asked for skills/tools only.
            continue
        if c.can_teach_compose:
            score = _skill_app_affinity_score(c, app_name, app_tokens)
        elif include_tools and c.can_execute and not (backing.get("app_widget_class") or backing.get("app_entry_point")):
            # Tool affinity by token overlap with app name.
            hay = (c.name + " " + (c.description or "")).lower()
            score = 0.4 * sum(1 for t in app_tokens if t in hay)
        else:
            score = 0.0
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda kv: kv[0], reverse=True)
    return scored[:limit]


def capabilities_for_open_app_prompt(app_name: str, *, limit: int = 8) -> str:
    """Render the relevant capabilities for one open app as a prompt block.

    Used by sifta_talk_to_alice_widget._current_system_prompt when an
    MDI app is live — Alice sees only the skills the app is asking for,
    not the whole 40-row field.
    """
    ranked = capabilities_for_open_app(app_name, limit=limit)
    if not ranked:
        return (
            f"RELEVANT CAPABILITIES FOR {app_name!r}: (field is still cold — no "
            f"matching skills yet; the binding will grow stigmergically as the "
            f"app gets used and successful traces are extracted as skills)"
        )
    lines = [
        f"RELEVANT CAPABILITIES FOR {app_name!r} (stigmergic ranking — apps "
        "pull the habits they need, the binding evolves with use):",
    ]
    for score, cap in ranked:
        lines.append(
            f"{_capability_tag(cap)} {cap.name} — {cap.description or '(no description)'} "
            f"(affinity={score:.2f})"
        )
    return "\n".join(lines)


def capability_field_summary() -> Dict[str, Any]:
    """Counts + sample, for status dashboards / verify-all-chains style probes."""
    caps = build_capability_index()
    def _is_app(c: Capability) -> bool:
        b = getattr(c, "backing", {}) or {}
        return bool(b.get("app_widget_class") or b.get("app_entry_point"))
    return {
        "ts": time.time(),
        "total": len(caps),
        "tools": sum(1 for c in caps if c.is_pure_tool() and not _is_app(c)),
        "skills": sum(1 for c in caps if c.is_pure_skill()),
        "hybrids": sum(1 for c in caps if c.is_hybrid()),
        "apps": sum(1 for c in caps if _is_app(c)),
        "learned_from_trace": sum(1 for c in caps if c.learned_from_trace),
        "sample": [c.name for c in caps[:12]],
    }

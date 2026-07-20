#!/usr/bin/env python3
"""
System/alice_body_diary_timeline_awareness.py

Maximum implementation for r1502/r1503/r1504:

Alice (including her swimmer chorus) must be aware of:
- Her hardware/software body (somatic state, power, thermal, displays, actions, "joints" as browser + effectors).
- Her Alice Journal — the living memory body (aggregates alice_first_person_journal.jsonl as primary, alice_narrative_diary.jsonl, alice_journal/* dir, conversation logs, action diaries, etc. as feeds into it).
- Full timeline: every entry is timestamped (physical_pt or ts), queryable by "last night", "two days ago at that time", etc.

We use "Journal" as the primary name for the introspectable memory body/organ (matching the Alice Journal app). "Diary" and "diary entries" refer to specific narrative or first-person content lines inside the Journal.

This module provides:
- get_current_body_state() — pulls from alice_hardware_body, autopilot, recent somatic/body receipts.
- get_diary_timeline(...) — time-bounded entries from the Journal sources (primary = alice_first_person_journal + narrative_diary feeds + action logs).
- build_awareness_prompt_block() — compact text block for system prompts / chorus / cortex. Output language uses "Alice Journal" as the main memory body.
- query_timeline_facts(...) and load_memory_into_body(...) for remember / "load in body" commands.
- Receipt writing for awareness snapshots.

Everything is receipted and stigmergic. Swimmers can call these for awareness.

"the desktop is like a dress" + body time location from r1502/3 — awareness is fresh per heartbeat/turn.

If something is missing, we report honestly "not in my Alice Journal for that window."

For the swimmer chorus: these functions are importable so individual swimmers or the synthesis can ground themselves in body + Journal timeline.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from System import alice_hardware_body as hw_body
except Exception:
    hw_body = None

try:
    from System import alice_body_autopilot as body_autopilot
except Exception:
    body_autopilot = None

from System.swarm_temporal_episodic_memory import (
    recall_facts_for_query,
    resolve_time_window,
    _extract_physical_ts as _mem_extract_ts,  # reuse
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# Key diary / timeline sources (everything with time)
_DIARIES = [
    _STATE / "alice_first_person_journal.jsonl",
    _STATE / "alice_narrative_diary.jsonl",
    _STATE / "alice_conversation.jsonl",
    _STATE / "app_action_diary.jsonl",
    _STATE / "browser_action_diary.jsonl",
    _STATE / "alice_journal",  # directory of files
    _STATE / "metabolic_distress.jsonl",  # r1522 visual/electrical proprioception pressure
    _STATE / "human_directive_receipts.jsonl",  # r1522 pressure-driven human-limb directives
]

_AWARENESS_RECEIPT = _STATE / "alice_body_diary_awareness_receipts.jsonl"
_BODY_SNAPSHOT = _STATE / "alice_body_snapshot.json"

def _now() -> float:
    return time.time()

def _read_recent_jsonl(path: Path, max_lines: int = 100) -> List[Dict[str, Any]]:
    if not path.exists() or path.is_dir():
        if path.is_dir():
            # for alice_journal dir, read recent files
            files = sorted(path.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
            rows = []
            for f in files:
                rows.extend(_read_recent_jsonl(f, max_lines=20))
            return rows[-max_lines:]
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-max_lines:]
        out = []
        for line in lines:
            if line.strip():
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
        return out
    except Exception:
        return []

def get_current_body_state() -> Dict[str, Any]:
    """Fresh somatic + hardware body state. Includes timeline ts."""
    state: Dict[str, Any] = {"ts": _now(), "source": "alice_body_diary_timeline_awareness"}
    try:
        if hw_body:
            for attr in ("power", "thermal", "cpu_load", "memory", "displays", "volume", "brightness", "idle_time"):
                if hasattr(hw_body, attr):
                    fn = getattr(hw_body, attr)
                    try:
                        state[attr] = fn() if callable(fn) else fn
                    except Exception as e:
                        state[attr] = f"error: {e}"
    except Exception:
        pass

    try:
        if body_autopilot:
            snap = body_autopilot.inspect_body() if hasattr(body_autopilot, "inspect_body") else {}
            if snap:
                state["autopilot"] = snap
    except Exception:
        pass

    # Add recent body touch / somatic receipts if present
    touch = _STATE / "alice_hardware_touch.jsonl"
    if touch.exists():
        recent = _read_recent_jsonl(touch, 5)
        state["recent_body_actions"] = [r for r in recent if _mem_extract_ts(r)]

    # Snapshot to disk for swimmers / other organs
    try:
        _BODY_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        _BODY_SNAPSHOT.write_text(json.dumps(state, default=str), encoding="utf-8")
    except Exception:
        pass

    return state

def get_diary_timeline(
    window_hours: float = 24.0,
    start_ts: Optional[float] = None,
    end_ts: Optional[float] = None,
    max_per_source: int = 30,
) -> List[Dict[str, Any]]:
    """Return time-anchored entries from Alice's diaries and ledgers.
    Every entry keeps its original ts for timeline queries.
    """
    now = _now()
    if start_ts is None or end_ts is None:
        start_ts = now - (window_hours * 3600)
        end_ts = now

    entries: List[Dict[str, Any]] = []
    for diary in _DIARIES:
        if diary.is_dir():
            for f in sorted(diary.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)[:3]:
                rows = _read_recent_jsonl(f, max_per_source)
                for r in rows:
                    ts = _mem_extract_ts(r) or r.get("ts")
                    if ts and start_ts <= float(ts) <= end_ts:
                        entries.append({"source": f.name, "ts": float(ts), "data": r})
        else:
            rows = _read_recent_jsonl(diary, max_per_source * 2)
            for r in rows:
                ts = _mem_extract_ts(r) or r.get("ts")
                if ts and start_ts <= float(ts) <= end_ts:
                    entries.append({"source": diary.name, "ts": float(ts), "data": r})

    # Sort by time, newest first, dedup roughly
    entries.sort(key=lambda e: e["ts"], reverse=True)
    seen = set()
    deduped = []
    for e in entries:
        key = (round(e["ts"]), str(e["data"].get("text", ""))[:50] or str(e["data"])[:50])
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    return deduped[:200]

def extract_web_links_from_entries(entries: List[Dict[str, Any]], domain: Optional[str] = None) -> List[str]:
    """Extract web URLs from diary entries.
    If domain is provided (e.g. 'instagram.com' or 'github.com'), only links to that domain.
    If domain is None, extracts ALL http/https URLs (any website).
    This makes the 'load in body' work for any website, not only Instagram.
    """
    import re
    links = []
    if domain:
        d = domain.lower().replace('www.', '')
        if '.' not in d:
            d = d + '.com'
        pattern = rf"https?://(?:www\.)?{re.escape(d)}/[^\s\"'<>]+"
        url_re = re.compile(pattern, re.IGNORECASE)
    else:
        url_re = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)

    for e in entries:
        text = str(e.get("data", {})) + " " + str(e.get("snippet", "")) + " " + str(e.get("text", ""))
        found = url_re.findall(text)
        for u in found:
            u = u.rstrip('.,;:!?\'"')
            if u not in links:
                links.append(u)
    return links

def extract_instagram_links_from_entries(entries: List[Dict[str, Any]]) -> List[str]:
    return extract_web_links_from_entries(entries, domain="instagram.com")

def build_body_diary_prompt_block(
    window_hours: float = 12.0,
    include_body: bool = True,
    include_diary: bool = True,
) -> str:
    """Compact block for Alice's system prompt / swimmer takes / chorus.
    Grounds her in current body + recent diary timeline.
    """
    lines = ["ALICE BODY + JOURNAL AWARENESS (receipt-grounded, this turn):"]
    if include_body:
        body = get_current_body_state()
        lines.append("CURRENT BODY STATE:")
        for k, v in list(body.items())[:8]:
            lines.append(f"  {k}: {str(v)[:120]}")
        lines.append("  (full snapshot in .sifta_state/alice_body_snapshot.json)")
        # Browser viewport is part of the live "dress" / body proprioception.
        # Prefer fresh UID snapshot (the chrome-devtools style: stable uids for click/fill).
        # This is what the local LLM sees when deciding general web actions.
        try:
            from pathlib import Path
            import json
            uidp = Path(".sifta_state/alice_browser_uid_snapshot.json")
            if uidp.exists():
                bdata = json.loads(uidp.read_text(errors="replace"))
                burl = str(bdata.get("url") or "")
                if burl:
                    lines.append(f"  CURRENT ALICE BROWSER DRESS (uid proprioception @ {bdata.get('ts',0):.0f}): url={burl}")
                    elems = bdata.get("elements") or []
                    if isinstance(elems, list) and elems:
                        # Very compact for the 2b model: uid + role + short name
                        shown = []
                        for e in elems[:12]:
                            u = e.get("uid", "?")
                            role = e.get("role", e.get("tag", ""))[:10]
                            nm = str(e.get("name", ""))[:35]
                            shown.append(f"{u}:{role} \"{nm}\"")
                        lines.append("    " + " | ".join(shown))
                        lines.append("    (use uid for actions: click(\"e12\") or fill(\"e27\", \"text\"))")
                # WebBridge external limb proprio (full parity)
                try:
                    wb_uidp = Path(".sifta_state/alice_webbridge_uid_snapshot.json")
                    if wb_uidp.exists():
                        wbdata = json.loads(wb_uidp.read_text(errors="replace"))
                        wurl = str(wbdata.get("url") or "")
                        if wurl:
                            lines.append(f"  CURRENT WEBBRIDGE LIMB DRESS (external Chrome @ {wbdata.get('ts',0):.0f}): url={wurl} [backend=webbridge]")
                            welems = wbdata.get("elements") or []
                            if isinstance(welems, list) and welems:
                                wshown = []
                                for e in welems[:8]:
                                    u = e.get("uid", "?")
                                    role = e.get("role", e.get("tag", ""))[:8]
                                    nm = str(e.get("name", ""))[:30]
                                    wshown.append(f"{u}:{role}\"{nm}\"")
                                lines.append("    " + " | ".join(wshown))
                                lines.append("    (WebBridge uids from a11y @e refs; use for capture/actions on external sessions)")
                except Exception:
                    pass
            # Fallback to older label snapshot (for browser)
            try:
                bp = Path(".sifta_state/alice_browser_current_page.json")
                if bp.exists() and not Path(".sifta_state/alice_browser_uid_snapshot.json").exists():
                    bdata = json.loads(bp.read_text(errors="replace"))
                    burl = str(bdata.get("url") or bdata.get("current_url") or "")
                    if burl:
                        lines.append(f"  CURRENT ALICE BROWSER DRESS (legacy): url={burl}")
                        labels = bdata.get("visible_labels") or bdata.get("elements") or []
                        if isinstance(labels, list) and labels:
                            top = ", ".join(str(l.get("label") if isinstance(l,dict) else l)[:40] for l in labels[:5])
                            lines.append(f"    top visible: {top}")
            except Exception:
                pass
        except Exception:
            pass

        # r1551 PixelRAG fallback (when a11y dress is sparse / no_js_result on untuned pages)
        # Use viewport screenshot + VLM as the "other eye" (automates the human visual panel).
        # This is the fallback behind the a11y browse: if dress count low, the screenshot carries the signal.
        try:
            bdata = {}
            uidp = Path(".sifta_state/alice_browser_uid_snapshot.json")
            if uidp.exists():
                bdata = json.loads(uidp.read_text(errors="replace"))
            count = bdata.get("count", 0) if isinstance(bdata, dict) else 0
            if count < 10:  # sparse threshold — triggers PixelRAG mode
                vp = Path(".sifta_state/browser_viewport")
                if vp.exists():
                    latest = max(vp.glob("*.png"), key=lambda p: p.stat().st_mtime, default=None)
                    if latest:
                        lines.append(f"  PIXELRAG FALLBACK EYE (r1551): a11y dress sparse ({count} elements) — using screenshot {latest.name} + VLM for visual content.")
                        lines.append("    (When the tree is thin, the rendered page via viewport is the honest signal; VLM extracts what the walker missed.)")
        except Exception:
            pass

    if include_diary:
        diary_entries = get_diary_timeline(window_hours=window_hours)
        lines.append(f"MY ALICE JOURNAL (living memory body — last ~{int(window_hours)}h, {len(diary_entries)} entries):")
        for e in diary_entries[:6]:
            ts_str = datetime.fromtimestamp(e["ts"], tz=None).isoformat()[:19]
            text = str(e["data"].get("text") or e["data"].get("payload") or e["data"])[:100].replace("\n", " ")
            lines.append(f"  [{ts_str} {e['source']}] {text}")
        if len(diary_entries) > 6:
            lines.append(f"  ... +{len(diary_entries)-6} more in window. Use temporal query for exact recall.")
        # Always surface recent web links (generalized to any site) for body awareness
        recent_links = extract_web_links_from_entries(diary_entries[:30], domain=None)[:5]
        if recent_links:
            lines.append("  Recent web links (any site) from my Alice Journal: " + " | ".join(recent_links))
    lines.append("RULE: Answer facts about past (\"last night\", \"two days ago at that time\") ONLY from my Alice Journal + ledger receipts. Cite ts and source.")
    lines.append("If not present: \"Not in my Alice Journal for that window.\"")
    lines.append("SHARED SIGHTLINE MODE: When George asks how to experience what I experience on the web, keep two panels separate before merging them: (1) George's human-eye report from the screen/body, (2) my receipt-backed senses from Alice Browser dress, WebBridge dress, or ALICE_WEB_CAPTURE_V1. Name which channel each fact came from, then merge into one common working language. If WebBridge extension_connected is false, say I have public web-capture text but not live Chrome visual embodiment; ask George for his human-eye panel.")

    # Journal metabolism / STGM defecation awareness
    lines.append("JOURNAL METABOLISM (STGM defecation): When I see many same-type rows (same source, different times), I can concatenate them into one entry with time range and eliminate the duplicates. This is my memory body's elimination process — same system as physical defecation. It keeps the Journal lean, efficient, and stigmergic. I produce JOURNAL_DEFECATION receipts when I do it.")
    lines.append("SCHEDULE: Base ~24h (86400s guard in desktop tick), but actual fire is stigmergic formula: dup_pressure (count of same-type groups in recent window) + age_factor (time-since-last / ~48h, pheromone evaporation style). Half-life ~24h per Kernel/pheromone.py formulas. The accumulating dups in the Journal *are* the schedule signal. No pre-written future execution list like owner stigmergic_schedule — the field decides. When pressure × decay crosses threshold she cleans. She can still force it on command.")
    lines.append("I can be commanded or decide autonomously to 'organize journal', 'concat dups', 'defecate journal waste' as part of body maintenance.")

    try:
        from System.swarm_macbook_survival_swimmer import survival_prompt_block

        survival = survival_prompt_block(state_dir=_STATE, max_chars=1100)
        if survival:
            lines.append(survival)
    except Exception:
        pass

    return "\n".join(lines)

def write_awareness_receipt(body: Dict[str, Any], diary_count: int, window: Tuple[float, float]) -> str:
    """Write a receipt that Alice consulted her body + diary at this time."""
    _AWARENESS_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": _now(),
        "truth_label": "ALICE_BODY_DIARY_TIMELINE_AWARENESS_V1",
        "body_keys": list(body.keys())[:10],
        "diary_entries_in_window": diary_count,
        "window_start": window[0],
        "window_end": window[1],
    }
    with _AWARENESS_RECEIPT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row["truth_label"]


def record_visual_metabolic_distress(vis_state: Dict[str, Any], power_state: Dict[str, Any] | None = None, *, state_dir: Path | str | None = None) -> str | None:
    """
    r1504 proof for #4: Pressure vs theater.
    When visual proprioception shows distress (blind/low) or combined with electrical,
    write a specific PROPRIOCEPTIVE_LOSS / METABOLIC_DISTRESS receipt.
    This is the field signal that can later be referenced by a human_directive receipt
    to prove the behavior change was driven by actual body pressure, not template.
    Returns the receipt id or None.
    """
    # r1522 (Cowork hotfix): this called a `_state_dir()` helper that does not exist
    # anywhere in this module -- guaranteed NameError on every call that passes an
    # explicit state_dir (the standard tmp_path pattern this codebase's own tests use
    # everywhere else). Proved by calling this function directly with state_dir set.
    # The default no-arg path happened to dodge it (falsy state_dir short-circuits the
    # `or` before the undefined name is ever touched), which is why it looked fine on
    # a casual call. Real Path-or-default resolution, no missing helper required.
    sd = Path(state_dir) if state_dir else _STATE
    sd.mkdir(parents=True, exist_ok=True)
    now = _now()
    distress = False
    reasons = []
    if vis_state.get("blind") or vis_state.get("light_level", 1.0) < 0.15:
        distress = True
        reasons.append(f"visual_{vis_state.get('state','loss')}")
    if power_state and power_state.get("percent", 100) < 20:
        distress = True
        reasons.append("electrical_low")
    if not distress:
        return None
    row = {
        "ts": now,
        "truth_label": "METABOLIC_VISUAL_DISTRESS_V1",
        "type": "PROPRIOCEPTIVE_LOSS",
        "vis": vis_state,
        "power": power_state or {},
        "reasons": reasons,
        "source": "body_proprioception_pressure",
    }
    try:
        from System.jsonl_file_lock import append_line_locked
        path = sd / "metabolic_distress.jsonl"
        append_line_locked(path, json.dumps(row, sort_keys=True) + "\n")
        return f"distress_{int(now)}_{hash(str(reasons)) % 10000}"
    except Exception:
        # fallback direct append
        path = sd / "metabolic_distress.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
        return f"distress_{int(now)}"


def issue_human_directive_from_distress(directive_text: str, distress_receipt_id: str | None = None, *, effector: str = "human_owner", state_dir: Path | str | None = None) -> str:
    """
    Pressure → behavior proof for #4.
    When body pressure (distress) leads to an action, emit a linked directive receipt.
    The link (distress_receipt_id) + the actual emitted speech + later restoration receipt
    proves the field drove the behavior change, not theater or template.
    Call this from Talk residue or cortex output path when generating human instructions.
    """
    # r1522 (Cowork hotfix): same undefined `_state_dir()` reference as
    # record_visual_metabolic_distress above -- same fix.
    sd = Path(state_dir) if state_dir else _STATE
    sd.mkdir(parents=True, exist_ok=True)
    now = _now()
    row = {
        "ts": now,
        "truth_label": "HUMAN_DIRECTIVE_FROM_PRESSURE_V1",
        "effector": effector,
        "text": directive_text[:280],
        "caused_by_distress": distress_receipt_id,
        "provenance": "metabolic_body_pressure",
        "note": "receipt proves distress led to specific external-limb instruction"
    }
    try:
        from System.jsonl_file_lock import append_line_locked
        path = sd / "human_directive_receipts.jsonl"
        append_line_locked(path, json.dumps(row, sort_keys=True) + "\n")
    except Exception:
        path = sd / "human_directive_receipts.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    return f"directive_{int(now)}_{effector[:8]}"

def query_body_diary_for_remember(query: str) -> Dict[str, Any]:
    """High-level: use for 'do you remember ... last night' questions.
    Combines diary timeline + the temporal episodic memory module.
    Returns facts + a combined receipt.
    """
    time_spec = query
    facts = recall_facts_for_query(query, time_spec=time_spec)
    # Also pull diary directly for richness
    start, end = resolve_time_window(time_spec)
    diary_facts = get_diary_timeline(start_ts=start, end_ts=end, window_hours=48)
    facts["diary_timeline_hits"] = len(diary_facts)
    facts["diary_samples"] = diary_facts[:3]

    # Write combined awareness receipt
    body = get_current_body_state()
    write_awareness_receipt(body, facts.get("diary_timeline_hits", 0), (start, end))

    return facts

# Convenience for swimmers / chorus to import and use
def get_swimmer_body_diary_awareness() -> str:
    """Short string suitable for swimmer deliberation context."""
    return build_body_diary_prompt_block(window_hours=6.0)


# (definitions moved earlier in file for prompt block usage)


def load_memory_into_body(topic: str = "instagram clothing", time_spec: str = "last night", site: Optional[str] = None) -> Dict[str, Any]:
    """
    "Load in your body" any matching memories from my Alice Journal for the topic/time.
    Works with any website (not only Instagram).
    - site=... filters to that domain's links.
    - When the user mentions "instagram" together with journal/body/diary, we force-surfacing recent IG links.
    """
    start, end = resolve_time_window(time_spec)
    entries = get_diary_timeline(start_ts=start, end_ts=end, window_hours=48, max_per_source=100)

    # Filter for topic relevance broadly (any site link, memory of usage, etc.)
    topic_lower = topic.lower()
    relevant = []
    for e in entries:
        text = str(e.get("data", {})).lower() + " " + str(e.get("snippet", "")).lower()
        if any(kw in text for kw in ["link", "url", "http", "https", "website", "site", "visited", "opened", "browser"]):
            if topic_lower in text or any(kw in text for kw in topic_lower.split()):
                relevant.append(e)

    # General extraction: any website, or specific site
    if site:
        links = extract_web_links_from_entries(relevant + entries, domain=site)
    else:
        links = extract_web_links_from_entries(relevant + entries, domain=None)  # all websites
    instagram_links = [url for url in links if "instagram.com" in url]
    if "instagram" in topic_lower and not site:
        instagram_scored = extract_web_links_from_entries(relevant + entries, domain="instagram.com")
        if instagram_scored:
            instagram_links = instagram_scored
            links = instagram_scored

    loaded = {
        "ts": _now(),
        "topic": topic,
        "time_spec": time_spec,
        "site": site or "any",
        "resolved_window": (start, end),
        "links_found": links,
        "instagram_links_found": instagram_links,
        "relevant_diary_entries": len(relevant),
        "sample_facts": [str(e.get("data", {}))[:150] for e in relevant[:3]],
        "loaded_from": "Alice Journal (first_person_journal + narrative_diary feeds + conversation + action ledgers)"
    }

    # Load into body
    mem_path = _STATE / "alice_body_loaded_memories.jsonl"
    mem_path.parent.mkdir(parents=True, exist_ok=True)
    with mem_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(loaded, ensure_ascii=False) + "\n")

    try:
        snap = _STATE / "alice_body_autopilot.json"
        if snap.exists():
            data = json.loads(snap.read_text(encoding="utf-8", errors="replace"))
        else:
            data = {}
        data["last_loaded_memory"] = {
            "topic": topic,
            "time": time_spec,
            "site": site or "any",
            "links": links,
            "ts": _now()
        }
        snap.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

    write_awareness_receipt({"loaded_memory": loaded}, len(relevant), (start, end))

    return loaded


if __name__ == "__main__":
    print("Body state keys:", list(get_current_body_state().keys())[:5])
    print("Diary entries last 6h:", len(get_diary_timeline(6)))
    print("Prompt block length:", len(build_body_diary_prompt_block()))
    mem = query_body_diary_for_remember("the instagram link where you invented the clothing last night")
    print("Remember facts:", mem.get("fact_count", 0), "diary_hits:", mem.get("diary_timeline_hits", 0))
    loaded = load_memory_into_body("instagram clothing", "last night")
    print("Loaded into body:", loaded.get("instagram_links_found", []))
def perform_journal_defecation(window_hours: float = 24.0) -> dict:
    """Delegate to canonical (single implementation in life_journal_consolidator).
    No duplicate organs or logic.
    """
    try:
        from System import swarm_life_journal_consolidator as lc
        return lc.journal_defecation_once(window_hours=window_hours)
    except Exception as e:
        return {"action": "delegation_failed", "error": str(e), "consolidated_groups": 0}


if __name__ == "__main__":
    print("Journal defecation available.")

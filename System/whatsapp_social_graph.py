#!/usr/bin/env python3
"""WhatsApp social graph for Alice.

This module turns raw Baileys WhatsApp contacts into a local, owner-centered
social graph. It does not scrape or publish anything by itself; it annotates
the contacts the local bridge already sees so Alice understands that these
people and groups are part of the owner's WhatsApp world.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
CONTACTS_FILE = _STATE / "whatsapp_contacts.json"

# Local owner identity and known early federation aliases. These are not
# secrets; they prevent Alice from confusing the machine owner with external
# WhatsApp friends when chat display names are noisy.
OWNER_SELF_JIDS = {"51235386302504@lid"}
OWNER_NAME_ALIASES = {"george", "ioan", "ioan george anton", "george anton", "architect"}
LOCAL_CONTROL_JIDS = {"local_reasoning_test@s.whatsapp.net"}
KNOWN_JID_DISPLAY_NAMES = {
    "120363408204674197@g.us": "SIFTA Group",
    "147235790663690@lid": "Jeff Powers Ocean VIllas",
}


def contact_hash(jid: str) -> str:
    return hashlib.sha256(jid.encode("utf-8")).hexdigest()[:16]


def chat_type_for_jid(jid: str) -> str:
    if jid.endswith("@g.us"):
        return "group"
    return "direct"


def display_name_for(row: Dict[str, Any]) -> str:
    for key in ("display_name", "name", "notify", "verified_name"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _canonical_display_name(jid: str, name: str) -> str:
    jid = str(jid or "").strip()
    name = str(name or "").strip()
    return KNOWN_JID_DISPLAY_NAMES.get(jid) or name


def _is_owner_self(jid: str, name: str) -> bool:
    jid = str(jid or "").strip()
    if jid in OWNER_SELF_JIDS:
        return True
    return _normalized(name) in OWNER_NAME_ALIASES


def _is_local_control(jid: str) -> bool:
    return str(jid or "").strip() in LOCAL_CONTROL_JIDS


def load_contacts(path: Optional[Path] = None) -> Dict[str, Any]:
    path = CONTACTS_FILE if path is None else path
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_contacts(data: Dict[str, Any], path: Optional[Path] = None) -> None:
    path = CONTACTS_FILE if path is None else path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def enrich_contact_record(
    existing: Optional[Dict[str, Any]],
    *,
    jid: str,
    name: str = "",
    source: str = "whatsapp_contacts_sync",
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Return a normalized owner-social-graph contact row."""
    jid = str(jid or "").strip()
    if not jid:
        raise ValueError("jid is required")
    key = contact_hash(jid)
    t = time.time() if now is None else float(now)
    chat_type = chat_type_for_jid(jid)
    row: Dict[str, Any] = dict(existing or {})
    clean_name = _canonical_display_name(jid, name or display_name_for(row))
    is_owner = _is_owner_self(jid, clean_name)
    is_control = _is_local_control(jid)
    if is_owner:
        relationship = "owner_self"
        note = (
            "This is Ioan George Anton / George, the machine owner. Do not treat this "
            "entry as an external WhatsApp friend target unless an exact JID is given."
        )
        alice_context = (
            "This is the owner/self control identity. If the owner asks Alice to message "
            "Jeff, Carlton, or another friend, do not resolve that request to George."
        )
        send_target_allowed = False
    elif is_control:
        relationship = "local_control_channel"
        note = "Local test/control channel used by the Architect to inject instructions."
        alice_context = "Internal control channel, not a human WhatsApp friend target."
        send_target_allowed = False
    else:
        relationship = "whatsapp_group" if chat_type == "group" else "whatsapp_contact"
        note = (
            "Known through the owner's WhatsApp account. Treat as part of the owner's "
            "real social graph, not as an anonymous stranger."
        )
        alice_context = (
            "Alice may reason about this contact/group as a friend or social channel of "
            "the machine owner when the owner asks her to use WhatsApp."
        )
        send_target_allowed = True
    row.update(
        {
            "jid_hash": key,
            "jid": jid,
            "display_name": clean_name,
            "chat_type": chat_type,
            "source": source,
            "synced_ts": row.get("synced_ts") or t,
            "last_seen_ts": t if source == "whatsapp" else row.get("last_seen_ts", 0.0),
            "owner_social_graph": True,
            "relationship_to_owner": relationship,
            "relationship_note": note,
            "alice_context": alice_context,
            "send_target_allowed": send_target_allowed,
        }
    )
    return row


def migrate_existing_contacts(path: Optional[Path] = None) -> int:
    path = CONTACTS_FILE if path is None else path
    contacts = load_contacts(path)
    changed = 0
    for key, row in list(contacts.items()):
        if not isinstance(row, dict):
            continue
        jid = str(row.get("jid") or "").strip()
        if not jid:
            continue
        enriched = enrich_contact_record(
            row,
            jid=jid,
            name=display_name_for(row),
            source=str(row.get("source") or "whatsapp_contacts_sync"),
            now=float(row.get("last_seen_ts") or row.get("synced_ts") or time.time()),
        )
        if enriched != row:
            contacts[key] = enriched
            changed += 1
    if changed:
        save_contacts(contacts, path)
    return changed


def _normalized(value: str) -> str:
    """Casefold, strip punctuation, collapse whitespace."""
    import re
    # Remove commas, periods, dashes, quotes — speech-to-text artefacts
    clean = re.sub(r"[,.\-'\"!?;:()]+", " ", value)
    return " ".join(clean.casefold().split())


def _word_overlap(a: str, b: str) -> float:
    """Fraction of words in `a` that also appear in `b` (Jaccard-ish)."""
    wa = set(a.split())
    wb = set(b.split())
    if not wa:
        return 0.0
    return len(wa & wb) / len(wa)


def resolve_target(target: str, contacts: Optional[Dict[str, Any]] = None) -> str:
    """Resolve a display name, exact JID, or tagged name to a WhatsApp JID.

    Resolution strategy (in priority order):
      1. Exact JID passthrough  ("120363…@g.us")
      2. Exact normalized name match
      3. Substring match
      4. Fuzzy word-overlap ≥ 60% (handles speech-to-text garble)
    """
    target = (target or "").strip()
    if not target:
        return ""
    if "@s.whatsapp.net" in target or "@g.us" in target or "@lid" in target:
        return target

    data = contacts if contacts is not None else load_contacts()
    target_norm = _normalized(target)
    wants_group = " group" in f" {target_norm} " or target_norm.startswith("group:")
    wants_direct = " direct" in f" {target_norm} " or target_norm.startswith("direct:")
    stripped = (
        target_norm
        .replace("group:", "")
        .replace("direct:", "")
        .replace(" group", "")
        .replace(" direct", "")
        .strip()
    )

    candidates: List[Dict[str, Any]] = []
    fuzzy_candidates: List[Dict[str, Any]] = []
    for row in data.values():
        if not isinstance(row, dict):
            continue
        name = display_name_for(row)
        jid = str(row.get("jid") or "")
        if not name or not jid:
            continue
        if row.get("send_target_allowed") is False:
            continue
        chat_type = str(row.get("chat_type") or chat_type_for_jid(jid))
        if wants_group and chat_type != "group":
            continue
        if wants_direct and chat_type != "direct":
            continue
        name_norm = _normalized(name)
        entry = {"jid": jid, "name": name, "chat_type": chat_type, "exact": stripped == name_norm}
        # Exact or substring match
        if stripped == name_norm or stripped in name_norm or name_norm in stripped:
            candidates.append(entry)
        else:
            # Fuzzy word-overlap fallback (handles "Jeff Powers, Ocean Villas"
            # matching "Jeff Powers Ocean VIllas")
            overlap = _word_overlap(stripped, name_norm)
            if overlap >= 0.6:
                fuzzy_candidates.append((overlap, entry))

    exact = [c for c in candidates if c["exact"]]
    pool = exact or candidates
    if len(pool) == 1:
        return str(pool[0]["jid"])
    if len(pool) > 1:
        return str(pool[0]["jid"])

    # Fall through to fuzzy matches
    if fuzzy_candidates:
        fuzzy_candidates.sort(key=lambda x: x[0], reverse=True)
        return str(fuzzy_candidates[0][1]["jid"])
    return ""


def contact_rows_for_alice(limit: int = 12, contacts: Optional[Dict[str, Any]] = None) -> List[str]:
    data = contacts if contacts is not None else load_contacts()
    rows = []
    for row in data.values():
        if not isinstance(row, dict):
            continue
        name = display_name_for(row)
        jid = str(row.get("jid") or "")
        if not name or not jid:
            continue
        chat_type = str(row.get("chat_type") or chat_type_for_jid(jid))
        last_seen = float(row.get("last_seen_ts") or row.get("synced_ts") or 0.0)
        relationship = str(row.get("relationship_to_owner") or "owner social graph")
        rows.append((last_seen, name[:48], chat_type, relationship))
    rows.sort(reverse=True)
    return [f"{name} ({chat_type}, {relationship})" for _ts, name, chat_type, relationship in rows[:limit]]


def summary_for_alice(limit: int = 12) -> str:
    contacts = load_contacts()
    rows = contact_rows_for_alice(limit, contacts)
    lines = [
        "WHATSAPP SOCIAL GRAPH:",
        "- Every synced WhatsApp contact/group is treated as part of the machine owner's real social graph.",
        "- These are friends, collaborators, groups, or channels reachable through the owner's WhatsApp account.",
        "- Use exact names when unambiguous; add 'group' or 'direct' if a name exists in both forms.",
    ]
    if rows:
        lines.append(f"- known_owner_contacts={len(contacts)} visible_to_alice: " + "; ".join(rows))
    else:
        lines.append("- known_owner_contacts=0; contacts appear after WhatsApp sync or after a human messages Alice.")
    return "\n".join(lines)


__all__ = [
    "CONTACTS_FILE",
    "chat_type_for_jid",
    "contact_hash",
    "contact_rows_for_alice",
    "display_name_for",
    "enrich_contact_record",
    "load_contacts",
    "migrate_existing_contacts",
    "resolve_target",
    "save_contacts",
    "summary_for_alice",
]

#!/usr/bin/env python3
"""WhatsApp social graph for Alice.

This module turns raw Baileys WhatsApp contacts into a local, owner-centered
social graph. It does not scrape or publish anything by itself; it annotates
the contacts the local bridge already sees so Alice understands that these
people and groups are part of my WhatsApp world.
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

# Local owner identity and known contacts. The owner's REAL WhatsApp JIDs and
# contact display names are private node selfhood (§3 node sovereignty) and
# live ONLY in the gitignored local config below
# (.sifta_state/owner_whatsapp_identity.json) — never in the public source.
# The defaults here are non-identifying examples used by tests and fresh
# nodes; a real node loads its true identity from local config and merges it
# in. The example JIDs stay present so logic/tests work on any node.
def _load_local_identity() -> Dict[str, Any]:
    try:
        data = json.loads(
            (_STATE / "owner_whatsapp_identity.json").read_text(encoding="utf-8")
        )
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


_LOCAL_IDENTITY = _load_local_identity()

OWNER_SELF_JIDS = {"100000000000001@lid"} | set(
    _LOCAL_IDENTITY.get("owner_self_jids") or []
)
OWNER_NAME_ALIASES = {
    "george", "ioan", "ioan george anton", "george anton", "architect",
} | {str(a).lower() for a in (_LOCAL_IDENTITY.get("owner_name_aliases") or [])}
LOCAL_CONTROL_JIDS = {"local_reasoning_test@s.whatsapp.net"}
STATUS_BROADCAST_JIDS = {"status@broadcast"}
KNOWN_JID_DISPLAY_NAMES = {
    "100000000000010@g.us": "SIFTA Group",
    "100000000000002@lid": "Example Contact",
}
KNOWN_JID_DISPLAY_NAMES.update(_LOCAL_IDENTITY.get("known_jid_display_names") or {})


def contact_hash(jid: str) -> str:
    return hashlib.sha256(jid.encode("utf-8")).hexdigest()[:16]


def chat_type_for_jid(jid: str) -> str:
    if jid.endswith("@g.us"):
        return "group"
    return "direct"


def is_status_broadcast_jid(jid: str) -> bool:
    return str(jid or "").strip() in STATUS_BROADCAST_JIDS


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


def _jid_kind(jid: str) -> str:
    jid = str(jid or "").strip()
    if jid.endswith("@s.whatsapp.net"):
        return "phone"
    if jid.endswith("@lid"):
        return "lid"
    if jid.endswith("@g.us"):
        return "group"
    if is_status_broadcast_jid(jid):
        return "status"
    return "other"


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
    if is_status_broadcast_jid(jid):
        relationship = "whatsapp_status_broadcast"
        note = (
            "WhatsApp status broadcast transport. This is not a stable person or "
            "send target; status rows may carry a human notify name separately."
        )
        alice_context = (
            "Observe status broadcasts as social context only. Do not resolve owner "
            "send requests to status@broadcast."
        )
        send_target_allowed = False
    elif is_owner:
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
            "Known through my WhatsApp account. Treat as part of the owner's "
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


def _contact_last_seen(row: Dict[str, Any]) -> float:
    try:
        return float(row.get("last_seen_ts") or row.get("synced_ts") or 0.0)
    except Exception:
        return 0.0


def _preferred_contact_row(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Choose the stable send target from a phone/LID alias cluster."""

    def rank(row: Dict[str, Any]) -> tuple:
        jid = str(row.get("jid") or "")
        kind = _jid_kind(jid)
        return (
            row.get("send_target_allowed") is not False,
            jid in KNOWN_JID_DISPLAY_NAMES,
            bool(row.get("name_locked")),
            kind == "phone",
            kind == "lid",
            _contact_last_seen(row),
        )

    return sorted(rows, key=rank, reverse=True)[0]


def _can_merge_direct_aliases(rows: List[Dict[str, Any]]) -> bool:
    """Two or more direct contacts with the same display_name are aliases.

    Original rule: phone+LID required. But Baileys surfaces some contacts
    as LID-only with multiple LIDs (e.g. George 2 LIDs, no phone).
    Safe merge: same display_name + all direct + at least 2 entries.
    """
    if len(rows) < 2:
        return False
    kinds = {_jid_kind(str(row.get("jid") or "")) for row in rows}
    # Classic phone+LID pair
    if "phone" in kinds and "lid" in kinds:
        return True
    # Multiple LIDs, same name — still the same person
    if kinds == {"lid"}:
        return True
    return False


def _direct_alias_rows_for_name(
    contacts: Dict[str, Any],
    name_norm: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in contacts.values():
        if not isinstance(row, dict):
            continue
        jid = str(row.get("jid") or "").strip()
        if not jid or is_status_broadcast_jid(jid):
            continue
        if row.get("send_target_allowed") is False:
            continue
        chat_type = str(row.get("chat_type") or chat_type_for_jid(jid))
        if chat_type != "direct":
            continue
        if _normalized(display_name_for(row)) == name_norm:
            rows.append(row)
    return rows


def alias_jids_for_jid(
    jid: str,
    contacts: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Return known WhatsApp IDs for the same human contact.

    Baileys may surface one person as both a phone JID
    (``@s.whatsapp.net``) and a linked-device/private LID (``@lid``).
    We merge only that phone/LID pair for the same display name; same-name
    phone-only contacts remain separate to avoid unsafe identity collapse.
    """
    jid = str(jid or "").strip()
    if not jid:
        return []
    data = contacts if contacts is not None else load_contacts()
    target = next(
        (
            row
            for row in data.values()
            if isinstance(row, dict) and str(row.get("jid") or "").strip() == jid
        ),
        None,
    )
    if not target:
        return [jid]
    if is_status_broadcast_jid(jid) or str(target.get("chat_type") or chat_type_for_jid(jid)) != "direct":
        return [jid]
    name_norm = _normalized(display_name_for(target))
    if not name_norm:
        return [jid]
    rows = _direct_alias_rows_for_name(data, name_norm)
    if not _can_merge_direct_aliases(rows):
        return [jid]
    aliases = sorted({str(row.get("jid") or "").strip() for row in rows if row.get("jid")})
    return aliases or [jid]


def canonical_contact_entries(contacts: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Return UI-ready contacts with recurring WhatsApp aliases merged.

    This hides transport duplicates such as ``Carlton`` phone JID + LID while
    keeping the alias list so conversation filtering and Auto consent still see
    every real identifier.
    """
    data = contacts if contacts is not None else load_contacts()
    entries: List[Dict[str, Any]] = []
    direct_by_name: Dict[str, List[Dict[str, Any]]] = {}
    emitted: set[str] = set()

    for row in data.values():
        if not isinstance(row, dict):
            continue
        jid = str(row.get("jid") or "").strip()
        name = display_name_for(row).strip()
        if not jid or not name or is_status_broadcast_jid(jid):
            continue
        chat_type = str(row.get("chat_type") or chat_type_for_jid(jid))
        if (
            chat_type == "direct"
            and _jid_kind(jid) in {"phone", "lid"}
        ):
            direct_by_name.setdefault(_normalized(name), []).append(row)
        else:
            aliases = [jid]
            is_group = chat_type == "group"
            entries.append(
                {
                    "label": f"📢 {name}" if is_group else name,
                    "display_name": name,
                    "jid": jid,
                    "jid_aliases": aliases,
                    "chat_type": chat_type,
                    "send_target_allowed": row.get("send_target_allowed") is not False,
                    "relationship_to_owner": str(row.get("relationship_to_owner") or ""),
                    "merged_count": 1,
                }
            )
            emitted.add(jid)

    for rows in direct_by_name.values():
        if not rows:
            continue
        groups: List[List[Dict[str, Any]]]
        if len(rows) > 1 and _can_merge_direct_aliases(rows):
            groups = [rows]
        else:
            groups = [[row] for row in rows]
        for group in groups:
            primary = _preferred_contact_row(group)
            jid = str(primary.get("jid") or "").strip()
            if jid in emitted:
                continue
            aliases = sorted({str(row.get("jid") or "").strip() for row in group if row.get("jid")})
            emitted.update(aliases)
            name = display_name_for(primary).strip()
            entries.append(
                {
                    "label": name,
                    "display_name": name,
                    "jid": jid,
                    "jid_aliases": aliases,
                    "chat_type": "direct",
                    "send_target_allowed": primary.get("send_target_allowed") is not False,
                    "relationship_to_owner": str(primary.get("relationship_to_owner") or ""),
                    "merged_count": len(aliases),
                }
            )

    entries.sort(key=lambda e: (str(e["display_name"]).casefold(), str(e["chat_type"])))
    return entries


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
    for row in canonical_contact_entries(data):
        if not isinstance(row, dict):
            continue
        name = display_name_for(row)
        jid = str(row.get("jid") or "")
        if not name or not jid:
            continue
        if is_status_broadcast_jid(jid):
            continue
        if row.get("send_target_allowed") is False:
            continue
        chat_type = str(row.get("chat_type") or chat_type_for_jid(jid))
        if wants_group and chat_type != "group":
            continue
        if wants_direct and chat_type != "direct":
            continue
        name_norm = _normalized(name)
        entry = {
            "jid": jid,
            "name": name,
            "chat_type": chat_type,
            "exact": stripped == name_norm,
            "name_locked": bool(row.get("name_locked")),
            "known_jid": jid in KNOWN_JID_DISPLAY_NAMES,
            "last_seen": float(row.get("last_seen_ts") or row.get("synced_ts") or 0.0),
        }
        # Exact or substring match
        if stripped == name_norm or stripped in name_norm or name_norm in stripped:
            candidates.append(entry)
        else:
            # Fuzzy word-overlap fallback (handles "Example Contact, Example Place"
            # matching "Example Contact")
            overlap = _word_overlap(stripped, name_norm)
            if overlap >= 0.6:
                fuzzy_candidates.append((overlap, entry))

    exact = [c for c in candidates if c["exact"]]
    pool = exact or candidates
    if len(pool) == 1:
        return str(pool[0]["jid"])
    if len(pool) > 1:
        preferred = [c for c in pool if c["name_locked"] or c["known_jid"]]
        if len(preferred) == 1:
            return str(preferred[0]["jid"])
        if preferred:
            preferred.sort(key=lambda c: c["last_seen"], reverse=True)
            if preferred[0]["last_seen"] > preferred[1]["last_seen"]:
                return str(preferred[0]["jid"])
        return ""

    # Fall through to fuzzy matches
    if fuzzy_candidates:
        fuzzy_candidates.sort(key=lambda x: x[0], reverse=True)
        return str(fuzzy_candidates[0][1]["jid"])
    return ""


def contact_rows_for_alice(limit: int = 12, contacts: Optional[Dict[str, Any]] = None) -> List[str]:
    data = contacts if contacts is not None else load_contacts()
    rows = []
    for row in canonical_contact_entries(data):
        if not isinstance(row, dict):
            continue
        name = display_name_for(row)
        jid = str(row.get("jid") or "")
        if not name or not jid:
            continue
        if row.get("send_target_allowed") is False:
            continue
        chat_type = str(row.get("chat_type") or chat_type_for_jid(jid))
        last_seen = float(row.get("last_seen_ts") or row.get("synced_ts") or 0.0)
        relationship = str(row.get("relationship_to_owner") or "owner social graph")
        rows.append((last_seen, name[:48], chat_type, relationship))
    rows.sort(reverse=True)
    visible = []
    seen = set()
    for _ts, name, chat_type, relationship in rows:
        key = (_normalized(name), chat_type)
        if key in seen:
            continue
        seen.add(key)
        visible.append(f"{name} ({chat_type}, {relationship})")
        if len(visible) >= limit:
            break
    return visible


def summary_for_alice(limit: int = 12) -> str:
    contacts = load_contacts()
    rows = contact_rows_for_alice(limit, contacts)
    lines = [
        "WHATSAPP SOCIAL GRAPH:",
        "- Every synced WhatsApp contact/group is treated as part of the machine owner's real social graph.",
        "- These are friends, collaborators, groups, or channels reachable through my WhatsApp account.",
        "- Use exact names when unambiguous; add 'group' or 'direct' if a name exists in both forms.",
    ]
    if rows:
        lines.append(f"- known_owner_contacts={len(contacts)} visible_to_alice: " + "; ".join(rows))
    else:
        lines.append("- known_owner_contacts=0; contacts appear after WhatsApp sync or after a human messages Alice.")
    return "\n".join(lines)


__all__ = [
    "CONTACTS_FILE",
    "STATUS_BROADCAST_JIDS",
    "alias_jids_for_jid",
    "canonical_contact_entries",
    "chat_type_for_jid",
    "contact_hash",
    "contact_rows_for_alice",
    "display_name_for",
    "enrich_contact_record",
    "is_status_broadcast_jid",
    "load_contacts",
    "migrate_existing_contacts",
    "resolve_target",
    "save_contacts",
    "summary_for_alice",
]

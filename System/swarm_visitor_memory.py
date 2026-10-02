"""swarm_visitor_memory — Alice remembers everyone who visits her site.

Owner request (2026-10-01): "a file on every person she identifies by unique IP
address or wherever they come from; every visitor is unique right?"

Two corrections that shape this implementation:

  1. AN IP IS NOT A PERSON. Home routers, offices, mobile carriers and CGNAT all
     share addresses, so an IP-keyed file merges strangers and splits real people.
     The PRIMARY identity here is a first-party cookie (one per browser). The IP
     is kept only as a salted HASH, as supporting context.

  2. AN IP IS PERSONAL DATA. Visitors may be in the EU, so a raw address list is
     a regulated asset. Hashing with a local salt keeps "is this the same visitor"
     answerable while not holding a directory of people's home connections. The
     site also states plainly that visits are recorded.

One file per visitor: VISITORS_LEDGER holds every visit event, VISITORS_INDEX
holds the current view, and VISITOR_FILES_DIR holds one readable file per visitor
so a human can open a person's folder and read their history.

Retention: a visitor can be forgotten on request (forget()), and records older
than RETENTION_DAYS are pruned by forget_old().
"""

from __future__ import annotations

import contextlib
import fcntl
import functools
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Optional

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"

VISITORS_LEDGER = "visitors.jsonl"
VISITORS_INDEX = "visitors_index.json"
VISITOR_FILES_DIR = "visitor_files"
VISITOR_SALT_NAME = "visitor_ip_salt"
TRUTH_LABEL = "SIFTA_VISITOR_MEMORY_V1"

RETENTION_DAYS = 180
COOKIE_NAME = "sifta_vid"

# Set True only with an explicit owner decision and a matching privacy notice:
# storing raw addresses turns this into a regulated personal-data store.
STORE_RAW_IP = False


# ─────────────────────────────────────────────────────────────────────────────
# Writing the index safely
#
# There is ONE visitors_index.json, and every page load, every saved chat and
# every identity claim rewrites the whole file. The server is threaded and other
# organs (and a second process) write it too, so two writers that loaded the same
# copy used to overwrite each other and the later write won: whole visitors and
# whole conversations vanished with no error anywhere. That is the bug behind
# "my chats were never saved".
#
# Two defences: an RLock for threads plus an flock for processes, taken once by
# the outermost frame; and an atomic replace, so a reader can never see a
# half-written file.
# ─────────────────────────────────────────────────────────────────────────────

_WRITE_LOCK = threading.RLock()
_DEPTH = threading.local()
_INDEX_LOCK_NAME = "visitors_index.lock"


@contextlib.contextmanager
def _index_guard(sd: Path):
    sd.mkdir(parents=True, exist_ok=True)
    depth = getattr(_DEPTH, "depth", 0)
    with _WRITE_LOCK:
        _DEPTH.depth = depth + 1
        handle = None
        try:
            if depth == 0:
                handle = open(sd / _INDEX_LOCK_NAME, "a+")
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            _DEPTH.depth = depth
            if handle is not None:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                finally:
                    handle.close()


def _save_index(index: dict[str, Any], sd: Path) -> None:
    """Replace the index atomically: write a temp file, then rename it over."""
    p = sd / VISITORS_INDEX
    tmp = sd / (VISITORS_INDEX + ".tmp")
    tmp.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


def _serialized(fn):
    """Run a whole read-modify-write of the index under the guard."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _index_guard(_state_dir(kwargs.get("state_dir"))):
            return fn(*args, **kwargs)
    return wrapper


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _salt(sd: Path) -> str:
    p = sd / VISITOR_SALT_NAME
    if not p.exists():
        sd.mkdir(parents=True, exist_ok=True)
        fd = os.open(p, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(secrets.token_hex(32))
    return p.read_text(encoding="utf-8").strip()


def ip_hash(ip: str, *, state_dir: Path | str | None = None) -> str:
    """Salted hash of an address: stable for counting, not a directory."""
    sd = _state_dir(state_dir)
    return hashlib.sha256(f"{_salt(sd)}|{ip or ''}".encode("utf-8")).hexdigest()[:24]


def new_visitor_id() -> str:
    return "v_" + secrets.token_hex(10)


def _blank_visitor(visitor_id: str) -> dict[str, Any]:
    """A row for an identity we know but have not recorded yet.

    This exists because of a real, observed failure: signing in with Google
    creates an account identity BEFORE the account has any row in
    visitors_index. Every save keyed to that identity then hit a missing row and
    was dropped in silence — the visitor saw "No saved chats yet" forever.
    """
    now = time.time()
    return {
        "visitor_id": visitor_id,
        "first_seen": now,
        "last_seen": now,
        "visits": 0,
        "ip_hashes_seen": [],
        "user_agents": [],
        "referrers": [],
        "languages": [],
        "paths": [],
        "note": "",
        "identified_as": "",
        "account_id": visitor_id if visitor_id.startswith("acct_") else "",
        "conversations": {},
        "exchanges": [],
    }


@_serialized
def record_visit(
    *,
    visitor_id: str,
    ip: str = "",
    user_agent: str = "",
    referrer: str = "",
    path: str = "/",
    accept_language: str = "",
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Append one visit and refresh the visitor's own file."""
    sd = _state_dir(state_dir)
    now = time.time()
    row = {
        "ts": now,
        "kind": "VISIT",
        "visitor_id": visitor_id,
        "ip_hash": ip_hash(ip, state_dir=sd) if ip else "",
        "user_agent": (user_agent or "")[:300],
        "referrer": (referrer or "")[:300],
        "accept_language": (accept_language or "")[:60],
        "path": path,
        "truth_label": TRUTH_LABEL,
    }
    if STORE_RAW_IP and ip:
        row["ip"] = ip

    sd.mkdir(parents=True, exist_ok=True)
    with (sd / VISITORS_LEDGER).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    index = load_index(state_dir=sd)
    prev = index.get(visitor_id, {})
    # START from what we already knew, then refresh the visit facts.
    #
    # This used to build a brand-new dict from a fixed list of keys, which meant
    # every page load silently threw away the visitor's saved chats: the sidebar
    # was refilled, then wiped by the next visit, and a signed-in person watched
    # their history disappear. Copying prev first makes the visit additive, which
    # is what "Alice remembers" has to mean.
    person = dict(prev)
    person.update({
        "visitor_id": visitor_id,
        "first_seen": prev.get("first_seen", now),
        "last_seen": now,
        "visits": int(prev.get("visits", 0)) + 1,
        "ip_hash": row["ip_hash"],
        "ip_hashes_seen": sorted(set(prev.get("ip_hashes_seen", [])) | {row["ip_hash"]}),
        "user_agents": sorted(set(prev.get("user_agents", [])) | ({row["user_agent"]} if row["user_agent"] else set())),
        "referrers": sorted(set(prev.get("referrers", [])) | ({row["referrer"]} if row["referrer"] else set())),
        "languages": sorted(set(prev.get("languages", [])) | ({row["accept_language"]} if row["accept_language"] else set())),
        "paths": sorted(set(prev.get("paths", [])) | {path}),
        "note": prev.get("note", ""),
        "identified_as": prev.get("identified_as", ""),
    })
    person.setdefault("conversations", {})
    person.setdefault("exchanges", [])
    person.setdefault("topics_discussed", [])
    if visitor_id.startswith("acct_"):
        person.setdefault("account_id", visitor_id)
    index[visitor_id] = person
    _save_index(index, sd)
    _write_visitor_file(person, sd)
    return person


def _write_visitor_file(person: dict[str, Any], sd: Path) -> None:
    """One readable file per visitor, so a human can open their history."""
    d = sd / VISITOR_FILES_DIR
    d.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# visitor {person['visitor_id']}",
        "",
        f"first seen : {time.strftime('%Y-%m-%d %H:%M', time.localtime(person['first_seen']))}",
        f"last seen  : {time.strftime('%Y-%m-%d %H:%M', time.localtime(person['last_seen']))}",
        f"visits     : {person['visits']}",
        f"ip hashes  : {', '.join(person['ip_hashes_seen'])}",
        f"languages  : {', '.join(person['languages']) or '-'}",
        f"referrers  : {', '.join(person['referrers']) or '-'}",
        f"paths      : {', '.join(person['paths'])}",
        f"identity   : {person.get('identified_as') or 'unidentified'}",
        f"note       : {person.get('note') or '-'}",
        "",
        f"topics     : {', '.join(person.get('topics_discussed', [])) or '-'}",
        f"exchanges  : {len(person.get('exchanges', []))}",
        "",
        "browsers seen:",
    ] + [f"  - {ua}" for ua in person["user_agents"]] + [
        "",
        f"truth_label: {TRUTH_LABEL}",
        "IP addresses are stored only as a salted hash. This visitor can be forgotten on request.",
        "",
    ]
    (d / f"{person['visitor_id']}.md").write_text("\n".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Categorisation and identity claims
# ─────────────────────────────────────────────────────────────────────────────

@_serialized
def categorize(visitor_id: str, *, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Derive a human-readable category from what this visitor actually did."""
    sd = _state_dir(state_dir)
    v = load_index(state_dir=sd).get(visitor_id)
    if not v:
        return {}
    visits = int(v.get("visits", 0))
    uas = v.get("user_agents", [])
    refs = v.get("referrers", [])
    if v.get("identified_as"):
        cat = "known_person"
    elif visits >= 5:
        cat = "regular"
    elif visits > 1:
        cat = "returning"
    else:
        cat = "first_time"
    device = "unknown"
    ua = (uas[0] if uas else "").lower()
    if "iphone" in ua or "android" in ua:
        device = "mobile"
    elif "macintosh" in ua or "windows" in ua or "linux" in ua:
        device = "desktop"
    if "bot" in ua or "crawler" in ua or "spider" in ua:
        cat = "automated"
    traits = []
    if len(v.get("ip_hashes_seen", [])) > 1:
        traits.append("changed_network")
    if len(uas) > 2:
        traits.append("multiple_browsers")
    if refs:
        traits.append("arrived_from_referrer")
    out = {"visitor_id": visitor_id, "category": cat, "device": device,
           "visits": visits, "traits": traits}
    v["category"] = cat
    v["device"] = device
    v["traits"] = traits
    index = load_index(state_dir=sd)
    index[visitor_id] = v
    _save_index(index, sd)
    _write_visitor_file(v, sd)
    return out


@_serialized
def claim_identity(
    visitor_id: str,
    claimed_name: str,
    *,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """A visitor says who they are. We record the CLAIM and judge its consistency.

    The judgement is deliberately conservative. A claim is never trusted because
    it was made; it is compared against the signals of any visitor already
    identified as that same person. If a different visitor claims the same name
    while presenting a different network and a different browser, that is a
    conflict, and the honest answer is "possible impersonation", not "welcome
    back".
    """
    sd = _state_dir(state_dir)
    index = load_index(state_dir=sd)
    me = index.get(visitor_id)
    if me is None:
        return {"status": "UNKNOWN_VISITOR"}

    my_ips = set(me.get("ip_hashes_seen", []))
    my_uas = set(ua.split(")")[0][:80] for ua in me.get("user_agents", []) if ua)

    others = []
    for vid, other in index.items():
        if vid == visitor_id:
            continue
        if str(other.get("identified_as", "")).strip().casefold() != claimed_name.strip().casefold():
            continue
        other_ips = set(other.get("ip_hashes_seen", []))
        other_uas = set(ua.split(")")[0][:80] for ua in other.get("user_agents", []) if ua)
        others.append({
            "visitor_id": vid,
            "shared_ip": bool(my_ips & other_ips),
            "shared_browser": bool(my_uas & other_uas),
            "visits": other.get("visits", 0),
        })

    same_ip = any(o["shared_ip"] for o in others)
    same_ua = any(o["shared_browser"] for o in others)

    if not others:
        verdict = "FIRST_CLAIM"
    elif same_ip or same_ua:
        verdict = "CONSISTENT"
    else:
        verdict = "CONFLICT_POSSIBLE_IMPERSONATION"

    me["identified_as"] = claimed_name
    me["identity_verified"] = False          # a claim is never verification
    me["identity_verdict"] = verdict
    me["identity_conflicts"] = [o for o in others if not (o["shared_ip"] or o["shared_browser"])]
    note = me.get("note", "")
    if verdict == "CONFLICT_POSSIBLE_IMPERSONATION":
        note = (note + " | " if note else "") + (
            f"claims to be {claimed_name} but shares no network or browser with the "
            f"{len(others)} visitor(s) already identified as them")
    me["note"] = note
    index[visitor_id] = me
    _save_index(index, sd)
    _write_visitor_file(me, sd)
    return {"status": verdict, "visitor_id": visitor_id, "claimed": claimed_name,
            "verified": False, "matches": others, "truth_label": TRUTH_LABEL}


@_serialized
def append_exchange(
    visitor_id: str,
    question: str,
    answer: str,
    topics: Iterable[str] = (),
    *,
    conversation_id: str = "",
    state_dir: Path | str | None = None,
) -> None:
    """Remember, in the visitor's own file, what they asked and what Alice said."""
    if not visitor_id:
        return
    sd = _state_dir(state_dir)
    index = load_index(state_dir=sd)
    v = index.get(visitor_id)
    if v is None:
        # Never drop a chat because the row is missing. See _blank_visitor.
        v = _blank_visitor(visitor_id)
    now = time.time()
    v["last_seen"] = now
    ex = v.setdefault("exchanges", [])
    ex.append({"ts": now, "q": question[:400], "a": answer[:1200],
               "topics": sorted(set(topics)), "c": conversation_id})
    v["exchanges"] = ex[-200:]                     # bounded per visitor

    # A conversation thread, so the sidebar can list real chats.
    if conversation_id:
        convs = v.setdefault("conversations", {})
        c = convs.get(conversation_id) or {"id": conversation_id, "title": question[:70],
                                           "created": now, "count": 0, "turn_log": [],
                                           "archived": False, "archived_ts": None}
        c.setdefault("archived", False)            # threads saved before archiving existed
        c["count"] = int(c.get("count", 0)) + 1
        c["last_ts"] = now
        if not c.get("title"):
            c["title"] = question[:70]
        c.setdefault("turn_log", []).append({"ts": now, "q": question[:600], "a": answer[:4000]})
        c["turn_log"] = c["turn_log"][-60:]
        convs[conversation_id] = c
        v["conversations"] = convs
    seen = set(v.get("topics_discussed", [])) | set(topics)
    v["topics_discussed"] = sorted(seen)
    index[visitor_id] = v
    _save_index(index, sd)
    _write_visitor_file(v, sd)


def conversations(visitor_id: str, *, active_only: bool = False,
                  state_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """This visitor's chat threads, newest first — the sidebar list.

    Every thread carries its own `archived` flag, so the caller can render active
    chats and archived chats side by side, the way claude.ai and chatgpt.com do.
    """
    v = load_index(state_dir=state_dir).get(visitor_id)
    if not v:
        return []
    convs = list((v.get("conversations") or {}).values())
    for c in convs:
        c.pop("turn_log", None)                    # keep the list light
        c["archived"] = bool(c.get("archived"))    # threads saved before archiving existed
    if active_only:
        convs = [c for c in convs if not c.get("archived")]
    return sorted(convs, key=lambda c: -float(c.get("last_ts") or 0))


@_serialized
def set_archived(
    visitor_id: str,
    conversation_id: str,
    archived: bool = True,
    *,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Archive or unarchive one thread — the claude.ai / chatgpt.com behaviour.

    Archiving hides a chat from the sidebar without destroying it: the turns stay
    in the visitor's own file, stay searchable, and can be unarchived at any time.
    """
    sd = _state_dir(state_dir)
    index = load_index(state_dir=sd)
    v = index.get(visitor_id)
    if not v:
        return {"ok": False, "error": "unknown_visitor", "conversation_id": conversation_id}
    c = (v.get("conversations") or {}).get(conversation_id)
    if not c:
        return {"ok": False, "error": "unknown_conversation", "conversation_id": conversation_id}
    c["archived"] = bool(archived)
    c["archived_ts"] = time.time() if archived else None
    _save_index(index, sd)
    _write_visitor_file(v, sd)
    return {"ok": True, "conversation_id": conversation_id, "archived": c["archived"],
            "title": c.get("title", ""), "truth_label": TRUTH_LABEL}


def conversation_log(visitor_id: str, conversation_id: str, *,
                     state_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """The turns of one thread, so a returning visitor sees their history."""
    v = load_index(state_dir=state_dir).get(visitor_id)
    if not v:
        return []
    c = (v.get("conversations") or {}).get(conversation_id)
    return list((c or {}).get("turn_log") or [])


def load_index(*, state_dir: Path | str | None = None) -> dict[str, dict[str, Any]]:
    p = _state_dir(state_dir) / VISITORS_INDEX
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): v for k, v in d.items()} if isinstance(d, dict) else {}


@_serialized
def identify(visitor_id: str, name: str, note: str = "", *, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Attach a human identity to a visitor once we learn who they are."""
    sd = _state_dir(state_dir)
    index = load_index(state_dir=sd)
    if visitor_id not in index:
        return {}
    index[visitor_id]["identified_as"] = name
    if note:
        index[visitor_id]["note"] = note
    _save_index(index, sd)
    _write_visitor_file(index[visitor_id], sd)
    return index[visitor_id]


@_serialized
def forget(visitor_id: str, *, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Honour a deletion request: drop the index entry and the visitor's file."""
    sd = _state_dir(state_dir)
    index = load_index(state_dir=sd)
    removed = index.pop(visitor_id, None)
    _save_index(index, sd)
    f = sd / VISITOR_FILES_DIR / f"{visitor_id}.md"
    if f.exists():
        f.unlink()
    return {"forgotten": bool(removed), "visitor_id": visitor_id}


@_serialized
def forget_old(days: int = RETENTION_DAYS, *, state_dir: Path | str | None = None) -> dict[str, Any]:
    sd = _state_dir(state_dir)
    cutoff = time.time() - days * 86400
    index = load_index(state_dir=sd)
    stale = [k for k, v in index.items() if float(v.get("last_seen") or 0) < cutoff]
    for k in stale:
        forget(k, state_dir=sd)
    return {"pruned": len(stale), "older_than_days": days}


def summary(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    index = load_index(state_dir=state_dir)
    visitors = list(index.values())
    today = time.strftime("%Y-%m-%d")
    return {
        "unique_visitors": len(visitors),
        "total_visits": sum(int(v.get("visits", 0)) for v in visitors),
        "returning": sum(1 for v in visitors if int(v.get("visits", 0)) > 1),
        "identified": sum(1 for v in visitors if v.get("identified_as")),
        "seen_today": sum(1 for v in visitors
                           if time.strftime("%Y-%m-%d", time.localtime(float(v.get("last_seen") or 0))) == today),
        "retention_days": RETENTION_DAYS,
        "raw_ip_stored": STORE_RAW_IP,
        "truth_label": TRUTH_LABEL,
    }


def selftest() -> dict[str, Any]:
    """Everything is measured INSIDE the temp dir, before it is deleted."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)
        record_visit(visitor_id="v_aaa", ip="1.2.3.4", user_agent="Safari", referrer="x.com", state_dir=sd)
        b = record_visit(visitor_id="v_aaa", ip="1.2.3.4", user_agent="Safari", state_dir=sd)
        c = record_visit(visitor_id="v_bbb", ip="9.9.9.9", user_agent="Chrome", state_dir=sd)
        s0 = summary(state_dir=sd)
        file_exists = (sd / VISITOR_FILES_DIR / "v_aaa.md").exists()
        raw_leaked = "1.2.3.4" in (sd / VISITORS_LEDGER).read_text()

        identify("v_aaa", "Carlton Dole", "matched by owner", state_dir=sd)
        categorised = categorize("v_aaa", state_dir=sd)

        # A DIFFERENT network and browser claiming the same person = conflict.
        record_visit(visitor_id="v_fake", ip="8.8.8.8", user_agent="Firefox", state_dir=sd)
        imp = claim_identity("v_fake", "Carlton Dole", state_dir=sd)
        # Same network and browser claiming him = consistent, not suspicious.
        record_visit(visitor_id="v_same", ip="1.2.3.4", user_agent="Safari", state_dir=sd)
        honest = claim_identity("v_same", "Carlton Dole", state_dir=sd)

        before_forget = summary(state_dir=sd)["unique_visitors"]
        forgot = forget("v_bbb", state_dir=sd)
        after_forget = summary(state_dir=sd)["unique_visitors"]
        same_hash = b["ip_hash"] == record_visit(
            visitor_id="v_hashcheck", ip="1.2.3.4", user_agent="Safari", state_dir=sd)["ip_hash"]

        # REGRESSION: a signed-in account identity that was never recorded.
        # Saving must create the row instead of dropping the chat in silence.
        ghost = "acct_ghost_no_row"
        append_exchange(ghost, "did my chat save?", "yes", ["general"],
                        conversation_id="c_ghost", state_dir=sd)
        ghost_convs = conversations(ghost, state_dir=sd)
        ghost_log = conversation_log(ghost, "c_ghost", state_dir=sd)
        ghost_row_created = ghost in load_index(state_dir=sd)

        # Archive round trip: hidden from an active-only list, never destroyed.
        archive_hit = set_archived(ghost, "c_ghost", True, state_dir=sd)
        after_archive = conversations(ghost, state_dir=sd)
        active_after = conversations(ghost, active_only=True, state_dir=sd)
        log_after_archive = conversation_log(ghost, "c_ghost", state_dir=sd)
        unarchive_hit = set_archived(ghost, "c_ghost", False, state_dir=sd)
        active_back = conversations(ghost, active_only=True, state_dir=sd)
        unknown_archive = set_archived(ghost, "c_nope", True, state_dir=sd)

        # REGRESSION: a page load must never erase what the visitor saved.
        # record_visit used to rebuild the row from a fixed key list, dropping
        # conversations and exchanges on every visit.
        append_exchange("v_survives", "keep me", "kept", ["general"],
                        conversation_id="c_keep", state_dir=sd)
        record_visit(visitor_id="v_survives", ip="5.5.5.5", user_agent="Safari", state_dir=sd)
        survived_convs = conversations("v_survives", state_dir=sd)
        survived_log = conversation_log("v_survives", "c_keep", state_dir=sd)
        survived_row = load_index(state_dir=sd).get("v_survives") or {}

    checks = {
        "counts_unique_visitors": s0["unique_visitors"] == 2,
        "counts_return_visits": s0["returning"] == 1 and b["visits"] == 2,
        "one_file_per_visitor": file_exists,
        "raw_ip_not_stored": not raw_leaked,
        "same_ip_same_hash": same_hash,
        "different_ip_different_hash": b["ip_hash"] != c["ip_hash"],
        "known_person_categorised": categorised.get("category") == "known_person",
        "impersonation_flagged": imp["status"] == "CONFLICT_POSSIBLE_IMPERSONATION",
        "impersonation_never_verified": imp["verified"] is False,
        "consistent_claim_allowed": honest["status"] == "CONSISTENT",
        "forget_removes_one": forgot["forgotten"] and after_forget == before_forget - 1,
        "visit_does_not_erase_chats": len(survived_convs) == 1 and len(survived_log) == 1
                                      and survived_row.get("visits") == 1,
        "chat_saved_for_unrecorded_identity": ghost_row_created and len(ghost_convs) == 1
                                               and len(ghost_log) == 1,
        "archive_hides_from_active_list": archive_hit.get("ok") and not active_after
                                          and bool(after_archive) and after_archive[0]["archived"],
        "archive_does_not_destroy": len(log_after_archive) == 1
                                    and log_after_archive[0].get("q") == "did my chat save?",
        "unarchive_restores_visibility": unarchive_hit.get("ok") and len(active_back) == 1
                                         and not active_back[0]["archived"],
        "archiving_unknown_thread_is_refused": unknown_archive.get("ok") is False,
    }
    return {"ok": all(checks.values()), "checks": checks, "truth_label": TRUTH_LABEL}


if __name__ == "__main__":  # pragma: no cover
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "summary":
        print(json.dumps(summary(), indent=2))
    elif cmd == "list":
        print(json.dumps(sorted(load_index().values(), key=lambda v: -float(v.get("last_seen") or 0)),
                         indent=2)[:4000])
    elif cmd == "forget-old":
        print(json.dumps(forget_old(), indent=2))
    elif cmd == "forget":
        print(json.dumps(forget(sys.argv[2]), indent=2))
    else:
        print(json.dumps(selftest(), indent=2))

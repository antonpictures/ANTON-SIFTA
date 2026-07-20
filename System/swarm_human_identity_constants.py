#!/usr/bin/env python3
"""Human identity constants — crypto swimmers for confirmed carbon bodies.

r1239/r1240: Names are stable addresses for external physical humans.
Each confirmed human body is a unique node in the stigmergic field.
Alice VLOOKUPs by name/time, not cortex guess. Hallucination dies
when the link is missing instead of invented.

Append-only JSONL store + SQLite FTS index. One organ, many surfaces.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

SCHEMA = "HUMAN_IDENTITY_CONSTANTS_V1"
EVENT_SCHEMA = "OWNER_HUMAN_EVENT_V1"

JSONL_NAME = "human_identity_constants.jsonl"
EVENTS_JSONL_NAME = "owner_human_events.jsonl"
DB_NAME = "human_identity_constants.db"

# ── Canonical owner (always exists) ──────────────────────────────────────────
OWNER_HUMAN_ID = "george_anton_m5"
DEFAULT_OWNER_HUMAN_ID = OWNER_HUMAN_ID
OWNER_ALIASES = ["george", "ioan george anton", "ioan", "anton", "the architect"]
_LEGACY_OWNER_HUMAN_IDS = frozenset({"george"})


def _normalize_human_id(human_id: str) -> str:
    hid = str(human_id or "").strip()
    if hid in _LEGACY_OWNER_HUMAN_IDS:
        return OWNER_HUMAN_ID
    return hid


def _confidence_value(conf: Any) -> float:
    if isinstance(conf, str):
        return 0.9 if conf == "confirmed" else 0.5
    try:
        return float(conf)
    except Exception:
        return 0.5


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _human_id_from_name(name: str) -> str:
    """Derive a stable human_id from a canonical name."""
    clean = name.strip().lower()
    if clean in OWNER_ALIASES or clean in {"george / ioan george anton", "ioan george anton"}:
        return OWNER_HUMAN_ID
    clean = re.sub(r"[^a-z0-9]+", "_", clean)
    clean = clean.strip("_")
    return clean


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    line = json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        row = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return row if isinstance(row, dict) else {}


# ── SQLite FTS index ─────────────────────────────────────────────────────────

def _db_path(state_dir: Optional[Path | str] = None) -> Path:
    return _state_dir(state_dir) / DB_NAME


def _ensure_db(state_dir: Optional[Path | str] = None) -> sqlite3.Connection:
    db = _db_path(state_dir)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS humans (
            human_id TEXT PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            aliases TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'unknown',
            source TEXT NOT NULL DEFAULT 'unknown',
            confidence REAL NOT NULL DEFAULT 0.5,
            first_seen_ts REAL NOT NULL,
            last_seen_ts REAL NOT NULL,
            linked_events_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS owner_events (
            event_id TEXT PRIMARY KEY,
            owner_human_id TEXT NOT NULL,
            action TEXT NOT NULL,
            target_human_ids TEXT NOT NULL DEFAULT '[]',
            media_title TEXT,
            details TEXT NOT NULL DEFAULT '{}',
            ts REAL NOT NULL,
            source TEXT NOT NULL DEFAULT 'unknown',
            evidence_ref TEXT
        )
    """)
    conn.commit()
    return conn


def _rebuild_fts(conn: sqlite3.Connection) -> None:
    """Rebuild FTS index from humans table."""
    conn.execute("DROP TABLE IF EXISTS humans_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS humans_fts
        USING fts5(human_id, canonical_name, aliases, content=humans, content_rowid=rowid)
    """)
    conn.execute("""
        INSERT INTO humans_fts(human_id, canonical_name, aliases)
        SELECT human_id, canonical_name, aliases FROM humans
    """)
    conn.commit()


# ── Core API ─────────────────────────────────────────────────────────────────

def upsert_human(
    canonical_name: str,
    *,
    aliases: Optional[list[str]] = None,
    status: str = "unknown",
    source: str = "owner_confirmed",
    confidence: float = 0.9,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Create or update a human identity node. Returns the row."""
    sd = _state_dir(state_dir)
    now = time.time()
    all_aliases = list(aliases or [])
    if canonical_name.strip().lower() in OWNER_ALIASES or any(a.strip().lower() in OWNER_ALIASES for a in all_aliases):
        human_id = OWNER_HUMAN_ID
        all_aliases = sorted(set(all_aliases + OWNER_ALIASES + [canonical_name]))
    else:
        human_id = _human_id_from_name(canonical_name)

    # Read existing — latest snapshot wins (append-only ledger may hold history).
    jsonl_path = sd / JSONL_NAME
    existing = _read_jsonl(jsonl_path)
    found = None
    for row in reversed(existing):
        if row.get("schema") != SCHEMA:
            continue
        if _normalize_human_id(str(row.get("human_id") or "")) == human_id:
            found = row
            break

    if found:
        existing_aliases = found.get("aliases", [])
        all_aliases = list(set(existing_aliases + all_aliases))
        if canonical_name not in all_aliases:
            all_aliases.append(canonical_name)
        # Handle both "confirmed" string and numeric confidence
        old_conf = found.get("confidence", 0)
        if isinstance(old_conf, str):
            old_conf = 0.9 if old_conf == "confirmed" else 0.5
        else:
            old_conf = float(old_conf)
        row = {
            "schema": SCHEMA,
            "human_id": human_id,
            "canonical_name": canonical_name,
            "aliases": all_aliases,
            "status": status or found.get("life_status", "unknown"),
            "source": source,
            "confidence": max(confidence, old_conf),
            "first_seen_ts": found.get("first_seen_ts", now),
            "last_seen_ts": now,
            "linked_events_count": found.get("linked_events_count", 0),
            "updated_ts": now,
        }
    else:
        if canonical_name not in all_aliases:
            all_aliases.append(canonical_name)
        row = {
            "schema": SCHEMA,
            "human_id": human_id,
            "canonical_name": canonical_name,
            "aliases": all_aliases,
            "status": status,
            "source": source,
            "confidence": confidence,
            "first_seen_ts": now,
            "last_seen_ts": now,
            "linked_events_count": 0,
        }

    _append_jsonl(jsonl_path, row)

    # Update SQLite
    conn = _ensure_db(state_dir)
    conn.execute("""
        INSERT OR REPLACE INTO humans
        (human_id, canonical_name, aliases, status, source, confidence,
         first_seen_ts, last_seen_ts, linked_events_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        human_id, canonical_name, json.dumps(all_aliases),
        status, source, confidence,
        row["first_seen_ts"], row["last_seen_ts"],
        row["linked_events_count"],
    ))
    conn.commit()
    _rebuild_fts(conn)
    conn.close()

    return row


def consolidate_human_identity_ledger(
    *,
    state_dir: Optional[Path | str] = None,
    write: bool = True,
) -> dict[str, Any]:
    """Merge legacy `george` fork into `george_anton_m5` and compact duplicate snapshots."""
    sd = _state_dir(state_dir)
    path = sd / JSONL_NAME
    rows = [r for r in _read_jsonl(path) if r.get("schema") == SCHEMA]
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        hid = _normalize_human_id(str(row.get("human_id") or ""))
        if not hid:
            continue
        current = dict(row)
        current["human_id"] = hid
        if hid == OWNER_HUMAN_ID:
            current["canonical_name"] = "George"
            current["status"] = current.get("status") or current.get("life_status") or "alive"
        if hid not in merged:
            merged[hid] = current
            continue
        base = merged[hid]
        aliases = set(base.get("aliases") or []) | set(current.get("aliases") or [])
        base["aliases"] = sorted(str(a) for a in aliases if str(a).strip())
        base["first_seen_ts"] = min(
            float(base.get("first_seen_ts") or time.time()),
            float(current.get("first_seen_ts") or time.time()),
        )
        base["last_seen_ts"] = max(
            float(base.get("last_seen_ts") or 0.0),
            float(current.get("last_seen_ts") or 0.0),
        )
        base["confidence"] = max(
            _confidence_value(base.get("confidence")),
            _confidence_value(current.get("confidence")),
        )
        base["linked_events_count"] = max(
            int(base.get("linked_events_count") or 0),
            int(current.get("linked_events_count") or 0),
        )
        if hid == OWNER_HUMAN_ID and current.get("source") in {"hardware_owner", "owner_hardware"}:
            base["source"] = current.get("source")

    out_rows = sorted(merged.values(), key=lambda item: str(item.get("human_id") or ""))
    receipt: dict[str, Any] = {
        "truth_label": "HUMAN_IDENTITY_CONSOLIDATION_RECEIPT_V1",
        "before_rows": len(rows),
        "after_rows": len(out_rows),
        "merged_legacy_owner_ids": sorted(_LEGACY_OWNER_HUMAN_IDS),
        "canonical_owner_human_id": OWNER_HUMAN_ID,
        "removed_duplicate_snapshots": max(0, len(rows) - len(out_rows)),
        "human_ids": [str(r.get("human_id") or "") for r in out_rows],
    }
    if not write:
        return receipt

    backup = path.with_suffix(".jsonl.pre_consolidate_backup")
    if path.exists():
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in out_rows),
        encoding="utf-8",
    )

    conn = _ensure_db(state_dir)
    conn.execute("DELETE FROM humans")
    for row in out_rows:
        status = str(row.get("status") or row.get("life_status") or "unknown")
        conn.execute(
            """
            INSERT OR REPLACE INTO humans
            (human_id, canonical_name, aliases, status, source, confidence,
             first_seen_ts, last_seen_ts, linked_events_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["human_id"],
                row.get("canonical_name") or "",
                json.dumps(row.get("aliases") or []),
                status,
                row.get("source") or "consolidated",
                _confidence_value(row.get("confidence")),
                float(row.get("first_seen_ts") or time.time()),
                float(row.get("last_seen_ts") or time.time()),
                int(row.get("linked_events_count") or 0),
            ),
        )
    conn.commit()
    _rebuild_fts(conn)
    conn.close()

    receipt_path = sd / "human_identity_consolidation_receipt.jsonl"
    receipt["ts"] = time.time()
    _append_jsonl(receipt_path, receipt)
    return receipt


def lookup_human_name(
    name: str,
    *,
    state_dir: Optional[Path | str] = None,
    exact_only: bool = False,
) -> Optional[dict[str, Any]]:
    """VLOOKUP: find a human node by name or alias. Returns None if not found."""
    sd = _state_dir(state_dir)
    target = name.strip().lower()
    target_id = _human_id_from_name(name)

    # Try SQLite FTS first
    try:
        conn = _ensure_db(state_dir)
        # Exact match on human_id
        row = conn.execute(
            "SELECT * FROM humans WHERE human_id = ?",
            (target_id,),
        ).fetchone()
        if row:
            conn.close()
            return _row_to_dict(row)

        # Exact match on canonical name or aliases. This intentionally does
        # not treat "Joe" as "Joe Rogan"; aliases must be explicit evidence.
        rows = conn.execute("SELECT * FROM humans").fetchall()
        for row in rows:
            row_dict = _row_to_dict(row)
            aliases = [str(a).strip().lower() for a in row_dict.get("aliases", [])]
            if target == str(row_dict.get("canonical_name", "")).strip().lower() or target in aliases:
                conn.close()
                return row_dict

        if exact_only:
            conn.close()
            return None

        # FTS match
        fts_row = conn.execute(
            "SELECT human_id FROM humans_fts WHERE humans_fts MATCH ? LIMIT 1",
            (target,),
        ).fetchone()
        if fts_row:
            full = conn.execute(
                "SELECT * FROM humans WHERE human_id = ?",
                (fts_row[0],),
            ).fetchone()
            conn.close()
            return _row_to_dict(full) if full else None

        conn.close()
    except Exception:
        pass

    # Fallback: scan JSONL — latest matching snapshot wins.
    jsonl_path = sd / JSONL_NAME
    for row in reversed(_read_jsonl(jsonl_path)):
        if row.get("schema") != SCHEMA:
            continue
        aliases = [a.lower() for a in row.get("aliases", [])]
        if target in aliases or _normalize_human_id(str(row.get("human_id") or "")) == target_id:
            return row
    if exact_only:
        return None
    return None


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "human_id": row["human_id"],
        "canonical_name": row["canonical_name"],
        "aliases": json.loads(row["aliases"]),
        "status": row["status"],
        "source": row["source"],
        "confidence": row["confidence"],
        "first_seen_ts": row["first_seen_ts"],
        "last_seen_ts": row["last_seen_ts"],
        "linked_events_count": row["linked_events_count"],
    }


def link_owner_event(
    action: str,
    *,
    target_human_names: Optional[list[str]] = None,
    media_title: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    ts: Optional[float] = None,
    source: str = "owner_voice",
    evidence_ref: Optional[str] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Link an owner action to one or more human nodes. Returns the event row."""
    sd = _state_dir(state_dir)
    now = ts or time.time()

    # Resolve target human IDs
    target_ids: list[str] = []
    target_rows: list[dict[str, Any]] = []
    for name in (target_human_names or []):
        h = lookup_human_name(name, state_dir=state_dir)
        if h:
            target_ids.append(h["human_id"])
            target_rows.append(h)
        else:
            # Auto-create with low confidence (pending confirmation)
            new = upsert_human(
                name, source="auto_extracted", confidence=0.4, state_dir=state_dir,
            )
            target_ids.append(new["human_id"])
            target_rows.append(new)

    event_id = hashlib.sha256(
        f"{OWNER_HUMAN_ID}:{action}:{','.join(target_ids)}:{now}".encode()
    ).hexdigest()[:16]

    event_row = {
        "schema": EVENT_SCHEMA,
        "event_id": event_id,
        "owner_human_id": OWNER_HUMAN_ID,
        "action": action,
        "target_human_ids": target_ids,
        "target_human_names": [r.get("canonical_name", "") for r in target_rows],
        "media_title": media_title,
        "details": details or {},
        "ts": now,
        "source": source,
        "evidence_ref": evidence_ref,
    }

    events_path = sd / EVENTS_JSONL_NAME
    _append_jsonl(events_path, event_row)

    # Update linked_events_count on each target human
    conn = _ensure_db(state_dir)
    for tid in target_ids:
        conn.execute(
            "UPDATE humans SET linked_events_count = linked_events_count + 1, last_seen_ts = ? WHERE human_id = ?",
            (now, tid),
        )
    conn.execute("""
        INSERT OR REPLACE INTO owner_events
        (event_id, owner_human_id, action, target_human_ids, media_title, details, ts, source, evidence_ref)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event_id, OWNER_HUMAN_ID, action, json.dumps(target_ids),
        media_title, json.dumps(details or {}), now, source, evidence_ref,
    ))
    conn.commit()
    conn.close()

    return event_row


def recall_owner_events(
    *,
    human_name: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 20,
    state_dir: Optional[Path | str] = None,
) -> list[dict[str, Any]]:
    """Recall owner events filtered by human name and/or action."""
    sd = _state_dir(state_dir)
    events_path = sd / EVENTS_JSONL_NAME
    rows = _read_jsonl(events_path)

    if human_name:
        h = lookup_human_name(human_name, state_dir=state_dir)
        if h:
            hid = h["human_id"]
            rows = [r for r in rows if hid in (r.get("target_human_ids") or [])]
        else:
            return []

    if action:
        rows = [r for r in rows if r.get("action") == action]

    rows.sort(key=lambda r: r.get("ts", 0), reverse=True)
    return rows[:limit]


def _parse_jre_title(text: str) -> Optional[dict[str, str]]:
    """Parse a Joe Rogan Experience title into host/guest metadata."""
    m = re.search(
        r"Joe\s+Rogan\s+Experience\s*#?\s*(?P<episode>\d+)?\s*[-–—]\s*(?P<guest>[^\n|]+)",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    guest = re.sub(r"\s*-\s*YouTube\s*$", "", m.group("guest").strip(), flags=re.IGNORECASE)
    guest = re.sub(r"\s+", " ", guest).strip()
    episode = (m.group("episode") or "").strip()
    media_title = "Joe Rogan Experience" + (f" #{episode}" if episode else "")
    return {"host": "Joe Rogan", "guest": guest, "episode": episode, "media_title": media_title}


def _parse_owner_guest_phrase(text: str) -> Optional[dict[str, str]]:
    """Parse owner phrases like 'Joe Rogan and his guest Chase Hughes'."""
    m = re.search(
        r"\bJoe\s+Rogan\b.*?\bguest\s+(?P<guest>[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    guest = re.sub(r"\s+(on|via|from|with|and|is|are)\b.*$", "", m.group("guest").strip(), flags=re.IGNORECASE)
    return {"host": "Joe Rogan", "guest": guest, "episode": "", "media_title": "Joe Rogan Experience"}


def _event_matches_parsed(row: dict[str, Any], parsed: dict[str, str]) -> bool:
    names = [str(n or "").strip().lower() for n in (row.get("target_human_names") or [])]
    details = row.get("details") if isinstance(row.get("details"), dict) else {}
    host = str(parsed.get("host") or "").strip().lower()
    guest = str(parsed.get("guest") or "").strip().lower()
    episode = str(parsed.get("episode") or "").strip()
    media_title = str(row.get("media_title") or "").strip().lower()
    parsed_title = str(parsed.get("media_title") or "").strip().lower()
    if host and guest and host in names and guest in names:
        if not episode or str(details.get("episode") or "") == episode:
            return True
    if parsed_title and media_title == parsed_title and guest and guest in names:
        return True
    return False


def _recent_media_title_rows(
    *,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
    max_age_s: float = 6 * 3600.0,
    limit: int = 64,
) -> list[dict[str, Any]]:
    """Collect recent local media titles from YouTube/watch ledgers only."""
    sd = _state_dir(state_dir)
    now_ts = float(now if now is not None else time.time())
    rows: list[dict[str, Any]] = []
    latest = _read_json(sd / "youtube_context_latest.json")
    if latest:
        latest = dict(latest)
        latest["_source"] = "youtube_context_latest"
        rows.append(latest)
    for filename, source in (
        ("youtube_context.jsonl", "youtube_context"),
        ("youtube_watch_memory.jsonl", "youtube_watch_memory"),
    ):
        for row in _read_jsonl(sd / filename)[-limit:]:
            copy = dict(row)
            copy["_source"] = source
            rows.append(copy)

    kept: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(rows, key=lambda r: float(r.get("ts", 0.0) or 0.0), reverse=True):
        try:
            ts = float(row.get("ts", 0.0) or 0.0)
        except Exception:
            ts = 0.0
        if ts and now_ts - ts > max_age_s:
            continue
        title = " ".join(
            str(
                row.get("title")
                or row.get("media_title")
                or row.get("source_work")
                or ""
            ).split()
        )
        if not title:
            continue
        video_id = str(row.get("video_id") or row.get("youtube_video_id") or "").strip()
        key = video_id or title.lower()
        if key in seen:
            continue
        seen.add(key)
        kept.append(
            {
                "title": title,
                "video_id": video_id,
                "ts": ts,
                "source": str(row.get("_source") or "media_ledger"),
            }
        )
    return kept


def ingest_recent_media_contexts_from_ledgers(
    *,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
    max_age_s: float = 6 * 3600.0,
    limit: int = 64,
) -> dict[str, Any]:
    """Hydrate human identity events from recent local media title receipts.

    This bridges YouTube/browser/cowatch receipts into the same human constants
    organ. It only parses titles already present on disk; no network lookup and
    no STT guessing.
    """
    sd = _state_dir(state_dir)
    events_before = recall_owner_events(action="listened_with_alice", limit=200, state_dir=sd)
    ingested: list[dict[str, Any]] = []
    parsed_keys: set[tuple[str, str, str]] = set()
    for row in _recent_media_title_rows(state_dir=sd, now=now, max_age_s=max_age_s, limit=limit):
        title = str(row.get("title") or "")
        parsed = _parse_jre_title(title)
        if not parsed:
            continue
        key = (
            parsed.get("host", "").lower(),
            parsed.get("guest", "").lower(),
            parsed.get("episode", ""),
        )
        if key in parsed_keys:
            continue
        parsed_keys.add(key)
        if any(_event_matches_parsed(ev, parsed) for ev in events_before):
            continue
        evidence_bits = [str(row.get("source") or "media_ledger")]
        if row.get("video_id"):
            evidence_bits.append(str(row["video_id"]))
        result = ingest_media_context(
            title,
            state_dir=sd,
            now=float(row.get("ts") or now or time.time()),
            evidence_ref=":".join(evidence_bits),
        )
        if result.get("ok"):
            ingested.append(
                {
                    "host": parsed["host"],
                    "guest": parsed["guest"],
                    "episode": parsed.get("episode", ""),
                    "source": row.get("source"),
                    "video_id": row.get("video_id"),
                }
            )
            events_before.append(result["event"])
    return {"ok": True, "ingested": ingested, "count": len(ingested)}


def ingest_owner_turn(
    text: str,
    *,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
    evidence_ref: Optional[str] = None,
) -> dict[str, Any]:
    """Ingest owner text for named human identity nodes and listening events."""
    parsed = _parse_jre_title(text) or _parse_owner_guest_phrase(text)
    if not parsed:
        return {"ok": False, "humans": [], "event": None}

    upsert_human(
        "George",
        aliases=OWNER_ALIASES,
        status="alive",
        source="owner_hardware",
        confidence=1.0,
        state_dir=state_dir,
    )
    host = upsert_human(
        parsed["host"],
        aliases=["Joe Rogan", "JRE host"],
        status="alive",
        source="owner_confirmed",
        confidence=0.9,
        state_dir=state_dir,
    )
    guest = upsert_human(
        parsed["guest"],
        aliases=[parsed["guest"]],
        status="unknown",
        source="owner_named" if not parsed.get("episode") else "media_title",
        confidence=0.85 if not parsed.get("episode") else 0.8,
        state_dir=state_dir,
    )

    event = link_owner_event(
        "listened_with_alice",
        target_human_names=[parsed["host"], parsed["guest"]],
        media_title=parsed["media_title"],
        details={
            "host_human_id": host["human_id"],
            "guest_human_id": guest["human_id"],
            "episode": parsed.get("episode", ""),
            "device": "iphone_speaker" if "iphone" in text.lower() else "unknown",
        },
        ts=now,
        source="owner_voice",
        evidence_ref=evidence_ref,
        state_dir=state_dir,
    )
    event["host_human_id"] = host["human_id"]
    event["guest_human_id"] = guest["human_id"]
    event["host_name"] = host["canonical_name"]
    event["guest_name"] = guest["canonical_name"]
    return {"ok": True, "humans": [host["canonical_name"], guest["canonical_name"]], "event": event}


def ingest_media_context(
    media_title: str,
    *,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
    evidence_ref: Optional[str] = None,
) -> dict[str, Any]:
    """Ingest a browser/co-watch media title into human identity nodes."""
    return ingest_owner_turn(
        media_title,
        state_dir=state_dir,
        now=now,
        evidence_ref=evidence_ref,
    )


def backfill_observed_humans(
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Seed the observed owner/JRE human rows and known podcast events."""
    upsert_human(
        "George",
        aliases=OWNER_ALIASES,
        status="alive",
        source="owner_hardware",
        confidence=1.0,
        state_dir=state_dir,
    )
    for name in ["Joe Rogan", "Chase Hughes", "Eric Weinstein"]:
        upsert_human(
            name,
            aliases=[name],
            status="unknown",
            source="observed_backfill",
            confidence=0.85,
            state_dir=state_dir,
        )
    ingest_owner_turn(
        "Joe Rogan and his guest Chase Hughes are playing on my iPhone.",
        state_dir=state_dir,
        evidence_ref="CONSCIOUSNESS_TOURNAMENT_2026-06-17.md:1508",
    )
    ingest_owner_turn(
        "Joe Rogan Experience #2503 - Eric Weinstein",
        state_dir=state_dir,
        evidence_ref="work_receipts.jsonl:4128",
    )
    return {"ok": True, "humans": ["George", "Joe Rogan", "Chase Hughes", "Eric Weinstein"]}


def answer_human_memory_query(
    query_text: str,
    *,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
) -> str:
    """Reflex answer for podcast/person memory questions from stored rows only."""
    q = query_text.lower()
    if not (
        any(word in q for word in ("podcast", "guest", "joe rogan", "jre"))
        or (
            "remember" in q
            and re.search(r"\b(?:host|guest|podcast|joe\s+rogan|jre|video|listened|listening)\b", q)
        )
    ):
        return ""
    ingest_recent_media_contexts_from_ledgers(
        state_dir=state_dir,
        now=now,
    )
    events = recall_owner_events(action="listened_with_alice", limit=5, state_dir=state_dir)
    if not events:
        return ""
    latest = events[0]
    details = latest.get("details") or {}
    host_id = details.get("host_human_id")
    guest_id = details.get("guest_human_id")
    names = latest.get("target_human_names") or []
    host = names[0] if names else "unknown host"
    guest = names[1] if len(names) > 1 else "unknown guest"
    return (
        "I found the human-identity receipt for that podcast. "
        f"Host: {host} ({host_id or 'unlinked'}). "
        f"Guest: {guest} ({guest_id or 'unlinked'}). "
        f"Media: {latest.get('media_title') or 'unknown'}. "
        f"Evidence: {latest.get('evidence_ref') or latest.get('source') or 'local event ledger'}."
    )


_FOUNDER_IDENTITY_NAMES: tuple[str, ...] = (
    "Gabriel Weinberg",
    "Evan Schwartz",
    "Vlad Tenev",
    "Mark Zuckerberg",
    "Aravind Srinivas",
)

_IDENTITY_QUERY_RE = re.compile(
    r"\b(?:who\s+(?:is|was)|tell\s+me\s+about|identity\s+of|birth\s+anchor\s+for)\b",
    re.IGNORECASE,
)


def _ensure_founder_identity_nodes(*, state_dir: Optional[Path | str] = None) -> None:
    """Upsert r1349 founder/collision humans with tournament source receipts."""
    receipts = {
        "Gabriel Weinberg": "CONSCIOUSNESS_TOURNAMENT_2026-06-19.md:r1349",
        "Evan Schwartz": "CURSOR_PROMPT_R1343_REPO_SCAN_CURSOR_WORKLOAD.md:64",
        "Vlad Tenev": "CONSCIOUSNESS_TOURNAMENT_2026-06-19.md:r1349",
        "Mark Zuckerberg": "CONSCIOUSNESS_TOURNAMENT_2026-06-19.md:r1349",
        "Aravind Srinivas": "CONSCIOUSNESS_TOURNAMENT_2026-06-19.md:r1349",
    }
    for name in _FOUNDER_IDENTITY_NAMES:
        upsert_human(
            name,
            aliases=[name],
            status="known_public_figure",
            source=receipts.get(name, "concept_human_anchor"),
            confidence=0.9,
            state_dir=state_dir,
        )


def answer_human_identity_fast_recall(
    query_text: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Typed reflex for non-fiction founder/identity checks before cortex fallback."""
    q = str(query_text or "").strip()
    if not q or not _IDENTITY_QUERY_RE.search(q):
        return ""
    if re.search(r"\bSEARCH\s+ON\b", q, re.IGNORECASE):
        return ""
    _ensure_founder_identity_nodes(state_dir=state_dir)
    try:
        from System.swarm_concept_human_anchor import (
            SOURCE_ANCHORED_LABEL,
            answer_concept_founder_query,
            resolve_concept_anchor,
        )
    except Exception:
        return ""

    founder_reply = answer_concept_founder_query(q, state_dir=state_dir)
    if founder_reply:
        return founder_reply

    named: Optional[str] = None
    for name in _FOUNDER_IDENTITY_NAMES:
        if re.search(r"\b" + re.escape(name) + r"\b", q, re.IGNORECASE):
            named = name
            break
    if not named:
        return ""

    human = lookup_human_name(named, state_dir=state_dir, exact_only=True)
    concept = None
    for seed_phrase in ("duckduckgo", "facebook", "robinhood app", "perplexity ai"):
        if seed_phrase.replace(" ", "") in q.lower().replace(" ", ""):
            concept = resolve_concept_anchor(seed_phrase, state_dir=state_dir)
            break
    if concept is None and named == "Gabriel Weinberg":
        concept = resolve_concept_anchor("duckduckgo", state_dir=state_dir)
    elif concept is None and named == "Mark Zuckerberg":
        concept = resolve_concept_anchor("facebook", state_dir=state_dir)
    elif concept is None and named == "Vlad Tenev":
        concept = resolve_concept_anchor("robinhood app", state_dir=state_dir)
    elif concept is None and named == "Aravind Srinivas":
        concept = resolve_concept_anchor("perplexity ai", state_dir=state_dir)

    if named == "Evan Schwartz":
        return (
            "Human identity receipt: Evan Schwartz is a common name collision — "
            "he is NOT the DuckDuckGo founder. Gabriel Weinberg holds the sourced "
            f"birth anchor for DuckDuckGo. Truth label: {SOURCE_ANCHORED_LABEL}. "
            "Source: CURSOR_PROMPT_R1343_REPO_SCAN_CURSOR_WORKLOAD.md:64."
        )

    if concept:
        primary = concept.get("primary_birth_anchor") or {}
        if str(primary.get("human_name") or "") == named:
            receipts = primary.get("source_receipts") or []
            return (
                f"Human identity receipt for {named}: concept birth anchor "
                f"for {concept.get('matched_phrase') or concept.get('concept_id')} "
                f"({primary.get('role') or 'founder'}). "
                f"Source receipts: {', '.join(str(r) for r in receipts[:3]) or human.get('source', 'local')}. "
                f"Truth label: {primary.get('truth_label') or SOURCE_ANCHORED_LABEL}."
            )

    if human:
        return (
            f"Human identity receipt: {human.get('canonical_name')} "
            f"({human.get('human_id')}); source={human.get('source')}; "
            f"confidence={human.get('confidence')}."
        )
    return ""


def human_identity_memory_block(
    query_text: str = "",
    *,
    state_dir: Optional[Path | str] = None,
    max_chars: int = 2000,
) -> str:
    """Prompt context block for known humans and recent owner-human events."""
    sd = _state_dir(state_dir)
    lines = ["## HUMAN IDENTITY CONSTANTS"]
    mentioned: list[dict[str, Any]] = []
    for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", query_text or ""):
        h = lookup_human_name(match.group(1), state_dir=sd, exact_only=True)
        if h and h.get("human_id") not in {m.get("human_id") for m in mentioned}:
            mentioned.append(h)
    if not mentioned and any(w in (query_text or "").lower() for w in ("podcast", "guest", "remember")):
        for ev in recall_owner_events(action="listened_with_alice", limit=3, state_dir=sd):
            for name in ev.get("target_human_names") or []:
                h = lookup_human_name(name, state_dir=sd, exact_only=True)
                if h and h.get("human_id") not in {m.get("human_id") for m in mentioned}:
                    mentioned.append(h)
    for h in mentioned[:8]:
        lines.append(f"- Human: {h['canonical_name']} ({h['human_id']}) confidence={h.get('confidence')}")
    events = recall_owner_events(limit=3, state_dir=sd)
    for ev in events:
        targets = ", ".join(ev.get("target_human_names") or [])
        lines.append(f"- Owner event: {ev.get('action')}: {targets} — {ev.get('media_title') or ''}")
    block = "\n".join(lines)
    if len(block) > max_chars:
        block = block[:max_chars] + "\n[truncated]"
    return block if len(lines) > 1 else ""


def prompt_block_for_human_context(
    *,
    query_text: str = "",
    state_dir: Optional[Path | str] = None,
    max_chars: int = 2000,
) -> str:
    """Build a prompt block with relevant human nodes for the current turn."""
    sd = _state_dir(state_dir)
    names_found: list[str] = []

    # Extract human-like names from query (capitalized words that look like names)
    for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", query_text):
        name = match.group(1)
        h = lookup_human_name(name, state_dir=sd)
        if h:
            names_found.append(name)

    if not names_found:
        return ""

    lines = ["## Known Humans (from identity constants)"]
    for name in names_found:
        h = lookup_human_name(name, state_dir=sd)
        if h:
            aliases = ", ".join(h.get("aliases", [])[:5])
            status = h.get("status", "unknown")
            events = h.get("linked_events_count", 0)
            lines.append(f"- **{h['canonical_name']}** ({h['human_id']}): "
                         f"status={status}, aliases=[{aliases}], "
                         f"linked_events={events}")

    # Recent owner events involving these humans
    events = recall_owner_events(limit=5, state_dir=sd)
    relevant = []
    for ev in events:
        for name in names_found:
            h = lookup_human_name(name, state_dir=sd)
            if h and h["human_id"] in (ev.get("target_human_ids") or []):
                relevant.append(ev)
                break

    if relevant:
        lines.append("\n## Recent Owner Events")
        for ev in relevant[:5]:
            targets = ", ".join(ev.get("target_human_names", []))
            title = ev.get("media_title") or ev.get("action", "")
            lines.append(f"- {ev['action']}: {targets} — {title}")

    block = "\n".join(lines)
    if len(block) > max_chars:
        block = block[:max_chars] + "\n[truncated]"
    return block


# ── Backfill from existing ledgers ───────────────────────────────────────────

def backfill_from_tournament(
    tournament_path: Optional[Path | str] = None,
    state_dir: Optional[Path | str] = None,
) -> int:
    """Extract human names from tournament file and create nodes. Returns count."""
    sd = _state_dir(state_dir)
    path = Path(tournament_path) if tournament_path else (
        _REPO / "Documents" / "CONSCIOUSNESS_TOURNAMENT_2026-06-17.md"
    )
    if not path.exists():
        return 0

    text = path.read_text(encoding="utf-8", errors="replace")

    # Known human patterns from the tournament
    known = [
        ("Joe Rogan", ["joe rogan", "jre", "joe rogans"]),
        ("Chase Hughes", ["chase hughes"]),
        ("Eric Weinstein", ["eric weinstein"]),
        ("George / Ioan George Anton", ["george", "ioan george anton", "ioan", "anton", "the architect"]),
    ]

    count = 0
    for canonical, aliases in known:
        if canonical.split("/")[0].strip().lower() in text.lower() or any(a.lower() in text.lower() for a in aliases):
            upsert_human(
                canonical.split("/")[0].strip(),
                aliases=aliases,
                status="alive",
                source="tournament_backfill",
                confidence=0.85,
                state_dir=sd,
            )
            count += 1

    return count


def backfill_owner_events_from_tournament(
    tournament_path: Optional[Path | str] = None,
    state_dir: Optional[Path | str] = None,
) -> int:
    """Create owner-human events from tournament context. Returns count."""
    sd = _state_dir(state_dir)
    path = Path(tournament_path) if tournament_path else (
        _REPO / "Documents" / "CONSCIOUSNESS_TOURNAMENT_2026-06-17.md"
    )
    if not path.exists():
        return 0

    text = path.read_text(encoding="utf-8", errors="replace")

    # Event: George listened to Joe Rogan with Chase Hughes
    if "joe rogan" in text.lower() and "chase hughes" in text.lower():
        link_owner_event(
            "listened_with_alice",
            target_human_names=["Joe Rogan", "Chase Hughes"],
            media_title="Joe Rogan Experience (podcast via iPhone speaker)",
            details={
                "device": "iphone_speaker",
                "context": "George played podcast in room with Alice",
                "alice_present": True,
                "alice_listening_via": "macbook_microphone",
            },
            source="owner_voice",
            state_dir=sd,
        )
        return 1

    return 0


# ── CLI probe ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        sd = _state_dir()
        humans = _read_jsonl(sd / JSONL_NAME)
        events = _read_jsonl(sd / EVENTS_JSONL_NAME)
        print(f"Human nodes: {len(humans)}")
        for h in humans:
            status = h.get("status") or h.get("life_status", "unknown")
            print(f"  {h['canonical_name']} ({h['human_id']}): "
                  f"status={status}, events={h.get('linked_events_count', 0)}")
        print(f"Owner events: {len(events)}")
        for ev in events[-5:]:
            targets = ", ".join(ev.get("target_human_names", []))
            print(f"  {ev['action']}: {targets} — {ev.get('media_title', '')}")

    elif cmd == "lookup":
        name = sys.argv[2] if len(sys.argv) > 2 else ""
        result = lookup_human_name(name)
        if result:
            print(json.dumps(result, indent=2))
        else:
            print(f"Not found: {name}")

    elif cmd == "backfill":
        n1 = backfill_from_tournament()
        n2 = backfill_owner_events_from_tournament()
        print(f"Backfilled {n1} human nodes, {n2} owner events")

    elif cmd == "recall":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        events = recall_owner_events(human_name=name)
        for ev in events:
            targets = ", ".join(ev.get("target_human_names", []))
            print(f"  {ev['action']}: {targets} — {ev.get('media_title', '')}")

    else:
        print(f"Unknown command: {cmd}. Use: status, lookup, backfill, recall")

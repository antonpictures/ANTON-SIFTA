#!/usr/bin/env python3
"""Internet forager home-vector organ.

Field bees can be carried away in darkness and still return if the release
point is inside learned territory. Alice's browser swimmers need the same
shape: a portable home vector, landmark orientation, a return-home command,
and verify-on-arrival so a spoofed yellow dot is not accepted as home.

This organ does not browse by itself. It writes the browser open-url drop and
receipts that Alice Browser already knows how to consume.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

from swarmrl.beenav_homing import Hive, perceptual_hash

try:
    from System.swarm_alice_browser_grok_paste_clipboard import grok_thread_id
except Exception:  # pragma: no cover - import fallback for standalone tests
    def grok_thread_id(url: str) -> str:
        return ""


TRUTH_LABEL = "INTERNET_FORAGER_HOME_VECTOR_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_HOME_VECTOR_FILE = "internet_forager_home_vector.json"
_HOME_VECTOR_LEDGER = "internet_forager_home_vectors.jsonl"
_ORIENTATION_LEDGER = "internet_forager_orientation.jsonl"
_BROWSER_OPEN_DROP = "alice_browser_open_url.txt"


def state_dir_path(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _host(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc.lower()
    except Exception:
        return ""


def _latest_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _read_recent_receipts(sd: Path, *, limit: int = 8) -> list[str]:
    receipts: list[str] = []
    for name in ("grok_browser_round_state.jsonl", "work_receipts.jsonl"):
        path = sd / name
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]:
                if not line.strip():
                    continue
                row = json.loads(line)
                rid = _clean(row.get("receipt_id") or row.get("trace_id") or row.get("id"))
                if rid and rid not in receipts:
                    receipts.append(rid)
        except Exception:
            continue
    return receipts[-limit:]


def page_landmark_sample(page: Mapping[str, Any] | None) -> dict[str, Any]:
    """Compact browser-page landmark sample for BeeNav-style matching."""
    page = page or {}
    url = _clean(page.get("url"))
    title = _clean(page.get("title"))
    text = _clean(page.get("text") or page.get("text_excerpt") or page.get("article_text"))
    return {
        "url_host": _host(url),
        "url_path": urlparse(url).path[:160] if url else "",
        "grok_thread_id": grok_thread_id(url),
        "title": title[:160],
        "text_hash": hashlib.sha256(text[:2000].encode("utf-8")).hexdigest() if text else "",
    }


def _stable_signature_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "home_url": _clean(data.get("home_url")),
        "home_thread_id": _clean(data.get("home_thread_id")),
        "home_host": _clean(data.get("home_host")),
        "global_surface": _clean(data.get("global_surface")),
        "mission_receipt_id": _clean(data.get("mission_receipt_id")),
        "owner_binding_sha256": _clean(data.get("owner_binding_sha256")),
        "landmark_hashes": list(data.get("landmark_hashes") or []),
        "recent_receipt_hashes": list(data.get("recent_receipt_hashes") or []),
    }


def sign_home_vector(data: Mapping[str, Any]) -> str:
    payload = _stable_signature_payload(data)
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BrowserForagerHomeVector:
    schema: str = TRUTH_LABEL
    truth_label: str = TRUTH_LABEL
    home_id: str = ""
    created_ts: float = 0.0
    home_url: str = ""
    home_host: str = ""
    home_thread_id: str = ""
    global_surface: str = "Global Chat + alice_conversation"
    mission_receipt_id: str = ""
    owner_binding_sha256: str = ""
    landmark_hashes: list[str] = field(default_factory=list)
    recent_receipt_hashes: list[str] = field(default_factory=list)
    signature_sha256: str = ""

    def as_row(self) -> dict[str, Any]:
        return asdict(self)


def verify_home_vector_signature(vector: Mapping[str, Any] | BrowserForagerHomeVector) -> bool:
    row = vector.as_row() if isinstance(vector, BrowserForagerHomeVector) else dict(vector)
    sig = _clean(row.get("signature_sha256"))
    return bool(sig and sig == sign_home_vector(row))


def load_home_vector(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    return _latest_json(state_dir_path(state_dir) / _HOME_VECTOR_FILE)


def capture_home_vector(
    *,
    page: Optional[Mapping[str, Any]] = None,
    mission: Optional[Mapping[str, Any]] = None,
    owner_binding: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Write a portable home vector from current mission/browser coordinates."""
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    page_data = dict(page or _latest_json(sd / "alice_browser_current_page.json"))
    mission_data = dict(mission or _latest_json(sd / "visible_grok_dialogue_mission.json"))
    home_url = _clean(mission_data.get("grok_url") or page_data.get("url"))
    sample = page_landmark_sample({**page_data, "url": home_url or page_data.get("url")})
    landmark_hash = perceptual_hash(sample)
    owner_binding_sha = (
        hashlib.sha256(_clean(owner_binding).encode("utf-8")).hexdigest()
        if _clean(owner_binding)
        else ""
    )
    recent_receipts = _read_recent_receipts(sd)
    recent_hashes = [
        hashlib.sha256(rid.encode("utf-8")).hexdigest()
        for rid in recent_receipts
    ]
    base = {
        "home_url": home_url,
        "home_host": _host(home_url),
        "home_thread_id": grok_thread_id(home_url),
        "global_surface": "Global Chat + alice_conversation",
        "mission_receipt_id": _clean(mission_data.get("start_driver_receipt_id") or mission_data.get("receipt_id")),
        "owner_binding_sha256": owner_binding_sha,
        "landmark_hashes": [landmark_hash],
        "recent_receipt_hashes": recent_hashes,
    }
    vector = BrowserForagerHomeVector(
        home_id=f"home-vector-{uuid.uuid4().hex[:12]}",
        created_ts=time.time(),
        signature_sha256=sign_home_vector(base),
        **base,
    )
    row = vector.as_row()
    row["action"] = "capture_internet_forager_home_vector"
    row["landmark_sample"] = sample
    (sd / _HOME_VECTOR_FILE).write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    for name in (_HOME_VECTOR_LEDGER, "work_receipts.jsonl"):
        try:
            with (sd / name).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass
    return row


def orient_forager(
    *,
    current_page: Optional[Mapping[str, Any]] = None,
    home_vector: Optional[Mapping[str, Any]] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Orient a browser forager relative to its saved hive coordinates."""
    sd = state_dir_path(state_dir)
    page = dict(current_page or _latest_json(sd / "alice_browser_current_page.json"))
    vector = dict(home_vector or load_home_vector(state_dir=sd))
    if not vector:
        return {
            "schema": TRUTH_LABEL,
            "truth_label": TRUTH_LABEL,
            "ok": False,
            "status": "no_home_vector",
            "can_return_home": False,
            "reason": "no portable home vector captured",
        }
    signature_ok = verify_home_vector_signature(vector)
    current_url = _clean(page.get("url"))
    home_url = _clean(vector.get("home_url"))
    current_thread = grok_thread_id(current_url)
    home_thread = _clean(vector.get("home_thread_id"))
    current_host = _host(current_url)
    home_host = _clean(vector.get("home_host"))
    same_thread = bool(home_thread and current_thread == home_thread)
    same_host = bool(home_host and current_host == home_host)
    sample = page_landmark_sample(page)
    sample_hash = perceptual_hash(sample)
    landmark_match = sample_hash in set(vector.get("landmark_hashes") or [])

    confidence = 0.2 if signature_ok else 0.0
    if same_host:
        confidence += 0.35
    if same_thread:
        confidence += 0.35
    if landmark_match:
        confidence += 0.1
    confidence = min(1.0, confidence)

    if not signature_ok:
        status = "spoofed_or_corrupt_home_vector"
        can_return = False
    elif same_thread or (home_url and current_url == home_url):
        status = "home"
        can_return = True
    elif same_host:
        status = "mapped_habitat_off_home_thread"
        can_return = True
    else:
        status = "outside_mapped_territory_portable_home_vector"
        can_return = bool(home_url)

    return {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ok": signature_ok,
        "status": status,
        "can_return_home": can_return,
        "confidence": round(confidence, 4),
        "current_url": current_url,
        "current_host": current_host,
        "current_thread_id": current_thread,
        "home_url": home_url,
        "home_host": home_host,
        "home_thread_id": home_thread,
        "signature_ok": signature_ok,
        "landmark_hash": sample_hash,
        "landmark_match": landmark_match,
        "reason": (
            "at hive coordinates"
            if status == "home"
            else "valid home vector can navigate back to hive coordinates"
            if can_return
            else "home vector failed verification"
        ),
    }


def verify_arrival(
    *,
    current_page: Optional[Mapping[str, Any]] = None,
    home_vector: Optional[Mapping[str, Any]] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Predator-gate arrival check: yellow dot + real hive coordinates."""
    orientation = orient_forager(
        current_page=current_page,
        home_vector=home_vector,
        state_dir=state_dir,
    )
    arrived = bool(orientation.get("signature_ok") and orientation.get("status") == "home")
    return {
        **orientation,
        "arrival_verified": arrived,
        "predator_gate": "admit_returning_forager" if arrived else "hold_forager_at_gate",
    }


def request_return_home(
    *,
    current_page: Optional[Mapping[str, Any]] = None,
    home_vector: Optional[Mapping[str, Any]] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Write Alice Browser's open-url drop to send the forager back home."""
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    orientation = orient_forager(current_page=current_page, home_vector=home_vector, state_dir=sd)
    row = {
        **orientation,
        "ts": time.time(),
        "receipt_id": f"internet-forager-return-{uuid.uuid4().hex[:12]}",
        "action": "request_internet_forager_return_home",
    }
    if orientation.get("can_return_home") and orientation.get("home_url"):
        try:
            (sd / _BROWSER_OPEN_DROP).write_text(str(orientation["home_url"]), encoding="utf-8")
            row["return_command_written"] = True
            row["return_command_file"] = _BROWSER_OPEN_DROP
        except Exception as exc:
            row["return_command_written"] = False
            row["return_error"] = f"{type(exc).__name__}: {exc}"
    else:
        row["return_command_written"] = False
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    for name in (_ORIENTATION_LEDGER, "work_receipts.jsonl"):
        try:
            with (sd / name).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass
    return row


__all__ = [
    "TRUTH_LABEL",
    "BrowserForagerHomeVector",
    "capture_home_vector",
    "load_home_vector",
    "orient_forager",
    "page_landmark_sample",
    "request_return_home",
    "sign_home_vector",
    "state_dir_path",
    "verify_arrival",
    "verify_home_vector_signature",
]

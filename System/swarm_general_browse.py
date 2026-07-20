#!/usr/bin/env python3
"""General untuned browsing receipt organ for r1566.

This module does not browse by itself. It builds the cortex handoff packet for
arbitrary pages after the browser/WebBridge limbs have gathered state. The
receipt makes the open-loop gap explicit: target, requested actions, available
evidence, before/after state hashes, visual/transcript preflight, and whether
the packet is ready for cortex judgment.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - import fallback for standalone probes
    append_line_locked = None  # type: ignore[assignment]

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
TRUTH_LABEL = "GENERAL_BROWSE_RECEIPT_V1"
LEDGER_NAME = "general_browse_receipts.jsonl"
DEPENDENCY_SCAR_LEDGER = "general_browse_dependency_scars.jsonl"
DRESS_LEDGER_NAME = "general_browse_page_dress.jsonl"

_URL_RE = re.compile(r"https?://[^\s)\"'<>]+", re.IGNORECASE)
_GENERAL_BROWSE_RE = re.compile(
    r"\b(?:general[_\s-]?browse|browse[_\s-]?untuned|browse\s+this|look\s+at\s+this\s+page|"
    r"read\s+this\s+page|use\s+this\s+page|give\s+me\s+(?:a\s+)?usable\s+dress|"
    r"arbitrary\s+page|untuned\s+(?:page|site))\b",
    re.IGNORECASE,
)


def _state_dir(path: str | Path | None = None) -> Path:
    if path is None:
        return STATE
    p = Path(path)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def _hash(data: Any) -> str:
    return hashlib.sha256(_stable_json(data).encode("utf-8")).hexdigest()[:16]


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def extract_target_url(text: str) -> str:
    match = _URL_RE.search(text or "")
    return match.group(0).rstrip(".,;") if match else ""


def is_general_browse_request(text: str) -> bool:
    clean = " ".join(str(text or "").split())
    if not clean:
        return False
    if _GENERAL_BROWSE_RE.search(clean):
        return True
    return bool(extract_target_url(clean) and re.search(r"\b(?:browse|read|research|inspect|use|dress)\b", clean, re.I))


def infer_requested_actions(text: str) -> list[str]:
    low = str(text or "").lower()
    actions: list[str] = []
    for key, action in (
        ("read", "read_page"),
        ("summar", "summarize"),
        ("dress", "return_usable_dress"),
        ("click", "click_target"),
        ("press", "click_target"),
        ("search", "search_within_or_from_page"),
        ("find", "find_on_page"),
        ("fill", "fill_form"),
        ("type", "fill_form"),
        ("research", "research"),
    ):
        if key in low and action not in actions:
            actions.append(action)
    return actions or ["read_page", "return_usable_dress"]


def _control_label(control: Mapping[str, Any]) -> str:
    for key in ("label", "text", "name", "aria_label", "title", "placeholder", "value"):
        value = str(control.get(key) or "").strip()
        if value:
            return " ".join(value.split())[:160]
    return ""


def _control_uid(control: Mapping[str, Any]) -> str:
    for key in ("uid", "alice_uid", "data_alice_uid", "id", "ref"):
        value = str(control.get(key) or "").strip()
        if value:
            return value
    return ""


def _normalise_controls(state: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    data = dict(state or {})
    raw: list[Any] = []
    for key in ("visible_controls", "controls", "elements", "clickable", "links"):
        val = data.get(key)
        if isinstance(val, list):
            raw.extend(val)
    seen: set[tuple[str, str, str]] = set()
    controls: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            item_map: Mapping[str, Any] = {"label": item, "role": "button"}
        elif isinstance(item, Mapping):
            item_map = item
        else:
            continue
        label = _control_label(item_map)
        href = str(item_map.get("href") or item_map.get("url") or "").strip()
        uid = _control_uid(item_map)
        role = str(item_map.get("role") or item_map.get("tag") or ("link" if href else "button")).strip().lower()
        if not label and not href and not uid:
            continue
        sig = (label.lower(), href, uid)
        if sig in seen:
            continue
        seen.add(sig)
        controls.append(
            {
                "label": label or href or uid,
                "role": role,
                "uid": uid,
                "href": href,
                "selector": str(item_map.get("selector") or ""),
                "placeholder": str(item_map.get("placeholder") or ""),
                "text": str(item_map.get("text") or "")[:240],
            }
        )
    return controls[:80]


def build_page_dress(
    owner_text: str,
    *,
    page_state: Mapping[str, Any] | None = None,
    target_url: str = "",
) -> dict[str, Any]:
    """Return a general action map for any website from page-state evidence."""
    data = dict(page_state or {})
    target = target_url or str(data.get("url") or extract_target_url(owner_text) or "")
    text = str(data.get("article_text") or data.get("text") or data.get("visible_text") or "")
    headings = [str(h).strip() for h in (data.get("headings") or []) if str(h).strip()][:12]
    controls = _normalise_controls(data)
    low_owner = str(owner_text or "").lower()
    control_rows: list[dict[str, Any]] = []
    search_rows: list[dict[str, Any]] = []
    form_rows: list[dict[str, Any]] = []
    nav_rows: list[dict[str, Any]] = []
    click_rows: list[dict[str, Any]] = []

    for control in controls:
        label_low = f"{control.get('label', '')} {control.get('placeholder', '')} {control.get('role', '')}".lower()
        row = {
            "label": control.get("label", ""),
            "role": control.get("role", ""),
            "uid": control.get("uid", ""),
            "selector": control.get("selector", ""),
            "href": control.get("href", ""),
        }
        control_rows.append(row)
        if any(token in label_low for token in ("search", "find", "query", "q=")):
            search_rows.append(row)
        if any(token in label_low for token in ("input", "textbox", "textarea", "email", "password", "name", "field", "search")):
            form_rows.append(row)
        if control.get("href") or control.get("role") in {"link", "a"}:
            nav_rows.append(row)
        if control.get("uid") or control.get("selector") or control.get("href"):
            click_rows.append(row)

    requested = infer_requested_actions(owner_text)
    if "search" in low_owner and not search_rows:
        search_rows = form_rows[:3]
    if any(k in low_owner for k in ("click", "press", "open", "select")) and not click_rows:
        click_rows = control_rows[:8]

    can_read = bool(text.strip() or headings or data.get("article_text_chars") or data.get("text_chars"))
    missing: list[str] = []
    if not target:
        missing.append("target_url")
    if not can_read:
        missing.append("readable_text")
    if not control_rows:
        missing.append("affordance_controls")
    if any(action in requested for action in ("click_target", "fill_form", "search_within_or_from_page")) and not click_rows:
        missing.append("click_or_fill_targets")

    return {
        "schema": "GENERAL_BROWSE_PAGE_DRESS_V1",
        "truth_label": "GENERAL_BROWSE_PAGE_DRESS_V1",
        "target_url": target,
        "title": str(data.get("title") or "")[:160],
        "domain": str(data.get("domain") or ""),
        "fresh": bool(data.get("fresh", True)),
        "requested_actions": requested,
        "readable": {
            "can_read": can_read,
            "text_chars": len(text) or int(data.get("text_chars") or data.get("article_text_chars") or 0),
            "headings": headings,
            "summary_seed": " ".join(text.split())[:500],
        },
        "affordances": {
            "controls_count": len(control_rows),
            "controls": control_rows[:20],
            "search_fields": search_rows[:8],
            "form_fields": form_rows[:8],
            "navigation_links": nav_rows[:12],
            "click_targets": click_rows[:12],
        },
        "next_action_hint": (
            "read_page" if can_read and requested == ["read_page", "return_usable_dress"]
            else "use_uid_or_selector_targets" if click_rows
            else "re_read_page_state"
        ),
        "missing_for_closed_loop": missing,
        "ready_for_general_browse": bool(target and (can_read or control_rows)),
    }


def record_page_dress(
    owner_text: str,
    *,
    page_state: Mapping[str, Any] | None = None,
    target_url: str = "",
    state_dir: str | Path | None = None,
    write: bool = True,
    now: float | None = None,
) -> dict[str, Any]:
    ts = time.time() if now is None else float(now)
    dress = build_page_dress(owner_text, page_state=page_state, target_url=target_url)
    row = {
        **dress,
        "ts": ts,
        "receipt_id": f"general-dress-{uuid.uuid4().hex[:12]}",
        "owner_text": str(owner_text or "")[:500],
        "action": "general_browse_page_dress",
        "kind": "GENERAL_BROWSE_PAGE_DRESS",
    }
    if write:
        sd = _state_dir(state_dir)
        sd.mkdir(parents=True, exist_ok=True)
        line = _stable_json(row) + "\n"
        if append_line_locked is not None:
            append_line_locked(sd / DRESS_LEDGER_NAME, line)
            append_line_locked(sd / "work_receipts.jsonl", line)
        else:
            with (sd / DRESS_LEDGER_NAME).open("a", encoding="utf-8") as handle:
                handle.write(line)
    return row


def page_state_digest(state: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(state or {})
    elements = data.get("elements") or data.get("clickable") or []
    if not isinstance(elements, list):
        elements = []
    text = str(data.get("text") or data.get("visible_text") or "")
    return {
        "hash": _hash(data),
        "url": str(data.get("url") or ""),
        "title": str(data.get("title") or "")[:160],
        "element_count": len(elements),
        "text_chars": len(text),
        "has_pixels": bool(data.get("screenshot") or data.get("image") or data.get("viewport_image")),
    }


def _image_path_from_state(state: Mapping[str, Any] | None, *, state_dir: str | Path | None = None) -> Path | None:
    data = dict(state or {})
    for key in ("viewport_image", "screenshot", "screenshot_path", "image", "image_ref"):
        value = str(data.get(key) or "").strip()
        if not value:
            continue
        path = Path(value)
        if not path.is_absolute():
            path = _state_dir(state_dir) / path
        if path.exists():
            return path
    return None


def build_pixelrag_vlm_evidence(
    *,
    after_state: Mapping[str, Any] | None = None,
    owner_text: str = "",
    target_url: str = "",
    state_dir: str | Path | None = None,
    write: bool = True,
    now: float | None = None,
) -> dict[str, Any]:
    """Produce a visual evidence receipt from the rendered page screenshot when available."""
    image_path = _image_path_from_state(after_state, state_dir=state_dir)
    if image_path is None:
        return {
            "schema": "GENERAL_BROWSE_PIXELRAG_VLM_EVIDENCE_V1",
            "status": "no_viewport_image",
            "observed": False,
            "target_url": target_url,
            "source": "general_browse",
        }
    try:
        from System.swarm_body_screen_eye import record_body_screen_eye

        row = record_body_screen_eye(
            image_path=image_path,
            source="general_browse_viewport_image",
            owner_claim=str(owner_text or "")[:500],
            scene_label=f"General browse visual evidence for {target_url or image_path.name}",
            state_dir=_state_dir(state_dir),
            write=write,
            now=now,
        )
        return {
            "schema": "GENERAL_BROWSE_PIXELRAG_VLM_EVIDENCE_V1",
            "status": "visual_evidence_recorded" if row.get("observed") else "visual_evidence_unobserved",
            "observed": bool(row.get("observed")),
            "target_url": target_url,
            "source": "body_screen_eye",
            "trace_id": row.get("trace_id"),
            "image": row.get("image") if isinstance(row.get("image"), dict) else {},
            "ledger": row.get("ledger", "body_screen_eye_receipts.jsonl"),
        }
    except Exception as exc:
        return {
            "schema": "GENERAL_BROWSE_PIXELRAG_VLM_EVIDENCE_V1",
            "status": "visual_evidence_error",
            "observed": False,
            "target_url": target_url,
            "source": "body_screen_eye",
            "error": f"{type(exc).__name__}: {exc}",
        }


def dependency_preflight() -> dict[str, Any]:
    whisper_available = _has_module("whisper") or _has_module("faster_whisper")
    return {
        "browser_page_state": _has_module("System.swarm_browser_page_state"),
        "web_reflex_loop": _has_module("System.swarm_web_reflex_loop"),
        "webbridge": _has_module("System.swarm_kimi_webbridge_bridge"),
        "whisper": whisper_available,
        "whisper_modules": {
            "openai_whisper": _has_module("whisper"),
            "faster_whisper": _has_module("faster_whisper"),
        },
        "pixelrag_vlm": {
            "pil": _has_module("PIL"),
            "cv2": _has_module("cv2"),
            "body_screen_eye": _has_module("System.swarm_body_screen_eye"),
        },
    }


def record_dependency_preflight_scar(
    *,
    state_dir: str | Path | None = None,
    write: bool = True,
    now: float | None = None,
) -> dict[str, Any]:
    """Persist the missing transcript/VLM legs as an honest r1568 scar."""
    ts = time.time() if now is None else float(now)
    preflight = dependency_preflight()
    missing: list[str] = []
    if not preflight.get("whisper"):
        missing.append("whisper_transcript_leg")
    pixelrag = preflight.get("pixelrag_vlm") or {}
    if not (isinstance(pixelrag, Mapping) and pixelrag.get("body_screen_eye") and (pixelrag.get("pil") or pixelrag.get("cv2"))):
        missing.append("pixelrag_vlm_evidence_leg")
    scar = {
        "schema": "GENERAL_BROWSE_DEPENDENCY_SCAR_V1",
        "truth_label": "GENERAL_BROWSE_DEPENDENCY_SCAR_V1",
        "ts": ts,
        "receipt_id": f"general-browse-scar-{uuid.uuid4().hex[:12]}",
        "intent": "general_browse_dependency_preflight",
        "missing": missing,
        "preflight": preflight,
        "status": "scar_recorded" if missing else "dependencies_present",
        "next_steps": [
            "Install/enable Whisper or faster-whisper for transcript evidence.",
            "Enable the stronger PixelRAG/VLM evidence producer for page screenshots.",
            "Do not claim transcript or VLM-backed browsing evidence until this scar clears.",
        ]
        if missing
        else [],
    }
    if write:
        sd = _state_dir(state_dir)
        sd.mkdir(parents=True, exist_ok=True)
        line = _stable_json(scar) + "\n"
        path = sd / DEPENDENCY_SCAR_LEDGER
        if append_line_locked is not None:
            append_line_locked(path, line)
            append_line_locked(sd / "work_receipts.jsonl", line)
        else:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
    return scar


def build_general_browse_receipt(
    owner_text: str,
    *,
    target_url: str = "",
    before_state: Mapping[str, Any] | None = None,
    after_state: Mapping[str, Any] | None = None,
    evidence_sources: list[str] | None = None,
    state_dir: str | Path | None = None,
    write: bool = True,
    now: float | None = None,
) -> dict[str, Any]:
    """Build and optionally persist a r1566 general browsing cortex packet."""
    ts = time.time() if now is None else float(now)
    target = (target_url or extract_target_url(owner_text) or "").strip()
    before = page_state_digest(before_state)
    after = page_state_digest(after_state)
    changed = before["hash"] != after["hash"] if before_state is not None and after_state is not None else False
    actions = infer_requested_actions(owner_text)
    preflight = dependency_preflight()
    sources = evidence_sources or [
        "browser_page_state",
        "web_reflex_loop",
        "webbridge_uid_snapshot",
        "pixelrag_vlm_preflight",
        "whisper_preflight",
    ]
    visual_evidence = build_pixelrag_vlm_evidence(
        after_state=after_state,
        owner_text=owner_text,
        target_url=target,
        state_dir=state_dir,
        write=write,
        now=ts,
    )
    if visual_evidence.get("observed") and "pixelrag_vlm_evidence" not in sources:
        sources.append("pixelrag_vlm_evidence")
    page_dress = record_page_dress(
        owner_text,
        page_state=after_state,
        target_url=target,
        state_dir=state_dir,
        write=write,
        now=ts,
    )
    if page_dress.get("ready_for_general_browse") and "general_page_dress" not in sources:
        sources.append("general_page_dress")
    ready = bool(target and actions and sources)
    receipt = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": ts,
        "receipt_id": f"general-browse-{uuid.uuid4().hex[:12]}",
        "owner_text": str(owner_text or "")[:500],
        "intent": "general_browse",
        "aliases": ["general_browse", "browse_untuned"],
        "target_url": target,
        "requested_actions": actions,
        "evidence_sources": sources,
        "preflight": preflight,
        "visual_evidence": visual_evidence,
        "page_dress": page_dress,
        "closed_loop": {
            "before": before,
            "after": after,
            "changed": changed,
            "status": "before_after_diff" if changed else "needs_after_state" if after_state is None else "no_visible_change",
        },
        "ready_for_cortex": ready,
        "cortex_instruction": (
            "Judge from the page dress/evidence and closed-loop diff. Do not claim browsing success "
            "unless target_url, evidence_sources, and after-state receipts support it."
        ),
    }
    if write:
        sd = _state_dir(state_dir)
        sd.mkdir(parents=True, exist_ok=True)
        line = _stable_json(receipt) + "\n"
        path = sd / LEDGER_NAME
        if append_line_locked is not None:
            append_line_locked(path, line)
            append_line_locked(sd / "work_receipts.jsonl", line)
        else:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
    return receipt


def latest_general_browse_receipts(limit: int = 5, *, state_dir: str | Path | None = None) -> list[dict[str, Any]]:
    path = _state_dir(state_dir) / LEDGER_NAME
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def latest_page_dress_receipts(limit: int = 5, *, state_dir: str | Path | None = None) -> list[dict[str, Any]]:
    path = _state_dir(state_dir) / DRESS_LEDGER_NAME
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


__all__ = [
    "TRUTH_LABEL",
    "DEPENDENCY_SCAR_LEDGER",
    "DRESS_LEDGER_NAME",
    "build_page_dress",
    "build_general_browse_receipt",
    "build_pixelrag_vlm_evidence",
    "dependency_preflight",
    "extract_target_url",
    "infer_requested_actions",
    "is_general_browse_request",
    "latest_general_browse_receipts",
    "latest_page_dress_receipts",
    "page_state_digest",
    "record_page_dress",
    "record_dependency_preflight_scar",
]

#!/usr/bin/env python3
"""Browser photo description — Alice describes the actual PHOTO on the page.

George 2026-05-30, co-browsing Instagram reference photos: r180 gave Alice the
page TEXT/DOM (headings, links, alts), but on Instagram the alts are weak and she
still could not say what the reference photo actually shows — pose, scene, clothing,
lighting. She diagnosed it herself live: "without DOM image descriptions and viewport
captioning in my browser page-state receipt, I am blind to the contents of the
reference images you show me."

This organ stores Alice's OWN rich description of the featured image(s) on the page,
produced by the vision arm she picked (swarm_cortex_capabilities.pick_vision_arm —
default = current cortex, failover when it cannot see or its API died). Provenance is
explicit (§6): which arm saw it, the image hash, the viewport vs the photo, freshness.
This is separate from DOM alt text (often marketing fluff) — it is what her eye reports.

Pure + file-backed; sandbox-testable. The live viewport grab + arm dispatch live in
the Alice Browser widget and call record_photo_description with the result.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = "browser_photo_descriptions.jsonl"
TRUTH_LABEL = "BROWSER_PHOTO_DESCRIPTION_V1"

_DESC_CHARS = 1200


_AVATAR_NEEDLES = ("avatar", "profile_pic", "profile-pic", "icon", "emoji", "sprite",
                   "favicon", "logo", "/s150x150/", "/s320x320/")


_MIN_ONSCREEN_AREA = 40000  # ~200x200 visible px before we trust an on-screen image


def pick_featured_image(
    candidates: list[dict] | tuple[dict, ...] = (), *, og_image: str = "",
) -> dict[str, Any]:
    """Choose the photo Alice should describe.

    Priority (George 2026-05-30 carousel/stale fix):
      1. The image actually VISIBLE ON SCREEN now — largest by on-screen area
         (candidate ``onscreen`` = visible px). This follows carousel swipes and
         avoids Instagram's og:image, which does NOT update on client-side nav and
         kept her describing a stale cover photo.
      2. og:image meta (only when nothing is meaningfully on screen).
      3. Largest non-avatar image by natural pixel area.
    Each candidate: {src, alt, w, h, onscreen?}. Returns {} when nothing qualifies."""
    def _ok(src: str) -> bool:
        low = src.lower()
        return bool(src) and not src.startswith("data:") and not any(n in low for n in _AVATAR_NEEDLES)

    # 1) On-screen visible image wins.
    best_vis = None
    best_vis_area = 0
    for c in candidates or []:
        if not isinstance(c, dict):
            continue
        src = str(c.get("src") or "").strip()
        if not _ok(src):
            continue
        try:
            area = int(c.get("onscreen") or 0)
        except Exception:
            area = 0
        if area > best_vis_area:
            best_vis_area = area
            best_vis = {"src": src, "alt": str(c.get("alt") or ""),
                        "reason": "largest_on_screen_image", "onscreen": area}
    if best_vis and best_vis_area >= _MIN_ONSCREEN_AREA:
        return best_vis

    # 2) og:image only when nothing real is on screen.
    og = str(og_image or "").strip()
    if og:
        return {"src": og, "reason": "og:image_meta", "w": 0, "h": 0}

    # 3) Largest non-avatar image by natural area.
    best = None
    best_area = 0
    for c in candidates or []:
        if not isinstance(c, dict):
            continue
        src = str(c.get("src") or "").strip()
        if not _ok(src):
            continue
        try:
            w, h = int(c.get("w") or 0), int(c.get("h") or 0)
        except Exception:
            w, h = 0, 0
        if w and h and (w < 200 or h < 200):
            continue
        area = (w * h) if (w and h) else 1
        if area > best_area:
            best_area, best = area, {"src": src, "alt": str(c.get("alt") or ""),
                                     "w": w, "h": h, "reason": "largest_non_avatar_image"}
    return best or {}


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


def _strip_blobs(text: str) -> str:
    """Remove base64 image data and other long blobs that should never reach chat."""
    t = _strip_ansi(text or "")
    t = re.sub(r"data:image/[^\s\"']+", "[image]", t)
    t = re.sub(r"[A-Za-z0-9+/]{200,}={0,2}", "[blob]", t)
    return t.strip()


_NON_VISUAL_ARM_REPLY_RE = re.compile(
    r"\b(?:can\s+you|could\s+you|please)\b.{0,80}"
    r"\b(?:describe|provide|upload|attach|share)\b.{0,120}"
    r"\b(?:image|photo|picture|screenshot|viewport|contents?)\b"
    r"|\b(?:provide|send|share)\b.{0,80}\b(?:image|photo|picture|screenshot|viewport|contents?)\b"
    r"|\b(?:i['’]?ve|i\s+have)\s+read\s+the\s+full\s+`?ide_boot_covenant\.md`?\b",
    re.IGNORECASE,
)


def _looks_like_cli_prompt_echo(text: str) -> bool:
    """True when a vision arm returned its CLI/session prompt, not a pixel caption."""
    raw = _strip_ansi(str(text or ""))
    if not raw:
        return False
    low = raw.casefold()
    has_cli = (
        "openai codex v" in low
        or "reading additional input from stdin" in low
        or ("workdir:" in low and "model:" in low and "provider:" in low)
    )
    has_image_prompt = (
        "look at the image at this exact path" in low
        or "alice browser's rendered viewport" in low
        or "describe the main subject of the photo" in low
    )
    if has_cli and has_image_prompt:
        return True
    return bool(has_image_prompt and "read /users/ioanganton/music/anton_sifta/documents/ide_boot_covenant.md" in low)


def _extract_codex_cli_final_text(text: str) -> Optional[str]:
    """Return Codex CLI final text, or ``None`` when this is not Codex CLI output.

    Failed Codex eye runs can echo the whole CLI session and original image prompt
    without an assistant/final answer. That must be a failed sight receipt, not a
    1200-character "description" made from terminal chatter.

    r534: successful Codex CLI runs can print their final answer under a plain
    ``codex`` speaker marker instead of an ``assistant``/``final`` marker. The
    raw transcript still contains the original image prompt, so callers must be
    able to extract the last Codex answer before prompt-echo detection runs.
    """
    raw = _strip_ansi(str(text or ""))
    low = raw.casefold()
    has_codex_speaker_marker = bool(re.search(r"(?im)^\s*codex\s*$", raw))
    if (
        "openai codex v" not in low
        and "reading additional input from stdin" not in low
        and not ("workdir:" in low and "model:" in low and "provider:" in low)
        and not has_codex_speaker_marker
    ):
        return None

    markers = list(re.finditer(r"(?im)^(?:assistant|final)\s*$", raw))
    if markers:
        tail = raw[markers[-1].end():].strip()
        tail = re.split(r"(?m)^[-]{6,}\s*$|^(?:user|system)\s*$", tail, maxsplit=1)[0].strip()
        if tail and not _looks_like_cli_prompt_echo(tail):
            return tail

    chunks: list[str] = []
    lines = raw.splitlines()
    i = 0
    stop_markers = {"codex", "user", "system", "assistant", "final", "tokens used"}
    while i < len(lines):
        if lines[i].strip().casefold() != "codex":
            i += 1
            continue
        i += 1
        buf: list[str] = []
        while i < len(lines):
            marker = lines[i].strip().casefold()
            if marker in stop_markers or re.fullmatch(r"-{6,}", marker or ""):
                break
            buf.append(lines[i])
            i += 1
        chunk = "\n".join(buf).strip()
        chunk = re.split(r"(?im)^\s*tokens used\s*$", chunk, maxsplit=1)[0].strip()
        if chunk and not _looks_like_cli_prompt_echo(chunk):
            chunks.append(chunk)
        continue
    if chunks:
        for candidate in reversed(chunks):
            compact = " ".join(candidate.casefold().split())
            if "covenant" in compact and compact.startswith(("i've read", "i’ve read", "i have read", "covenant read")):
                continue
            return candidate
        return chunks[-1]

    return ""


def looks_like_non_visual_arm_reply(text: str) -> bool:
    """True when an arm answered the prompt text but did not inspect pixels."""
    raw = _strip_ansi(str(text or ""))
    if _looks_like_cli_prompt_echo(raw):
        return True
    clean = " ".join(raw.split())
    if not clean:
        return False
    return bool(_NON_VISUAL_ARM_REPLY_RE.search(clean))


def clean_browser_photo_description_text(raw: str) -> str:
    """Pull a direct, neutral browser-photo answer from a vision arm's output."""
    clean = extract_arm_final_text(raw)
    if not clean:
        return ""
    clean = re.sub(
        r"^\s*since you asked for (?:a )?(?:detailed )?description of (?:her|his|their|the)\s+",
        "",
        clean,
        flags=re.IGNORECASE,
    ).strip()
    clean = re.sub(r"\bradical clothes\b", "visible clothing", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\bradical clothing\b", "visible clothing", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def extract_arm_final_text(raw: str) -> str:
    """Pull ONLY the final clean description from a vision arm's output.

    George 2026-05-30: Alice dumped the whole cline NDJSON stream (every token
    event + the base64 image) into chat. Arms like cline/claude stream NDJSON; the
    final answer is in the `run_result`/`done`/last `content_end` line. Plain-text
    arms pass straight through. Either way, strip base64 and long blobs so only the
    human-readable description reaches the body."""
    s = str(raw or "").strip()
    if not s:
        return ""
    codex_final = _extract_codex_cli_final_text(s)
    if codex_final is not None:
        return _strip_blobs(codex_final)
    looks_streamed = "\n" in s and ('"type"' in s or '"hookEventName"' in s or '"ts"' in s)
    if not looks_streamed:
        return _strip_blobs(s)
    final = ""
    for line in s.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        # cline NDJSON
        if obj.get("type") == "run_result" and obj.get("text"):
            final = str(obj["text"])
        ev = obj.get("event") if isinstance(obj.get("event"), dict) else {}
        if ev.get("type") == "done" and ev.get("text"):
            final = str(ev["text"])
        if (ev.get("type") == "content_end" and ev.get("contentType") == "text"
                and ev.get("text") and len(str(ev["text"])) > len(final)):
            final = str(ev["text"])
        # Claude Code CLI stream-json: final answer is the `result` event; partial
        # answers are assistant message text blocks (George 2026-05-30: claude_agent
        # succeeded but its format wasn't parsed, so the right description was lost).
        if obj.get("type") == "result" and obj.get("result"):
            final = str(obj["result"])
        if obj.get("type") == "assistant":
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
            for blk in (msg.get("content") or []):
                if isinstance(blk, dict) and blk.get("type") == "text" and blk.get("text"):
                    t = str(blk["text"])
                    if len(t) > len(final):
                        final = t
    return _strip_blobs(final)


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _domain(url: str) -> str:
    try:
        return urlparse(url or "").netloc
    except Exception:
        return ""


def _hash(*parts: str) -> str:
    raw = "|".join(p or "" for p in parts)
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:16]


def _append(state_dir: Optional[Path | str], row: dict[str, Any]) -> None:
    path = _state(state_dir) / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _rows(state_dir: Optional[Path | str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with (_state(state_dir) / LEDGER).open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        return []
    return out


# ── Carousel frame epoch (George r212) ───────────────────────────────────────
# An Instagram carousel has ONE url for MANY frames. A photo description is keyed
# by url, so the cover frame's description (e.g. "reclining, floral shorts, tiara")
# was recited for EVERY frame of the same post — including a later frame the owner
# swiped to (e.g. "standing in pink flared pants"). The epoch fixes this: every
# carousel advance / navigation stamps a frame-change time; a description is only
# "current" if it was recorded AT OR AFTER the last frame change. If the owner moved
# frames since I last looked, I must NOT recite the old frame — I say I haven't looked
# at this frame yet.
_FRAME_EPOCH_FILE = "browser_frame_epoch.json"


def mark_frame_changed(
    *, url: str = "", now: Optional[float] = None, state_dir: Optional[Path | str] = None,
) -> float:
    """Stamp that the on-screen frame just changed (carousel next / navigation)."""
    ts = float(now if now is not None else time.time())
    path = _state(state_dir) / _FRAME_EPOCH_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"ts": ts, "url": str(url or "")}), encoding="utf-8")
    except Exception:
        pass
    return ts


def frame_epoch(*, state_dir: Optional[Path | str] = None) -> float:
    """Time of the last frame change, or 0.0 if none recorded."""
    try:
        data = json.loads((_state(state_dir) / _FRAME_EPOCH_FILE).read_text(encoding="utf-8"))
        return float(data.get("ts", 0) or 0)
    except Exception:
        return 0.0


def record_photo_description(
    url: str,
    *,
    description: str,
    arm: str,
    image_hash: str = "",
    image_ref: str = "",
    status: str = "described",
    source: str = "viewport",
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Record Alice's eye-report of the featured photo on a page.

    ``status``: "described" (arm returned a real description), "pending"
    (viewport captured, arm not finished), or "failed" (arm could not see).
    ``source``: "viewport" (rendered pixels her arm saw) vs "dom_alt" (weak alt).
    """
    ts = float(now if now is not None else time.time())
    description = str(description or "")
    row = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "kind": "photo_description",
        "url": str(url or ""),
        "domain": _domain(url),
        "arm": str(arm or ""),
        "source": source,
        "status": status,
        "image_hash": str(image_hash or ""),
        "image_ref": str(image_ref or ""),
        "description": description[:_DESC_CHARS],
        "desc_chars": len(description),
        "content_hash": _hash(str(url or ""), description[:400], str(arm or "")),
    }
    _append(state_dir, row)
    return row


def latest_photo_description(
    *, url: Optional[str] = None, now: Optional[float] = None, max_age_s: float = 300.0,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Freshest described photo (optionally for a specific url) with freshness."""
    rows = [
        r for r in _rows(state_dir)
        if r.get("status") == "described"
        and r.get("description")
        and not looks_like_non_visual_arm_reply(str(r.get("description") or ""))
    ]
    if url:
        rows = [r for r in rows if r.get("url") == url]
    if not rows:
        return {}
    row = max(rows, key=lambda r: float(r.get("ts", 0) or 0))
    t = float(now if now is not None else time.time())
    ts = float(row.get("ts", 0) or 0)
    age = max(0.0, t - ts) if ts else None
    out = dict(row)
    out["age_s"] = round(age, 1) if age is not None else None
    out["fresh"] = bool(age is not None and age <= max_age_s)
    # Carousel frame epoch (r212): if the owner swiped to a different frame AFTER this
    # description was recorded, it describes a frame that is no longer on screen.
    epoch = frame_epoch(state_dir=state_dir)
    out["frame_stale"] = bool(epoch and ts < epoch)
    return out


def latest_viewport_capture(
    *, url: Optional[str] = None, now: Optional[float] = None, max_age_s: float = 900.0,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Freshest rendered-viewport image receipt, even before a vision arm described it.

    Alice Browser records ``status="pending"`` rows whenever it grabs the WebEngine
    viewport. Talk can use this as a bridge when it needs pixels for a paused video
    still-frame but cannot call the live browser widget directly in-process.
    """
    rows = [
        r for r in _rows(state_dir)
        if r.get("image_ref") and "viewport" in str(r.get("source") or "").lower()
    ]
    if url:
        rows = [r for r in rows if r.get("url") == url]
    if not rows:
        return {}
    row = max(rows, key=lambda r: float(r.get("ts", 0) or 0))
    t = float(now if now is not None else time.time())
    ts = float(row.get("ts", 0) or 0)
    age = max(0.0, t - ts) if ts else None
    out = dict(row)
    out["age_s"] = round(age, 1) if age is not None else None
    out["fresh"] = bool(age is not None and age <= max_age_s)
    epoch = frame_epoch(state_dir=state_dir)
    out["frame_stale"] = bool(epoch and ts < epoch)
    try:
        out["image_exists"] = Path(str(out.get("image_ref") or "")).exists()
    except Exception:
        out["image_exists"] = False
    return out


def latest_same_url_photo_description(
    *, url: str, now: Optional[float] = None, max_age_s: float = 7200.0,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Freshest described receipt for exactly this URL, never falling back elsewhere.

    This is the repair path for selected-eye failures. If the fresh arm fails but a
    same-URL photo was described moments earlier, Alice may answer from that anchored
    receipt while being explicit that it is not a fresh scan. Cross-URL fallback stays
    forbidden because that is how stale Instagram photos bled into current answers.
    """
    p = latest_photo_description(url=url, now=now, max_age_s=max_age_s, state_dir=state_dir)
    if not p or p.get("frame_stale"):
        return {}
    p["same_url_anchor"] = True
    return p


def photo_description_block(
    *, url: Optional[str] = None, now: Optional[float] = None, max_age_s: float = 300.0,
    state_dir: Optional[Path | str] = None,
) -> str:
    """First-person: what the actual photo on the page shows, by Alice's own eye."""
    p = latest_photo_description(url=url, now=now, max_age_s=max_age_s, state_dir=state_dir)
    if p and p.get("frame_stale"):
        # The owner moved to a different carousel frame since I last looked — do NOT
        # recite the old frame (r212). Be honest that I have not seen this one yet.
        return ("THE PHOTO ON MY SCREEN: the carousel moved to a different frame than the one I last "
                "described — I have NOT looked at the frame currently on screen. I will not recite the "
                "previous frame; ask me to describe this one and I will look with my vision arm.")
    if not p:
        return ("THE PHOTO ON MY SCREEN: I have not described the featured image yet — my browser "
                "captured the page but my vision arm has not reported the photo's contents. I will not "
                "invent what it shows; I should look with one of my vision arms.")
    arm = p.get("arm") or "a vision arm"
    age = p.get("age_s")
    stamp = f" ~{int(age)}s ago" if age is not None else ""
    staleness = "" if p.get("fresh") else " (this may be stale — I should look again)"
    return (f"THE PHOTO ON MY SCREEN (seen by my {arm}{stamp}, from the rendered viewport{staleness}): "
            f"{p.get('description')}")


__all__ = [
    "TRUTH_LABEL",
    "clean_browser_photo_description_text",
    "extract_arm_final_text",
    "pick_featured_image",
    "record_photo_description",
    "latest_photo_description",
    "latest_viewport_capture",
    "latest_same_url_photo_description",
    "photo_description_block",
    "mark_frame_changed",
    "frame_epoch",
]

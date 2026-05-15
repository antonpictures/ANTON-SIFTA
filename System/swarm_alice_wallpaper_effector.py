#!/usr/bin/env python3
"""
swarm_alice_wallpaper_effector.py
=================================

Receipt-bearing wallpaper effector for Alice.

This module is intentionally independent of the Talk widget and the desktop
Qt classes. The cortex-gated router can call it after owner confirmation; the
organ then searches, validates, saves, applies by filesystem state, and writes
append-only receipts.

Truth boundary: this changes local SIFTA wallpaper files/state. It does not
claim web-image provenance beyond the fetched URL, MIME, size, and content hash.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import struct
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - fallback for isolated import tests
    append_line_locked = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
PICTURES_DIR = REPO_ROOT / "Library" / "Desktop Pictures"
WEB_FETCHED_DIR = PICTURES_DIR / "web_fetched"
CHAT_WALLPAPER_PATH = PICTURES_DIR / "CHAT.jpg"
WALLPAPER_LEDGER = STATE_DIR / "wallpaper_changes.jsonl"
BLOCKLIST_PATH = REPO_ROOT / "System" / "swarm_network_blocklist.txt"

TRUTH_LABEL = "WALLPAPER_EFFECTOR_V1"
SEARCH_ENGINE = "duckduckgo_html"
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MIN_DIMENSION = 256
MAX_DIMENSION = 4096
DEFAULT_SURPRISE_QUERY = "beautiful bee swarm digital field wallpaper"
STGM_COST = 0.50

TARGETS = {"chat", "desktop", "both"}


@dataclass(frozen=True)
class WallpaperIntent:
    action: str
    query: str = ""
    target: str = "both"
    raw_text: str = ""


@dataclass(frozen=True)
class WallpaperCandidate:
    url: str
    source: str = SEARCH_ENGINE
    title: str = ""


@dataclass
class WallpaperResult:
    ok: bool
    status: str
    receipt_id: str
    target: str
    query: str
    saved_path: str = ""
    chosen_url: str = ""
    content_sha256: str = ""
    mime: str = ""
    bytes: int = 0
    width: int = 0
    height: int = 0
    previous_desktop_path: Optional[str] = None
    previous_chat_backup_path: Optional[str] = None
    dry_run: bool = False
    truth_boundary: str = (
        "local wallpaper effector only; no claim about image content beyond fetched URL, MIME, size, dimensions, and hash"
    )
    error: str = ""


class WallpaperEffectorError(RuntimeError):
    """Raised for expected effecter validation failures."""


def _now() -> float:
    return time.time()


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, sort_keys=True)
    if append_line_locked is not None:
        append_line_locked(path, line + "\n")
    else:  # pragma: no cover
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def _read_blocklist(path: Path = BLOCKLIST_PATH) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip().lower()
        if clean and not clean.startswith("#"):
            out.add(clean)
    return out


def _domain(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise WallpaperEffectorError("scheme_not_allowed")
    if not parsed.netloc:
        raise WallpaperEffectorError("missing_domain")
    return parsed.netloc.split(":", 1)[0].lower()


def _domain_blocked(url: str, blocklist: set[str]) -> bool:
    host = _domain(url)
    return any(host == blocked or host.endswith("." + blocked) for blocked in blocklist)


def parse_wallpaper_intent(text: str) -> Optional[WallpaperIntent]:
    """Parse owner natural language into a wallpaper intent.

    This is a deterministic gate, not an LLM. The router still has to confirm
    owner audience before passing the intent to the effector.
    """

    raw = text or ""
    s = " ".join(raw.strip().split())
    if not s:
        return None
    low = s.lower()

    if "wallpaper" in low or "background" in low or "desktop image" in low:
        if re.search(r"\b(undo|revert|go back|back to previous|restore)\b", low):
            return WallpaperIntent(action="undo_wallpaper", target=_target_from_text(low), raw_text=raw)

    trigger = re.search(r"\b(wallpaper|background|desktop image|chat image)\b", low)
    verb = re.search(r"\b(change|set|make|switch|update|put|give|fetch|find|grab)\b", low)
    if not (trigger and verb):
        return None

    target = _target_from_text(low)
    query = ""
    patterns = [
        r"(?:wallpaper|background|desktop image|chat image)\s+(?:to|as|for|of)\s+(.+)$",
        r"(?:change|set|make|switch|update|put|give|fetch|find|grab).{0,60}?(?:to|as|for|of)\s+(.+)$",
    ]
    for pat in patterns:
        m = re.search(pat, s, flags=re.IGNORECASE)
        if m:
            query = m.group(1).strip()
            break

    if not query and re.search(r"\b(surprise me|whatever|anything)\b", low):
        query = DEFAULT_SURPRISE_QUERY
    query = _clean_query(query)
    if not query:
        query = DEFAULT_SURPRISE_QUERY

    return WallpaperIntent(action="set_wallpaper", query=query, target=target, raw_text=raw)


def _target_from_text(low: str) -> str:
    has_chat = "chat" in low or "conversation" in low
    has_desktop = "desktop" in low or "launcher" in low or "os " in low
    if has_chat and not has_desktop:
        return "chat"
    if has_desktop and not has_chat:
        return "desktop"
    return "both"


def _clean_query(query: str) -> str:
    q = query.strip().strip(" .,!?:;\"'")
    q = re.sub(r"^(please|pls|alice)\b[:, ]*", "", q, flags=re.IGNORECASE).strip()
    q = re.sub(r"\b(only the chat|only chat|only the desktop|only desktop|for both|both)\b", "", q, flags=re.IGNORECASE)
    q = re.sub(r"\s+", " ", q).strip(" .,!?:;\"'")
    return q


def search_duckduckgo_images(
    query: str,
    *,
    opener: Optional[Callable[[urllib.request.Request, float], bytes]] = None,
    max_results: int = 8,
) -> list[WallpaperCandidate]:
    """Return image candidates from DuckDuckGo without an API key.

    The primary path uses DuckDuckGo's image JSON endpoint after obtaining
    `vqd` from the public page. A static HTML fallback scrapes direct image
    URLs from result markup. Tests inject `opener` so this function has no
    network dependency in CI.
    """

    if not query.strip():
        raise WallpaperEffectorError("empty_query")
    open_bytes = opener or _urlopen_bytes
    encoded = urllib.parse.urlencode({"q": query})
    page_url = f"https://duckduckgo.com/?{encoded}&iax=images&ia=images"
    candidates: list[WallpaperCandidate] = []
    try:
        page = open_bytes(_request(page_url), 12.0).decode("utf-8", errors="ignore")
        vqd = _extract_vqd(page)
        if vqd:
            image_url = (
                "https://duckduckgo.com/i.js?"
                + urllib.parse.urlencode(
                    {"l": "us-en", "o": "json", "q": query, "vqd": vqd, "f": ",,,", "p": "1"}
                )
            )
            payload = open_bytes(_request(image_url, referer=page_url), 12.0)
            data = json.loads(payload.decode("utf-8", errors="ignore"))
            for item in data.get("results", []):
                url = str(item.get("image") or "").strip()
                if url:
                    candidates.append(WallpaperCandidate(url=url, title=str(item.get("title") or "")))
                if len(candidates) >= max_results:
                    return candidates
    except Exception:
        candidates = []

    html_url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": f"{query} wallpaper image"})
    try:
        page = open_bytes(_request(html_url), 12.0).decode("utf-8", errors="ignore")
        for url in _extract_image_urls_from_html(page):
            candidates.append(WallpaperCandidate(url=url))
            if len(candidates) >= max_results:
                break
    except Exception as exc:
        if not candidates:
            raise WallpaperEffectorError(f"search_failed:{type(exc).__name__}") from exc
    return candidates


def _request(url: str, *, referer: str = "") -> urllib.request.Request:
    headers = {
        "User-Agent": "SIFTA-WallpaperEffector/1.0 (+local-owner-request)",
        "Accept": "text/html,application/json,image/*,*/*;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    return urllib.request.Request(url, headers=headers)


def _urlopen_bytes(req: urllib.request.Request, timeout: float) -> bytes:
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(MAX_IMAGE_BYTES + 1)


def _extract_vqd(page: str) -> str:
    for pat in (r"vqd=['\"]([^'\"]+)['\"]", r"vqd=([0-9-]+)&", r"\"vqd\":\"([^\"]+)\""):
        m = re.search(pat, page)
        if m:
            return html.unescape(m.group(1))
    return ""


_URL_RE = re.compile(r"https?://[^\\'\"<>\s)]+", re.IGNORECASE)


def _extract_image_urls_from_html(page: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"(?:uddg|u|imgurl|image)=([^&\"'>\s]+)", page, flags=re.IGNORECASE):
        url = html.unescape(urllib.parse.unquote(m.group(1)))
        if url.startswith("http") and _looks_like_image_url(url) and url not in seen:
            seen.add(url)
            found.append(url)
    for url in _URL_RE.findall(html.unescape(page)):
        url = urllib.parse.unquote(url)
        if _looks_like_image_url(url) and url not in seen:
            seen.add(url)
            found.append(url)
    return found


def _looks_like_image_url(url: str) -> bool:
    path = urllib.parse.urlparse(url).path.lower()
    return path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))


def download_image(
    candidate: WallpaperCandidate,
    *,
    opener: Optional[Callable[[urllib.request.Request, float], tuple[bytes, dict[str, str]]]] = None,
    max_bytes: int = MAX_IMAGE_BYTES,
) -> tuple[bytes, str]:
    blocklist = _read_blocklist()
    if _domain_blocked(candidate.url, blocklist):
        raise WallpaperEffectorError("domain_blocked")
    if opener:
        body, headers = opener(_request(candidate.url), 15.0)
    else:
        body, headers = _download_with_headers(candidate.url, max_bytes=max_bytes)
    if len(body) > max_bytes:
        raise WallpaperEffectorError("image_too_large")
    header_mime = str(headers.get("content-type") or headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    sniffed = sniff_image_mime(body)
    mime = header_mime or sniffed
    if not mime.startswith("image/"):
        raise WallpaperEffectorError("mime_not_image")
    if sniffed and header_mime and not header_mime.startswith("image/"):
        raise WallpaperEffectorError("mime_not_image")
    width, height = image_dimensions(body)
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        raise WallpaperEffectorError("image_too_small")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise WallpaperEffectorError("image_too_large_dimensions")
    return body, sniffed or mime


def _download_with_headers(url: str, *, max_bytes: int) -> tuple[bytes, dict[str, str]]:
    req = _request(url)
    with urllib.request.urlopen(req, timeout=20.0) as resp:
        length = resp.headers.get("Content-Length")
        if length and int(length) > max_bytes:
            raise WallpaperEffectorError("image_too_large")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise WallpaperEffectorError("image_too_large")
        return b"".join(chunks), {k.lower(): v for k, v in resp.headers.items()}


def sniff_image_mime(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return ""


def image_dimensions(data: bytes) -> tuple[int, int]:
    mime = sniff_image_mime(data)
    if mime == "image/png" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if mime == "image/gif" and len(data) >= 10:
        return struct.unpack("<HH", data[6:10])
    if mime == "image/jpeg":
        return _jpeg_dimensions(data)
    if mime == "image/webp":
        dims = _webp_dimensions(data)
        if dims:
            return dims
    raise WallpaperEffectorError("unsupported_or_invalid_image")


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        i += 2
        if marker in {0xD8, 0xD9}:
            continue
        if i + 2 > len(data):
            break
        seg_len = struct.unpack(">H", data[i : i + 2])[0]
        if seg_len < 2 or i + seg_len > len(data):
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            height = struct.unpack(">H", data[i + 3 : i + 5])[0]
            width = struct.unpack(">H", data[i + 5 : i + 7])[0]
            return width, height
        i += seg_len
    raise WallpaperEffectorError("invalid_jpeg_dimensions")


def _webp_dimensions(data: bytes) -> Optional[tuple[int, int]]:
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if chunk == b"VP8 " and len(data) >= 30:
        width = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        height = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return width, height
    if chunk == b"VP8L" and len(data) >= 25:
        b0, b1, b2, b3 = data[21], data[22], data[23], data[24]
        width = 1 + (((b1 & 0x3F) << 8) | b0)
        height = 1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
        return width, height
    return None


def execute_wallpaper_intent(
    intent: WallpaperIntent,
    *,
    owner_confirmed: bool = False,
    dry_run: bool = False,
    candidates: Optional[Iterable[WallpaperCandidate]] = None,
    searcher: Optional[Callable[[str], list[WallpaperCandidate]]] = None,
    downloader: Optional[Callable[[WallpaperCandidate], tuple[bytes, str]]] = None,
) -> WallpaperResult:
    if intent.action == "undo_wallpaper":
        return undo_last_wallpaper_change(owner_confirmed=owner_confirmed, dry_run=dry_run, target=intent.target)
    if intent.action != "set_wallpaper":
        return _failure("unknown_action", intent.target, intent.query, dry_run=dry_run)
    return set_wallpaper_from_query(
        intent.query,
        target=intent.target,
        owner_confirmed=owner_confirmed,
        dry_run=dry_run,
        candidates=candidates,
        searcher=searcher,
        downloader=downloader,
    )


def set_wallpaper_from_query(
    query: str,
    *,
    target: str = "both",
    owner_confirmed: bool = False,
    dry_run: bool = False,
    candidates: Optional[Iterable[WallpaperCandidate]] = None,
    searcher: Optional[Callable[[str], list[WallpaperCandidate]]] = None,
    downloader: Optional[Callable[[WallpaperCandidate], tuple[bytes, str]]] = None,
) -> WallpaperResult:
    target = target if target in TARGETS else "both"
    if not owner_confirmed:
        result = _failure("owner_gate_required", target, query, dry_run=dry_run)
        _write_wallpaper_receipt(result, candidate_urls=[])
        return result

    try:
        candidate_list = list(candidates) if candidates is not None else (searcher or search_duckduckgo_images)(query)
    except Exception as exc:
        result = _failure("search_failed", target, query, dry_run=dry_run, error=f"{type(exc).__name__}:{exc}")
        _write_wallpaper_receipt(result, candidate_urls=[])
        return result
    if not candidate_list:
        result = _failure("no_candidates", target, query, dry_run=dry_run)
        _write_wallpaper_receipt(result, candidate_urls=[])
        return result

    errors: list[str] = []
    for candidate in candidate_list:
        try:
            body, mime = (downloader or download_image)(candidate)
            width, height = image_dimensions(body)
            result = _apply_image_bytes(
                body,
                mime,
                width,
                height,
                query=query,
                target=target,
                chosen_url=candidate.url,
                dry_run=dry_run,
            )
            _write_wallpaper_receipt(result, candidate_urls=[c.url for c in candidate_list])
            return result
        except Exception as exc:
            errors.append(f"{candidate.url}:{type(exc).__name__}:{exc}")

    result = _failure("all_candidates_failed", target, query, dry_run=dry_run, error=" | ".join(errors[:3]))
    _write_wallpaper_receipt(result, candidate_urls=[c.url for c in candidate_list])
    return result


def _apply_image_bytes(
    body: bytes,
    mime: str,
    width: int,
    height: int,
    *,
    query: str,
    target: str,
    chosen_url: str,
    dry_run: bool,
) -> WallpaperResult:
    sha = hashlib.sha256(body).hexdigest()
    ext = _extension_for_mime(mime)
    ts = int(_now())
    WEB_FETCHED_DIR.mkdir(parents=True, exist_ok=True)
    saved_path = WEB_FETCHED_DIR / f"web_{ts}_{sha[:8]}{ext}"
    previous_desktop = _load_current_desktop_wallpaper()
    previous_chat_backup: Optional[str] = None

    if not dry_run:
        _atomic_write_bytes(saved_path, body)
        if target in {"desktop", "both"}:
            _save_desktop_wallpaper(saved_path)
        if target in {"chat", "both"}:
            previous_chat_backup = _backup_chat_wallpaper()
            _atomic_write_bytes(CHAT_WALLPAPER_PATH, body)

    return WallpaperResult(
        ok=True,
        status="dry_run_ready" if dry_run else "applied",
        receipt_id=uuid.uuid4().hex[:16],
        target=target,
        query=query,
        saved_path=str(saved_path),
        chosen_url=chosen_url,
        content_sha256=sha,
        mime=mime,
        bytes=len(body),
        width=width,
        height=height,
        previous_desktop_path=previous_desktop,
        previous_chat_backup_path=previous_chat_backup,
        dry_run=dry_run,
    )


def _extension_for_mime(mime: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(mime, ".img")


def _atomic_write_bytes(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_bytes(body)
    os.replace(tmp, path)


def _load_current_desktop_wallpaper() -> Optional[str]:
    try:
        from System.sifta_desktop_themes import load_custom_wallpaper_path

        return load_custom_wallpaper_path()
    except Exception:
        state = STATE_DIR / "desktop_wallpaper.json"
        try:
            return json.loads(state.read_text(encoding="utf-8")).get("path")
        except Exception:
            return None


def _save_desktop_wallpaper(path: Path) -> None:
    try:
        from System.sifta_desktop_themes import save_custom_wallpaper_path

        save_custom_wallpaper_path(str(path.resolve()))
    except Exception:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / "desktop_wallpaper.json").write_text(
            json.dumps({"path": str(path.resolve()), "changed_at": _now()}, indent=2),
            encoding="utf-8",
        )


def _backup_chat_wallpaper() -> Optional[str]:
    if not CHAT_WALLPAPER_PATH.exists():
        return None
    sha = hashlib.sha256(CHAT_WALLPAPER_PATH.read_bytes()).hexdigest()[:8]
    backup = WEB_FETCHED_DIR / f"previous_chat_{int(_now())}_{sha}{CHAT_WALLPAPER_PATH.suffix or '.jpg'}"
    WEB_FETCHED_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CHAT_WALLPAPER_PATH, backup)
    return str(backup)


def undo_last_wallpaper_change(*, owner_confirmed: bool = False, dry_run: bool = False, target: str = "both") -> WallpaperResult:
    target = target if target in TARGETS else "both"
    if not owner_confirmed:
        result = _failure("owner_gate_required", target, "undo", dry_run=dry_run)
        _write_wallpaper_receipt(result, kind="WALLPAPER_UNDO", candidate_urls=[])
        return result

    row = _last_applied_wallpaper_row()
    if not row:
        result = _failure("nothing_to_undo", target, "undo", dry_run=dry_run)
        _write_wallpaper_receipt(result, kind="WALLPAPER_UNDO", candidate_urls=[])
        return result

    previous_desktop = row.get("previous_desktop_path")
    previous_chat = row.get("previous_chat_backup_path")
    if not dry_run:
        if target in {"desktop", "both"}:
            _restore_desktop_wallpaper(previous_desktop)
        if target in {"chat", "both"} and previous_chat:
            shutil.copy2(previous_chat, CHAT_WALLPAPER_PATH)

    result = WallpaperResult(
        ok=True,
        status="dry_run_undo_ready" if dry_run else "undone",
        receipt_id=uuid.uuid4().hex[:16],
        target=target,
        query="undo",
        previous_desktop_path=previous_desktop,
        previous_chat_backup_path=previous_chat,
        dry_run=dry_run,
    )
    _write_wallpaper_receipt(result, kind="WALLPAPER_UNDO", candidate_urls=[])
    return result


def _last_applied_wallpaper_row() -> Optional[dict[str, Any]]:
    if not WALLPAPER_LEDGER.exists():
        return None
    last: Optional[dict[str, Any]] = None
    for line in WALLPAPER_LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") == "WALLPAPER_CHANGE" and row.get("ok") is True and row.get("dry_run") is False:
            last = row
    return last


def _restore_desktop_wallpaper(previous: Optional[str]) -> None:
    try:
        from System.sifta_desktop_themes import save_custom_wallpaper_path

        if previous is None:
            save_custom_wallpaper_path(None)
        else:
            save_custom_wallpaper_path(str(previous))
        return
    except Exception:
        pass
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = STATE_DIR / "desktop_wallpaper.json"
    if previous is None:
        state.unlink(missing_ok=True)
    else:
        state.write_text(json.dumps({"path": str(previous), "changed_at": _now()}, indent=2), encoding="utf-8")


def _failure(status: str, target: str, query: str, *, dry_run: bool, error: str = "") -> WallpaperResult:
    return WallpaperResult(
        ok=False,
        status=status,
        receipt_id=uuid.uuid4().hex[:16],
        target=target,
        query=query,
        dry_run=dry_run,
        error=error or status,
    )


def _write_wallpaper_receipt(
    result: WallpaperResult,
    *,
    kind: str = "WALLPAPER_CHANGE",
    candidate_urls: list[str],
) -> None:
    row = asdict(result)
    row.update(
        {
            "ts": _now(),
            "kind": kind,
            "truth_label": TRUTH_LABEL,
            "search_engine": SEARCH_ENGINE,
            "candidate_urls": candidate_urls,
            "stgm_cost": STGM_COST if result.ok and not result.dry_run and kind == "WALLPAPER_CHANGE" else 0.0,
        }
    )
    row["integrity"] = hashlib.sha256(
        json.dumps({k: v for k, v in row.items() if k != "integrity"}, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    _append_jsonl(WALLPAPER_LEDGER, row)


def render_owner_reply(result: WallpaperResult) -> str:
    if result.ok and result.status == "applied":
        kb = result.bytes / 1024.0
        return (
            f"Wallpaper applied for {result.target}: {result.query}. "
            f"Saved {kb:.1f} KB as {Path(result.saved_path).name}, sha8 {result.content_sha256[:8]}. "
            f"Receipt {result.receipt_id}. Say undo wallpaper to revert."
        )
    if result.ok and result.status == "dry_run_ready":
        return (
            f"Wallpaper dry-run ready for {result.target}: {result.query}. "
            f"Candidate {result.chosen_url}, sha8 {result.content_sha256[:8]}. Receipt {result.receipt_id}."
        )
    if result.ok and result.status in {"undone", "dry_run_undo_ready"}:
        return f"Wallpaper undo {result.status.replace('_', ' ')}. Receipt {result.receipt_id}."
    return f"Wallpaper effector refused: {result.status}. Receipt {result.receipt_id}."


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="SIFTA wallpaper effector")
    ap.add_argument("query", nargs="*", help="wallpaper query or natural-language command")
    ap.add_argument("--target", choices=sorted(TARGETS), default="both")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--owner-confirmed", action="store_true", help="router/owner gate has already confirmed this action")
    args = ap.parse_args(argv)
    text = " ".join(args.query).strip()
    intent = parse_wallpaper_intent(text) or WallpaperIntent(action="set_wallpaper", query=text, target=args.target, raw_text=text)
    if args.target:
        intent = WallpaperIntent(action=intent.action, query=intent.query, target=args.target, raw_text=intent.raw_text)
    result = execute_wallpaper_intent(intent, owner_confirmed=args.owner_confirmed, dry_run=args.dry_run)
    print(render_owner_reply(result))
    return 0 if result.ok else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

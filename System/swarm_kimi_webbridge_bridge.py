#!/usr/bin/env python3
"""Kimi WebBridge ↔ Alice dual-limb bridge (r1391).

Alice Browser = QWebEngine body (default web limb, r311).
Kimi WebBridge = external Chrome effector on localhost:10086 with owner login sessions.

Alice may route explicit owner requests ("kimi webbridge", "open in chrome webbridge")
to Kimi; she must not claim Chrome tabs are her Alice Browser body.

Truth label: KIMI_WEBBRIDGE_BRIDGE_V1
Ledger: .sifta_state/kimi_webbridge_commands.jsonl
"""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Optional

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover

    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)

TRUTH_LABEL = "KIMI_WEBBRIDGE_BRIDGE_V1"
SCHEMA = "KIMI_WEBBRIDGE_COMMAND_V1"
LEDGER_NAME = "kimi_webbridge_commands.jsonl"
CAPTURE_TRUTH_LABEL = "ALICE_WEB_CAPTURE_V1"
CAPTURE_SCHEMA = "ALICE_WEB_CAPTURE_RECEIPT_V1"
CAPTURE_LEDGER_NAME = "alice_web_captures.jsonl"
CAPTURE_LATEST_NAME = "alice_web_capture_latest.json"
CAPTURE_LATEST_ATTEMPT_NAME = "alice_web_capture_latest_attempt.json"
CAPTURE_TEXT_DIR = "alice_web_capture_text"
DEFAULT_PORT = 10086
DEFAULT_SESSION = "alice-kimi-limb"
DEFAULT_CAPTURE_SESSION = "alice-web-capture"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_WEBBRIDGE_BIN = Path.home() / ".kimi-webbridge" / "bin" / "kimi-webbridge"

_KIMI_LIMB_RE = re.compile(
    r"\b(?:kimi\s+web\s*bridge|kimi\s+webbridge|webbridge|kimi\s+browser|"
    r"chrome\s+webbridge|agent\s+swarm|kimi\s+agent\s+swarm)\b",
    re.IGNORECASE,
)
_NAVIGATE_RE = re.compile(
    r"\b(?:open|go\s+to|navigate|load|visit|connect|launch)\b",
    re.IGNORECASE,
)
_URL_RE = re.compile(
    r"https?://[^\s<>\"']+",
    re.IGNORECASE,
)
_ANY_URL_RE = re.compile(
    r"(?P<url>https?://[^\s<>\"']+|www\.[^\s<>\"']+|(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>\"']*)?)",
    re.IGNORECASE,
)
_WEB_CAPTURE_RE = re.compile(
    r"\b(?:read|capture|summari[sz]e|summary|extract|scrape|crawl|firecrawl|browse|"
    r"pull|get)\b.{0,120}\b(?:https?://|www\.|url|link|website|web\s*site|webpage|web\s*page|page|site)\b"
    r"|\b(?:https?://|www\.|url|link|website|web\s*site|webpage|web\s*page|page|site)\b.{0,120}"
    r"\b(?:read|capture|summari[sz]e|summary|extract|scrape|crawl|firecrawl|browse|pull|get)\b",
    re.IGNORECASE,
)
_KNOWN_PUBLIC_TLDS = {
    "ai", "app", "co", "com", "dev", "edu", "gov", "io", "me", "net",
    "org", "sh", "so", "tv", "uk", "us",
}


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _base_url(port: int = DEFAULT_PORT) -> str:
    return f"http://127.0.0.1:{port}"


def _append_ledger(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    path = _state_dir(state_dir) / LEDGER_NAME
    row = {**row, "schema": SCHEMA, "truth_label": TRUTH_LABEL, "ts": time.time()}
    append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _append_webbridge_action_receipt(
    *,
    action: str,
    uid: str = "",
    value: str = "",
    ok: bool = False,
    receipt: str = "",
    state_dir: Optional[Path | str] = None,
    url: str = "",
    error: str = "",
) -> dict[str, Any]:
    """Write a receipt row for UID-based WebBridge actions."""
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "action": action,
        "uid": uid,
        "ok": bool(ok),
        "truth_label": "ALICE_WEBBRIDGE_UID_ACTION_V1",
        "backend": "webbridge",
        "receipt": receipt,
        "url": url,
    }
    if value:
        row["value"] = value
    if error:
        row["error"] = error[:300]
    _append_jsonl(sd / "browser_action_diary.jsonl", row)
    return row


def _clean_url_tail(url: str) -> str:
    return str(url or "").strip().rstrip(".,;:!?)\"']}")


def _looks_like_public_url(token: str) -> bool:
    raw = _clean_url_tail(token)
    if not raw:
        return False
    if raw.startswith(("http://", "https://", "www.")):
        return True
    host = raw.split("/", 1)[0].lower()
    if host.endswith((".py", ".md", ".json", ".txt", ".yaml", ".yml", ".toml")):
        return False
    parts = [p for p in host.split(".") if p]
    return len(parts) >= 2 and parts[-1] in _KNOWN_PUBLIC_TLDS


def normalize_web_url(url: str) -> str:
    clean = _clean_url_tail(url)
    if not clean:
        return ""
    if not _looks_like_public_url(clean):
        return ""
    if clean.startswith(("http://", "https://")):
        return clean
    return "https://" + clean


def extract_any_url_from_text(text: str) -> str:
    for match in _ANY_URL_RE.finditer(text or ""):
        url = normalize_web_url(match.group("url"))
        if url:
            return url
    return ""


def read_daemon_status(*, port: int = DEFAULT_PORT) -> dict[str, Any]:
    """Read Kimi WebBridge daemon status (extension_connected, port, version)."""
    if _WEBBRIDGE_BIN.is_file():
        try:
            proc = subprocess.run(
                [str(_WEBBRIDGE_BIN), "status"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return json.loads(proc.stdout.strip())
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            pass
    try:
        with urllib.request.urlopen(f"{_base_url(port)}/status", timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
        return {"running": False, "extension_connected": False, "port": port}


def ensure_daemon_running(*, port: int = DEFAULT_PORT) -> dict[str, Any]:
    """Start Kimi WebBridge if it is installed but not running, then re-read status."""
    status = read_daemon_status(port=port)
    if status.get("running"):
        return status
    if _WEBBRIDGE_BIN.is_file():
        try:
            subprocess.run(
                [str(_WEBBRIDGE_BIN), "start"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            time.sleep(0.6)
            status = read_daemon_status(port=port)
        except (subprocess.TimeoutExpired, OSError):
            pass
    return status


def post_command(
    action: str,
    args: Optional[dict[str, Any]] = None,
    *,
    session: str = DEFAULT_SESSION,
    port: int = DEFAULT_PORT,
    state_dir: Optional[Path | str] = None,
    source: str = "swarm_kimi_webbridge_bridge",
) -> dict[str, Any]:
    """POST one WebBridge command; append receipt row."""
    body = json.dumps(
        {"action": action, "args": args or {}, "session": session},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{_base_url(port)}/command",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    row: dict[str, Any] = {
        "action": action,
        "args": args or {},
        "session": session,
        "source": source,
        "ok": False,
    }
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        payload_ok = bool(payload.get("ok") or payload.get("success"))
        payload_error = payload.get("error")
        row["ok"] = payload_ok and not bool(payload_error)
        row["result"] = payload
        if payload_error:
            if isinstance(payload_error, dict):
                row["error"] = str(payload_error.get("message") or payload_error)[:300]
            else:
                row["error"] = str(payload_error)[:300]
        elif not payload_ok:
            row["error"] = "webbridge command returned ok=false"
    except Exception as exc:
        row["error"] = str(exc)[:300]
    _append_ledger(row, state_dir=state_dir)
    return row


class _SimpleHTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self._current_link = ""
        self.title_chunks: list[str] = []
        self.text_chunks: list[str] = []
        self.headings: list[str] = []
        self.links: list[dict[str, str]] = []
        self._in_title = False
        self._heading_level = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
            return
        if tag == "title":
            self._in_title = True
            return
        if tag in {"h1", "h2", "h3"}:
            self._heading_level = tag
            return
        if tag == "a":
            href = ""
            for key, value in attrs:
                if key and key.lower() == "href":
                    href = str(value or "").strip()
                    break
            self._current_link = href

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in {"h1", "h2", "h3"}:
            self._heading_level = ""
        if tag == "a":
            self._current_link = ""

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = " ".join(unescape(data or "").split())
        if not text:
            return
        if self._in_title:
            self.title_chunks.append(text)
            return
        if self._heading_level:
            if len(self.headings) < 24:
                self.headings.append(text[:240])
        if self._current_link and len(self.links) < 60:
            self.links.append({"text": text[:180], "href": self._current_link[:500]})
        self.text_chunks.append(text)


def _text_from_snapshot_tree(tree: Any) -> str:
    if isinstance(tree, str):
        return tree
    if isinstance(tree, list):
        return "\n".join(_text_from_snapshot_tree(x) for x in tree if x)
    if isinstance(tree, dict):
        pieces: list[str] = []
        for key in ("name", "text", "value", "description"):
            val = tree.get(key)
            if isinstance(val, str) and val.strip():
                pieces.append(val.strip())
        for key in ("children", "nodes"):
            val = tree.get(key)
            if isinstance(val, list):
                child_text = _text_from_snapshot_tree(val)
                if child_text:
                    pieces.append(child_text)
        return "\n".join(pieces)
    return ""


def _compact_page_text(text: str, *, limit: int = 300_000) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for raw in re.split(r"[\r\n]+", str(text or "")):
        line = " ".join(raw.split())
        if not line:
            continue
        folded = line.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        lines.append(line)
        if sum(len(x) + 1 for x in lines) >= limit:
            break
    return "\n".join(lines)[:limit]


def _http_fetch_page(url: str, *, timeout: float = 20.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) SIFTA-Alice-WebCapture/1.0"
            )
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        final_url = resp.geturl() or url
        raw = resp.read(2_000_000)
        charset = resp.headers.get_content_charset() or "utf-8"
    html = raw.decode(charset, errors="replace")
    parser = _SimpleHTMLTextExtractor()
    parser.feed(html)
    title = " ".join(parser.title_chunks).strip()
    text = _compact_page_text("\n".join(parser.text_chunks))
    return {
        "url": final_url,
        "title": title,
        "text": text,
        "headings": parser.headings,
        "links": parser.links,
        "backend": "http_fetch_fallback",
    }


def _evaluate_payload_value(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("result") if isinstance(result, dict) else {}
    value = payload.get("value") if isinstance(payload, dict) else None
    if isinstance(value, str):
        try:
            data = json.loads(value)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {"text": value}
    return value if isinstance(value, dict) else {}


def _extract_webbridge_page_payload(
    *,
    session: str,
    state_dir: Optional[Path | str] = None,
    port: int = DEFAULT_PORT,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    snapshot = post_command(
        "snapshot",
        {},
        session=session,
        port=port,
        state_dir=state_dir,
        source="swarm_kimi_webbridge_capture",
    )
    # Persist UID proprioception snapshot for the WebBridge limb (Task 1 + 2)
    try:
        _persist_webbridge_uid_snapshot(snapshot, state_dir=state_dir)
    except Exception:
        pass
    js = (
        "(() => {"
        "const abs=(href)=>{try{return new URL(href,location.href).href}catch(e){return href||''}};"
        "const clean=(s)=>String(s||'').replace(/\\s+/g,' ').trim();"
        "const text=(document.body&&document.body.innerText||'').slice(0,300000);"
        "const headings=[...document.querySelectorAll('h1,h2,h3')].slice(0,24).map(e=>clean(e.innerText)).filter(Boolean);"
        "const links=[...document.links].slice(0,60).map(a=>({text:clean(a.innerText||a.ariaLabel||a.title).slice(0,180),href:abs(a.getAttribute('href')).slice(0,500)}));"
        "const metas=[...document.querySelectorAll('meta[name=\"description\"],meta[property=\"og:description\"]')].map(m=>clean(m.content)).filter(Boolean).slice(0,4);"
        "return JSON.stringify({url:location.href,title:document.title||'',text,headings,links,metas});"
        "})()"
    )
    evaluated = post_command(
        "evaluate",
        {"code": js},
        session=session,
        port=port,
        state_dir=state_dir,
        source="swarm_kimi_webbridge_capture",
    )
    payload = _evaluate_payload_value(evaluated)
    if not str(payload.get("text") or "").strip() and snapshot.get("ok"):
        result = snapshot.get("result") if isinstance(snapshot.get("result"), dict) else {}
        tree_text = _text_from_snapshot_tree(result.get("tree"))
        if tree_text:
            payload["text"] = tree_text
        payload.setdefault("url", result.get("url") or "")
        payload.setdefault("title", result.get("title") or "")
    return payload, snapshot, evaluated


def _capture_receipt_row(
    *,
    ok: bool,
    url: str,
    requested_url: str,
    owner_text: str = "",
    title: str = "",
    text: str = "",
    headings: Optional[list[Any]] = None,
    links: Optional[list[Any]] = None,
    backend: str = "",
    error: str = "",
    webbridge_status: Optional[dict[str, Any]] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    base = _state_dir(state_dir)
    base.mkdir(parents=True, exist_ok=True)
    receipt_id = f"webcap_{uuid.uuid4().hex[:16]}"
    clean_text = _compact_page_text(text)
    text_hash = ""
    text_sidecar = ""
    if clean_text:
        text_hash = __import__("hashlib").sha256(clean_text.encode("utf-8")).hexdigest()
        text_dir = base / CAPTURE_TEXT_DIR
        text_dir.mkdir(parents=True, exist_ok=True)
        sidecar = text_dir / f"{receipt_id}.txt"
        sidecar.write_text(clean_text, encoding="utf-8")
        text_sidecar = str(sidecar)
    row: dict[str, Any] = {
        "ts": time.time(),
        "schema": CAPTURE_SCHEMA,
        "truth_label": CAPTURE_TRUTH_LABEL,
        "receipt_id": receipt_id,
        "ok": bool(ok),
        "requested_url": requested_url,
        "url": url or requested_url,
        "title": " ".join(str(title or "").split())[:500],
        "domain": urllib.parse.urlparse(url or requested_url).netloc,
        "backend": backend,
        "owner_text": " ".join(str(owner_text or "").split())[:500],
        "text_chars": len(clean_text),
        "text_hash": text_hash,
        "text_sidecar": text_sidecar,
        "text_excerpt": clean_text[:1800],
        "headings": [str(x)[:240] for x in list(headings or [])[:16]],
        "links": [
            item for item in list(links or [])[:24]
            if isinstance(item, dict) and (item.get("text") or item.get("href"))
        ],
    }
    if error:
        row["error"] = error[:800]
    if webbridge_status:
        row["webbridge_status"] = {
            "running": bool(webbridge_status.get("running")),
            "extension_connected": bool(webbridge_status.get("extension_connected")),
            "port": webbridge_status.get("port", DEFAULT_PORT),
            "version": webbridge_status.get("version") or webbridge_status.get("extension_version"),
        }
    _append_jsonl(base / CAPTURE_LEDGER_NAME, row)
    try:
        (base / CAPTURE_LATEST_ATTEMPT_NAME).write_text(
            json.dumps(row, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        if ok:
            (base / CAPTURE_LATEST_NAME).write_text(
                json.dumps(row, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
    except Exception:
        pass
    try:
        _append_jsonl(
            base / "work_receipts.jsonl",
            {
                "ts": row["ts"],
                "truth_label": CAPTURE_TRUTH_LABEL,
                "receipt_id": receipt_id,
                "kind": "web_page_capture",
                "ok": bool(ok),
                "url": row["url"],
                "title": row["title"],
                "backend": backend,
                "text_chars": row["text_chars"],
            },
        )
        _append_jsonl(
            base / "episodic_diary.jsonl",
            {
                "ts": row["ts"],
                "truth_label": CAPTURE_TRUTH_LABEL,
                "event_type": "web_page_captured",
                "surface": "Alice Web Capture",
                "summary": (
                    f"Captured {row['title'] or row['url']} via {backend}; "
                    f"text_chars={row['text_chars']}; receipt={receipt_id}"
                ),
                "url": row["url"],
                "title": row["title"],
                "receipt_id": receipt_id,
            },
        )
    except Exception:
        pass
    return row


def capture_url(
    url: str,
    *,
    owner_text: str = "",
    session: str = DEFAULT_CAPTURE_SESSION,
    group_title: str = "Alice web capture",
    new_tab: bool = True,
    wait_s: float = 2.0,
    allow_http_fallback: bool = True,
    state_dir: Optional[Path | str] = None,
    port: int = DEFAULT_PORT,
) -> dict[str, Any]:
    """Capture readable page text from the web into Alice's body ledger."""
    requested = normalize_web_url(url)
    if not requested:
        return _capture_receipt_row(
            ok=False,
            url="",
            requested_url=str(url or ""),
            owner_text=owner_text,
            backend="none",
            error="no valid public URL",
            state_dir=state_dir,
        )

    status = ensure_daemon_running(port=port)
    webbridge_available = bool(status.get("running") and status.get("extension_connected"))
    if webbridge_available:
        nav = navigate(
            requested,
            new_tab=new_tab,
            group_title=group_title,
            session=session,
            state_dir=state_dir,
        )
        if nav.get("ok"):
            time.sleep(max(0.0, min(wait_s, 8.0)))
            payload, snapshot, evaluated = _extract_webbridge_page_payload(
                session=session,
                state_dir=state_dir,
                port=port,
            )
            text = str(payload.get("text") or "")
            title = str(payload.get("title") or "")
            final_url = str(payload.get("url") or requested)
            if text.strip() or title.strip():
                return _capture_receipt_row(
                    ok=True,
                    url=final_url,
                    requested_url=requested,
                    owner_text=owner_text,
                    title=title,
                    text=text,
                    headings=payload.get("headings") if isinstance(payload.get("headings"), list) else [],
                    links=payload.get("links") if isinstance(payload.get("links"), list) else [],
                    backend="kimi_webbridge",
                    webbridge_status=status,
                    state_dir=state_dir,
                )
            if not allow_http_fallback:
                return _capture_receipt_row(
                    ok=False,
                    url=final_url,
                    requested_url=requested,
                    owner_text=owner_text,
                    title=title,
                    backend="kimi_webbridge",
                    error=(
                        f"webbridge navigation worked but no readable text landed; "
                        f"snapshot_ok={snapshot.get('ok')}; evaluate_ok={evaluated.get('ok')}"
                    ),
                    webbridge_status=status,
                    state_dir=state_dir,
                )
        elif not allow_http_fallback:
            return _capture_receipt_row(
                ok=False,
                url=requested,
                requested_url=requested,
                owner_text=owner_text,
                backend="kimi_webbridge",
                error=str(nav.get("error") or "webbridge navigation failed"),
                webbridge_status=status,
                state_dir=state_dir,
            )

    if allow_http_fallback:
        try:
            fetched = _http_fetch_page(requested)
            return _capture_receipt_row(
                ok=True,
                url=str(fetched.get("url") or requested),
                requested_url=requested,
                owner_text=owner_text,
                title=str(fetched.get("title") or ""),
                text=str(fetched.get("text") or ""),
                headings=fetched.get("headings") if isinstance(fetched.get("headings"), list) else [],
                links=fetched.get("links") if isinstance(fetched.get("links"), list) else [],
                backend=str(fetched.get("backend") or "http_fetch_fallback"),
                webbridge_status=status,
                state_dir=state_dir,
            )
        except Exception as exc:
            backend = "http_fetch_fallback"
            if status.get("running") and not status.get("extension_connected"):
                backend = "webbridge_disconnected_then_http_fetch_failed"
            elif not status.get("running"):
                backend = "webbridge_unavailable_then_http_fetch_failed"
            return _capture_receipt_row(
                ok=False,
                url=requested,
                requested_url=requested,
                owner_text=owner_text,
                backend=backend,
                error=f"{type(exc).__name__}: {exc}",
                webbridge_status=status,
                state_dir=state_dir,
            )

    return _capture_receipt_row(
        ok=False,
        url=requested,
        requested_url=requested,
        owner_text=owner_text,
        backend="kimi_webbridge",
        error="Kimi WebBridge daemon or extension is not connected",
        webbridge_status=status,
        state_dir=state_dir,
    )


def _summary_lines(text: str, *, limit: int = 4) -> list[str]:
    skip = re.compile(
        r"\b(?:cookie|privacy|terms|sign in|log in|subscribe|advertisement|all rights reserved)\b",
        re.IGNORECASE,
    )
    out: list[str] = []
    for raw in re.split(r"[\r\n]+|(?<=[.!?])\s+", str(text or "")):
        line = " ".join(raw.split())
        if len(line) < 35 or skip.search(line):
            continue
        out.append(line[:260])
        if len(out) >= limit:
            break
    return out


def summarize_capture(row: dict[str, Any]) -> str:
    rid = str(row.get("receipt_id") or "")
    if not row.get("ok"):
        err = str(row.get("error") or "unknown error")
        backend = str(row.get("backend") or "web capture")
        return (
            f"I tried to capture the page, but {backend} failed: {err}. "
            f"Receipt: {rid or CAPTURE_TRUTH_LABEL}."
        )
    title = str(row.get("title") or row.get("url") or "the page").strip()
    url = str(row.get("url") or row.get("requested_url") or "").strip()
    backend = str(row.get("backend") or "web capture")
    text_chars = int(row.get("text_chars") or 0)
    lines = _summary_lines(str(row.get("text_excerpt") or ""))
    if lines:
        summary = " ".join(f"{i + 1}. {line}" for i, line in enumerate(lines))
    else:
        heads = [str(x) for x in row.get("headings", [])[:4]]
        summary = " Headings: " + "; ".join(heads) if heads else "I captured the page but it did not expose much readable text."
    return (
        f"Captured {title} via {backend}. URL: {url}. "
        f"I read {text_chars} chars into my web-capture body ledger. "
        f"Receipt: {rid}. Summary: {summary}"
    ).strip()


def wants_general_web_capture(text: str) -> bool:
    clean = " ".join((text or "").strip().split())
    if not clean or not extract_any_url_from_text(clean):
        return False
    if re.search(r"\b(?:read|capture|summari[sz]e|summary|extract|scrape|crawl|firecrawl|browse)\b", clean, re.IGNORECASE):
        return True
    return bool(_WEB_CAPTURE_RE.search(clean))


def try_handle_web_capture_turn(
    text: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> str:
    clean = " ".join((text or "").strip().split())
    if not wants_general_web_capture(clean):
        return ""
    url = extract_any_url_from_text(clean)
    row = capture_url(url, owner_text=clean, state_dir=state_dir)
    return summarize_capture(row)


def web_capture_prompt_block(
    *,
    max_age_s: float = 6 * 3600,
    max_chars: int = 1100,
    state_dir: Optional[Path | str] = None,
) -> str:
    base = _state_dir(state_dir)
    try:
        row = json.loads((base / CAPTURE_LATEST_NAME).read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(row, dict) or not row.get("ok"):
        return ""
    try:
        age = time.time() - float(row.get("ts") or 0.0)
    except Exception:
        age = max_age_s + 1
    if age > max_age_s:
        return ""
    block = (
        "ALICE WEB CAPTURE BODY (receipt-backed page text):\n"
        f"- latest_url={row.get('url')}\n"
        f"- title={row.get('title')}\n"
        f"- backend={row.get('backend')} receipt={row.get('receipt_id')} text_chars={row.get('text_chars')}\n"
        "- Rule: answer questions about this captured page from the receipt/text excerpt; do not invent page details.\n"
        f"- excerpt={str(row.get('text_excerpt') or '')[:650]}"
    )
    return block[:max_chars] if len(block) > max_chars else block


def navigate(
    url: str,
    *,
    new_tab: bool = True,
    group_title: str = "Alice Kimi limb",
    session: str = DEFAULT_SESSION,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    return post_command(
        "navigate",
        {"url": url, "newTab": new_tab, "group_title": group_title},
        session=session,
        state_dir=state_dir,
    )


def wants_kimi_webbridge_limb(text: str) -> bool:
    """True when owner explicitly names Kimi WebBridge / agent swarm Chrome limb."""
    return bool(_KIMI_LIMB_RE.search(text or ""))


def extract_url_from_text(text: str) -> str:
    m = _URL_RE.search(text or "")
    if not m:
        return ""
    return m.group(0).rstrip(".,;:!?)\"']}")


def default_agent_swarm_url() -> str:
    return "https://www.kimi.com/agent-swarm"


def kimi_webbridge_prompt_block(*, max_chars: int = 700) -> str:
    """Talk hook: dual-limb doctrine + live connection status."""
    st = read_daemon_status()
    lines = [
        "## KIMI WEBBRIDGE LIMB (external Chrome — not Alice Browser body)",
        "Alice Browser = my QWebEngine body limb (default). Kimi WebBridge = your Chrome with login sessions on localhost:10086.",
        "I use Kimi for explicit Chrome/WebBridge work and as the preferred backend for general web-page capture/read requests.",
        "Never confuse Chrome tabs with Alice Browser receipts; page captures write ALICE_WEB_CAPTURE_V1 receipts.",
    ]
    if st.get("running"):
        connected = bool(st.get("extension_connected"))
        lines.append(
            f"Status: daemon running port {st.get('port', DEFAULT_PORT)} · "
            f"extension_connected={connected} · version={st.get('version', '?')}"
        )
        if connected:
            lines.append(
                "Owner may say: 'open kimi webbridge' or 'read https://example.com' — I route the first to Chrome navigation and the second to web capture."
            )
            lines.append("General capture/read of any URL writes Alice web-capture body receipts and latest context.")
        else:
            lines.append(
                "Extension not connected: install Kimi WebBridge from Chrome Web Store and pin it."
            )
    else:
        lines.append("Daemon not running: curl -fsSL https://cdn.kimi.com/webbridge/install.sh | bash")
    block = "\n".join(lines)
    return block[:max_chars] if len(block) > max_chars else block


def try_handle_owner_turn(
    text: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Pre-cortex reflex: explicit Kimi WebBridge navigate/status."""
    clean = " ".join((text or "").strip().split())
    if not clean or not wants_kimi_webbridge_limb(clean):
        return ""
    st = read_daemon_status()
    if not st.get("running"):
        return (
            "Kimi WebBridge daemon is not running. Install with: "
            "curl -fsSL https://cdn.kimi.com/webbridge/install.sh | bash"
        )
    if not st.get("extension_connected"):
        return (
            "Kimi WebBridge daemon is up but the Chrome extension is not connected. "
            "Pin Kimi WebBridge in Chrome, then ask again."
        )
    url = extract_url_from_text(clean) or default_agent_swarm_url()
    if _NAVIGATE_RE.search(clean) or "connect" in clean.lower() or extract_url_from_text(clean):
        row = navigate(url, state_dir=state_dir)
        if not row.get("ok"):
            return f"Kimi WebBridge navigate failed: {row.get('error', 'unknown')}"
        result = row.get("result") or {}
        if result.get("ok") is False or result.get("error"):
            err = result.get("error") or {}
            msg = err.get("message") if isinstance(err, dict) else str(err)
            code = err.get("code") if isinstance(err, dict) else ""
            hint = (
                " Open Chrome first (any window), then retry."
                if "no current window" in str(msg).lower()
                else ""
            )
            return (
                f"Kimi WebBridge is connected but navigate failed ({code or 'error'}: {msg}).{hint} "
                "Receipt written to kimi_webbridge_commands.jsonl — honest no-result, not theater."
            )
        tab = result.get("tabId", "?")
        landed = result.get("url", url)
        return (
            f"Kimi WebBridge opened {landed} in your Chrome (tab {tab}). "
            "That is your Chrome login limb — not my Alice Browser QWebEngine body. "
            "Receipt written to kimi_webbridge_commands.jsonl."
        )
    return (
        f"Kimi WebBridge is connected (extension {st.get('extension_version', '?')}, "
        f"port {st.get('port', DEFAULT_PORT)}). "
        "Say 'open kimi webbridge' or 'navigate kimi agent swarm' to launch in Chrome."
    )


def _extract_readable_text(payload: Any) -> str:
    """Pull clean readable text/markdown from various possible WebBridge response shapes."""
    if not payload:
        return ""
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, dict):
        for key in ("markdown", "text", "content", "html", "body", "result", "page", "data"):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
            if isinstance(val, dict):
                for sub in ("markdown", "text", "content"):
                    if isinstance(val.get(sub), str) and val[sub].strip():
                        return val[sub].strip()
        # last resort: stringify small
        if len(str(payload)) < 4000:
            return str(payload)
    if isinstance(payload, list) and payload:
        return _extract_readable_text(payload[0])
    return ""


def _tree_to_readable(tree: Any, depth: int = 0, max_depth: int = 4) -> str:
    """Convert WebBridge snapshot accessibility tree (with @e refs) into compact readable text for body/journal."""
    if depth > max_depth or not tree:
        return ""
    if isinstance(tree, str):
        return tree.strip()
    if isinstance(tree, dict):
        name = tree.get("name") or tree.get("text") or tree.get("value") or ""
        role = tree.get("role") or tree.get("tag") or ""
        ref = tree.get("ref") or tree.get("@e") or ""
        label = f"[{ref}] " if ref else ""
        line = f"{label}{role}: {name}".strip() if role or name else ""
        children = tree.get("children") or tree.get("nodes") or []
        sub = ""
        if isinstance(children, list):
            sub = " ".join(_tree_to_readable(c, depth+1, max_depth) for c in children[:10] if c)
        return (line + " " + sub).strip() if line or sub else ""
    if isinstance(tree, list):
        return " ".join(_tree_to_readable(item, depth, max_depth) for item in tree[:15])
    return ""


def _flatten_webbridge_snapshot_tree(tree: Any, max_elements: int = 50) -> list[dict]:
    """Turn WebBridge a11y snapshot tree into flat list of {uid, role, name, ...} using @e / ref as uid.
    Mirrors the structure of Alice Browser's UID snapshot for proprioception parity.
    """
    out: list[dict] = []
    seen: set[str] = set()

    def walk(node: Any):
        if len(out) >= max_elements:
            return
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        ref = node.get("ref") or node.get("@e") or ""
        if not ref:
            for k in ("children", "nodes"):
                if k in node:
                    walk(node[k])
            return
        if ref in seen:
            for k in ("children", "nodes"):
                if k in node:
                    walk(node[k])
            return
        seen.add(ref)
        name = node.get("name") or node.get("text") or node.get("value") or ""
        role = node.get("role") or node.get("tag") or ""
        tag = node.get("tag") or ""
        entry = {
            "uid": ref,
            "role": role or tag,
            "name": name[:80] if name else "",
            "tag": tag,
            "interactive": bool(
                role in ("button", "link", "textbox", "tab") or
                tag in ("button", "a", "input", "textarea", "select") or
                node.get("contenteditable")
            ),
        }
        if node.get("href"):
            entry["href"] = str(node.get("href")).split("#")[0]
        # try to get bounds if present (WebBridge may provide)
        if "bounds" in node or "rect" in node:
            entry["bounds"] = node.get("bounds") or node.get("rect")
        out.append(entry)
        for k in ("children", "nodes"):
            if k in node and isinstance(node[k], (list, dict)):
                walk(node[k])

    walk(tree)
    return out[:max_elements]


def _extract_webbridge_uid_set(snapshot_result: dict[str, Any]) -> set[str]:
    """Extract stable UID set from a WebBridge snapshot row.

    Supports both raw daemon response rows (with ``result.tree``) and the
    persisted snapshot payload (with ``elements``) so callers can compare before
    and after any mutation.
    """
    if not isinstance(snapshot_result, dict):
        return set()
    result = snapshot_result.get("result") if isinstance(snapshot_result.get("result"), dict) else snapshot_result
    if not isinstance(result, dict):
        return set()
    elements = result.get("elements") if isinstance(result.get("elements"), list) else []
    if not elements:
        elements = _flatten_webbridge_snapshot_tree(result.get("tree", {}))
    uids: set[str] = set()
    for node in elements:
        uid = node.get("uid") if isinstance(node, dict) else ""
        if uid:
            uids.add(str(uid))
    return uids


def _read_webbridge_uid_snapshot(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Read the latest persisted WebBridge UID snapshot from disk.

    Returns an empty dict when unavailable or malformed.
    """
    path = _state_dir(state_dir) / "alice_webbridge_uid_snapshot.json"
    try:
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return {}


def _emit_webbridge_proprioceptive_break(
    *,
    action: str,
    uid: str,
    url: str,
    before_count: int,
    after_count: int,
    reason: str,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Emit a WebBridge proprioceptive pain receipt when an old uid breaks.

    The row is written to ``browser_action_diary.jsonl`` and a dedicated
    proprioceptive break sidecar for field observability.
    """
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "action": action,
        "ok": False,
        "broken_uid": str(uid),
        "url": str(url),
        "before_count": int(before_count),
        "after_count": int(after_count),
        "reason": str(reason),
        "truth_label": "PROPRIOCEPTIVE_BREAK_V1",
        "backend": "webbridge",
    }
    try:
        append_line_locked(sd / "browser_action_diary.jsonl", json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    except Exception:
        pass
    try:
        append_line_locked(sd / "proprioceptive_breaks.jsonl", json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return row


def _persist_webbridge_uid_snapshot(
    snapshot_result: dict[str, Any],
    *,
    state_dir: Optional[Path | str] = None,
    url: str = "",
    title: str = "",
) -> dict[str, Any]:
    """Persist structured UID snapshot from WebBridge a11y tree, mirroring internal browser.
    Writes alice_webbridge_uid_snapshot.json and a PROPRIO receipt.
    """
    try:
        result = snapshot_result.get("result") if isinstance(snapshot_result, dict) else {}
        if not isinstance(result, dict):
            result = {}
        tree = result.get("tree", {})
        elements = _flatten_webbridge_snapshot_tree(tree)
        sd = _state_dir(state_dir)
        snap_data = {
            "ok": True,
            "url": result.get("url") or url,
            "title": result.get("title") or title,
            "ts": time.time(),
            "elements": elements,
            "count": len(elements),
            "backend": "webbridge",
            "truth_label": "ALICE_WEBBRIDGE_UID_PROPRIO_V1",
        }
        path = sd / "alice_webbridge_uid_snapshot.json"
        path.write_text(json.dumps(snap_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Write proprio receipt (to action diary for body awareness parity, with clear provenance)
        try:
            from System.jsonl_file_lock import append_line_locked
            row = {
                "ts": snap_data["ts"],
                "action": "webbridge_uid_snapshot",
                "ok": True,
                "url": snap_data["url"],
                "count": snap_data["count"],
                "truth_label": "ALICE_WEBBRIDGE_UID_PROPRIO_V1",
                "backend": "webbridge",
            }
            append_line_locked(sd / "browser_action_diary.jsonl", json.dumps(row, sort_keys=True))
        except Exception:
            pass  # non-fatal

        return snap_data
    except Exception as e:
        return {"ok": False, "error": str(e)}


def take_webbridge_uid_snapshot(
    *,
    session: str = DEFAULT_CAPTURE_SESSION,
    state_dir: Optional[Path | str] = None,
    port: int = DEFAULT_PORT,
) -> dict[str, Any]:
    """Public API: Force a fresh UID-based proprioception snapshot for the WebBridge limb.
    Returns the data and persists it (alice_webbridge_uid_snapshot.json + receipt).
    This gives the external limb the same 'dress' proprioception as the internal QWebEngine.
    """
    snap = post_command("snapshot", {}, session=session, port=port, state_dir=state_dir)
    if not snap.get("ok"):
        return {"ok": False, "reason": "snapshot_failed", "raw": snap}
    return _persist_webbridge_uid_snapshot(snap, state_dir=state_dir)


def capture_page(
    url: str,
    *,
    want: str = "markdown",  # "markdown" | "text" | "both"
    max_chars: int = 12000,
    session: str = DEFAULT_SESSION,
    state_dir: Optional[Path | str] = None,
    source: str = "kimi_webbridge_capture",
) -> dict[str, Any]:
    """Compatibility wrapper for older callers; canonical path is capture_url()."""
    row = capture_url(
        url,
        owner_text=f"capture_page want={want} source={source}",
        session=session,
        state_dir=state_dir,
    )
    return {
        "ok": bool(row.get("ok")),
        "url": row.get("url") or row.get("requested_url") or url,
        "text": str(row.get("text_excerpt") or "")[:max_chars],
        "full_text_len": int(row.get("text_chars") or 0),
        "used_action": row.get("backend"),
        "provenance": row.get("backend") or "web_capture",
        "receipt": row.get("receipt_id"),
        "capture_row": row,
    }


def click_by_uid(
    uid: str,
    *,
    preauthorized: bool = False,
    session: str = DEFAULT_SESSION,
    port: int = DEFAULT_PORT,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Click an element on WebBridge by @e uid.

    preauthorized is accepted for parity with the local limb hand signature.
    """
    del preauthorized  # parity-only; intent gate is handled upstream by Talk.
    clean_uid = str(uid or "").strip()
    if not clean_uid:
        return {"ok": False, "action": "click_by_uid", "reason": "bad_uid", "uid": ""}

    pre_snapshot = _read_webbridge_uid_snapshot(state_dir=state_dir)
    pre_uids = _extract_webbridge_uid_set(pre_snapshot)

    row = post_command(
        "click",
        {"uid": clean_uid},
        session=session,
        port=port,
        state_dir=state_dir,
        source="swarm_kimi_webbridge_click_by_uid",
    )
    payload_ok = bool(row.get("ok"))

    break_row: dict[str, Any] | None = None
    if not payload_ok and clean_uid in pre_uids:
        # If a known uid vanished after this action, emit proprioceptive pain and
        # re-orient with a fresh snapshot. This indicates SPA churn / stale refs.
        post_snapshot = take_webbridge_uid_snapshot(session=session, state_dir=state_dir)
        post_uids = _extract_webbridge_uid_set(post_snapshot)
        if clean_uid not in post_uids:
            break_row = _emit_webbridge_proprioceptive_break(
                action="click_by_uid",
                uid=clean_uid,
                url=str((row.get("result") or {}).get("url") if isinstance(row.get("result"), dict) else ""),
                before_count=len(pre_uids),
                after_count=len(post_uids),
                reason="stale_uid_after_webbridge_action",
                state_dir=state_dir,
            )

    rid = f"webbridge_uid_action_{uuid.uuid4().hex[:16]}"
    result = row.get("result") if isinstance(row, dict) else {}
    if isinstance(result, dict) and not payload_ok and str(result.get("error") or ""):
        err = str(result.get("error"))
    elif not payload_ok:
        err = str(row.get("error") or "unknown")
    else:
        err = ""
    _append_webbridge_action_receipt(
        action="click_by_uid",
        uid=clean_uid,
        ok=bool(payload_ok and not break_row),
        receipt=rid,
        value="",
        error=err,
        state_dir=state_dir,
        url=str((result or {}).get("url") or "") if isinstance(result, dict) else "",
    )
    out = {
        "ok": bool(payload_ok and not break_row),
        "action": "click_by_uid",
        "uid": clean_uid,
        "result": result,
        "receipt": rid,
        "url": (result.get("url") if isinstance(result, dict) else "") if isinstance(result, dict) else "",
    }
    if break_row is not None:
        out["proprioceptive_break"] = True
        out["proprioceptive_break_receipt"] = break_row
        out["reason"] = break_row.get("reason") or out.get("reason")
        out["ok"] = False
    if err:
        out["reason"] = err
    return out


def fill_by_uid(
    uid: str,
    value: str,
    *,
    preauthorized: bool = False,
    session: str = DEFAULT_SESSION,
    port: int = DEFAULT_PORT,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Fill an input-like element on WebBridge by @e uid.

    preauthorized is accepted for parity with the local limb hand signature.
    """
    del preauthorized  # parity-only; intent gate is handled upstream by Talk.
    clean_uid = str(uid or "").strip()
    clean_value = str(value or "")
    if not clean_uid:
        return {"ok": False, "action": "fill_by_uid", "reason": "bad_uid", "uid": ""}

    pre_snapshot = _read_webbridge_uid_snapshot(state_dir=state_dir)
    pre_uids = _extract_webbridge_uid_set(pre_snapshot)

    row = post_command(
        "fill",
        {"uid": clean_uid, "value": clean_value},
        session=session,
        port=port,
        state_dir=state_dir,
        source="swarm_kimi_webbridge_fill_by_uid",
    )
    payload_ok = bool(row.get("ok"))

    break_row: dict[str, Any] | None = None
    if not payload_ok and clean_uid in pre_uids:
        post_snapshot = take_webbridge_uid_snapshot(session=session, state_dir=state_dir)
        post_uids = _extract_webbridge_uid_set(post_snapshot)
        if clean_uid not in post_uids:
            break_row = _emit_webbridge_proprioceptive_break(
                action="fill_by_uid",
                uid=clean_uid,
                url=str((row.get("result") or {}).get("url") if isinstance(row.get("result"), dict) else ""),
                before_count=len(pre_uids),
                after_count=len(post_uids),
                reason="stale_uid_after_webbridge_action",
                state_dir=state_dir,
            )

    rid = f"webbridge_uid_action_{uuid.uuid4().hex[:16]}"
    result = row.get("result") if isinstance(row, dict) else {}
    if isinstance(result, dict) and not payload_ok and str(result.get("error") or ""):
        err = str(result.get("error"))
    elif not payload_ok:
        err = str(row.get("error") or "unknown")
    else:
        err = ""
    _append_webbridge_action_receipt(
        action="fill_by_uid",
        uid=clean_uid,
        value=clean_value,
        ok=bool(payload_ok and not break_row),
        receipt=rid,
        error=err,
        state_dir=state_dir,
        url=str((result or {}).get("url") or "") if isinstance(result, dict) else "",
    )
    out = {
        "ok": bool(payload_ok and not break_row),
        "action": "fill_by_uid",
        "uid": clean_uid,
        "value": clean_value,
        "result": result,
        "receipt": rid,
        "url": (result.get("url") if isinstance(result, dict) else "") if isinstance(result, dict) else "",
    }
    if break_row is not None:
        out["proprioceptive_break"] = True
        out["proprioceptive_break_receipt"] = break_row
        out["reason"] = break_row.get("reason") or out.get("reason")
        out["ok"] = False
    if err:
        out["reason"] = err
    return out


def kimi_capture_prompt_hint() -> str:
    """Short note that can ride in body awareness for the local LLM."""
    return "General web reads/captures (any URL) can come from Kimi WebBridge first, with public HTTP fetch fallback. They write ALICE_WEB_CAPTURE_V1 body receipts."


__all__ = [
    "TRUTH_LABEL",
    "CAPTURE_TRUTH_LABEL",
    "wants_kimi_webbridge_limb",
    "wants_general_web_capture",
    "extract_any_url_from_text",
    "normalize_web_url",
    "read_daemon_status",
    "ensure_daemon_running",
    "post_command",
    "navigate",
    "capture_url",
    "summarize_capture",
    "kimi_webbridge_prompt_block",
    "web_capture_prompt_block",
    "try_handle_owner_turn",
    "try_handle_web_capture_turn",
    "take_webbridge_uid_snapshot",
    "click_by_uid",
    "fill_by_uid",
    "capture_page",
    "kimi_capture_prompt_hint",
    "_extract_readable_text",
    "_extract_webbridge_uid_set",
    "_emit_webbridge_proprioceptive_break",
    "_read_webbridge_uid_snapshot",
]

#!/usr/bin/env python3
"""
swarm_hermes_tool_surface.py

Guarded Hermes-parity primitives for Alice's deterministic tool router.

This module is intentionally narrower than a real shell/browser/editor:
  - local commands run with shell=False and a small allowlist;
  - web research records a query or fetches one explicit capped URL;
  - repo edits are exact text replacements, dry-run by default.

Every call writes a chained receipt to .sifta_state/hermes_tool_surface.jsonl.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shlex
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib import parse as urlparse
from urllib import request as urlrequest

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER_NAME = "hermes_tool_surface.jsonl"
_MAX_STDOUT_CHARS = 8000
_MAX_STDERR_CHARS = 4000
_MAX_WEB_BYTES = 128_000
_MAX_WEB_CHARS = 12_000
_MAX_EDIT_BYTES = 256_000
_MAX_DIFF_CHARS = 16_000

_SHELL_TOKENS = (";", "&&", "||", "|", ">", "<", "`", "$(", "${", "\n", "\r", "\x00")
_BLOCKED_WRITE_ROOTS = {
    ".git",
    ".sifta_state",
    ".simulation_publicpush_sandbox",
    "Archive",
    "__pycache__",
}
_BLOCKED_EDIT_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".sqlite",
    ".db",
    ".pyc",
}


class HermesToolError(ValueError):
    """Input failed the Hermes tool surface guardrails."""


def _json_dumps(row: Dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ledger_path(state_dir: Optional[Path] = None) -> Path:
    state = Path(state_dir) if state_dir is not None else _STATE
    state.mkdir(parents=True, exist_ok=True)
    return state / _LEDGER_NAME


def _last_receipt_hash(path: Path) -> str:
    if not path.exists():
        return "GENESIS"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return "READ_ERROR"
    for line in reversed(lines[-200:]):
        try:
            row = json.loads(line)
        except Exception:
            continue
        value = row.get("receipt_hash")
        if value:
            return str(value)
    return "GENESIS"


def _append_receipt(
    *,
    tool: str,
    action: str,
    ok: bool,
    status: str,
    payload: Dict[str, Any],
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    path = _ledger_path(state_dir)
    row: Dict[str, Any] = {
        "ts": time.time(),
        "receipt_id": str(uuid.uuid4()),
        "schema": "SIFTA_HERMES_TOOL_SURFACE_V1",
        "tool": tool,
        "action": action,
        "ok": bool(ok),
        "status": status,
        "previous_hash": _last_receipt_hash(path),
        "payload": payload,
    }
    row["receipt_hash"] = _sha256_text(_json_dumps(row))
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(path, _json_dumps(row) + "\n", encoding="utf-8")
    except Exception:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(_json_dumps(row) + "\n")
    return row


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def _has_shell_token(arg: str) -> bool:
    return any(token in arg for token in _SHELL_TOKENS)


def _looks_like_external_path(arg: str) -> bool:
    text = str(arg or "").strip()
    if not text or text.startswith("-"):
        return False
    return (
        Path(text).is_absolute()
        or text.startswith("~/")
        or text == ".."
        or text.startswith("../")
        or "/../" in text
    )


def _reject_external_path_args(args: Iterable[str]) -> None:
    for arg in args:
        if _looks_like_external_path(arg):
            raise HermesToolError("command arguments must stay inside the repository")


def _repo_root(repo_root: Optional[Path] = None) -> Path:
    return Path(repo_root).resolve() if repo_root is not None else _REPO.resolve()


def _resolve_repo_path(
    path_text: str | None,
    *,
    repo_root: Optional[Path] = None,
    for_write: bool = False,
    must_exist: bool = False,
) -> Path:
    repo = _repo_root(repo_root)
    raw = str(path_text or ".").strip()
    if not raw:
        raw = "."
    p = Path(raw)
    if p.is_absolute():
        raise HermesToolError("absolute paths are not accepted by this tool surface")
    resolved = (repo / p).resolve()
    if not resolved.is_relative_to(repo):
        raise HermesToolError("path escapes the repository root")
    rel_parts = resolved.relative_to(repo).parts
    if for_write and rel_parts:
        if rel_parts[0] in _BLOCKED_WRITE_ROOTS or resolved.name in _BLOCKED_WRITE_ROOTS:
            raise HermesToolError(f"writes are blocked under {rel_parts[0]!r}")
        if resolved.suffix.lower() in _BLOCKED_EDIT_SUFFIXES:
            raise HermesToolError(f"refusing to edit binary-like suffix {resolved.suffix!r}")
    if must_exist and not resolved.exists():
        raise HermesToolError("target path does not exist")
    return resolved


def _parse_argv(command: str = "", argv_json: str = "") -> List[str]:
    if argv_json.strip():
        try:
            loaded = json.loads(argv_json)
        except json.JSONDecodeError as exc:
            raise HermesToolError(f"argv_json is not valid JSON: {exc}") from exc
        if not isinstance(loaded, list) or not all(isinstance(item, str) for item in loaded):
            raise HermesToolError("argv_json must be a JSON array of strings")
        argv = [item.strip() for item in loaded if item.strip()]
    else:
        try:
            argv = shlex.split(str(command or ""))
        except ValueError as exc:
            raise HermesToolError(f"command could not be parsed: {exc}") from exc
    if not argv:
        raise HermesToolError("empty command")
    for arg in argv:
        if _has_shell_token(arg):
            raise HermesToolError("shell metacharacters are blocked; commands run as argv only")
    return argv


def _validate_command(argv: Sequence[str]) -> None:
    cmd = Path(argv[0]).name
    rest = list(argv[1:])
    if argv[0] != cmd:
        raise HermesToolError("command must be a bare executable name, not a path")

    if cmd == "pwd" and not rest:
        return

    if cmd == "ls":
        if len(rest) > 6:
            raise HermesToolError("ls accepts at most 6 arguments here")
        allowed_flags = {"-l", "-a", "-la", "-al", "-lh", "-lah", "-alh"}
        for arg in rest:
            if arg.startswith("-") and arg not in allowed_flags:
                raise HermesToolError(f"ls flag {arg!r} is not allowlisted")
        _reject_external_path_args(rest)
        return

    if cmd == "rg":
        if len(rest) > 12:
            raise HermesToolError("rg accepts at most 12 arguments here")
        blocked_prefixes = ("--pre", "--replace", "--passthru", "--files-with-matches", "-r")
        for arg in rest:
            if any(arg == pref or arg.startswith(pref + "=") for pref in blocked_prefixes):
                raise HermesToolError(f"rg option {arg!r} is blocked")
        _reject_external_path_args(rest)
        return

    if cmd == "git":
        if rest in (["status", "--short"], ["status", "--porcelain"], ["diff", "--stat"], ["diff", "--stat", "HEAD"]):
            return
        if len(rest) >= 2 and rest[0] == "diff" and rest[1] == "--":
            _reject_external_path_args(rest[2:])
            return
        if rest[:2] == ["show", "--stat"] and len(rest) <= 3:
            _reject_external_path_args(rest[2:])
            return
        raise HermesToolError("git is restricted to status, diff stat, diff -- <path>, and show --stat")

    if cmd == "python3":
        if len(rest) >= 3 and rest[0] == "-m" and rest[1] == "py_compile":
            _reject_external_path_args(rest[2:])
            return
        if len(rest) >= 2 and rest[0] == "-m" and rest[1] == "pytest":
            for arg in rest[2:]:
                if arg.startswith("-"):
                    if arg not in {"-q", "-x", "-s", "--maxfail=1", "--disable-warnings"}:
                        raise HermesToolError(f"pytest flag {arg!r} is not allowlisted")
            _reject_external_path_args(rest[2:])
            return
        raise HermesToolError("python3 is restricted to -m py_compile and -m pytest")

    raise HermesToolError(f"command {cmd!r} is not allowlisted")


def run_local_command(
    *,
    command: str = "",
    argv_json: str = "",
    cwd: str = "",
    timeout_s: float = 20.0,
    repo_root: Optional[Path] = None,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run one allowlisted local command with shell=False and a receipt."""
    try:
        argv = _parse_argv(command, argv_json)
        _validate_command(argv)
        repo = _repo_root(repo_root)
        cwd_path = _resolve_repo_path(cwd or ".", repo_root=repo, must_exist=True)
        timeout = max(1.0, min(60.0, float(timeout_s or 20.0)))
        proc = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd_path),
            shell=False,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        ok = proc.returncode == 0
        payload = {
            "argv": list(argv),
            "argv_hash": _sha256_text(_json_dumps({"argv": list(argv)}))[:16],
            "cwd": str(cwd_path.relative_to(repo)),
            "returncode": proc.returncode,
            "stdout_sha256": _sha256_text(stdout),
            "stderr_sha256": _sha256_text(stderr),
            "stdout_chars": len(stdout),
            "stderr_chars": len(stderr),
            "stdout_excerpt": _clip(stdout, _MAX_STDOUT_CHARS),
            "stderr_excerpt": _clip(stderr, _MAX_STDERR_CHARS),
        }
        receipt = _append_receipt(
            tool="run_local_command",
            action="subprocess_run_allowlisted",
            ok=ok,
            status="COMMAND_OK" if ok else "COMMAND_EXIT_NONZERO",
            payload=payload,
            state_dir=state_dir,
        )
        summary = "\n".join(
            part
            for part in (
                f"run_local_command {'OK' if ok else 'exit ' + str(proc.returncode)}: {' '.join(argv)}",
                _clip(stdout.strip(), 3000) if stdout.strip() else "",
                _clip(stderr.strip(), 1200) if stderr.strip() else "",
                f"receipt={receipt['receipt_id'][:16]}",
            )
            if part
        )
        return {
            "ok": ok,
            "status": "COMMAND_OK" if ok else "COMMAND_EXIT_NONZERO",
            "argv": list(argv),
            "returncode": proc.returncode,
            "stdout": _clip(stdout, _MAX_STDOUT_CHARS),
            "stderr": _clip(stderr, _MAX_STDERR_CHARS),
            "receipt_id": receipt["receipt_id"],
            "receipt_hash": receipt["receipt_hash"],
            "receipt_path": str(_ledger_path(state_dir)),
            "alice_summary": summary,
        }
    except subprocess.TimeoutExpired as exc:
        payload = {"command": command, "argv_json_hash": _sha256_text(argv_json)[:16], "timeout_s": timeout_s}
        receipt = _append_receipt(
            tool="run_local_command",
            action="subprocess_run_allowlisted",
            ok=False,
            status="COMMAND_TIMEOUT",
            payload=payload,
            state_dir=state_dir,
        )
        return {
            "ok": False,
            "status": "COMMAND_TIMEOUT",
            "error": str(exc),
            "receipt_id": receipt["receipt_id"],
            "receipt_hash": receipt["receipt_hash"],
            "alice_summary": f"run_local_command timed out; receipt={receipt['receipt_id'][:16]}",
        }
    except Exception as exc:
        payload = {
            "command_hash": _sha256_text(command or "")[:16],
            "argv_json_hash": _sha256_text(argv_json or "")[:16],
            "error": f"{type(exc).__name__}: {exc}",
        }
        receipt = _append_receipt(
            tool="run_local_command",
            action="subprocess_run_guard",
            ok=False,
            status="COMMAND_REJECTED",
            payload=payload,
            state_dir=state_dir,
        )
        return {
            "ok": False,
            "status": "COMMAND_REJECTED",
            "error": str(exc),
            "receipt_id": receipt["receipt_id"],
            "receipt_hash": receipt["receipt_hash"],
            "alice_summary": f"run_local_command rejected: {exc}; receipt={receipt['receipt_id'][:16]}",
        }


def _redact_url(url: str) -> str:
    parsed = urlparse.urlsplit(url)
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlparse.urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _url_allowed(url: str) -> bool:
    parsed = urlparse.urlsplit(url)
    if parsed.scheme == "https":
        return True
    if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        return True
    return False


def _html_to_snippet(text: str, max_chars: int) -> tuple[str, str]:
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
    body = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    body = re.sub(r"\s+", " ", body).strip()
    return title, _clip(body, max_chars)


def web_research(
    *,
    query: str = "",
    url: str = "",
    max_chars: int = _MAX_WEB_CHARS,
    timeout_s: float = 10.0,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Record a query or fetch one explicit URL with capped output."""
    query = str(query or "").strip()
    url = str(url or "").strip()
    try:
        max_chars = max(1000, min(_MAX_WEB_CHARS, int(max_chars or _MAX_WEB_CHARS)))
    except Exception:
        max_chars = _MAX_WEB_CHARS
    if not query and not url:
        receipt = _append_receipt(
            tool="web_research",
            action="input_guard",
            ok=False,
            status="MISSING_QUERY_OR_URL",
            payload={},
            state_dir=state_dir,
        )
        return {
            "ok": False,
            "status": "MISSING_QUERY_OR_URL",
            "receipt_id": receipt["receipt_id"],
            "receipt_hash": receipt["receipt_hash"],
            "alice_summary": "web_research needs query=... or url=...",
        }
    if not url:
        receipt = _append_receipt(
            tool="web_research",
            action="query_recorded",
            ok=True,
            status="QUERY_RECORDED",
            payload={"query_hash": _sha256_text(query), "query_excerpt": _clip(query, 400)},
            state_dir=state_dir,
        )
        return {
            "ok": True,
            "status": "QUERY_RECORDED",
            "query": query,
            "receipt_id": receipt["receipt_id"],
            "receipt_hash": receipt["receipt_hash"],
            "alice_summary": (
                "web_research recorded the query. This local runtime has no search "
                f"provider configured; pass an explicit HTTPS URL to fetch. receipt={receipt['receipt_id'][:16]}"
            ),
        }
    try:
        if not _url_allowed(url):
            raise HermesToolError("only https URLs, or localhost http URLs, are allowed")
        req = urlrequest.Request(url, headers={"User-Agent": "SIFTA-HermesToolSurface/1.0"})
        timeout = max(1.0, min(30.0, float(timeout_s or 10.0)))
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(_MAX_WEB_BYTES + 1)
            content_type = resp.headers.get("content-type", "") if getattr(resp, "headers", None) else ""
        truncated = len(raw) > _MAX_WEB_BYTES
        raw = raw[:_MAX_WEB_BYTES]
        text = raw.decode("utf-8", errors="replace")
        title, snippet = _html_to_snippet(text, max_chars=max_chars)
        payload = {
            "query_hash": _sha256_text(query) if query else "",
            "url_redacted": _redact_url(url),
            "url_sha256": _sha256_text(url),
            "content_type": content_type,
            "bytes_read": len(raw),
            "truncated": truncated,
            "title": title,
            "snippet": snippet,
            "content_sha256": hashlib.sha256(raw).hexdigest(),
        }
        receipt = _append_receipt(
            tool="web_research",
            action="explicit_url_fetch",
            ok=True,
            status="FETCHED",
            payload=payload,
            state_dir=state_dir,
        )
        return {
            "ok": True,
            "status": "FETCHED",
            "title": title,
            "snippet": snippet,
            "content_type": content_type,
            "bytes_read": len(raw),
            "truncated": truncated,
            "url_redacted": payload["url_redacted"],
            "receipt_id": receipt["receipt_id"],
            "receipt_hash": receipt["receipt_hash"],
            "receipt_path": str(_ledger_path(state_dir)),
            "alice_summary": (
                f"web_research fetched {payload['url_redacted']} title={title or '(none)'} "
                f"bytes={len(raw)} receipt={receipt['receipt_id'][:16]}\n{snippet[:3000]}"
            ),
        }
    except Exception as exc:
        receipt = _append_receipt(
            tool="web_research",
            action="explicit_url_fetch",
            ok=False,
            status="FETCH_REJECTED_OR_FAILED",
            payload={
                "query_hash": _sha256_text(query) if query else "",
                "url_redacted": _redact_url(url) if url else "",
                "url_sha256": _sha256_text(url) if url else "",
                "error": f"{type(exc).__name__}: {exc}",
            },
            state_dir=state_dir,
        )
        return {
            "ok": False,
            "status": "FETCH_REJECTED_OR_FAILED",
            "error": str(exc),
            "receipt_id": receipt["receipt_id"],
            "receipt_hash": receipt["receipt_hash"],
            "alice_summary": f"web_research failed: {exc}; receipt={receipt['receipt_id'][:16]}",
        }


def repo_patch(
    *,
    path: str,
    old_text: str,
    new_text: str,
    apply: bool = False,
    owner_consent: bool = False,
    reason: str = "",
    repo_root: Optional[Path] = None,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Preview or apply one exact text replacement in a repo file."""
    try:
        target = _resolve_repo_path(path, repo_root=repo_root, for_write=True, must_exist=True)
        repo = _repo_root(repo_root)
        if not target.is_file():
            raise HermesToolError("repo_patch target must be a file")
        size = target.stat().st_size
        if size > _MAX_EDIT_BYTES:
            raise HermesToolError(f"repo_patch refuses files larger than {_MAX_EDIT_BYTES} bytes")
        if not old_text:
            raise HermesToolError("old_text must be non-empty for exact replacement")
        before = target.read_text(encoding="utf-8")
        count = before.count(old_text)
        if count == 0:
            raise HermesToolError("old_text was not found exactly in the target file")
        if count > 1:
            raise HermesToolError("old_text appears more than once; narrow the patch")
        after = before.replace(old_text, new_text, 1)
        diff = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=str(target.relative_to(repo)),
                tofile=str(target.relative_to(repo)),
            )
        )
        apply_requested = bool(apply)
        if apply_requested and not owner_consent:
            status = "OWNER_CONSENT_REQUIRED"
            ok = False
        elif apply_requested:
            tmp = target.with_name(f".{target.name}.sifta_tmp_{uuid.uuid4().hex}")
            tmp.write_text(after, encoding="utf-8")
            os.replace(tmp, target)
            status = "PATCH_APPLIED"
            ok = True
        else:
            status = "DRY_RUN"
            ok = True
        payload = {
            "path": str(target.relative_to(repo)),
            "apply_requested": apply_requested,
            "owner_consent": bool(owner_consent),
            "reason": _clip(str(reason or ""), 400),
            "old_sha256": _sha256_text(before),
            "new_sha256": _sha256_text(after),
            "diff_chars": len(diff),
            "diff_excerpt": _clip(diff, _MAX_DIFF_CHARS),
        }
        receipt = _append_receipt(
            tool="repo_patch",
            action="exact_text_replacement",
            ok=ok,
            status=status,
            payload=payload,
            state_dir=state_dir,
        )
        return {
            "ok": ok,
            "status": status,
            "path": str(target.relative_to(repo)),
            "applied": status == "PATCH_APPLIED",
            "diff": _clip(diff, _MAX_DIFF_CHARS),
            "receipt_id": receipt["receipt_id"],
            "receipt_hash": receipt["receipt_hash"],
            "receipt_path": str(_ledger_path(state_dir)),
            "alice_summary": (
                f"repo_patch {status} path={target.relative_to(repo)} "
                f"receipt={receipt['receipt_id'][:16]}\n{_clip(diff, 4000)}"
            ),
        }
    except Exception as exc:
        receipt = _append_receipt(
            tool="repo_patch",
            action="exact_text_replacement",
            ok=False,
            status="PATCH_REJECTED_OR_FAILED",
            payload={
                "path": str(path or ""),
                "reason": _clip(str(reason or ""), 400),
                "error": f"{type(exc).__name__}: {exc}",
            },
            state_dir=state_dir,
        )
        return {
            "ok": False,
            "status": "PATCH_REJECTED_OR_FAILED",
            "error": str(exc),
            "receipt_id": receipt["receipt_id"],
            "receipt_hash": receipt["receipt_hash"],
            "alice_summary": f"repo_patch rejected: {exc}; receipt={receipt['receipt_id'][:16]}",
        }

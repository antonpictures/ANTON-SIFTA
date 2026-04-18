#!/usr/bin/env python3
"""
System/swarm_shadow_state.py — Copy-on-write JSONL substrate (the dream sandbox)
═══════════════════════════════════════════════════════════════════════════════
Substrate for the DeepMind Dreamer Protocol.

Why this exists
---------------
The hippocampal replay engine (AG31's swarm_hippocampal_replay.py) needs to
mutate `.sifta_state/*.jsonl` files thousands of times per night to simulate
counterfactuals — "what if the Architect had rejected this?", "what if this
ran on M1 instead of M5?" — without ever touching the real ledgers.

The cerebellar MCTS engine (future) needs the same primitive: drop a
candidate action into a sandbox, run it forward, observe consequences,
discard the sandbox if the outcome was bad.

Both are the same substrate: a copy-on-write view over the SIFTA state dir.

The contract — daughter-safe by construction
---------------------------------------------
1. NEVER mutates base state. All writes go to an overlay tempdir.
2. discard() deletes the overlay; rollback is structural, not transactional.
3. read_lines(relpath) returns base + overlay lines in append order so
   readers can't tell they're in a sandbox.
4. context-manager use auto-discards on exit (even on exception) — leaks
   are impossible with `with ShadowState() as s:` discipline.
5. commit() exists but is opt-in and EXTREMELY rare; the dream engine
   should essentially never commit. Default = discard.
6. No locks held against the base files; concurrent real writes during a
   shadow session are fine (they'll be visible to the next read_lines call).

Pure stdlib. No new pip dependencies.
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_BASE_STATE = _REPO / ".sifta_state"
_SHADOW_AUDIT = _BASE_STATE / "shadow_state_audit.jsonl"

MODULE_VERSION = "2026-04-18.shadow_state.v1"

# Maximum on-disk size of a single overlay before we refuse to grow it.
# Prevents a runaway dreamer from filling the disk.
MAX_OVERLAY_BYTES = 64 * 1024 * 1024     # 64 MB per shadow session

# Maximum number of pending lines buffered in memory before a flush is forced.
MAX_BUFFER_LINES = 4096


# ──────────────────────────────────────────────────────────────────────
# ShadowState — the substrate
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ShadowSession:
    """Audit record for one shadow session — committed to disk on
    discard/commit so the Architect can audit dream activity."""
    session_id: str
    created_ts: float
    base_state_dir: str
    overlay_dir: str
    purpose: str
    files_touched: List[str] = field(default_factory=list)
    lines_written: int = 0
    bytes_written: int = 0
    outcome: str = "open"          # "open" | "discarded" | "committed" | "aborted"
    duration_ms: float = 0.0
    error: str = ""


class ShadowOverflowError(IOError):
    """Raised when an overlay would exceed MAX_OVERLAY_BYTES."""


class ShadowState:
    """A read-through, write-overlay view over .sifta_state/.

    Standard usage (always prefer `with` form — auto-discard on exception):

        from System.swarm_shadow_state import shadow_session

        with shadow_session(purpose="dreamer.replay.42") as shadow:
            shadow.append_line(
                "warp9_concierge_proposals.jsonl",
                json.dumps({...mutated...}),
            )
            rows = shadow.read_lines("warp9_concierge_proposals.jsonl")
            # ... evaluate counterfactual ...
        # overlay auto-discarded here; base state untouched
    """

    def __init__(
        self,
        *,
        base_state_dir: Optional[Path] = None,
        overlay_dir: Optional[Path] = None,
        purpose: str = "unspecified",
    ):
        self.base = (base_state_dir or _BASE_STATE).resolve()
        if not self.base.exists():
            raise FileNotFoundError(f"base state dir does not exist: {self.base}")

        self._owns_overlay = overlay_dir is None
        if overlay_dir is None:
            overlay_dir = Path(tempfile.mkdtemp(prefix="sifta_shadow_"))
        self.overlay = Path(overlay_dir).resolve()
        self.overlay.mkdir(parents=True, exist_ok=True)

        self.session = ShadowSession(
            session_id=uuid.uuid4().hex[:16],
            created_ts=time.time(),
            base_state_dir=str(self.base),
            overlay_dir=str(self.overlay),
            purpose=purpose,
        )

        # Buffered writes per overlay-relative path. Flushed on:
        # - read_lines() against the same path (consistency)
        # - buffer reaching MAX_BUFFER_LINES
        # - discard() / commit()
        self._buffers: Dict[str, List[str]] = {}
        self._closed = False

    # ── Sandboxing helpers ────────────────────────────────────────────

    def _normalize_relpath(self, relpath: str) -> str:
        """Reject any path that escapes the state dir (no .., no absolute)."""
        rp = Path(relpath)
        if rp.is_absolute():
            raise ValueError(f"shadow paths must be relative; got {relpath!r}")
        # Resolve and make sure it stays under base
        resolved = (self.base / rp).resolve()
        try:
            resolved.relative_to(self.base)
        except ValueError as exc:
            raise ValueError(
                f"shadow path {relpath!r} escapes base state dir"
            ) from exc
        return str(rp.as_posix())

    def _overlay_path(self, relpath: str) -> Path:
        rel = self._normalize_relpath(relpath)
        out = self.overlay / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    def _base_path(self, relpath: str) -> Path:
        return self.base / self._normalize_relpath(relpath)

    def _check_size_budget(self, additional_bytes: int) -> None:
        if self.session.bytes_written + additional_bytes > MAX_OVERLAY_BYTES:
            raise ShadowOverflowError(
                f"shadow session {self.session.session_id} would exceed "
                f"{MAX_OVERLAY_BYTES} bytes (current={self.session.bytes_written}, "
                f"+{additional_bytes})"
            )

    # ── Core read / write API ─────────────────────────────────────────

    def append_line(self, relpath: str, line: str) -> None:
        """Append a single line to the overlay version of `relpath`.
        The base file is never touched. If `line` lacks a trailing newline
        it is added automatically."""
        if self._closed:
            raise RuntimeError("shadow session already closed")
        rel = self._normalize_relpath(relpath)
        if not line.endswith("\n"):
            line = line + "\n"
        self._check_size_budget(len(line.encode("utf-8")))

        buf = self._buffers.setdefault(rel, [])
        buf.append(line)
        self.session.lines_written += 1
        self.session.bytes_written += len(line.encode("utf-8"))
        if rel not in self.session.files_touched:
            self.session.files_touched.append(rel)
        if len(buf) >= MAX_BUFFER_LINES:
            self._flush_one(rel)

    def append_json(self, relpath: str, payload: Any) -> None:
        """Convenience wrapper: append a JSON-serialised payload as one line."""
        self.append_line(relpath, json.dumps(payload, ensure_ascii=False))

    def _flush_one(self, rel: str) -> None:
        """Flush in-memory buffer for `rel` to overlay disk."""
        buf = self._buffers.get(rel)
        if not buf:
            return
        out = self._overlay_path(rel)
        with out.open("a", encoding="utf-8") as fh:
            fh.writelines(buf)
        self._buffers[rel] = []

    def _flush_all(self) -> None:
        for rel in list(self._buffers.keys()):
            self._flush_one(rel)

    def read_lines(self, relpath: str) -> List[str]:
        """Return base lines + overlay lines (in that order) for `relpath`.
        Newlines are stripped. Sandbox readers see the merged view."""
        if self._closed:
            raise RuntimeError("shadow session already closed")
        rel = self._normalize_relpath(relpath)
        # Flush pending writes so what we read is what we wrote.
        self._flush_one(rel)

        out: List[str] = []
        base = self._base_path(rel)
        if base.exists():
            try:
                with base.open("r", encoding="utf-8") as fh:
                    for ln in fh:
                        out.append(ln.rstrip("\n"))
            except OSError:
                pass
        overlay = self.overlay / rel
        if overlay.exists():
            try:
                with overlay.open("r", encoding="utf-8") as fh:
                    for ln in fh:
                        out.append(ln.rstrip("\n"))
            except OSError:
                pass
        return out

    def read_json_rows(self, relpath: str) -> List[Dict[str, Any]]:
        """Like read_lines but returns parsed JSON dicts; bad rows are skipped."""
        out: List[Dict[str, Any]] = []
        for ln in self.read_lines(relpath):
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        return out

    # ── Lifecycle ─────────────────────────────────────────────────────

    def discard(self) -> ShadowSession:
        """Throw the overlay away. Base state untouched. Idempotent."""
        if self._closed:
            return self.session
        self._closed = True
        self.session.outcome = "discarded"
        self.session.duration_ms = round(
            (time.time() - self.session.created_ts) * 1000, 2
        )
        try:
            if self._owns_overlay and self.overlay.exists():
                shutil.rmtree(self.overlay, ignore_errors=True)
        finally:
            self._audit()
        return self.session

    def commit(self) -> ShadowSession:
        """Merge overlay → base by appending each overlay file to its base
        counterpart. Use ONLY when the dream engine has decided the result
        should become real (extremely rare — usually you discard).

        Returns the audit session so the caller can record what landed.
        Note: this is append-only. We never overwrite base files.
        """
        if self._closed:
            raise RuntimeError("shadow session already closed")
        self._flush_all()
        self._closed = True
        try:
            for rel in self.session.files_touched:
                src = self.overlay / rel
                if not src.exists():
                    continue
                dst = self._base_path(rel)
                dst.parent.mkdir(parents=True, exist_ok=True)
                with src.open("r", encoding="utf-8") as ifh, \
                     dst.open("a", encoding="utf-8") as ofh:
                    shutil.copyfileobj(ifh, ofh)
            self.session.outcome = "committed"
            self.session.duration_ms = round(
                (time.time() - self.session.created_ts) * 1000, 2
            )
        except Exception as exc:
            self.session.outcome = "aborted"
            self.session.error = repr(exc)[:500]
        finally:
            try:
                if self._owns_overlay and self.overlay.exists():
                    shutil.rmtree(self.overlay, ignore_errors=True)
            except OSError:
                pass
            self._audit()
        return self.session

    def _audit(self) -> None:
        """Append the session record to .sifta_state/shadow_state_audit.jsonl
        so the Architect can audit dreamer activity."""
        try:
            row = {
                "session_id": self.session.session_id,
                "created_ts": self.session.created_ts,
                "purpose": self.session.purpose,
                "files_touched": self.session.files_touched,
                "lines_written": self.session.lines_written,
                "bytes_written": self.session.bytes_written,
                "outcome": self.session.outcome,
                "duration_ms": self.session.duration_ms,
                "error": self.session.error,
            }
            _SHADOW_AUDIT.parent.mkdir(parents=True, exist_ok=True)
            with _SHADOW_AUDIT.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ── Context-manager wrapper ───────────────────────────────────────

    def __enter__(self) -> "ShadowState":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Always discard on exit (even on success) unless caller already
        # called commit(). Discard is idempotent.
        if not self._closed:
            self.discard()


@contextmanager
def shadow_session(*, purpose: str = "unspecified") -> Iterator[ShadowState]:
    """Preferred entry point. Auto-discards on exit; even on exception."""
    s = ShadowState(purpose=purpose)
    try:
        yield s
    finally:
        if not s._closed:
            s.discard()


# ──────────────────────────────────────────────────────────────────────
# Audit reader — for AG31 + Concierge dashboards
# ──────────────────────────────────────────────────────────────────────

def recent_shadow_sessions(*, since_ts: float = 0.0, limit: int = 100) -> List[Dict[str, Any]]:
    """Return recent ShadowSession audit rows, most-recent last."""
    if not _SHADOW_AUDIT.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with _SHADOW_AUDIT.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("created_ts", 0) < since_ts:
                    continue
                out.append(row)
    except OSError:
        return []
    return out[-limit:]


# ──────────────────────────────────────────────────────────────────────
# Smoke
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print(f"[C47H-SMOKE-SHADOW] base_state={_BASE_STATE}")
    print(f"[C47H-SMOKE-SHADOW] {MODULE_VERSION}")

    # 1) Basic write+read+discard cycle
    rel = "warp9_concierge_proposals.jsonl"
    base_count_before = 0
    if (_BASE_STATE / rel).exists():
        base_count_before = sum(
            1 for line in (_BASE_STATE / rel).open("r", encoding="utf-8") if line.strip()
        )

    with shadow_session(purpose="smoke.basic") as shadow:
        shadow.append_json(rel, {"shadow_test": True, "value": 1})
        shadow.append_json(rel, {"shadow_test": True, "value": 2})
        merged = shadow.read_json_rows(rel)
        shadow_only = sum(1 for r in merged if r.get("shadow_test"))
        print(f"[C47H-SMOKE-SHADOW] inside: base+overlay rows={len(merged)}, shadow-only={shadow_only}")
        assert shadow_only == 2, "shadow rows should be visible inside session"
        assert len(merged) == base_count_before + 2

    base_count_after = 0
    if (_BASE_STATE / rel).exists():
        base_count_after = sum(
            1 for line in (_BASE_STATE / rel).open("r", encoding="utf-8") if line.strip()
        )
    print(f"[C47H-SMOKE-SHADOW] after discard: base count {base_count_before} -> {base_count_after}")
    assert base_count_after == base_count_before, "discard must not touch base"

    # 2) Sandbox-escape rejection
    try:
        with shadow_session(purpose="smoke.escape") as shadow:
            shadow.append_line("../../etc/passwd", "owned\n")
        print("[C47H-SMOKE-SHADOW] FAIL: escape should have raised", file=sys.stderr)
        sys.exit(1)
    except ValueError:
        print("[C47H-SMOKE-SHADOW] sandbox-escape correctly refused")

    # 3) Auto-discard on exception
    try:
        with shadow_session(purpose="smoke.exception") as shadow:
            shadow.append_json(rel, {"shadow_test": True, "exc_path": True})
            raise RuntimeError("simulated dream-engine fault")
    except RuntimeError:
        pass
    base_count_final = 0
    if (_BASE_STATE / rel).exists():
        base_count_final = sum(
            1 for line in (_BASE_STATE / rel).open("r", encoding="utf-8") if line.strip()
        )
    assert base_count_final == base_count_before, "exception path must auto-discard"
    print("[C47H-SMOKE-SHADOW] auto-discard on exception OK")

    # 4) Audit visibility
    sessions = recent_shadow_sessions(since_ts=time.time() - 60)
    print(f"[C47H-SMOKE-SHADOW] recent shadow sessions in audit: {len(sessions)}")
    for s in sessions[-3:]:
        print(f"    {s['session_id']} purpose={s['purpose']!r} outcome={s['outcome']}")

    print("[C47H-SMOKE-SHADOW OK]")

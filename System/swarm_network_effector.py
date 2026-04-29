#!/usr/bin/env python3
"""
swarm_network_effector.py — Safe network effector execution law (Cell Membrane)
══════════════════════════════════════════════════════════════════════

Lifecycle: PROPOSE → SANDBOX → COMMIT → RECEIPT

- Starts with a strict whitelist of read-only domains (huggingface, nvidia, openai).
- No write actions to the internet. Only GET/HEAD.
- Sandbox issues a HEAD request to ensure the URL is alive.
- Commit issues a GET request, hashes the payload, and writes the receipt.
- Redirects are intercepted and blocked if they attempt to escape the whitelist.

See: Documents/IDE_BOOT_COVENANT.md
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked

SCHEMA_V1 = "SIFTA_EFFECTOR_RECEIPT_V1"
KIND_NETWORK_READ = "network_read"
PHASE_COMMIT = "COMMIT"
PHASE_BROKEN = "BROKEN"

_MAX_B64_PAYLOAD = 65_536  # bytes before base64
_DEFAULT_REGISTRATION_TRACE = Path(__file__).resolve().parents[1] / ".sifta_state" / "ide_stigmergic_trace.jsonl"
_ANONYMOUS_CALLERS = {"", "anonymous", "unknown", "none", "null"}

ALLOWED_DOMAINS = {
    "huggingface.co",
    "developer.nvidia.com",
    "api.openai.com",
}


def _canonical_dumps(obj: Dict[str, Any]) -> str:
    body = {k: v for k, v in sorted(obj.items()) if k != "integrity"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def receipt_integrity(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_dumps(payload).encode("utf-8")).hexdigest()


def verify_receipt_row(row: Dict[str, Any]) -> bool:
    if row.get("schema") != SCHEMA_V1:
        return False
    got = row.get("integrity")
    if not got or not isinstance(got, str):
        return False
    expect = receipt_integrity({k: v for k, v in row.items() if k != "integrity"})
    return got == expect


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def extract_domain(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.split(":")[0]


class WhitelistRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Immune system intercept: Block redirects to unwhitelisted domains."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        domain = extract_domain(newurl)
        if domain not in ALLOWED_DOMAINS:
            raise urllib.error.URLError(f"redirect_domain_escape:{domain}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _build_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(WhitelistRedirectHandler())


@dataclass
class ProposedNetworkAction:
    action_id: str
    kind: str
    url: str
    caller_id: str


class NetworkEffectorRuntime:
    """
    Network-bound effector (Cell Membrane).
    """

    def __init__(
        self,
        receipt_path: Path,
        registration_trace_path: Optional[Path] = None,
        default_caller_id: Optional[str] = None,
        require_registered_caller: bool = True,
    ) -> None:
        self.receipt_path = receipt_path
        self.registration_trace_path = registration_trace_path or _DEFAULT_REGISTRATION_TRACE
        self.default_caller_id = default_caller_id
        self.require_registered_caller = require_registered_caller
        self._pending: Dict[str, ProposedNetworkAction] = {}
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self._committed_ids: set[str] = self._load_committed_ids()

    def _load_committed_ids(self) -> set[str]:
        committed: set[str] = set()
        if not self.receipt_path.is_file():
            return committed
        with open(self.receipt_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not verify_receipt_row(row) or row.get("kind") != KIND_NETWORK_READ:
                    continue
                aid = str(row.get("action_id") or "")
                if not aid:
                    continue
                if row.get("phase") == PHASE_COMMIT and row.get("ok") is True:
                    committed.add(aid)
        return committed

    def _registered_caller_tokens(self) -> set[str]:
        tokens: set[str] = set()
        if not self.registration_trace_path.is_file():
            return tokens
        with open(self.registration_trace_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for key in ("doctor", "trace_id", "agent_id", "caller_id"):
                    value = row.get(key)
                    if value is not None:
                        tokens.add(str(value).strip())
        return tokens

    def _resolve_caller_id(self, action: Dict[str, Any]) -> str:
        caller_id = str(action.get("caller_id") or self.default_caller_id or "").strip()
        if caller_id.lower() in _ANONYMOUS_CALLERS:
            raise ValueError("anonymous_caller_refused")
        if self.require_registered_caller and caller_id not in self._registered_caller_tokens():
            raise ValueError("unregistered_caller_refused")
        return caller_id

    def _caller_for_action(self, action_id: str) -> Optional[str]:
        p = self._pending.get(action_id)
        if p:
            return p.caller_id
        row = self.receipt(action_id)
        if row and row.get("caller_id"):
            return str(row.get("caller_id"))
        return self.default_caller_id

    def _append_receipt(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(row)
        row.setdefault("schema", SCHEMA_V1)
        row.setdefault("status", "ok" if row.get("ok") is True else "error")
        if "truth_note" not in row:
            phase = row.get("phase", "UNKNOWN")
            if row.get("ok") is True:
                row["truth_note"] = f"{phase} recorded by deterministic network effector runtime."
            else:
                row["truth_note"] = f"{phase} recorded failure before or during deterministic network effector runtime."
        row["integrity"] = receipt_integrity(row)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        append_line_locked(self.receipt_path, json.dumps(row, separators=(",", ":")) + "\n")
        return row

    def propose(self, action: Dict[str, Any]) -> ProposedNetworkAction:
        """Step 1: Propose read. Verify domain is allowed."""
        caller_id = self._resolve_caller_id(action)
        if action.get("kind") != KIND_NETWORK_READ:
            raise ValueError(f"unsupported_kind:{action.get('kind')}")
        
        url = str(action.get("url", ""))
        if not url.startswith("https://") and not url.startswith("http://"):
            raise ValueError("invalid_url_scheme")

        domain = extract_domain(url)
        if domain not in ALLOWED_DOMAINS:
            raise ValueError("domain_not_whitelisted")

        aid = str(action.get("action_id") or uuid.uuid4())
        if aid in self._committed_ids:
            raise ValueError("action_id_already_committed")

        p = ProposedNetworkAction(
            action_id=aid,
            kind=KIND_NETWORK_READ,
            url=url,
            caller_id=caller_id,
        )
        self._pending[aid] = p
        return p

    def sandbox(self, action_id: str) -> Dict[str, Any]:
        """Step 2: HEAD request only — no data mutation, verifies endpoint is alive."""
        p = self._pending.get(action_id)
        if not p:
            return {"ok": False, "reason": "unknown_action_id"}
        
        domain = extract_domain(p.url)
        if domain not in ALLOWED_DOMAINS:
            return {"ok": False, "reason": "domain_not_whitelisted"}

        opener = _build_opener()
        req = urllib.request.Request(p.url, method="HEAD", headers={"User-Agent": "SIFTA/7.0 Membrane"})
        try:
            resp = opener.open(req, timeout=10)
            return {"ok": True, "status_code": resp.status, "content_type": resp.headers.get("Content-Type")}
        except urllib.error.HTTPError as e:
            return {"ok": False, "reason": f"http_error_{e.code}"}
        except urllib.error.URLError as e:
            return {"ok": False, "reason": f"url_error_{e.reason}"}
        except Exception as e:
            return {"ok": False, "reason": f"sandbox_error_{e}"}

    def commit(self, action_id: str) -> Dict[str, Any]:
        """Step 3: GET allowed ONLY after validation, hashes payload."""
        if action_id in self._committed_ids:
            self._append_receipt({
                "phase": PHASE_BROKEN,
                "action_id": action_id,
                "kind": KIND_NETWORK_READ,
                "ts": time.time(),
                "ok": False,
                "error": "double_commit",
                "caller_id": self._caller_for_action(action_id),
            })
            return {"ok": False, "error": "double_commit"}

        p = self._pending.get(action_id)
        if not p:
            self._append_receipt({
                "phase": PHASE_BROKEN,
                "action_id": action_id,
                "kind": KIND_NETWORK_READ,
                "ts": time.time(),
                "ok": False,
                "error": "unknown_or_expired_action",
                "caller_id": self._caller_for_action(action_id),
            })
            return {"ok": False, "error": "unknown_or_expired_action"}

        sb = self.sandbox(action_id)
        if not sb.get("ok"):
            err = sb.get("reason", "sandbox_failed")
            self._append_receipt({
                "phase": PHASE_BROKEN,
                "action_id": action_id,
                "kind": KIND_NETWORK_READ,
                "url": p.url,
                "ts": time.time(),
                "ok": False,
                "error": err,
                "caller_id": p.caller_id,
                "truth_note": f"Rejected GET request due to sandbox HEAD failure: {err}",
            })
            del self._pending[action_id]
            return {"ok": False, "error": err}

        opener = _build_opener()
        req = urllib.request.Request(p.url, method="GET", headers={"User-Agent": "SIFTA/7.0 Membrane"})
        try:
            resp = opener.open(req, timeout=30)
            data = resp.read()
            status_code = resp.status
        except urllib.error.HTTPError as e:
            # We still record HTTP errors as a broken phase because it failed to fetch.
            # But maybe the Architect wants 4xx recorded as commits? We'll log as BROKEN.
            self._append_receipt({
                "phase": PHASE_BROKEN,
                "action_id": action_id,
                "kind": KIND_NETWORK_READ,
                "url": p.url,
                "ts": time.time(),
                "ok": False,
                "error": f"http_error_{e.code}",
                "caller_id": p.caller_id,
            })
            del self._pending[action_id]
            return {"ok": False, "error": f"http_error_{e.code}"}
        except Exception as e:
            self._append_receipt({
                "phase": PHASE_BROKEN,
                "action_id": action_id,
                "kind": KIND_NETWORK_READ,
                "url": p.url,
                "ts": time.time(),
                "ok": False,
                "error": f"fetch_error_{e}",
                "caller_id": p.caller_id,
            })
            del self._pending[action_id]
            return {"ok": False, "error": str(e)}

        del self._pending[action_id]
        self._committed_ids.add(action_id)

        content_sha256 = hashlib.sha256(data).hexdigest()
        receipt_row = {
            "phase": PHASE_COMMIT,
            "action_id": action_id,
            "kind": KIND_NETWORK_READ,
            "url": p.url,
            "status_code": status_code,
            "ts": time.time(),
            "ok": True,
            "caller_id": p.caller_id,
            "content_sha256": content_sha256,
            "truth_note": f"Membrane safely fetched {len(data)} bytes from allowed domain.",
        }
        
        # Only embed content if it's small enough to not pollute the JSONL ledger
        if len(data) <= _MAX_B64_PAYLOAD:
            receipt_row["content_b64"] = _b64(data)

        self._append_receipt(receipt_row)

        return {
            "ok": True, 
            "action_id": action_id, 
            "status_code": status_code,
            "content_sha256": content_sha256,
            "content": data
        }

    def receipt(self, action_id: str) -> Optional[Dict[str, Any]]:
        if not self.receipt_path.is_file():
            return None
        last: Optional[Dict[str, Any]] = None
        with open(self.receipt_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("action_id") == action_id:
                    last = row
        return last

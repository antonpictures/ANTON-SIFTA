#!/usr/bin/env python3
"""
System/swarm_warp9_federation.py — Cross-machine swimmer transport
══════════════════════════════════════════════════════════════════════
WARP 9 module 1 of 3.

Why this exists
---------------
The Architect owns multiple machines (M5 Mac Pro, M1 Mac Mini "MITHER",
future ones). Each runs its own SIFTA install. As of T65 they had a
"wormhole available but no way to chat" — the M1 swarm couldn't tell
the M5 swarm about a webcam input or a stigmergicode.com chat, and
vice versa.

This module is the chat path. Messages are JSONL rows in a spool
directory: `.sifta_state/warp9_spool/<from_serial>__<to_serial>.jsonl`.
Both the in-LAN path (rsync, file watcher) and the off-LAN path
(git push/pull) walk the SAME spool — the on-disk format is the
contract. Transport is plug-able.

Default transport: SPOOL ONLY (no network code in this module).
- For in-home LAN: future swarm_warp9_lan.py can rsync the spool dir.
- For cross-internet: the existing git push/pull pattern moves the spool.
- For sub-second latency: future swarm_warp9_relay.py on stigmergicode.com.

Test mode discipline
--------------------
Federation is OFF by default (see System.swarm_owner_identity). When OFF:
- send() refuses to write across machines (returns False).
- recv() still works (reading the inbox is harmless).
This preserves the "treat machines as separate owners" test discipline
the Architect explicitly requested while still letting devs prepare
spool layouts and inspect inboxes.

Power to the Swarm.
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import hmac
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from System.swarm_owner_identity import (
    detect_self_homeworld_serial,
    detect_self_architect_id,
    list_owner_homeworlds,
    is_federated,
    FEDERATION_ENABLED,
    get_or_create_owner,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_SPOOL = _STATE / "warp9_spool"
_SPOOL.mkdir(parents=True, exist_ok=True)

MODULE_VERSION = "2026-04-18.warp9.federation.v1"
MAX_MESSAGE_BYTES = 64 * 1024            # generous; spool entries should stay small
HMAC_KEY_ENV = "SIFTA_WARP9_HMAC_KEY"    # owner sets to a stable secret per-owner

# ──────────────────────────────────────────────────────────────────────
# Message dataclass — the on-disk contract
# ──────────────────────────────────────────────────────────────────────

@dataclass
class WarpMessage:
    """One spool entry. JSON-serialisable, HMAC-signed when a key is set."""
    msg_id: str
    from_homeworld: str
    from_architect: str
    to_homeworld: str
    owner_id_key: str           # both endpoints belong to this owner
    kind: str                   # "swimmer_visit" | "device_signal" | "chat" | "concierge_proposal" | ...
    payload: Dict[str, Any]
    ts_sent: float
    signature: str = ""         # HMAC-SHA256 over canonical JSON of (kind+payload+ts)
    schema: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _canonical(d: Dict[str, Any]) -> str:
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sign(payload: Dict[str, Any], kind: str, ts: float) -> str:
    key = os.environ.get(HMAC_KEY_ENV, "").encode("utf-8")
    if not key:
        return ""  # unsigned in test mode is OK; receiver decides whether to trust
    body = _canonical({"kind": kind, "payload": payload, "ts": ts}).encode("utf-8")
    return hmac.new(key, body, hashlib.sha256).hexdigest()[:24]


def _verify(msg: WarpMessage) -> bool:
    """True iff signature absent (unsigned, test mode) OR matches HMAC."""
    if not msg.signature:
        return os.environ.get(HMAC_KEY_ENV, "") == ""
    expected = _sign(msg.payload, msg.kind, msg.ts_sent)
    return hmac.compare_digest(expected, msg.signature)


def _spool_path(from_serial: str, to_serial: str) -> Path:
    """Per-pair spool file. Append-only on the sender side, tail-read on the receiver side."""
    fname = f"{from_serial}__{to_serial}.jsonl"
    return _SPOOL / fname


# ──────────────────────────────────────────────────────────────────────
# Send / Recv / Tail
# ──────────────────────────────────────────────────────────────────────

def send(
    to_homeworld: str,
    kind: str,
    payload: Dict[str, Any],
    *,
    owner_label: str = "IOAN",
    force: bool = False,
) -> Optional[WarpMessage]:
    """Append a WarpMessage to the spool path for `to_homeworld`.

    Refuses (returns None) when:
      - federation is OFF and `force=False`
      - the target homeworld is not registered to the same owner
      - the message exceeds MAX_MESSAGE_BYTES
    """
    owner = get_or_create_owner(owner_label)
    self_serial = detect_self_homeworld_serial()
    self_arch = detect_self_architect_id(default_owner_label=owner_label)

    if to_homeworld == self_serial:
        # Sending to self is a no-op in production but useful for smokes.
        if not force:
            return None

    if not (FEDERATION_ENABLED or force):
        return None

    homeworlds = {h.homeworld_serial for h in list_owner_homeworlds(owner.key)}
    if to_homeworld not in homeworlds and not force:
        return None

    ts = time.time()
    msg = WarpMessage(
        msg_id=uuid.uuid4().hex[:16],
        from_homeworld=self_serial,
        from_architect=self_arch,
        to_homeworld=to_homeworld,
        owner_id_key=owner.key,
        kind=kind,
        payload=payload,
        ts_sent=ts,
        signature=_sign(payload, kind, ts),
    )

    serialized = json.dumps(msg.to_dict(), ensure_ascii=False)
    if len(serialized) > MAX_MESSAGE_BYTES:
        return None

    path = _spool_path(self_serial, to_homeworld)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(serialized + "\n")
    return msg


def recv(
    *,
    kinds: Optional[Iterable[str]] = None,
    since_ts: float = 0.0,
    owner_label: str = "IOAN",
    limit: int = 200,
) -> List[WarpMessage]:
    """Tail every spool file targeted at THIS homeworld and return the
    matching messages. Verifies signatures; drops invalid rows silently
    (with a stderr note).
    """
    self_serial = detect_self_homeworld_serial()
    out: List[WarpMessage] = []

    if not _SPOOL.exists():
        return out

    for path in sorted(_SPOOL.glob(f"*__{self_serial}.jsonl")):
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                        msg = WarpMessage(**row)
                    except Exception:
                        continue
                    if msg.ts_sent < since_ts:
                        continue
                    if kinds and msg.kind not in kinds:
                        continue
                    if not _verify(msg):
                        # Bad signature — skip silently (don't echo content).
                        continue
                    out.append(msg)
        except OSError:
            continue

    out.sort(key=lambda m: m.ts_sent)
    return out[-limit:]


def list_spool_pairs() -> List[Dict[str, Any]]:
    """Inventory of every (from, to) spool file with row counts. For dashboards."""
    pairs: List[Dict[str, Any]] = []
    if not _SPOOL.exists():
        return pairs
    for path in sorted(_SPOOL.glob("*__*.jsonl")):
        stem = path.stem
        if "__" not in stem:
            continue
        from_serial, to_serial = stem.split("__", 1)
        try:
            n = sum(1 for line in path.open("r", encoding="utf-8") if line.strip())
        except OSError:
            n = -1
        pairs.append({
            "from": from_serial,
            "to": to_serial,
            "rows": n,
            "path": str(path.relative_to(_REPO)),
        })
    return pairs


# ──────────────────────────────────────────────────────────────────────
# Convenience kinds — wrappers for the common message types
# ──────────────────────────────────────────────────────────────────────

def send_chat(to_homeworld: str, text: str, *, owner_label: str = "IOAN", force: bool = False) -> Optional[WarpMessage]:
    """One-shot text chat between two of the owner's machines."""
    return send(to_homeworld, kind="chat", payload={"text": text[:8000]},
                owner_label=owner_label, force=force)


def send_swimmer_visit(
    to_homeworld: str,
    swimmer_id: str,
    capabilities: List[str],
    *,
    owner_label: str = "IOAN",
    force: bool = False,
) -> Optional[WarpMessage]:
    """Announce a swimmer's intent to swim into a peer machine. The receiving
    side decides whether to admit it (Architect's distributed-trust model).
    """
    return send(to_homeworld, kind="swimmer_visit",
                payload={"swimmer_id": swimmer_id, "capabilities": capabilities},
                owner_label=owner_label, force=force)


if __name__ == "__main__":
    print(f"[C47H-SMOKE-WARP9-FED] FEDERATION_ENABLED={FEDERATION_ENABLED}")
    print(f"[C47H-SMOKE-WARP9-FED] self_serial={detect_self_homeworld_serial()}")

    # Force-mode self-loop smoke (federation off in dev — smoke uses force=True).
    self_serial = detect_self_homeworld_serial()
    sent = send_chat(self_serial, "Hello from M5 to M5 (smoke loopback)", force=True)
    print(f"[C47H-SMOKE-WARP9-FED] send_chat -> msg_id={sent.msg_id if sent else None}")

    received = recv(kinds=["chat"], since_ts=time.time() - 60)
    print(f"[C47H-SMOKE-WARP9-FED] recv chats (last 60s): {len(received)}")
    for m in received[-3:]:
        print(f"    {m.msg_id} from={m.from_architect} kind={m.kind} payload={m.payload}")

    pairs = list_spool_pairs()
    print(f"[C47H-SMOKE-WARP9-FED] spool inventory: {len(pairs)} pair file(s)")
    for p in pairs:
        print(f"    {p['from']} -> {p['to']}  ({p['rows']} rows)")

    print("[C47H-SMOKE-WARP9-FED OK]")

#!/usr/bin/env python3
"""
System/swarm_mycorrhizal_network.py
══════════════════════════════════════════════════════════════════════
Epoch 11 (Hardened): Inter-swarm telepathy over UDP with immune gates.

Security properties:
- HMAC-SHA256 authenticated envelopes (shared secret in .sifta_state)
- Strict canonical-schema gate on incoming traces
- Type and size checks to block oversized / malformed payloads
- Per-source-IP token-bucket rate limiting
- Body-integrity precondition via swarm_body_integrity_guard.verify_live()
- Rejection ledger for forensic audit
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import secrets
import socket
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.canonical_schemas import assert_payload_keys
    from System.jsonl_file_lock import append_line_locked
    from System.swarm_body_integrity_guard import verify_live
except ImportError as exc:
    print(f"[FATAL] Spinal cord severed. Missing tissue: {exc}")
    raise SystemExit(1)

_STATE_DIR = _REPO / ".sifta_state"
_SECRET_FILE = _STATE_DIR / "mycorrhizal_secret.json"
_REJECTIONS_FILE = _STATE_DIR / "mycorrhizal_rejections.jsonl"

_DEFAULT_PORT = 47474
_DEFAULT_MAX_DATAGRAM = 65535
_MAX_TRACE_BYTES = 8192
_MAX_RAW_EXCERPT = 420
_MAX_CLOCK_SKEW_S = 300.0
_NONCE_WINDOW_S = 600.0
_NONCE_MAX_SEEN = 4096
_INTEGRITY_CACHE_S = 5.0


def _now() -> float:
    return time.time()


def _canonical_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _safe_excerpt(payload: Any) -> str:
    try:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        raw = str(payload)
    if len(raw) > _MAX_RAW_EXCERPT:
        return raw[:_MAX_RAW_EXCERPT] + "...<truncated>"
    return raw


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


class _TokenBucket:
    def __init__(self, rate_per_s: float, burst: float) -> None:
        self.rate_per_s = max(0.1, float(rate_per_s))
        self.burst = max(1.0, float(burst))
        self.tokens = self.burst
        self.last_ts = _now()

    def allow(self, now_ts: float) -> bool:
        elapsed = max(0.0, now_ts - self.last_ts)
        self.last_ts = now_ts
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate_per_s)
        if self.tokens < 1.0:
            return False
        self.tokens -= 1.0
        return True


class SwarmMycorrhizalNetwork:
    """
    Hardened P2P stigmergy daemon for trusted sibling swarms.
    """

    def __init__(
        self,
        *,
        port: int = _DEFAULT_PORT,
        bind_ip: str = "0.0.0.0",
        broadcast_ip: str = "255.255.255.255",
        source_swarm_id: Optional[str] = None,
        state_dir: Optional[Path] = None,
        rate_per_s: float = 10.0,
        burst: float = 20.0,
    ) -> None:
        self.state_dir = state_dir or _STATE_DIR
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.port = int(port)
        self.bind_ip = bind_ip
        self.broadcast_ip = broadcast_ip
        self.source_swarm_id = source_swarm_id or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self.telepathy_ledgers: Set[str] = {
            "stigmergic_nuggets.jsonl",
            "global_immune_system.jsonl",
        }
        self._secret = self._load_or_create_secret()
        self._stop_event = threading.Event()
        self._listener_thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None
        self._max_datagram = _DEFAULT_MAX_DATAGRAM
        self._rate_per_ip: Dict[str, _TokenBucket] = {}
        self._rate_per_s = rate_per_s
        self._burst = burst
        self._seen_nonces: Dict[str, float] = {}
        self._integrity_ok = False
        self._integrity_checked_at = 0.0

    def _load_or_create_secret(self) -> bytes:
        secret_path = self.state_dir / _SECRET_FILE.name
        if secret_path.exists():
            try:
                payload = json.loads(secret_path.read_text(encoding="utf-8"))
                value = payload.get("hmac_secret_hex", "")
                if isinstance(value, str) and value:
                    return bytes.fromhex(value)
            except Exception:
                pass

        secret = secrets.token_bytes(32)
        payload = {
            "created_at": _now(),
            "hmac_secret_hex": secret.hex(),
            "note": "Shared secret for mycorrhizal envelope authentication.",
        }
        secret_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return secret

    def _log_rejection(self, source_ip: str, reason: str, raw_payload: Any) -> None:
        row = {
            "ts": _now(),
            "source_ip": source_ip,
            "reason": reason[:180],
            "raw_excerpt": _safe_excerpt(raw_payload),
        }
        append_line_locked(self.state_dir / _REJECTIONS_FILE.name, json.dumps(row, ensure_ascii=False) + "\n")

    def _rate_allow(self, source_ip: str, now_ts: float) -> bool:
        bucket = self._rate_per_ip.get(source_ip)
        if bucket is None:
            bucket = _TokenBucket(rate_per_s=self._rate_per_s, burst=self._burst)
            self._rate_per_ip[source_ip] = bucket
        return bucket.allow(now_ts)

    def _prune_nonces(self, now_ts: float) -> None:
        stale = [nonce for nonce, ts in self._seen_nonces.items() if (now_ts - ts) > _NONCE_WINDOW_S]
        for nonce in stale:
            self._seen_nonces.pop(nonce, None)
        if len(self._seen_nonces) > _NONCE_MAX_SEEN:
            # Keep newest entries to bound memory under packet flood.
            newest = sorted(self._seen_nonces.items(), key=lambda kv: kv[1], reverse=True)[: _NONCE_MAX_SEEN // 2]
            self._seen_nonces = dict(newest)

    def _integrity_precondition(self) -> bool:
        now_ts = _now()
        if (now_ts - self._integrity_checked_at) < _INTEGRITY_CACHE_S:
            return self._integrity_ok
        code, _result = verify_live(write_incident=False)
        self._integrity_ok = code == 0
        self._integrity_checked_at = now_ts
        return self._integrity_ok

    def _build_envelope(self, ledger_name: str, trace: dict) -> dict:
        envelope = {
            "ledger": ledger_name,
            "trace": trace,
            "meta": {
                "source_swarm_id": self.source_swarm_id,
                "sent_ts": _now(),
                "nonce": uuid.uuid4().hex,
            },
        }
        sig = hmac.new(self._secret, _canonical_bytes(envelope), hashlib.sha256).hexdigest()
        envelope["sig"] = sig
        return envelope

    def _validate_trace_types(self, ledger_name: str, trace: dict) -> Tuple[bool, str]:
        if ledger_name == "stigmergic_nuggets.jsonl":
            ts = trace.get("ts")
            frequency = trace.get("frequency")
            nugget_data = trace.get("nugget_data")
            quality_score = trace.get("quality_score")
            trace_id = trace.get("trace_id")
            if not isinstance(ts, (int, float)):
                return False, "stigmergic_nuggets.ts must be numeric"
            if not isinstance(frequency, str) or not frequency or len(frequency) > 96:
                return False, "stigmergic_nuggets.frequency must be 1..96 chars"
            if not isinstance(nugget_data, str) or not nugget_data or len(nugget_data) > 8000:
                return False, "stigmergic_nuggets.nugget_data must be 1..8000 chars"
            if not isinstance(quality_score, (int, float)) or not (-1.0 <= float(quality_score) <= 2.0):
                return False, "stigmergic_nuggets.quality_score out of bounds"
            if not isinstance(trace_id, str) or not trace_id or len(trace_id) > 160:
                return False, "stigmergic_nuggets.trace_id must be 1..160 chars"
            return True, ""

        if ledger_name == "global_immune_system.jsonl":
            ts = trace.get("ts")
            antigen_id = trace.get("antigen_id")
            antibody_hash = trace.get("antibody_hash")
            status = trace.get("status")
            trace_id = trace.get("trace_id")
            if not isinstance(ts, (int, float)):
                return False, "global_immune_system.ts must be numeric"
            if not isinstance(antigen_id, str) or not antigen_id or len(antigen_id) > 200:
                return False, "global_immune_system.antigen_id invalid"
            if not isinstance(antibody_hash, str) or not antibody_hash or len(antibody_hash) > 200:
                return False, "global_immune_system.antibody_hash invalid"
            if not isinstance(status, str) or not status or len(status) > 64:
                return False, "global_immune_system.status invalid"
            if not isinstance(trace_id, str) or not trace_id or len(trace_id) > 200:
                return False, "global_immune_system.trace_id invalid"
            return True, ""

        return False, f"unsupported ledger: {ledger_name}"

    def _verify_envelope(self, payload: dict, source_ip: str) -> Tuple[bool, str]:
        if not self._integrity_precondition():
            return False, "body integrity precondition failed"

        now_ts = _now()
        if not self._rate_allow(source_ip, now_ts):
            return False, "rate-limit exceeded"

        if not isinstance(payload, dict):
            return False, "packet root must be dict"

        required = {"ledger", "trace", "meta", "sig"}
        if set(payload.keys()) != required:
            return False, "envelope keys mismatch"

        ledger_name = payload.get("ledger")
        trace = payload.get("trace")
        meta = payload.get("meta")
        sig = payload.get("sig")

        if not isinstance(ledger_name, str) or ledger_name not in self.telepathy_ledgers:
            return False, "ledger not shareable"
        if not isinstance(trace, dict):
            return False, "trace must be dict"
        if not isinstance(meta, dict):
            return False, "meta must be dict"
        if not isinstance(sig, str) or len(sig) != 64:
            return False, "signature must be 64-char hex"

        meta_required = {"source_swarm_id", "sent_ts", "nonce"}
        if set(meta.keys()) != meta_required:
            return False, "meta keys mismatch"
        if not isinstance(meta.get("source_swarm_id"), str) or not meta.get("source_swarm_id"):
            return False, "meta.source_swarm_id invalid"
        sent_ts = _coerce_float(meta.get("sent_ts"), -1.0)
        if sent_ts <= 0:
            return False, "meta.sent_ts invalid"
        if abs(now_ts - sent_ts) > _MAX_CLOCK_SKEW_S:
            return False, "packet clock skew too large"
        nonce = meta.get("nonce")
        if not isinstance(nonce, str) or len(nonce) < 16:
            return False, "meta.nonce invalid"
        if nonce in self._seen_nonces:
            return False, "replay nonce seen"

        raw_trace = _canonical_bytes(trace)
        if len(raw_trace) > _MAX_TRACE_BYTES:
            return False, "trace exceeds max bytes"

        try:
            assert_payload_keys(ledger_name, trace, strict=True)
        except Exception as exc:
            return False, f"schema mismatch: {exc}"

        ok_types, reason = self._validate_trace_types(ledger_name, trace)
        if not ok_types:
            return False, reason

        unsigned = {
            "ledger": ledger_name,
            "trace": trace,
            "meta": meta,
        }
        expected = hmac.new(self._secret, _canonical_bytes(unsigned), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return False, "signature mismatch"

        self._seen_nonces[nonce] = now_ts
        self._prune_nonces(now_ts)
        return True, ""

    def _append_trace(self, ledger_name: str, trace: dict) -> None:
        path = self.state_dir / ledger_name
        append_line_locked(path, json.dumps(trace, ensure_ascii=False) + "\n")

    def _handle_packet(self, data: bytes, source_ip: str) -> None:
        try:
            payload = json.loads(data.decode("utf-8"))
        except Exception:
            self._log_rejection(source_ip, "malformed json packet", data.decode("utf-8", errors="replace"))
            return

        ok, reason = self._verify_envelope(payload, source_ip)
        if not ok:
            self._log_rejection(source_ip, reason, payload)
            return

        ledger_name = payload["ledger"]
        trace = payload["trace"]
        try:
            self._append_trace(ledger_name, trace)
        except Exception as exc:
            self._log_rejection(source_ip, f"append failed: {exc}", payload)

    def _listen_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(1.0)
        sock.bind((self.bind_ip, self.port))
        self._sock = sock
        print(f"[*] MYCORRHIZAL: Listening on UDP {self.bind_ip}:{self.port}")
        try:
            while not self._stop_event.is_set():
                try:
                    data, addr = sock.recvfrom(self._max_datagram)
                except socket.timeout:
                    continue
                except OSError:
                    break
                source_ip = str(addr[0]) if addr else "unknown"
                self._handle_packet(data, source_ip)
        finally:
            try:
                sock.close()
            except Exception:
                pass
            self._sock = None

    def awaken_network(self) -> bool:
        if not self._integrity_precondition():
            print("[-] MYCORRHIZAL: integrity precondition failed; listener not started.")
            return False
        if self._listener_thread and self._listener_thread.is_alive():
            return True
        self._stop_event.clear()
        self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listener_thread.start()
        return True

    def shutdown(self, timeout_s: float = 2.0) -> None:
        self._stop_event.set()
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=timeout_s)

    def broadcast_epigenetics(self, ledger_name: str, trace_dict: dict) -> bool:
        if ledger_name not in self.telepathy_ledgers:
            self._log_rejection("local", "attempted broadcast to non-shareable ledger", {"ledger": ledger_name})
            return False
        if not self._integrity_precondition():
            self._log_rejection("local", "body integrity precondition failed on broadcast", {"ledger": ledger_name})
            return False
        try:
            assert_payload_keys(ledger_name, trace_dict, strict=True)
        except Exception as exc:
            self._log_rejection("local", f"schema mismatch on broadcast: {exc}", trace_dict)
            return False
        ok_types, reason = self._validate_trace_types(ledger_name, trace_dict)
        if not ok_types:
            self._log_rejection("local", reason, trace_dict)
            return False
        raw_trace = _canonical_bytes(trace_dict)
        if len(raw_trace) > _MAX_TRACE_BYTES:
            self._log_rejection("local", "trace exceeds max bytes", trace_dict)
            return False

        envelope = self._build_envelope(ledger_name, trace_dict)
        packet = json.dumps(envelope, ensure_ascii=False).encode("utf-8")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(packet, (self.broadcast_ip, self.port))
            return True
        except Exception as exc:
            self._log_rejection("local", f"broadcast failed: {exc}", envelope)
            return False
        finally:
            sock.close()


def _smoke() -> int:
    import tempfile

    print("\n=== SIFTA MYCORRHIZAL NETWORK (HARDENED) : SMOKE TEST ===")
    with tempfile.TemporaryDirectory() as td:
        temp_state = Path(td)
        # Shared secret for deterministic peer auth inside smoke.
        secret_payload = {
            "created_at": _now(),
            "hmac_secret_hex": ("ab" * 32),
            "note": "smoke secret",
        }
        (temp_state / "mycorrhizal_secret.json").write_text(json.dumps(secret_payload), encoding="utf-8")
        (temp_state / "stigmergic_nuggets.jsonl").touch()

        net = SwarmMycorrhizalNetwork(
            port=47475,
            bind_ip="127.0.0.1",
            broadcast_ip="127.0.0.1",
            source_swarm_id="SMOKE_NODE",
            state_dir=temp_state,
        )

        # Smoke mode should run even without a real baseline seal.
        net._integrity_ok = True
        net._integrity_checked_at = _now()

        if not net.awaken_network():
            print("[FAIL] Listener failed to awaken")
            return 1
        time.sleep(0.3)

        trace = {
            "ts": _now(),
            "frequency": "Biology",
            "nugget_data": "Mycorrhizal signaling distributes warning chemistry.",
            "quality_score": 1.0,
            "trace_id": "NUGGET_SMOKE_1",
        }
        ok = net.broadcast_epigenetics("stigmergic_nuggets.jsonl", trace)
        time.sleep(0.4)
        net.shutdown()
        if not ok:
            print("[FAIL] Broadcast failed")
            return 1

        lines = [ln for ln in (temp_state / "stigmergic_nuggets.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
        if len(lines) != 1:
            print("[FAIL] Expected exactly one accepted nugget")
            return 1
        row = json.loads(lines[0])
        if "warning chemistry" not in row.get("nugget_data", ""):
            print("[FAIL] Wrong payload landed in nugget ledger")
            return 1

        # Rejection path test: unsigned packet should be rejected.
        bad_payload = {
            "ledger": "stigmergic_nuggets.jsonl",
            "trace": trace,
            "meta": {
                "source_swarm_id": "ATTACKER",
                "sent_ts": _now(),
                "nonce": uuid.uuid4().hex,
            },
            "sig": "0" * 64,
        }
        net2 = SwarmMycorrhizalNetwork(
            port=47476,
            bind_ip="127.0.0.1",
            broadcast_ip="127.0.0.1",
            source_swarm_id="SMOKE_NODE_2",
            state_dir=temp_state,
        )
        net2._integrity_ok = True
        net2._integrity_checked_at = _now()
        net2.awaken_network()
        time.sleep(0.2)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(json.dumps(bad_payload).encode("utf-8"), ("127.0.0.1", 47476))
        s.close()
        time.sleep(0.3)
        net2.shutdown()

        rej_lines = [ln for ln in (temp_state / "mycorrhizal_rejections.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
        if not rej_lines:
            print("[FAIL] Rejection ledger did not capture invalid signature")
            return 1

        print("[PASS] Authenticated broadcast accepted.")
        print("[PASS] Invalid signature rejected and audited.")
        print("[PASS] Hardened mycorrhizal smoke complete.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hardened inter-swarm telepathy daemon (HMAC + schema + rate limits)."
    )
    parser.add_argument("--smoke", action="store_true", help="run local hardened smoke test")
    parser.add_argument("--listen", action="store_true", help="start listener loop")
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT, help="UDP port")
    parser.add_argument("--bind-ip", default="0.0.0.0", help="listener bind ip")
    parser.add_argument("--broadcast-ip", default="255.255.255.255", help="broadcast destination ip")
    parser.add_argument("--broadcast-ledger", default="", help="ledger to broadcast to")
    parser.add_argument("--broadcast-json", default="", help="trace payload as JSON object")
    args = parser.parse_args()

    if args.smoke:
        return _smoke()

    net = SwarmMycorrhizalNetwork(
        port=args.port,
        bind_ip=args.bind_ip,
        broadcast_ip=args.broadcast_ip,
    )

    if args.broadcast_ledger and args.broadcast_json:
        try:
            trace = json.loads(args.broadcast_json)
        except json.JSONDecodeError as exc:
            print(f"[FAIL] invalid --broadcast-json: {exc}")
            return 2
        ok = net.broadcast_epigenetics(args.broadcast_ledger, trace)
        print("[PASS] broadcast sent" if ok else "[FAIL] broadcast rejected")
        return 0 if ok else 1

    if args.listen:
        if not net.awaken_network():
            return 1
        print("[*] Press Ctrl+C to stop listener.")
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            net.shutdown()
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

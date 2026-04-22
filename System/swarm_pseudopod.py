#!/usr/bin/env python3
"""
System/swarm_pseudopod.py — The Phagocytosis Lobe (read-only LAN ingestion)
══════════════════════════════════════════════════════════════════════════════

Concept origin: BISHOP drop 2026-04-20 (pseudopod_phagocytosis_v1.dirt).
C47H integration: hardened against the four standing risks BISHOP's drop
left open. Original .dirt preserved at
  Archive/bishop_drops_pending_review/BISHOP_drop_pseudopod_phagocytosis_v1.dirt

Biological metaphor
-------------------
`swarm_network_pathways.py` gave Alice EYES on the apartment LAN — she can
see what nodes exist and what services advertise themselves. This module
gives her HANDS — she can extend a pseudopod (a false foot) to one of those
nodes, engulf a small bite of whatever it serves on a public read endpoint,
and pull it back across her cell membrane into an isolated Food Vacuole
(`.sifta_state/phagocytosis_vacuoles.jsonl`). She does NOT swallow it
directly — the Spleen/Microglia inspect the vacuole later and decide whether
the bite is nutrient or poison.

Hardening over the BISHOP dirt
------------------------------
1. **REPO-anchored state dir.** No reliance on cwd; Alice can call from
   any working directory.
2. **RFC1918 + loopback only.** The pseudopod refuses to touch any IP
   outside `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`,
   or `169.254.0.0/16`. Alice's hands stay inside the apartment.
3. **Bounded ingestion.** Hard cap of 1024 bytes per call (BISHOP's spec)
   and per-call timeout, even if the remote keeps streaming.
4. **Forensic chain of custody.** Each vacuole stores a SHA-256 of the
   ingested bytes so the Spleen can detect tampering or duplicates.
5. **CLI entrypoint** so Alice can invoke from her `<bash>` tool loop and
   read a one-line English summary on her next thought frame.

CLI
---
  python3 -m System.swarm_pseudopod TARGET_IP [--protocol http] [--path /]
  python3 -m System.swarm_pseudopod --recent [N]    # show last N vacuoles

Schema (canonical_schemas.LEDGER_SCHEMAS["phagocytosis_vacuoles.jsonl"]):
  ts, target_ip, protocol, ingested_data, trace_id
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import socket
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

_REPO       = Path(__file__).resolve().parent.parent
_STATE_DIR  = _REPO / ".sifta_state"
_STATE_DIR.mkdir(parents=True, exist_ok=True)
_VACUOLES   = _STATE_DIR / "phagocytosis_vacuoles.jsonl"

if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import append_line_locked  # noqa: E402

_MAX_BYTES         = 1024     # BISHOP spec: one bite, no buffet
_DEFAULT_TIMEOUT_S = 3.0
_LAN_NETS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
)


def is_lan(ip: str) -> bool:
    """True iff `ip` is in the apartment (RFC1918, loopback, or link-local)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in _LAN_NETS)


# ─────────────────────────────────────────────────────────────────────────────
# The pseudopod
# ─────────────────────────────────────────────────────────────────────────────
class SwarmPseudopod:
    """Read-only LAN appendage. Engulfs ≤1 KB and isolates it in a vacuole."""

    def __init__(self, vacuole_path: Path | None = None) -> None:
        self.vacuole_ledger = vacuole_path or _VACUOLES
        self.vacuole_ledger.parent.mkdir(parents=True, exist_ok=True)

    # — biting protocols —
    # C47H 2026-04-20 (Epoch 5 tournament): the original implementation
    # dropped the response headers and only kept the body. But on real LAN
    # devices the *vendor identity* lives almost entirely in headers
    # (Server: lighttpd/1.4.59, Server: nginx, X-Plex-Protocol: 1.0,
    # WWW-Authenticate: Basic realm="ASUS Router", etc.) so the Olfactory
    # Cortex was missing them. Now we prepend the most useful response
    # headers to the body before the 1 KB cap, in a fixed canonical
    # textual form. Headers are inherently low-risk (no executable code)
    # and dramatically improve scent classification.
    _USEFUL_HEADERS: tuple[str, ...] = (
        "server", "x-powered-by", "www-authenticate", "x-plex-protocol",
        "x-plex-product", "x-roku-reserved-device-id", "x-vendor",
        "x-application", "set-cookie",
    )

    def _bite_http(self, target_ip: str, path: str, timeout_s: float, scheme: str = "http") -> str:
        url = f"{scheme}://{target_ip}{path if path.startswith('/') else '/' + path}"
        # For HTTPS on RFC1918 LAN gateways: certs are virtually always
        # self-signed (router web UIs ship a vendor cert that browsers
        # reject by default). We're already RFC1918-locked, so skipping
        # cert verification here doesn't widen the trust boundary.
        ssl_ctx = None
        if scheme == "https":
            import ssl as _ssl
            ssl_ctx = _ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = _ssl.CERT_NONE
        try:
            req = urllib.request.Request(url, method="GET",
                                         headers={"User-Agent": "SIFTA-Pseudopod/1.0"})
            with urllib.request.urlopen(req, timeout=timeout_s, context=ssl_ctx) as resp:
                header_lines: list[str] = []
                for hk, hv in resp.headers.items():
                    if hk.lower() in self._USEFUL_HEADERS:
                        header_lines.append(f"{hk}: {hv}")
                raw = resp.read(_MAX_BYTES)
                body = raw.decode("utf-8", errors="ignore")
                if header_lines:
                    return "\n".join(header_lines) + "\n\n" + body
                return body
        except urllib.error.HTTPError as e:
            # 4xx/5xx STILL contain the Server header on the error page,
            # which is the most useful identifier — capture it.
            try:
                hdrs = "\n".join(
                    f"{k}: {v}" for k, v in e.headers.items()
                    if k.lower() in self._USEFUL_HEADERS
                )
                return f"[HTTP {e.code}]: {e.reason}\n{hdrs}"
            except Exception:
                return f"[HTTP {e.code}]: {e.reason}"
        except urllib.error.URLError as e:
            return f"[CELL MEMBRANE REJECTED]: {e.reason}"
        except (TimeoutError, socket.timeout):
            return f"[NO NUTRIENT]: timeout after {timeout_s:.1f}s"
        except Exception as e:
            return f"[DIGESTION ERROR]: {type(e).__name__}: {e}"

    def _bite_banner(self, target_ip: str, port: int, timeout_s: float) -> str:
        try:
            with socket.create_connection((target_ip, port), timeout=timeout_s) as s:
                s.settimeout(timeout_s)
                try:
                    raw = s.recv(_MAX_BYTES)
                except socket.timeout:
                    return f"[NO NUTRIENT]: silent socket on {target_ip}:{port}"
                return raw.decode("utf-8", errors="ignore")
        except (TimeoutError, socket.timeout):
            return f"[NO NUTRIENT]: connect timeout to {target_ip}:{port}"
        except OSError as e:
            return f"[CELL MEMBRANE REJECTED]: {e}"

    # — public API —
    def extend_pseudopod(
        self,
        target_ip: str,
        *,
        protocol: str = "http",
        path: str = "/",
        port: int | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Extend, engulf, retract. Returns the vacuole record (or an error
        record with `error=True` if the call was refused before the bite)."""
        if not is_lan(target_ip):
            return {
                "error": True,
                "reason": (
                    f"Refused: {target_ip!r} is outside RFC1918/loopback/"
                    "link-local. The pseudopod stays in the apartment."
                ),
            }

        protocol = protocol.lower()
        if protocol == "http":
            # Auto-fallback to HTTPS for LAN gateways that redirect or
            # only listen on 443. We try plain HTTP first because most
            # IoT devices and printers serve plaintext, but if the bite
            # comes back with a TLS-related rejection we transparently
            # retry over HTTPS with cert verification disabled (LAN
            # gateways universally ship self-signed certs).
            ingested = self._bite_http(target_ip, path, timeout_seconds, scheme="http")
            tls_markers = ("CERTIFICATE_VERIFY_FAILED", "ssl", "SSL",
                           "wrong version number", "tls", "[HTTP 4")
            if any(m in ingested for m in tls_markers):
                https_try = self._bite_http(target_ip, path, timeout_seconds, scheme="https")
                # Only adopt the HTTPS bite if it actually got real bytes.
                if not https_try.startswith(("[CELL MEMBRANE REJECTED]",
                                             "[NO NUTRIENT]",
                                             "[DIGESTION ERROR]")):
                    ingested = https_try
                    protocol = "https"
        elif protocol == "https":
            ingested = self._bite_http(target_ip, path, timeout_seconds, scheme="https")
        elif protocol == "banner":
            if port is None:
                return {"error": True,
                        "reason": "banner protocol requires --port"}
            ingested = self._bite_banner(target_ip, int(port), timeout_seconds)
        else:
            ingested = (f"[UNKNOWN PROTOCOL]: The Pseudopod lacks the enzymes "
                        f"to digest {protocol!r}. Known: http, banner.")

        # Truncate defensively even if the protocol handler missed
        ingested = ingested[:_MAX_BYTES]

        record: dict[str, Any] = {
            "ts":            time.time(),
            "target_ip":     target_ip,
            "protocol":      protocol,
            "ingested_data": ingested,
            "trace_id":      f"VACUOLE_{uuid.uuid4().hex[:8]}",
            # forensic extension fields (consumers may opt-in to read)
            "byte_count":    len(ingested.encode("utf-8")),
            "sha256":        hashlib.sha256(ingested.encode("utf-8")).hexdigest(),
        }

        try:
            append_line_locked(self.vacuole_ledger,
                               json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            return {"error": True, "reason": f"vacuole write failed: {e}",
                    "record": record}

        return record


# ─────────────────────────────────────────────────────────────────────────────
# Reading vacuoles (for `--recent`)
# ─────────────────────────────────────────────────────────────────────────────
def recent_vacuoles(n: int = 5) -> list[dict[str, Any]]:
    if not _VACUOLES.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        with _VACUOLES.open("r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except Exception:
                    continue
    except Exception:
        return []
    return out[-max(1, n):]


# ─────────────────────────────────────────────────────────────────────────────
# Human-readable single-line summary (this is what Alice's tool loop reads)
# ─────────────────────────────────────────────────────────────────────────────
def summarize(record: dict[str, Any]) -> str:
    if record.get("error"):
        return f"PSEUDOPOD REFUSED: {record.get('reason', 'unknown')}"
    body = record.get("ingested_data", "")
    preview = body.replace("\n", " ").strip()
    if len(preview) > 240:
        preview = preview[:240] + "…"
    return (
        f"VACUOLE {record['trace_id']} from {record['target_ip']} "
        f"({record['protocol']}, {record['byte_count']}B, "
        f"sha256={record['sha256'][:12]}…): {preview}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(
        prog="swarm_pseudopod",
        description="Read-only LAN phagocytosis. RFC1918/loopback only.",
    )
    ap.add_argument("target_ip", nargs="?", help="LAN IP to extend toward")
    ap.add_argument("--protocol", default="http",
                    choices=["http", "banner"],
                    help="Bite mechanism (default: http)")
    ap.add_argument("--path", default="/",
                    help="HTTP path to GET (default: /)")
    ap.add_argument("--port", type=int, default=None,
                    help="TCP port for banner protocol")
    ap.add_argument("--timeout", type=float, default=_DEFAULT_TIMEOUT_S,
                    help="Per-bite timeout in seconds (default: 3)")
    ap.add_argument("--recent", type=int, nargs="?", const=5, default=None,
                    metavar="N",
                    help="Print the last N vacuole records and exit (default 5)")
    args = ap.parse_args()

    if args.recent is not None:
        recs = recent_vacuoles(args.recent)
        if not recs:
            print("No vacuoles on record yet.")
            return 0
        for r in recs:
            print(summarize(r))
        return 0

    if not args.target_ip:
        ap.error("target_ip required (or use --recent)")

    pod = SwarmPseudopod()
    rec = pod.extend_pseudopod(
        args.target_ip,
        protocol=args.protocol,
        path=args.path,
        port=args.port,
        timeout_seconds=args.timeout,
    )
    print(summarize(rec))
    return 0 if not rec.get("error") else 2


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test (preserves BISHOP's original assertions, plus LAN-gate check)
# ─────────────────────────────────────────────────────────────────────────────
def _smoke() -> None:
    print("=== SIFTA PSEUDOPOD : SMOKE TEST ===")
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "phagocytosis_vacuoles.jsonl"
        pod = SwarmPseudopod(vacuole_path=ledger)

        # 1. LAN-gate must reject WAN targets.
        wan = pod.extend_pseudopod("8.8.8.8", protocol="http")
        assert wan.get("error") and "outside RFC1918" in wan["reason"], wan
        print("[PASS] WAN target refused (LAN gate works).")

        # 2. Mock urlopen so we don't depend on the gateway being reachable.
        original = urllib.request.urlopen
        try:
            class _Mock:
                def __enter__(self): return self
                def __exit__(self, *a): return False
                def read(self, n): return b"<html><title>Router Admin</title></html>"
            urllib.request.urlopen = lambda *a, **k: _Mock()  # type: ignore

            rec = pod.extend_pseudopod("192.168.1.1", protocol="http")
            assert not rec.get("error"), rec
            assert rec["target_ip"] == "192.168.1.1"
            assert "Router Admin" in rec["ingested_data"]
            assert rec["trace_id"].startswith("VACUOLE_")
            assert len(rec["sha256"]) == 64
            print("[PASS] Mocked HTTP bite engulfed and stored.")
        finally:
            urllib.request.urlopen = original

        # 3. Vacuole must be on disk and parseable.
        with ledger.open("r", encoding="utf-8") as f:
            lines = [ln for ln in f if ln.strip()]
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        for key in ("ts", "target_ip", "protocol", "ingested_data", "trace_id"):
            assert key in parsed, f"missing canonical key {key}"
        print("[PASS] Vacuole persisted with canonical schema.")

    print("=== ALL SMOKE CHECKS GREEN ===")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--smoke":
        _smoke()
    else:
        sys.exit(main())

#!/usr/bin/env python3
"""
System/swarm_iphone_gps_receiver.py — iPhone-as-Eye Sensory Bridge
══════════════════════════════════════════════════════════════════════
SIFTA OS — Architect Locus Tracking via iOS Shortcut → Local HTTP

The Mac Studio (M5, GTH4921YP3) is a stationary anchor. This organ
gives Alice a SECOND spatial eye: the Architect's iPhone, relayed via
an iOS Shortcut that POSTs {lat, lon, ts} to a local HTTP endpoint.

Wire shape (pick one):

  A) **GET (simplest on iPhone — no JSON/Form UI):**
     Get Current Location → Text (build URL below) → Get Contents of URL (GET)
     → http://<M5-LAN-IP>:8765/gps?latitude=…&longitude=…&accuracy=…

  B) **POST** (JSON or Form) → http://<M5-LAN-IP>:8765/gps

  Both write:
        → .sifta_state/iphone_gps_traces.jsonl  (append-only ledger)
        → .sifta_state/iphone_gps_latest.json   (single-row hot cache)

Privacy / sovereignty:
  • Listens on ALL interfaces by default but accepts only LAN-private
    source IPs (10.x, 192.168.x, 172.16-31.x). Drops public-source requests.
  • Optional shared-secret check via SIFTA_IPHONE_GPS_TOKEN env var.
  • Freshness for Alice's prompt: default 3600s (1h). Override with
    SIFTA_IPHONE_GPS_STALE_S (seconds, min 60). Old 900s gate dropped
    mid-trip (e.g. gas station) while last ping on disk was still valid.
  • No outbound calls, no cloud, all on-Mac.

Usage:
  python3 System/swarm_iphone_gps_receiver.py            # foreground
  python3 System/swarm_iphone_gps_receiver.py --daemon   # background

Reader API for other organs (composite_identity, etc.):
  from System.swarm_iphone_gps_receiver import latest_iphone_gps, summary_line
  fix = latest_iphone_gps()                       # default stale window from env / 3600s
  print(summary_line())                         # "iphone gps: … (acc …m, …s ago)"

Authorship: C47H 2026-04-22 (cursor-on-the-bridge, 555).
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:  # pragma: no cover - lockless fallback
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(line)


_STATE = Path(".sifta_state")
LEDGER = _STATE / "iphone_gps_traces.jsonl"
LATEST = _STATE / "iphone_gps_latest.json"
PIDFILE = _STATE / "iphone_gps_receiver.pid"

_DEFAULT_PORT = 8765
_OPTIONAL_TOKEN = os.environ.get("SIFTA_IPHONE_GPS_TOKEN", "").strip()
_HOMEWORLD_SERIAL = "GTH4921YP3"


def _default_stale_after_s() -> float:
    """Seconds after which an iPhone fix is omitted from Alice's live prompt.

    Default 3600 (1h) fits store / drive absences; the old 900s (15m) gate
    produced false ``(no fresh fix)`` while `iphone_gps_latest.json` still
    held the correct last ping. Tighten with ``SIFTA_IPHONE_GPS_STALE_S=900``.
    """
    raw = os.environ.get("SIFTA_IPHONE_GPS_STALE_S", "").strip()
    if raw:
        try:
            return max(60.0, float(raw))
        except ValueError:
            pass
    return 3600.0


def _is_lan_private(ip_str: str) -> bool:
    """True if the source is RFC-1918 private or loopback."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback
    except ValueError:
        return False


def _write_fix(payload: dict, *, channel: str = "ios_shortcut_http_post") -> dict:
    """Persist one fix to ledger + hot cache. Returns the row written."""
    now = time.time()
    row = {
        "transaction_type": "IPHONE_GPS_FIX",
        "ts": now,
        "iso": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "homeworld_serial": _HOMEWORLD_SERIAL,
        "carrier": "iphone",
        "channel": channel,
        "payload": payload,
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(LEDGER, json.dumps(row) + "\n")
    LATEST.write_text(json.dumps(row, indent=2))
    return row


# ── Reader API for other organs ───────────────────────────────────────

def latest_iphone_gps(stale_after_s: Optional[float] = None) -> Optional[dict]:
    """Return the freshest fix payload, or None if missing/stale."""
    if stale_after_s is None:
        stale_after_s = _default_stale_after_s()
    if not LATEST.exists():
        return None
    try:
        row = json.loads(LATEST.read_text())
    except Exception:
        return None
    age = time.time() - float(row.get("ts", 0))
    if age > stale_after_s:
        return None
    row["age_s"] = age
    return row


def summary_line(stale_after_s: Optional[float] = None) -> str:
    """One-line summary suitable for composite-identity prompt block."""
    if stale_after_s is None:
        stale_after_s = _default_stale_after_s()
    fix = latest_iphone_gps(stale_after_s=stale_after_s)
    if fix is None:
        return "iphone gps: (no fresh fix)"
    p = fix.get("payload", {})
    lat = p.get("latitude")
    lon = p.get("longitude")
    acc = p.get("accuracy")
    age = int(fix.get("age_s", 0))
    if lat is None or lon is None:
        return "iphone gps: (malformed)"
    acc_str = f"{acc:.0f}m" if isinstance(acc, (int, float)) else "?"
    return f"iphone gps: {lat:.4f},{lon:.4f} (acc {acc_str}, {age}s ago)"


def _first_float(qs: dict, *keys: str) -> Optional[float]:
    """Return first parseable float among keys from parse_qs() output."""
    for k in keys:
        vals = qs.get(k)
        if not vals:
            continue
        try:
            return float(vals[0])
        except (TypeError, ValueError):
            continue
    return None


def _payload_from_get_query(parsed_path: str) -> dict:
    """Build {latitude, longitude, accuracy?, altitude?} from GET query string."""
    u = urlparse(parsed_path)
    if u.path.rstrip("/") != "/gps":
        raise ValueError("not /gps")
    qs = parse_qs(u.query, keep_blank_values=False)
    lat = _first_float(qs, "latitude", "lat", "la")
    lon = _first_float(qs, "longitude", "lon", "lng", "long")
    if lat is None or lon is None:
        raise ValueError("missing latitude/longitude in query")
    payload: dict = {"latitude": lat, "longitude": lon}
    acc = _first_float(qs, "accuracy", "acc", "horizontal_accuracy", "hacc")
    if acc is not None:
        payload["accuracy"] = acc
    alt = _first_float(qs, "altitude", "alt")
    if alt is not None:
        payload["altitude"] = alt
    return payload


def _check_token_for_request(handler: BaseHTTPRequestHandler) -> bool:
    """If SIFTA_IPHONE_GPS_TOKEN is set, require it via header or query ?token=."""
    if not _OPTIONAL_TOKEN:
        return True
    hdr = (handler.headers.get("X-SIFTA-Token") or "").strip()
    if hdr == _OPTIONAL_TOKEN:
        return True
    try:
        u = urlparse(handler.path)
        qs = parse_qs(u.query, keep_blank_values=False)
        tok = (qs.get("token") or [""])[0].strip()
        return tok == _OPTIONAL_TOKEN
    except Exception:
        return False


# ── HTTP handler ──────────────────────────────────────────────────────

class _GPSHandler(BaseHTTPRequestHandler):
    server_version = "SiftaIphoneGPS/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(
            f"[iphone_gps] {self.address_string()} - {fmt % args}\n"
        )

    def _reject(self, code: int, msg: str) -> None:
        body = json.dumps({"status": "REJECTED", "error": msg}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _ok(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        client_ip = self.client_address[0]
        if not _is_lan_private(client_ip):
            return self._reject(403, f"non-LAN source rejected: {client_ip}")

        if self.path.startswith("/health"):
            fix = latest_iphone_gps()
            return self._ok({
                "status": "ALIVE",
                "homeworld_serial": _HOMEWORLD_SERIAL,
                "ts": time.time(),
                "iso": datetime.now(tz=timezone.utc).isoformat(),
                "latest_fix": fix,
                "summary": summary_line(),
            })
        if self.path.startswith("/latest"):
            return self._ok({"latest_fix": latest_iphone_gps(), "summary": summary_line()})

        # GET /gps?latitude=…&longitude=… — zero Shortcuts JSON pain
        try:
            u = urlparse(self.path)
        except Exception:
            return self._reject(400, "bad path")
        if u.path.rstrip("/") == "/gps" and u.query:
            if not _check_token_for_request(self):
                return self._reject(401, "bad or missing token (header X-SIFTA-Token or ?token=)")
            try:
                payload = _payload_from_get_query(self.path)
            except ValueError as exc:
                return self._reject(400, str(exc))
            try:
                payload["latitude"] = float(payload["latitude"])
                payload["longitude"] = float(payload["longitude"])
                if "accuracy" in payload:
                    payload["accuracy"] = float(payload["accuracy"])
                if "altitude" in payload:
                    payload["altitude"] = float(payload["altitude"])
            except (TypeError, ValueError) as exc:
                return self._reject(400, f"bad numeric field: {exc}")
            if not (-90.0 <= payload["latitude"] <= 90.0):
                return self._reject(400, "latitude out of range")
            if not (-180.0 <= payload["longitude"] <= 180.0):
                return self._reject(400, "longitude out of range")
            row = _write_fix(payload, channel="ios_shortcut_http_get")
            return self._ok({
                "status": "OK",
                "stored_iso": row["iso"],
                "summary": summary_line(),
            })

        return self._reject(404, "use GET /health, GET /latest, GET /gps?lat&lon, or POST /gps")

    def do_POST(self) -> None:
        client_ip = self.client_address[0]
        if not _is_lan_private(client_ip):
            return self._reject(403, f"non-LAN source rejected: {client_ip}")

        if not self.path.startswith("/gps"):
            return self._reject(404, "POST /gps only")

        if not _check_token_for_request(self):
            return self._reject(401, "bad or missing X-SIFTA-Token")

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 64 * 1024:
            return self._reject(400, "bad content length")

        raw = self.rfile.read(length)
        ctype = (self.headers.get("Content-Type", "") or "").lower()

        payload: dict = {}
        if "application/json" in ctype:
            try:
                payload = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception as exc:
                return self._reject(400, f"bad json: {exc}")
        else:
            # iOS Shortcuts often POST as form/text — accept "lat,lon" or "lat,lon,acc"
            text = raw.decode("utf-8", errors="replace").strip()
            parts = [p.strip() for p in text.split(",") if p.strip()]
            try:
                if len(parts) >= 2:
                    payload["latitude"] = float(parts[0])
                    payload["longitude"] = float(parts[1])
                if len(parts) >= 3:
                    payload["accuracy"] = float(parts[2])
                if len(parts) >= 4:
                    payload["altitude"] = float(parts[3])
            except ValueError as exc:
                return self._reject(400, f"bad text payload: {exc}")

        if "latitude" not in payload or "longitude" not in payload:
            return self._reject(400, "payload missing latitude/longitude")

        try:
            payload["latitude"] = float(payload["latitude"])
            payload["longitude"] = float(payload["longitude"])
            if "accuracy" in payload:
                payload["accuracy"] = float(payload["accuracy"])
            if "altitude" in payload:
                payload["altitude"] = float(payload["altitude"])
        except (TypeError, ValueError) as exc:
            return self._reject(400, f"bad numeric field: {exc}")

        if not (-90.0 <= payload["latitude"] <= 90.0):
            return self._reject(400, "latitude out of range")
        if not (-180.0 <= payload["longitude"] <= 180.0):
            return self._reject(400, "longitude out of range")

        row = _write_fix(payload, channel="ios_shortcut_http_post")
        return self._ok({
            "status": "OK",
            "stored_iso": row["iso"],
            "summary": summary_line(),
        })


# ── Server lifecycle ──────────────────────────────────────────────────

def serve(host: str = "0.0.0.0", port: int = _DEFAULT_PORT) -> None:
    PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    PIDFILE.write_text(str(os.getpid()))
    httpd = ThreadingHTTPServer((host, port), _GPSHandler)
    sys.stderr.write(
        f"[iphone_gps] listening on http://{host}:{port}/gps  "
        f"(token={'on' if _OPTIONAL_TOKEN else 'off'})\n"
    )
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        sys.stderr.write("[iphone_gps] shutdown requested\n")
    finally:
        try:
            PIDFILE.unlink(missing_ok=True)
        except Exception:
            pass
        httpd.server_close()


def proof_of_property() -> None:
    """Sanity self-check (no network)."""
    assert _is_lan_private("192.168.1.100")
    assert _is_lan_private("10.0.0.5")
    assert _is_lan_private("172.20.4.1")
    assert _is_lan_private("127.0.0.1")
    assert not _is_lan_private("8.8.8.8")
    assert not _is_lan_private("not-an-ip")

    p = _payload_from_get_query("/gps?lat=1&lon=2&acc=3")
    assert p == {"latitude": 1.0, "longitude": 2.0, "accuracy": 3.0}

    test_payload = {"latitude": 32.9886, "longitude": -115.5303, "accuracy": 12.5, "altitude": -34.0}
    row = _write_fix(test_payload, channel="ios_shortcut_http_post")
    assert row["payload"]["latitude"] == 32.9886
    assert LATEST.exists()
    fix = latest_iphone_gps(stale_after_s=60)
    assert fix is not None
    line = summary_line(stale_after_s=60)
    assert "iphone gps: 32.9886,-115.5303" in line
    print("proof_of_property: 8/8 PASS")


def _main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=_DEFAULT_PORT)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--daemon", action="store_true",
                    help="fork a background server (logs to .sifta_state/iphone_gps_receiver.log)")
    ap.add_argument("--smoke", action="store_true", help="run proof_of_property and exit")
    args = ap.parse_args()

    if args.smoke:
        proof_of_property()
        return

    if args.daemon:
        log = _STATE / "iphone_gps_receiver.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        pid = os.fork()
        if pid > 0:
            print(f"[iphone_gps] daemon pid={pid} log={log}")
            return
        os.setsid()
        with open(log, "ab", buffering=0) as f:
            os.dup2(f.fileno(), 1)
            os.dup2(f.fileno(), 2)
        serve(host=args.host, port=args.port)
        return

    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    _main()

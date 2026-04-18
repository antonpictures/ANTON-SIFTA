#!/usr/bin/env python3
"""
System/sentry_web_consumer.py — Mac Mini (M1_SENTRY) Telemetry Web Server
═════════════════════════════════════════════════════════════════════════

Serves the organism's telemetry_snapshot.json as a live HTTP API endpoint.
Designed to run on the Mac Mini node that hosts the Architect's websites.

The Mac Mini becomes the organism's public face:
    GET /api/swarm/state  → full telemetry snapshot
    GET /api/swarm/health → simple healthcheck
    GET /api/swarm/experience → Alice's experience report

Architecture (Gemini DYOR):
    - S-MADRL: agents read/write environment, not each other (ResearchGate 2025)
    - ECS: entities are IDs, components are JSON, systems are autonomous (GitHub 2024)
    - Pheromone extinction: arXiv:2509.20095 — explorers restore plasticity

Node serials:
    M5 Foundry (Mac Studio):  GTH4921YP3
    M1 Sentry (Mac Mini):     C07FL0JAQ6NV
"""

from __future__ import annotations

import json
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE = _REPO / ".sifta_state"
SNAPSHOT_FILE = _STATE / "telemetry_snapshot.json"
EXPERIENCE_FILE = _STATE / "alice_experience_report.txt"
BOOT_FILE = _STATE / "swarm_boot.json"


def _read_json_safe(path: Path) -> dict[str, Any]:
    """Read a JSON file, return empty dict on failure."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _read_text_safe(path: Path) -> str:
    """Read a text file, return empty string on failure."""
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


class SwarmHandler(BaseHTTPRequestHandler):
    """HTTP handler for the organism's public API."""

    def _cors_headers(self):
        """Allow any frontend to read the organism's mind."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self._cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        path = self.path.rstrip("/")

        if path == "/api/swarm/state":
            snap = _read_json_safe(SNAPSHOT_FILE)
            if snap:
                snap["served_by"] = "M1_SENTRY"
                snap["served_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                self._send_json(snap)
            else:
                self._send_json({"error": "no snapshot", "hint": "run telemetry_snapshot.py"}, 503)

        elif path == "/api/swarm/health":
            snap = _read_json_safe(SNAPSHOT_FILE)
            age = time.time() - snap.get("snapshot_ts", 0) if snap else float("inf")
            healthy = age < 120  # stale after 2 minutes

            self._send_json({
                "status": "alive" if healthy else "stale",
                "snapshot_age_seconds": round(age, 1),
                "climate": snap.get("climate", "UNKNOWN"),
                "lambda_norm": snap.get("manifold", {}).get("lambda_norm", None),
                "node": "M1_SENTRY",
                "serial": "C07FL0JAQ6NV",
            })

        elif path == "/api/swarm/experience":
            report = _read_text_safe(EXPERIENCE_FILE)
            if report:
                self._send_text(report)
            else:
                self._send_text("No experience report yet. Run swarm_experience.py.", 404)

        elif path == "/api/swarm/boot":
            boot = _read_json_safe(BOOT_FILE)
            if isinstance(boot, list):
                self._send_json({"nodes": boot, "served_by": "M1_SENTRY"})
            else:
                self._send_json(boot or {"error": "no boot state"})

        elif path == "/" or path == "":
            self._send_json({
                "name": "SIFTA Swarm OS",
                "node": "M1_SENTRY (Mac Mini)",
                "serial": "C07FL0JAQ6NV",
                "endpoints": [
                    "/api/swarm/state",
                    "/api/swarm/health",
                    "/api/swarm/experience",
                    "/api/swarm/boot",
                ],
                "documentation": "GET any endpoint for JSON. CORS enabled.",
            })

        else:
            self._send_json({"error": "not found", "path": self.path}, 404)

    def log_message(self, format, *args):
        """Structured logging so it can be parsed by foragers."""
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        print(f"[SENTRY {ts}] {args[0]} {args[1]} {args[2]}")


def serve(host: str = "0.0.0.0", port: int = 8420):
    """
    Start the organism's public face.
    Port 8420: 84=SIFTA, 20=swarm.
    """
    server = HTTPServer((host, port), SwarmHandler)
    print(f"═══════════════════════════════════════════════════════")
    print(f"  SIFTA SENTRY — Organism Public Face")
    print(f"  Node: M1_SENTRY (Mac Mini) C07FL0JAQ6NV")
    print(f"  Listening: http://{host}:{port}")
    print(f"═══════════════════════════════════════════════════════")
    print(f"  GET /api/swarm/state       → full telemetry snapshot")
    print(f"  GET /api/swarm/health      → healthcheck")
    print(f"  GET /api/swarm/experience  → Alice's report")
    print(f"  GET /api/swarm/boot        → swarm node registry")
    print(f"═══════════════════════════════════════════════════════")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  SENTRY shutting down gracefully.")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="SIFTA Sentry — telemetry web server")
    p.add_argument("--port", type=int, default=8420, help="Port (default: 8420)")
    p.add_argument("--host", default="0.0.0.0", help="Bind address")
    args = p.parse_args()
    serve(args.host, args.port)

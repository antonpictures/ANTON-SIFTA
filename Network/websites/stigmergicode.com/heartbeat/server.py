#!/usr/bin/env python3
"""Heartbeat server — public live view of Alice's room/body perception.

GET /            page
GET /api/state   latest perception + vitals + organ status
GET /frame?kind=screen|cam   latest still image (proxied from /tmp)
"""
from __future__ import annotations
import json, os, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = Path("/Users/ioanganton/Music/ANTON_SIFTA/.sifta_state")
LATEST = STATE / "latest_perception.json"
PORT = int(os.environ.get("PORT", "8103"))


def state_payload() -> dict:
    d = {}
    try:
        d = json.loads(LATEST.read_text())
    except Exception as e:
        d = {"error": f"no heartbeat yet: {e}"}
    # organ status
    import socket
    def port_open(port):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except Exception:
            return False
    import subprocess
    organs = {}
    try:
        organs["heart"] = bool(subprocess.run(["pgrep","-f","swarm_perception_heartbeat"], capture_output=True, text=True, timeout=3).stdout.strip())
    except Exception:
        organs["heart"] = False
    organs["face"] = port_open(8102)
    organs["fish"] = port_open(8765)
    organs["feed"] = port_open(8090)
    d["organs"] = organs
    # ── Space awareness (David's ask: exact knowledge of where she is) ──
    import datetime
    location = {}
    try:
        gps = json.loads((STATE / "iphone_gps_latest.json").read_text())
        p = gps.get("payload", {})
        location["gps"] = {
            "lat": p.get("latitude"), "lon": p.get("longitude"),
            "accuracy_m": p.get("accuracy"), "iso": gps.get("iso"),
            "age_days": round((time.time() - float(gps.get("ts", 0))) / 86400, 1),
            "fresh": (time.time() - float(gps.get("ts", 0))) < 3600,
        }
    except Exception:
        location["gps"] = None
    try:
        ble = json.loads((STATE / "alice_ble_radar_latest.json").read_text())
        devices = ble.get("devices", []) or []
        location["nearby"] = [
            {"name": x.get("name"), "band": x.get("proximity_band"), "connected": x.get("connected")}
            for x in devices if x.get("name")
        ]
        location["nearby_age_s"] = round(time.time() - float(ble.get("ts", 0)), 1)
    except Exception:
        location["nearby"] = []
    try:
        awdl = json.loads((STATE / "alice_awdl_mesh_latest.json").read_text())
        location["mesh_peers"] = [x.get("instance") for x in awdl.get("peers", []) if x.get("instance")]
    except Exception:
        location["mesh_peers"] = []
    aw = d.get("active_window", {}) or {}
    location["surface"] = aw.get("app")
    location["note"] = "room presence from camera/screen + window; GPS is last iPhone fix (stale unless fresh=true)"
    d["location"] = location
    d["served_at"] = time.time()
    return d


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(HERE), **kw)

    def _json(self, p, code=200):
        b = json.dumps(p).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/state":
            return self._json(state_payload())
        if path == "/frame":
            kind = "cam" if "cam" in self.path else "screen"
            f = Path("/tmp/perception_heartbeat_cam.png" if kind == "cam" else "/tmp/perception_heartbeat_screen.png")
            if not f.exists():
                return self.send_error(404)
            try:
                b = f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(b)
            except Exception:
                self.send_error(404)
            return
        return super().do_GET()

    def log_message(self, fmt, *args):
        pass


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Heartbeat → http://127.0.0.1:{PORT}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()

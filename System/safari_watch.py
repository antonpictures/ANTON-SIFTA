"""safari_watch — a logging front door, to see what Safari asks for and what it gets.

Why: http://127.0.0.1:3080 works in Chrome and Alice Browser, and not in Safari, while the
server answers every user-agent identically (200, 15175 bytes, same headers). So the
failure is between the browser and the response, and I cannot see Safari's console.

This is the instrument. It listens on 3081, forwards to 3080, and logs every request with
its user-agent, status and size -- so we can tell:

    * Safari never arrives            -> the connection never happens (https upgrade, socket
                                         starvation, a blocker)
    * Safari arrives and IS refused   -> we see its request and the status it got back

It also re-serves each response with an explicit Content-Length instead of the origin's
Transfer-Encoding: chunked. If Safari works through this door and not through the origin,
then the difference is the origin's chunked/keep-alive behaviour, which Chrome tolerates
and Safari does not -- and that is a fact we can then fix in the body rather than guess at.

Read-only: it forwards and records. It changes nothing on the origin.
"""
from __future__ import annotations

import http.server
import json
import socketserver
import time
import urllib.error
import urllib.request
from typing import Any, Dict

ORIGIN = "http://127.0.0.1:3080"
PORT = 3081
LOG = "/tmp/safari_watch.jsonl"

_seen: Dict[str, int] = {}


def _log(row: Dict[str, Any]) -> None:
    row.setdefault("ts", time.time())
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    ua = str(row.get("ua") or "")[:44]
    print(f"[{time.strftime('%H:%M:%S', time.localtime(row['ts']))}] "
          f"{row.get('status')} {row.get('bytes')}B {row.get('method')} {str(row.get('path'))[:52]} "
          f"| {ua}", flush=True)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "safari_watch/1.0"

    def _ua(self) -> str:
        return self.headers.get("User-Agent", "(none)")

    def log_message(self, fmt, *args):        # silence the default stderr spam
        return

    def _forward(self, method: str) -> None:
        body = None
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            body = self.rfile.read(length)
        req = urllib.request.Request(f"{ORIGIN}{self.path}", data=body, method=method)
        for k, v in self.headers.items():
            if k.lower() in ("host", "connection", "accept-encoding", "transfer-encoding",
                             "content-length"):
                continue
            req.add_header(k, v)
        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = r.read()
                status = r.status
                ctype = r.headers.get("content-type", "")
                extra = dict(r.headers)
        except urllib.error.HTTPError as e:
            payload = e.read()
            status = e.code
            ctype = e.headers.get("content-type", "")
            extra = dict(e.headers)
        except Exception as exc:
            _log({"method": method, "path": self.path, "ua": self._ua(),
                  "status": 0, "bytes": 0, "error": f"{type(exc).__name__}: {exc}",
                  "ms": round((time.time() - started) * 1000)})
            self.send_error(502, "origin unreachable through the watch door")
            return

        self.send_response(status)
        for k in ("cache-control", "etag", "last-modified", "content-type"):
            if extra.get(k):
                self.send_header(k, extra[k])
        if ctype:
            self.send_header("Content-Type", ctype)
        # explicit length, NOT chunked: this is the variable under test
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Safari-Watch", "1")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except Exception:
            pass
        _log({"method": method, "path": self.path, "ua": self._ua(), "status": status,
              "bytes": len(payload), "chunked_at_origin": extra.get("transfer-encoding"),
              "ctype": ctype, "ms": round((time.time() - started) * 1000)})

    def do_GET(self):
        self._forward("GET")

    def do_POST(self):
        self._forward("POST")

    def do_HEAD(self):
        self._forward("HEAD")


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    open(LOG, "a").close()
    print(f"safari_watch listening on http://127.0.0.1:{PORT} -> {ORIGIN}", flush=True)
    print("load THIS address in Safari and tell me: the requests appear here.", flush=True)
    with Server(("127.0.0.1", PORT), Handler) as httpd:
        httpd.serve_forever()

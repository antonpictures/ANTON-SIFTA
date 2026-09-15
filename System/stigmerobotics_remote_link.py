"""Scoped WAN rover admission and an explicitly armed command queue.

Telemetry credentials remain read-only. Motion uses a separate, short-lived
control credential and one-shot commands that a David-side gateway must pass
through its local RVR1 safety gate. SQLite makes ticket, sequence and command
claims atomic across HTTP workers. Credentials never appear in public records.
"""
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit

IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("rover gateway refuses redirects")


def digest(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 256:
        raise PermissionError("rover credential required")
    return hashlib.sha256(value.encode()).hexdigest()


class RemoteRoverLink:
    def __init__(self, state_dir, clock=time.time):
        self.clock = clock
        self.root = Path(state_dir) / "remote_rovers"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        self.path = self.root / "links.sqlite3"
        with self.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS links (
                robot TEXT PRIMARY KEY, ticket_hash TEXT, ticket_until REAL,
                token_hash TEXT, token_until REAL, connection TEXT,
                control_hash TEXT, control_until REAL,
                sequence INTEGER DEFAULT -1, sample TEXT, received REAL)''')
            columns = {row[1] for row in db.execute("PRAGMA table_info(links)")}
            if "control_hash" not in columns:
                db.execute("ALTER TABLE links ADD COLUMN control_hash TEXT")
            if "control_until" not in columns:
                db.execute("ALTER TABLE links ADD COLUMN control_until REAL")
            db.execute('''CREATE TABLE IF NOT EXISTS rover_commands (
                command_id TEXT PRIMARY KEY, robot TEXT NOT NULL,
                connection TEXT NOT NULL, created REAL NOT NULL,
                expires REAL NOT NULL, linear INTEGER NOT NULL,
                angular INTEGER NOT NULL, timeout_ms INTEGER NOT NULL,
                state TEXT NOT NULL, claimed REAL, result TEXT)''')
        os.chmod(self.path, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def invite(self, robot):
        """Local/owner-authorized call only. Re-enrollment revokes the old link."""
        if not isinstance(robot, str) or not IDENTIFIER.fullmatch(robot):
            raise ValueError("robot_id must be 1-64 letters, digits, underscores or hyphens")
        ticket = secrets.token_urlsafe(32)
        now = self.clock()
        with self.db() as db:
            exists = db.execute("SELECT 1 FROM links WHERE robot=?", (robot,)).fetchone()
            if not exists and db.execute("SELECT count(*) FROM links").fetchone()[0] >= 16:
                raise ValueError("rover enrollment limit reached")
            db.execute("INSERT OR REPLACE INTO links(robot,ticket_hash,ticket_until) VALUES(?,?,?)",
                       (robot, digest(ticket), now + 300))
        return {"robot_id": robot, "ticket": ticket, "expires_at": now + 300,
                "scope": "rover.telemetry", "motion_enabled": False}

    def pair(self, ticket):
        now = self.clock()
        with self.db() as db:
            row = db.execute("SELECT * FROM links WHERE ticket_hash=?", (digest(ticket),)).fetchone()
            if not row or now >= row["ticket_until"]:
                raise PermissionError("rover invitation expired or used")
            token, connection = secrets.token_urlsafe(32), uuid.uuid4().hex
            db.execute('''UPDATE links SET ticket_hash=NULL, token_hash=?, token_until=?,
                          connection=?, control_hash=NULL, control_until=NULL WHERE robot=?''',
                       (digest(token), now + 43200, connection, row["robot"]))
            return {"robot_id": row["robot"], "token": token,
                    "connection_id": connection, "expires_at": now + 43200,
                    "scope": "rover.telemetry", "motion_enabled": False}

    def _authenticated(self, db, token):
        row = db.execute("SELECT * FROM links WHERE token_hash=?", (digest(token),)).fetchone()
        if not row or self.clock() >= row["token_until"]:
            raise PermissionError("rover link expired or revoked")
        return row

    def arm(self, robot):
        """Issue a separate owner-authorized control token for one short lease."""
        if not isinstance(robot, str) or not IDENTIFIER.fullmatch(robot):
            raise ValueError("robot_id must be 1-64 letters, digits, underscores or hyphens")
        token = secrets.token_urlsafe(32)
        now = self.clock()
        with self.db() as db:
            row = db.execute("SELECT * FROM links WHERE robot=?", (robot,)).fetchone()
            if not row or not row["token_hash"] or now >= row["token_until"]:
                raise PermissionError("rover must be paired before control can be armed")
            db.execute("UPDATE links SET control_hash=?, control_until=? WHERE robot=?",
                       (digest(token), now + 300, robot))
        return {"robot_id": robot, "control_token": token, "expires_at": now + 300,
                "scope": "rover.control", "motion_enabled": True}

    def _control(self, db, token):
        row = db.execute("SELECT * FROM links WHERE control_hash=?", (digest(token),)).fetchone()
        if not row or self.clock() >= row["control_until"]:
            raise PermissionError("rover control lease expired or revoked")
        if not row["token_hash"] or self.clock() >= row["token_until"]:
            raise PermissionError("rover link expired or revoked")
        return row

    def enqueue_command(self, token, payload):
        required = {"robot_id", "connection_id", "command_id", "linear_mm_s",
                    "angular_mrad_s", "timeout_ms"}
        if not isinstance(payload, dict) or set(payload) != required:
            raise ValueError("invalid rover command envelope")
        command_id = payload["command_id"]
        if not isinstance(command_id, str) or not IDENTIFIER.fullmatch(command_id):
            raise ValueError("invalid command_id")
        linear, angular, timeout = (payload["linear_mm_s"], payload["angular_mrad_s"],
                                    payload["timeout_ms"])
        if (type(linear) is not int or not -1000 <= linear <= 1000 or
                type(angular) is not int or not -1667 <= angular <= 1667 or
                type(timeout) is not int or not 1 <= timeout <= 1000):
            raise ValueError("command exceeds finite RVR1 bounds")
        now = self.clock()
        with self.db() as db:
            row = self._control(db, token)
            if (payload["robot_id"] != row["robot"] or
                    payload["connection_id"] != row["connection"]):
                raise PermissionError("wrong rover or connection")
            existing = db.execute("SELECT * FROM rover_commands WHERE command_id=?",
                                  (command_id,)).fetchone()
            if existing:
                if (existing["robot"], existing["connection"], existing["linear"],
                        existing["angular"], existing["timeout_ms"]) != (
                            row["robot"], row["connection"], linear, angular, timeout):
                    raise ValueError("conflicting command_id")
                return {"accepted": True, "duplicate": True, "command_id": command_id,
                        "state": existing["state"]}
            db.execute('''INSERT INTO rover_commands
                (command_id,robot,connection,created,expires,linear,angular,timeout_ms,state)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                       (command_id, row["robot"], row["connection"], now,
                        now + timeout / 1000.0 + 2.0, linear, angular, timeout, "pending"))
        return {"accepted": True, "duplicate": False, "command_id": command_id,
                "state": "pending", "expires_at": now + timeout / 1000.0 + 2.0}

    def poll_commands(self, token, limit=8):
        if type(limit) is not int or not 1 <= limit <= 8:
            raise ValueError("command limit must be 1-8")
        now = self.clock()
        with self.db() as db:
            row = self._control(db, token)
            db.execute("UPDATE rover_commands SET state='expired' WHERE robot=? AND state='pending' AND expires<=?",
                       (row["robot"], now))
            commands = db.execute('''SELECT * FROM rover_commands
                WHERE robot=? AND connection=? AND state='pending' AND expires>?
                ORDER BY created LIMIT ?''', (row["robot"], row["connection"], now, limit)).fetchall()
            ids = [item["command_id"] for item in commands]
            if ids:
                db.executemany("UPDATE rover_commands SET state='claimed', claimed=? WHERE command_id=?",
                               [(now, command_id) for command_id in ids])
            return {"robot_id": row["robot"], "connection_id": row["connection"],
                    "commands": [{"command_id": item["command_id"],
                                   "linear_mm_s": item["linear"],
                                   "angular_mrad_s": item["angular"],
                                   "timeout_ms": item["timeout_ms"]} for item in commands]}

    def ack_command(self, token, payload):
        if not isinstance(payload, dict) or set(payload) != {"robot_id", "connection_id",
                                                              "command_id", "state", "result"}:
            raise ValueError("invalid rover command acknowledgment")
        if (not isinstance(payload["command_id"], str) or
                not IDENTIFIER.fullmatch(payload["command_id"]) or
                payload["state"] not in {"accepted", "applied", "stopped", "rejected", "failed"} or
                not isinstance(payload["result"], dict)):
            raise ValueError("invalid rover command acknowledgment")
        encoded = json.dumps(payload["result"], sort_keys=True, allow_nan=False,
                             separators=(",", ":"))
        if len(encoded.encode()) > 4096:
            raise ValueError("command result exceeds 4 KiB")
        with self.db() as db:
            row = self._control(db, token)
            if (payload["robot_id"], payload["connection_id"]) != (row["robot"], row["connection"]):
                raise PermissionError("wrong rover or connection")
            changed = db.execute('''UPDATE rover_commands SET state=?, result=?
                WHERE command_id=? AND robot=? AND connection=? AND state='claimed' ''',
                                  (payload["state"], encoded, payload["command_id"],
                                   row["robot"], row["connection"])).rowcount
            if not changed:
                raise ValueError("command is not claimed or already acknowledged")
        return {"accepted": True, "command_id": payload["command_id"], "state": payload["state"]}

    def receive(self, token, payload):
        if not isinstance(payload, dict) or set(payload) != {
                "robot_id", "connection_id", "sequence", "captured_at", "readings"}:
            raise ValueError("invalid rover telemetry envelope")
        sequence, stamp, readings = payload["sequence"], payload["captured_at"], payload["readings"]
        if type(sequence) is not int or not 0 <= sequence < 2**63:
            raise ValueError("invalid telemetry sequence")
        if (type(stamp) not in (float, int) or not math.isfinite(stamp) or stamp < 0
                or not isinstance(readings, dict) or not readings):
            raise ValueError("finite capture time and readings required")
        # Values are device reports, not verified sensor facts or executable instructions.
        encoded = json.dumps(payload, sort_keys=True, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode()) > 16384:
            raise ValueError("telemetry exceeds 16 KiB")
        now = self.clock()
        with self.db() as db:
            row = self._authenticated(db, token)
            if (payload["robot_id"] != row["robot"]
                    or payload["connection_id"] != row["connection"]):
                raise PermissionError("wrong rover or connection")
            if sequence == row["sequence"] and encoded == row["sample"]:
                return {"accepted": True, "duplicate": True, "sequence": sequence}
            if sequence <= row["sequence"]:
                raise ValueError("stale sequence or conflicting duplicate")
            db.execute("UPDATE links SET sequence=?,sample=?,received=? WHERE robot=?",
                       (sequence, encoded, now, row["robot"]))
            return {"accepted": True, "duplicate": False, "sequence": sequence}

    def status(self, token):
        with self.db() as db:
            row = self._authenticated(db, token)
            return self._view(row)

    def owner_status(self):
        """Caller must enforce owner authentication; never returns any secrets."""
        with self.db() as db:
            return [self._view(row) for row in db.execute("SELECT * FROM links ORDER BY robot")]

    def _view(self, row):
        now = self.clock()
        age = None if row["received"] is None else now - row["received"]
        active = bool(row["token_hash"] and now < row["token_until"])
        state = ("unpaired" if not row["token_hash"] else "expired" if not active else
                 "awaiting_telemetry" if age is None else
                 "online_armed" if row["control_hash"] and self.clock() < row["control_until"] and 0 <= age <= 15 else
                 "online_unarmed" if 0 <= age <= 15 else "stale")
        return {"robot_id": row["robot"], "connection_id": row["connection"],
                "state": state, "sequence": row["sequence"], "received_at": row["received"],
                "receive_age_s": age, "motion_enabled": bool(row["control_hash"] and self.clock() < row["control_until"]),
                "truth_label": "DEVICE_REPORTED",
                "capture_clock_verified": False,
                "last_sample": json.loads(row["sample"]) if row["sample"] else None}


class RemoteRoverGateway:
    """Outbound David-side client for scoped rover endpoints.

    The gateway is transport-only: callbacks supply readings from David's
    firmware. Motion commands are only fetched with a separate control token;
    callers must pass each one through the local RVR1 safety gate. Callers may
    retry an identical telemetry envelope after an uncertain network result;
    the server's sequence/idempotency rules handle that retry.
    """

    ALLOWED_PATHS = {"/api/rover/telemetry", "/api/rover/chat",
                     "/api/rover/command/ack"}

    def __init__(self, base_url, *, token, robot_id, connection_id,
                 control_token=None, timeout=10, opener=None):
        parts = urlsplit(str(base_url))
        if parts.scheme != "https" and parts.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("rover gateway requires HTTPS")
        if not parts.hostname or parts.query or parts.fragment:
            raise ValueError("base URL must be an origin")
        if not isinstance(robot_id, str) or not IDENTIFIER.fullmatch(robot_id):
            raise ValueError("invalid robot_id")
        if not isinstance(connection_id, str) or not IDENTIFIER.fullmatch(connection_id):
            raise ValueError("invalid connection_id")
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
            raise ValueError("timeout must be between 0 and 60 seconds")
        self.base_url = str(base_url).rstrip("/") + "/"
        self.token = str(token)
        digest(self.token)
        self.control_token = None if control_token is None else str(control_token)
        if self.control_token is not None:
            digest(self.control_token)
        self.robot_id = robot_id
        self.connection_id = connection_id
        self.timeout = float(timeout)
        self.opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect())

    def _post(self, path, payload, *, token=None):
        if path not in self.ALLOWED_PATHS:
            raise ValueError("gateway path is not in the rover scope")
        body = json.dumps(payload, sort_keys=True, allow_nan=False,
                          separators=(",", ":")).encode()
        if len(body) > 32768:
            raise ValueError("gateway request exceeds 32 KiB")
        request = urllib.request.Request(
            urljoin(self.base_url, path.lstrip("/")), data=body, method="POST",
            headers={"Authorization": f"Bearer {self.token if token is None else token}",
                     "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                result = json.loads(response.read(32769).decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"rover server rejected {path}: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ConnectionError("rover server result is uncertain; retry the same envelope") from exc
        if not isinstance(result, dict):
            raise RuntimeError("rover server returned invalid JSON")
        return result

    def _get(self, path, *, token, query=""):
        request = urllib.request.Request(
            urljoin(self.base_url, path.lstrip("/")) + query, method="GET",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                result = json.loads(response.read(32769).decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"rover server rejected {path}: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ConnectionError("rover server result is uncertain; retry or poll again") from exc
        if not isinstance(result, dict) or result.get("robot_id") != self.robot_id:
            raise RuntimeError("rover server returned invalid reply scope")
        return result

    def send_telemetry(self, *, sequence, captured_at, readings):
        payload = {"robot_id": self.robot_id, "connection_id": self.connection_id,
                   "sequence": sequence, "captured_at": captured_at, "readings": readings}
        return self._post("/api/rover/telemetry", payload)

    def send_chat(self, *, request_id, text, captured_at=None):
        if not isinstance(request_id, str) or not IDENTIFIER.fullmatch(request_id):
            raise ValueError("request_id must be a short idempotency key")
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000:
            raise ValueError("chat text must contain 1-4000 characters")
        payload = {"robot_id": self.robot_id, "connection_id": self.connection_id,
                   "request_id": request_id, "text": text.strip()}
        if captured_at is not None:
            payload["captured_at"] = captured_at
        return self._post("/api/rover/chat", payload)

    def poll_replies(self, *, after_ts=0.0):
        """Poll Alice's existing reply ledger for this robot session."""
        if not isinstance(after_ts, (int, float)) or isinstance(after_ts, bool) or not math.isfinite(after_ts):
            raise ValueError("after_ts must be finite")
        return self._get("/api/rover/replies", token=self.token,
                         query=f"?after_ts={float(after_ts):.6f}")

    def poll_commands(self, *, limit=8):
        """Claim each queued command once; an interrupted gateway will not replay it."""
        if self.control_token is None:
            raise PermissionError("a separate rover control token is required")
        if type(limit) is not int or not 1 <= limit <= 8:
            raise ValueError("command limit must be 1-8")
        return self._get("/api/rover/commands", token=self.control_token,
                         query=f"?limit={limit}")

    def ack_command(self, *, command_id, state, result):
        if self.control_token is None:
            raise PermissionError("a separate rover control token is required")
        payload = {"robot_id": self.robot_id, "connection_id": self.connection_id,
                   "command_id": command_id, "state": state, "result": result}
        return self._post("/api/rover/command/ack", payload, token=self.control_token)

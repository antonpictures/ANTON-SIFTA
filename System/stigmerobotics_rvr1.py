"""RVR1 LAN adapter for David's rover; no network activity on import.

Wire contract: E_Motion-Rover commit 5fdd0351fc20dc3697e913dee46aaeac5ebfb63b.
RVR1 authenticates packets but does not encrypt them. Keep this leg on the LAN
or a private tunnel. The SIFTA gateway supplies the encrypted WAN leg.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import ipaddress
import secrets
import socket
import struct
import time
import zlib

HEADER = struct.Struct("<4sBBHI")
HELLO, SESSION_OPEN, VELOCITY = 1, 2, 0x10
LIDAR, BATTERY, CONTROL, CAPABILITIES = 0x20, 0x21, 0x22, 0x81
STATUS = {0: "accepted", 1: "applied", 2: "timed_out",
          3: "stale_sequence", 4: "released"}


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("integer outside protocol bounds")
    return value


@dataclass(frozen=True)
class Packet:
    kind: int
    session: int
    payload: bytes


def encode(packet: Packet, key: bytes) -> bytes:
    if not isinstance(key, bytes) or not key:
        raise ValueError("RVR1 requires a nonempty private key")
    integer(packet.kind, 0, 255)
    integer(packet.session, 1, 0xffffffff)
    if not isinstance(packet.payload, bytes) or len(packet.payload) > 224:
        raise ValueError("RVR1 payload exceeds firmware datagram size")
    body = HEADER.pack(b"RVR1", 1, packet.kind, len(packet.payload), packet.session) + packet.payload
    signed = body + struct.pack("<I", zlib.crc32(body) & 0xffffffff)
    return signed + hmac.new(key, signed, hashlib.sha256).digest()[:16]


def decode(data: bytes, key: bytes) -> Packet:
    if not isinstance(key, bytes) or not key:
        raise ValueError("RVR1 requires a nonempty private key")
    if not 32 <= len(data) <= 256:
        raise ValueError("invalid RVR1 datagram length")
    magic, version, kind, size, session = HEADER.unpack_from(data)
    if magic != b"RVR1" or version != 1 or not session or size + 32 != len(data):
        raise ValueError("invalid RVR1 header")
    if not hmac.compare_digest(data[-16:], hmac.new(key, data[:-16], hashlib.sha256).digest()[:16]):
        raise ValueError("invalid RVR1 authentication")
    if struct.unpack("<I", data[-20:-16])[0] != zlib.crc32(data[:-20]) & 0xffffffff:
        raise ValueError("invalid RVR1 CRC")
    return Packet(kind, session, data[12:-20])


def sequence_is_newer(candidate: int, previous: int) -> bool:
    integer(candidate, 0, 65535)
    integer(previous, 0, 65535)
    return 0 < ((candidate - previous) & 65535) < 32768


def velocity_payload(linear: int, angular: int, timeout_ms: int, sequence: int) -> bytes:
    # Firmware's timeout=0 disables stopping; remote commands always expire.
    return struct.pack("<hhHH", integer(linear, -1000, 1000),
                       integer(angular, -1667, 1667),
                       integer(timeout_ms, 1, 1000), integer(sequence, 0, 65535))


class Observations:
    """Bounded complete-scan assembly; ages are device reports, not synchronized time."""

    def __init__(self):
        self.last_scan = None
        self.last_scan_at = None
        self.last_points = None
        self.pending = None

    def ingest(self, packet: Packet, now: float):
        data = packet.payload
        common = {"protocol": "RVR1", "rover_session": packet.session,
                  "truth_label": "DEVICE_REPORTED", "capture_clock_verified": False}
        if packet.kind == BATTERY:
            if len(data) != 6:
                raise ValueError("invalid battery payload")
            mv, age = struct.unpack("<HI", data)
            return dict(common, modality="battery", millivolts=mv, age_ms=age,
                        stale=age > 2000)
        if packet.kind == CONTROL:
            if len(data) != 8:
                raise ValueError("invalid control payload")
            seq, status, state, remaining, authenticated = struct.unpack("<HBBHBx", data)
            if status not in STATUS or state not in (0, 1, 2) or authenticated != 1:
                raise ValueError("invalid control status")
            return dict(common, modality="control", sequence=seq, status=STATUS[status],
                        state=state, remaining_ms=remaining,
                        timeout_disabled=remaining == 65535, physical_motion_verified=False)
        if packet.kind != LIDAR:
            return None
        if len(data) < 10:
            raise ValueError("short lidar payload")
        scan, flags, chunk, count, reserved, turn, age = struct.unpack_from("<HBBBBhH", data)
        if (not 1 <= count <= 24 or len(data) != 10 + 4 * count or
                flags & ~3 or reserved or not -1000 <= turn <= 1000):
            self.pending = None
            raise ValueError("invalid lidar chunk")
        if age > 1000:
            self.pending = None
            return None
        if flags & 1:
            if chunk != 0 or (self.last_scan is not None and not sequence_is_newer(scan, self.last_scan)):
                return None
            # Never let a duplicate first fragment renew assembly freshness.
            if self.pending and self.pending[0] == scan:
                return None
            self.pending = [scan, 0, now, [], age]
        pending = self.pending
        if not pending:
            return None
        if scan != pending[0] or chunk != pending[1] or now - pending[2] > 1:
            self.pending = None
            return None
        pending[3].extend(struct.unpack_from("<hh", data, 10 + i * 4) for i in range(count))
        pending[1] += 1
        pending[4] = max(pending[4], age)
        if len(pending[3]) > 720:
            self.pending = None
            raise ValueError("lidar scan exceeds point budget")
        if not flags & 2:
            return None
        self.pending = None
        self.last_scan = scan
        self.last_scan_at = now
        self.last_points = tuple(pending[3])
        return dict(common, modality="lidar", scan=scan, points_mm=pending[3],
                    age_ms=pending[4], assembly_ms=int(1000 * (now - pending[2])),
                    steering_turn_permille=turn, coverage="front_180_degrees")

    def obstacle_clear(self, linear, *, now, max_age_s=1.0,
                       stop_distance_mm=300, corridor_half_width_mm=220):
        """Conservative front-LiDAR gate; unknown rear/side space is blocked."""
        if type(linear) is not int or not -1000 <= linear <= 1000:
            raise ValueError("linear velocity outside RVR1 bounds")
        if linear == 0:
            return True
        if (self.last_scan_at is None or self.last_points is None or
                now < self.last_scan_at or now - self.last_scan_at > max_age_s):
            return False
        if linear < 0:
            return False  # The supplied scan is front-only; reverse is unobserved.
        for forward_mm, lateral_mm in self.last_points:
            if (0 <= forward_mm <= stop_distance_mm and
                    abs(lateral_mm) <= corridor_half_width_mm):
                return False
        return True


class RoverClient:
    """Single-threaded session. Explicit open; read-only unless velocity is called.

    The caller owns local obstacle checks and intent expiry. Do not feed LLM
    replies directly into velocity(). This adapter never renews commands itself.
    """

    def __init__(self, host: str, key: bytes, port=4210, *, clock=time.monotonic):
        self.target = (str(ipaddress.IPv4Address(host)), integer(port, 1, 65535))
        if not isinstance(key, bytes) or not key:
            raise ValueError("RVR1 requires a nonempty private key")
        self._key = key
        self.clock = clock
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", 0))
        self.session = secrets.randbits(32) or 1
        self.sequence = secrets.randbelow(65536)
        self.opened_at = None
        self.observations = Observations()
        self.capabilities = None

    def close(self):
        self.opened_at = None
        self.sock.close()

    def _send(self, kind, payload=b""):
        self.sock.sendto(encode(Packet(kind, self.session, payload), self._key), self.target)

    def _receive(self, deadline):
        while self.clock() < deadline:
            self.sock.settimeout(max(0.001, deadline - self.clock()))
            try:
                data, address = self.sock.recvfrom(257)
            except socket.timeout:
                break
            if address != self.target:
                continue
            try:
                packet = decode(data, self._key)
            except ValueError:
                continue
            if packet.session == self.session:
                return packet
        raise TimeoutError("no valid response from paired rover")

    def open(self):
        self.opened_at = None
        self._send(HELLO)
        deadline = self.clock() + 2
        while True:
            packet = self._receive(deadline)
            if packet.kind == CAPABILITIES and len(packet.payload) == 20:
                version, auth, port, linear, angular, timeout, points, sensors, challenge = struct.unpack(
                    "<BBHhhHBBQ", packet.payload)
                if version != 1 or auth != 1 or not 1 <= port <= 65535 or not challenge:
                    raise ValueError("invalid rover capabilities")
                if not 0 < linear <= 1000 or not 0 < angular <= 1667 or not 0 < points <= 24 or not timeout:
                    raise ValueError("unsupported rover limits")
                self.capabilities = {"linear": linear, "angular": angular, "timeout": timeout,
                                     "sensors": sensors}
                self._send(SESSION_OPEN, struct.pack("<Q", challenge))
                break
        while True:
            packet = self._receive(deadline)
            if packet.kind == CONTROL:
                status = self.observations.ingest(packet, self.clock())
                if status["sequence"] == 0 and status["status"] == "accepted":
                    self.opened_at = self.clock()
                    return status

    def poll(self, timeout=1.0):
        if not 0 < timeout <= 2:
            raise ValueError("poll timeout outside bounds")
        if self.opened_at is None:
            raise RuntimeError("rover session is not open")
        deadline = self.clock() + timeout
        while True:
            packet = self._receive(deadline)
            row = self.observations.ingest(packet, self.clock())
            if row is not None:
                return row

    def velocity(self, linear, angular, *, timeout_ms=250):
        if self.opened_at is None:
            raise RuntimeError("rover session is not open")
        if self.clock() - self.opened_at > 20:
            raise RuntimeError("rover session requires a fresh handshake")
        if abs(linear) > self.capabilities["linear"] or abs(angular) > self.capabilities["angular"]:
            raise ValueError("velocity exceeds advertised limits")
        if timeout_ms > self.capabilities["timeout"]:
            raise ValueError("timeout exceeds advertised limit")
        sequence = (self.sequence + 1) & 65535
        payload = velocity_payload(linear, angular, timeout_ms, sequence)
        self._send(VELOCITY, payload)
        self.sequence = sequence
        return {"sequence": sequence, "status": "sent", "physical_motion_verified": False}

    def safe_velocity(self, linear, angular, *, timeout_ms=250,
                      stop_distance_mm=300, corridor_half_width_mm=220):
        """Send only after a fresh front scan clears the conservative corridor."""
        if type(linear) is not int or type(angular) is not int:
            raise ValueError("RVR1 velocity values must be integers")
        if not self.observations.obstacle_clear(
                linear, now=self.clock(), stop_distance_mm=stop_distance_mm,
                corridor_half_width_mm=corridor_half_width_mm):
            raise RuntimeError("local safety gate rejected stale, blocked or unobserved path")
        return self.velocity(linear, angular, timeout_ms=timeout_ms)
